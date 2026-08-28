#!/usr/bin/env python3
"""Versioned benchmark v2 execution, coverage, and publication gates."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


VALID_STATUSES = ("scored", "infrastructure_error", "skipped")
PRIMARY_REPEAT_INDEX = 0
SCORER_ONLY_FIELDS = (
    "expected_primary_skill",
    "expected_secondary_skills",
    "expected_decision",
    "expected_clarify_contains",
    "required_constraint_contains",
    "forbidden_substring",
    "required_step_contains",
    "required_expected_output_contains",
    "min_runnable_steps",
    "min_expected_outputs",
    "required_parameter_contains",
    "forbidden_parameter_contains",
    "required_evidence_contains",
    "parameter_name",
    "expected_parameter_status",
)


def _fn(api: Mapping[str, Any], name: str) -> Any:
    return api[name]


def _path(repo_root: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize_text(value: str) -> str:
    sanitized = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+", r"\1<REDACTED>", value)
    sanitized = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "<REDACTED_API_KEY>", sanitized)
    sanitized = re.sub(
        r"(?i)((?:api[_-]?key|token|cookie)\s*[:=]\s*[\"']?)[^\s\"',}]+",
        r"\1<REDACTED>",
        sanitized,
    )
    sanitized = re.sub(r"/Users/[^/\s]+/", "<HOME>/", sanitized)
    sanitized = re.sub(r"/home/[^/\s]+/", "<HOME>/", sanitized)
    return sanitized


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize_value(item) for key, item in value.items()}
    return value


def normalize_query(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def git_metadata(repo_root: Path) -> Dict[str, Any]:
    def run(*args: str) -> str:
        proc = subprocess.run(
            ["git", *args], cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False
        )
        return proc.stdout.strip()

    status = run("status", "--porcelain")
    diff = run("diff", "--binary", "--", "benchmark", "evals", "registry", "scripts", "skills")
    return {
        "commit": run("rev-parse", "HEAD") or None,
        "dirty": bool(status),
        "status_sha256": sha256_text(status),
        "diff_sha256": sha256_text(diff) if status else None,
    }


def _manifest_entry(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        return {"id": item}
    if isinstance(item, dict):
        return dict(item)
    raise ValueError(f"manifest case entry must be a string or mapping: {item!r}")


def load_manifest_cases(
    manifest: Dict[str, Any],
    repo_root: Path,
    known_skills: Iterable[str],
    known_tasks: Iterable[str],
    api: Mapping[str, Any],
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    if manifest.get("schema_version") != 2:
        raise ValueError("v2 manifest must declare schema_version: 2")
    case_sources = manifest.get("case_sources")
    selected = manifest.get("cases")
    defaults = manifest.get("suite_defaults") or {}
    if not isinstance(case_sources, dict) or not isinstance(selected, dict) or not isinstance(defaults, dict):
        raise ValueError("v2 manifest requires case_sources, cases, and suite_defaults mappings")

    suites = list(selected.keys())
    source_cases = _fn(api, "load_suite_cases")(case_sources, suites, repo_root)
    known_skill_set = set(known_skills)
    known_task_set = set(known_tasks)
    output: Dict[str, List[Dict[str, Any]]] = {}
    seen_ids: set[str] = set()
    seen_queries: Dict[str, str] = {}
    duplicate_query_pairs: List[List[str]] = []
    errors: List[str] = []
    benchmark_scope = str(defaults.get("scope") or "") == "benchmark"

    required_metadata = (
        "scope",
        "split",
        "case_study_coupled",
        "provenance",
        "difficulty",
        "ambiguity",
        "missing_input_risk",
    )
    for suite in suites:
        entries = selected.get(suite)
        if not isinstance(entries, list):
            raise ValueError(f"manifest cases.{suite} must be a list")
        source_by_id = {str(case.get("id")): case for case in source_cases.get(suite, [])}
        resolved: List[Dict[str, Any]] = []
        for raw_entry in entries:
            entry = _manifest_entry(raw_entry)
            case_id = str(entry.get("id") or "")
            if not case_id or case_id not in source_by_id:
                errors.append(f"unknown_case:{suite}:{case_id or '<empty>'}")
                continue
            if case_id in seen_ids:
                errors.append(f"duplicate_id:{case_id}")
                continue
            seen_ids.add(case_id)

            case = dict(source_by_id[case_id])
            metadata = dict(defaults)
            metadata.update({key: value for key, value in entry.items() if key != "id"})
            metadata["task_group"] = metadata.get("task_group") or case.get("task") or "general"
            metadata["allowed_decisions"] = metadata.get("allowed_decisions") or [
                str(case.get("expected_decision") or "route")
            ]
            missing = [key for key in required_metadata if key not in metadata]
            if missing:
                errors.append(f"missing_metadata:{suite}:{case_id}:{','.join(missing)}")

            query = str(case.get("query") or "")
            normalized_query = normalize_query(query)
            if normalized_query in seen_queries:
                duplicate_query_pairs.append([seen_queries[normalized_query], case_id])
                if benchmark_scope:
                    errors.append(f"duplicate_query:{seen_queries[normalized_query]}:{case_id}")
            else:
                seen_queries[normalized_query] = case_id

            coupled = bool(metadata.get("case_study_coupled")) or bool(
                re.search(r"case[-_ ]study", json.dumps(case, ensure_ascii=False), flags=re.IGNORECASE)
            )
            if benchmark_scope and coupled:
                errors.append(f"case_study_coupled:{suite}:{case_id}")

            task = case.get("task")
            if task and task not in known_task_set:
                errors.append(f"unknown_task:{suite}:{case_id}:{task}")
            for field in ("expected_primary_skill", "required_selected_skill"):
                skill_id = case.get(field)
                if skill_id and skill_id not in known_skill_set:
                    errors.append(f"unknown_skill:{suite}:{case_id}:{skill_id}")

            case["benchmark_metadata"] = metadata
            resolved.append(case)
        output[suite] = resolved

    if errors:
        raise ValueError("invalid v2 manifest: " + "; ".join(errors))
    required_skill_coverage = [str(item) for item in manifest.get("required_skill_coverage") or []]
    covered_skills = set()
    for case in output.get("routing", []):
        for field in ("expected_primary_skill", "covered_skill"):
            skill_id = case.get(field)
            if skill_id:
                covered_skills.add(str(skill_id))
    missing_skill_coverage = sorted(set(required_skill_coverage) - covered_skills)
    if missing_skill_coverage:
        raise ValueError("invalid v2 manifest: missing_skill_coverage:" + ",".join(missing_skill_coverage))
    audit = {
        "manifest_id": manifest.get("manifest_id"),
        "case_count": sum(len(cases) for cases in output.values()),
        "suite_counts": {suite: len(cases) for suite, cases in output.items()},
        "normalized_query_count": len(seen_queries),
        "case_study_free": benchmark_scope,
        "duplicate_queries": len(duplicate_query_pairs),
        "duplicate_query_pairs": duplicate_query_pairs,
        "required_skill_coverage": required_skill_coverage,
        "covered_skills": sorted(covered_skills),
        "skill_coverage_complete": not missing_skill_coverage,
    }
    return output, audit


def load_protocol(
    protocol: Dict[str, Any], participant_map: Dict[str, Dict[str, Any]]
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], List[str]]:
    if protocol.get("schema_version") != 2:
        raise ValueError("v2 protocol must declare schema_version: 2")
    raw_tracks = protocol.get("tracks")
    raw_participants = protocol.get("participants")
    if not isinstance(raw_tracks, list) or not isinstance(raw_participants, list):
        raise ValueError("v2 protocol requires tracks and participants lists")

    tracks: Dict[str, Dict[str, Any]] = {}
    for item in raw_tracks:
        if not isinstance(item, dict) or not item.get("id") or not isinstance(item.get("suites"), list):
            raise ValueError(f"invalid protocol track: {item!r}")
        tracks[str(item["id"])] = dict(item)

    participants: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for item in raw_participants:
        entry = {"id": item} if isinstance(item, str) else dict(item) if isinstance(item, dict) else {}
        participant_id = str(entry.get("id") or "")
        if participant_id not in participant_map:
            raise ValueError(f"unknown protocol participant: {participant_id}")
        merged = dict(participant_map[participant_id])
        merged.update(entry)
        participants[participant_id] = merged
        order.append(participant_id)
    return tracks, participants, order


def _drop_example_values(value: Any) -> Any:
    if isinstance(value, list):
        return [_drop_example_values(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _drop_example_values(item)
            for key, item in value.items()
            if str(key) not in {"examples", "example", "updated_at"}
        }
    return value


def build_context_bundle(
    query: str,
    skills: List[Dict[str, Any]],
    repo_root: Optional[Path] = None,
    schema_context: Optional[Dict[str, Any]] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    query_tokens = set(re.findall(r"[a-z0-9][a-z0-9_.-]+", query.lower()))
    ranked: List[Tuple[int, str, Dict[str, Any]]] = []
    for skill in skills:
        skill_id = str(skill.get("id") or "")
        searchable = " ".join(
            [skill_id, str(skill.get("family") or ""), *[str(item) for item in skill.get("tasks") or []],
             *[str(item) for item in skill.get("triggers") or []]]
        ).lower()
        skill_tokens = set(re.findall(r"[a-z0-9][a-z0-9_.-]+", searchable))
        score = len(query_tokens & skill_tokens)
        if f"${skill_id}" in query.lower() or skill_id in query.lower():
            score += 100
        ranked.append((score, skill_id, skill))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    chosen = [item[2] for item in ranked[: max(1, limit)]]
    documents: List[Dict[str, Any]] = []
    for skill in chosen:
        document: Dict[str, Any] = {
            "id": str(skill.get("id") or ""),
            "family": skill.get("family"),
            "tasks": skill.get("tasks") or [],
            "triggers": skill.get("triggers") or [],
            "enabled": bool(skill.get("enabled", False)),
        }
        if repo_root is not None and skill.get("path"):
            metadata_path = repo_root / str(skill["path"]) / "skill.yaml"
            if metadata_path.exists():
                try:
                    import yaml
                    parsed = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
                    if isinstance(parsed, dict):
                        document["skill_metadata"] = _drop_example_values(parsed)
                except Exception:
                    document["skill_metadata_sha256"] = sha256_file(metadata_path)
        documents.append(document)
    bundle = {"skills": documents, "schemas": _drop_example_values(schema_context or {})}
    content = json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2)
    document_ids = [f"skill:{d['id']}:skill.yaml" for d in documents]
    if schema_context:
        document_ids.extend(["registry:input_schema", "registry:task_contracts", "registry:parameter_catalog"])
    return {"retriever": "registry-token-overlap-v1", "document_ids": document_ids,
            "content": content, "content_sha256": sha256_text(content)}


def render_v2_prompt(
    template: str,
    track_id: str,
    case: Dict[str, Any],
    skill_catalog: str,
    context_bundle: Dict[str, Any],
    schema_text: str,
) -> str:
    replacements = {
        "{{QUERY}}": str(case.get("query") or ""),
        "{{SKILL_CATALOG}}": skill_catalog,
        "{{CONTEXT_BUNDLE}}": str(context_bundle.get("content") or "{}"),
        "{{CANONICAL_TASK}}": str(case.get("task") or "unknown"),
        "{{JSON_SCHEMA}}": schema_text,
    }
    rendered = template
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    return rendered


def validate_rendered_prompt(prompt: str, track_id: str, case: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if re.search(r"\{\{[A-Z0-9_]+\}\}", prompt):
        errors.append("unresolved_template_token")
    case_id = str(case.get("id") or "")
    if case_id and case_id in prompt:
        errors.append("case_id_leakage")
    prompt_lower = prompt.lower()
    for field in SCORER_ONLY_FIELDS:
        if field.lower() in prompt_lower:
            errors.append(f"scorer_field_leakage:{field}")
    if track_id == "task-blind-routing":
        if "task hint:" in prompt_lower or "canonical task supplied" in prompt_lower:
            errors.append("gold_task_marker_leakage")
    return errors


def score_case_v2(
    suite: str, case: Dict[str, Any], normalized: Dict[str, Any], score_track: str, api: Mapping[str, Any]
) -> Dict[str, Any]:
    decision = normalized.get("decision")
    metadata = case.get("benchmark_metadata") or {}
    allowed = [str(item) for item in metadata.get("allowed_decisions") or []]
    if decision == "clarify" and "clarify" in allowed and suite in {"groundedness", "task_success"}:
        question = str(normalized.get("clarify_question") or "").strip()
        required_missing = str(case.get("required_missing_input_contains") or "").strip()
        actual_missing = [str(item) for item in normalized.get("missing_inputs") or []]
        missing_ok = not required_missing or any(required_missing.lower() in item.lower() for item in actual_missing)
        validation_ok = not normalized.get("validation_errors")
        checks = [
            {"name": "decision_allowed", "pass": True, "expected": allowed, "actual": decision},
            {"name": "clarify_question_present", "pass": bool(question), "actual": question},
            {"name": "required_missing_input", "pass": missing_ok, "expected": required_missing, "actual": actual_missing},
            {"name": "normalization_validation", "pass": validation_ok,
             "actual": normalized.get("validation_errors") or []},
        ]
        return {"pass": all(bool(check["pass"]) for check in checks), "checks": checks}
    result = _fn(api, "score_case")(suite, case, normalized, track=score_track)
    if suite == "routing":
        expected = {str(item) for item in case.get("expected_secondary_skills") or []}
        actual = {str(item) for item in normalized.get("secondary_skills") or []}
        true_positive = len(expected & actual)
        precision = true_positive / len(actual) if actual else (1.0 if not expected else 0.0)
        recall = true_positive / len(expected) if expected else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        exact = actual == expected
        result.setdefault("components", {})["secondary"] = {
            "precision": precision, "recall": recall, "f1": f1, "exact_match": exact
        }
        if score_track == "strict" and not expected:
            # An empty gold list is an explicit negative: do not accept
            # invented secondary routes. For non-empty gold lists, secondary
            # candidates are ranked alternatives, so containment is the
            # reproducible requirement and precision/F1 remain diagnostics.
            exact_negative = not actual
            for check in result.get("checks", []):
                if check.get("name") == "secondary_skills_contains_expected":
                    check["name"] = "secondary_skills_exact_negative"
                    check["pass"] = exact_negative
                    check["unexpected"] = sorted(actual)
            result["pass"] = all(bool(check.get("pass")) for check in result.get("checks", []))
        expected_task = case.get("task")
        if expected_task:
            result.setdefault("components", {})["task_inference"] = {
                "expected": expected_task,
                "actual": normalized.get("inferred_task"),
                "correct": normalized.get("inferred_task") == expected_task,
            }
    return result


def _empty_normalized(api: Mapping[str, Any], known_skills: Iterable[str], reason: str) -> Dict[str, Any]:
    normalized = _fn(api, "normalize_from_raw_text")("", known_skills)
    normalized["validation_errors"] = [reason]
    return normalized


def _mock_path(root: Path, participant_id: str, track: str, suite: str, case_id: str, repeat: int) -> Optional[Path]:
    candidates = [
        root / participant_id / track / suite / case_id / f"{repeat}.json",
        root / participant_id / track / suite / case_id / f"{repeat}.txt",
        root / participant_id / suite / f"{case_id}.json",
        root / participant_id / suite / f"{case_id}.txt",
    ]
    return next((path for path in candidates if path.exists()), None)


def _record_paths(participant_id: str, track: str, suite: str, case_id: str, repeat: int) -> Dict[str, Path]:
    stem = Path(participant_id) / track / suite / case_id / str(repeat)
    return {
        "prompt": Path("prompts") / stem.with_suffix(".txt"),
        "raw": Path("raw_outputs") / stem.with_suffix(".txt"),
        "record": Path("case_records") / stem.with_suffix(".json"),
    }


def _execution_fingerprint(
    protocol_id: str,
    manifest_id: str,
    participant: Dict[str, Any],
    track: str,
    suite: str,
    case: Dict[str, Any],
    repeat: int,
    prompt: str,
    scorer_sha256: str,
) -> str:
    public_participant = {key: value for key, value in participant.items() if "key" not in key.lower() and "token" not in key.lower()}
    payload = {
        "protocol_id": protocol_id,
        "manifest_id": manifest_id,
        "participant": public_participant,
        "track": track,
        "suite": suite,
        "case": case,
        "repeat": repeat,
        "prompt_sha256": sha256_text(prompt),
        "scorer_sha256": scorer_sha256,
    }
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def execute_case(
    args: Any,
    api: Mapping[str, Any],
    repo_root: Path,
    participant: Dict[str, Any],
    participant_id: str,
    track_id: str,
    suite: str,
    case: Dict[str, Any],
    prompt: str,
    repeat: int,
    known_skills: Iterable[str],
    include_disabled: bool,
    api_key: str,
    base_url: str,
    timeout_s: int,
    max_retries: int,
) -> Tuple[str, str, Optional[str], Dict[str, Any], Dict[str, Any]]:
    if args.dry_run:
        reason = "dry_run_skipped"
        return "skipped", "", reason, _empty_normalized(api, known_skills, reason), {"attempts": 0}

    if args.mock_response_dir:
        mock_root = Path(args.mock_response_dir).resolve()
        path = _mock_path(mock_root, participant_id, track_id, suite, str(case["id"]), repeat)
        if path is None:
            reason = "missing_mock_response"
            return "skipped", "", reason, _empty_normalized(api, known_skills, reason), {"attempts": 0}
        raw = path.read_text(encoding="utf-8")
        return "scored", raw, None, _fn(api, "normalize_from_raw_text")(raw, known_skills), {
            "attempts": 1, "mock_path": str(path)
        }

    kind = participant.get("kind")
    if kind == "local_agent":
        if suite == "routing":
            cmd = ["bash", str(repo_root / "scripts/route_query.sh"), "--query", str(case.get("query") or ""),
                   "--top-k", str(max(1, len(set(known_skills)))), "--format", "json"]
        else:
            cmd = ["bash", str(repo_root / "scripts/run_agent.sh"), "--query", str(case.get("query") or ""),
                   "--format", "json"]
        if track_id == "task-conditioned" and case.get("task"):
            cmd.extend(["--task", str(case["task"])])
        if include_disabled:
            cmd.append("--include-disabled")
        try:
            raw, parsed, run_error = _fn(api, "run_subprocess_json")(cmd)
        except Exception as exc:
            reason = f"local_runner_exception:{type(exc).__name__}"
            return "infrastructure_error", "", reason, _empty_normalized(api, known_skills, reason), {
                "attempts": 1, "command": cmd
            }
        if run_error:
            normalized = _fn(api, "normalize_from_raw_text")(raw, known_skills)
            infrastructure = run_error.startswith("subprocess_exit_")
            if not infrastructure:
                normalized.setdefault("validation_errors", []).append(run_error)
            return "infrastructure_error" if infrastructure else "scored", raw, run_error, normalized, {
                "attempts": 1, "command": cmd
            }
        normalized = _fn(api, "normalize_from_object")(parsed or {}, raw, known_skills)
        return "scored", raw, None, normalized, {"attempts": 1, "command": cmd}

    if kind == "openai_responses":
        result = _fn(api, "call_openai_responses")(participant, prompt, api_key, base_url, timeout_s, max_retries)
    elif kind == "openai_chat":
        result = _fn(api, "call_openai_chat")(participant, prompt, api_key, base_url, timeout_s, max_retries)
    else:
        raise ValueError(f"unsupported participant kind: {kind}")

    raw = str(result.get("raw_text") or "")
    metadata = {
        "attempts": int(result.get("attempts") or 0),
        "requested_model": participant.get("model"),
        "response_metadata": result.get("response_metadata") or {},
        "usage": result.get("usage") or {},
    }
    error = str(result.get("error") or "") or None
    if result.get("ok"):
        return "scored", raw, None, _fn(api, "normalize_from_raw_text")(raw, known_skills), metadata
    infrastructure = bool(error and ("_http_" in error or error.startswith("network_error")))
    status = "infrastructure_error" if infrastructure else "scored"
    normalized = _fn(api, "normalize_from_raw_text")(raw, known_skills)
    if not infrastructure and error:
        normalized.setdefault("validation_errors", []).append(error)
    return status, raw, error, normalized, metadata


def _coverage_key(participant: str, track: str, suite: str, case_id: str, repeat: int) -> str:
    return "|".join([participant, track, suite, case_id, str(repeat)])


def build_coverage(records: List[Dict[str, Any]], expected: List[Dict[str, Any]], participants: List[str]) -> Dict[str, Any]:
    expected_keys = {
        _coverage_key(item["participant_id"], item["benchmark_track"], item["suite"], item["case_id"], item["repeat_index"])
        for item in expected
    }
    records_by_key: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        key = _coverage_key(record["participant_id"], record["benchmark_track"], record["suite"],
                            str(record["case"]["id"]), int(record["repeat_index"]))
        records_by_key.setdefault(key, []).append(record)

    status_counts = {status: 0 for status in VALID_STATUSES}
    unexpected_status = 0
    for record in records:
        status = str(record.get("status"))
        if status in status_counts:
            status_counts[status] += 1
        else:
            unexpected_status += 1
    missing = sorted(expected_keys - set(records_by_key))
    duplicates = sorted(key for key, values in records_by_key.items() if len(values) != 1)
    unexpected = sorted(set(records_by_key) - expected_keys)

    participant_coverage: Dict[str, Any] = {}
    for participant_id in participants:
        participant_specs = [item for item in expected if item["participant_id"] == participant_id]
        participant_expected = [key for key in expected_keys if key.startswith(participant_id + "|")]
        participant_records = [record for record in records if record.get("participant_id") == participant_id]
        counts = {status: sum(1 for record in participant_records if record.get("status") == status) for status in VALID_STATUSES}
        passed = sum(
            1 for record in participant_records
            if record.get("status") == "scored" and record.get("scores", {}).get("strict", {}).get("pass")
        )
        tracks: Dict[str, Any] = {}
        for track in sorted({item["benchmark_track"] for item in participant_specs}):
            tracks[track] = {}
            for suite in sorted({item["suite"] for item in participant_specs if item["benchmark_track"] == track}):
                specs = [item for item in participant_specs if item["benchmark_track"] == track and item["suite"] == suite]
                suite_records = [record for record in participant_records
                                 if record.get("benchmark_track") == track and record.get("suite") == suite]
                suite_counts = {status: sum(1 for record in suite_records if record.get("status") == status)
                                for status in VALID_STATUSES}
                suite_passed = sum(
                    1 for record in suite_records
                    if record.get("status") == "scored" and record.get("scores", {}).get("strict", {}).get("pass")
                )
                tracks[track][suite] = {
                    "expected": len(specs),
                    "observed": len(suite_records),
                    **suite_counts,
                    "pass": suite_passed,
                    "fail": suite_counts["scored"] - suite_passed,
                }
        participant_coverage[participant_id] = {
            "expected": len(participant_expected),
            "observed": len(participant_records),
            **counts,
            "pass": passed,
            "fail": counts["scored"] - passed,
            "tracks": tracks,
            "complete": len(participant_records) == len(participant_expected) and counts["scored"] == len(participant_expected),
        }

    comparisons: List[Dict[str, Any]] = []
    if "s2f-agent" in participants:
        primary_specs = [item for item in expected if item["participant_id"] == "s2f-agent" and item["repeat_index"] == PRIMARY_REPEAT_INDEX]
        for baseline in [pid for pid in participants if pid != "s2f-agent"]:
            tracks = sorted({item["benchmark_track"] for item in primary_specs})
            for track in tracks:
                track_specs = [item for item in primary_specs if item["benchmark_track"] == track]
                for suite in ["overall"] + sorted({item["suite"] for item in track_specs}):
                    relevant = track_specs if suite == "overall" else [item for item in track_specs if item["suite"] == suite]
                    reasons: List[str] = []
                    for item in relevant:
                        for participant_id in ("s2f-agent", baseline):
                            key = _coverage_key(participant_id, track, item["suite"], item["case_id"], PRIMARY_REPEAT_INDEX)
                            values = records_by_key.get(key, [])
                            if len(values) != 1:
                                reasons.append(f"{participant_id}:{item['suite']}:{item['case_id']}:missing_or_duplicate")
                            elif values[0].get("status") != "scored":
                                reasons.append(f"{participant_id}:{item['suite']}:{item['case_id']}:{values[0].get('status')}")
                    comparisons.append({"target": "s2f-agent", "baseline": baseline, "benchmark_track": track,
                                        "suite": suite, "valid": not reasons, "invalid_reasons": reasons})

    complete = (
        not missing and not duplicates and not unexpected and not unexpected_status
        and status_counts["infrastructure_error"] == 0 and status_counts["skipped"] == 0
        and status_counts["scored"] == len(expected_keys)
    )
    return {
        "schema_version": 2,
        "expected_records": len(expected_keys),
        "observed_records": len(records),
        "status_counts": status_counts,
        "pass": sum(1 for record in records if record.get("status") == "scored"
                    and record.get("scores", {}).get("strict", {}).get("pass")),
        "fail": sum(1 for record in records if record.get("status") == "scored"
                    and not record.get("scores", {}).get("strict", {}).get("pass")),
        "missing_keys": missing,
        "duplicate_keys": duplicates,
        "unexpected_keys": unexpected,
        "participants": participant_coverage,
        "comparisons": comparisons,
        "complete": complete,
    }


def _overall_macro_ci(
    records: List[Dict[str, Any]], suites: List[str], iterations: int, seed: int, score_track: str, api: Mapping[str, Any]
) -> Optional[List[float]]:
    by_suite = {suite: [r for r in records if r.get("suite") == suite and r.get("status") == "scored"] for suite in suites}
    if not any(by_suite.values()):
        return None
    rng = random.Random(seed)
    draws: List[float] = []
    for _ in range(iterations):
        suite_values: List[float] = []
        for suite in suites:
            values = by_suite[suite]
            if not values:
                continue
            by_group: Dict[str, List[Dict[str, Any]]] = {}
            for record in values:
                metadata = record.get("case", {}).get("benchmark_metadata", {})
                group = str(metadata.get("task_group") or record.get("case", {}).get("task") or "general")
                by_group.setdefault(group, []).append(record)
            group_values: List[float] = []
            for group_records in by_group.values():
                sampled = [group_records[rng.randrange(len(group_records))] for _ in group_records]
                outcomes = [1.0 if _fn(api, "record_passes")(record, score_track) else 0.0 for record in sampled]
                group_values.append(sum(outcomes) / len(outcomes))
            if group_values:
                suite_values.append(sum(group_values) / len(group_values))
        if suite_values:
            draws.append(sum(suite_values) / len(suite_values))
    return _fn(api, "bootstrap_ci")(draws)


def _holm_adjust(comparisons: List[Dict[str, Any]]) -> None:
    indexed = [(idx, item.get("mcnemar", {}).get("p_value")) for idx, item in enumerate(comparisons)]
    valid = sorted([(idx, float(p)) for idx, p in indexed if p is not None], key=lambda pair: pair[1])
    count = len(valid)
    running = 0.0
    for rank, (idx, p_value) in enumerate(valid):
        adjusted = min(1.0, (count - rank) * p_value)
        running = max(running, adjusted)
        comparisons[idx]["mcnemar"]["holm_adjusted_p_value"] = running


def build_component_metrics(
    records: List[Dict[str, Any]], participant_ids: List[str], suites: List[str], score_track: str
) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for participant_id in participant_ids:
        output[participant_id] = {}
        for suite in suites:
            suite_records = [
                record for record in records
                if record.get("participant_id") == participant_id and record.get("suite") == suite
                and record.get("status") == "scored"
            ]
            checks: Dict[str, Dict[str, int]] = {}
            secondary_values: Dict[str, List[float]] = {"precision": [], "recall": [], "f1": []}
            task_values: List[bool] = []
            for record in suite_records:
                score = record.get("scores", {}).get(score_track, {})
                for check in score.get("checks", []):
                    name = str(check.get("name") or "unknown")
                    item = checks.setdefault(name, {"passed": 0, "total": 0})
                    item["total"] += 1
                    item["passed"] += int(bool(check.get("pass")))
                secondary = score.get("components", {}).get("secondary") or {}
                for name in secondary_values:
                    if secondary.get(name) is not None:
                        secondary_values[name].append(float(secondary[name]))
                task = score.get("components", {}).get("task_inference") or {}
                if task.get("correct") is not None:
                    task_values.append(bool(task["correct"]))
            output[participant_id][suite] = {
                "checks": {
                    name: {**values, "rate": values["passed"] / values["total"] if values["total"] else None}
                    for name, values in sorted(checks.items())
                },
                "secondary": {
                    name: sum(values) / len(values) if values else None for name, values in secondary_values.items()
                },
                "task_inference_accuracy": sum(task_values) / len(task_values) if task_values else None,
            }
    return output


def compute_track_results(
    records: List[Dict[str, Any]],
    track_suites: Dict[str, List[str]],
    participant_ids: List[str],
    iterations: int,
    seed: int,
    coverage: Dict[str, Any],
    api: Mapping[str, Any],
) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    validity = {
        (item["baseline"], item["benchmark_track"], item["suite"]): item
        for item in coverage.get("comparisons", [])
    }
    primary_records = [record for record in records if record.get("repeat_index") == PRIMARY_REPEAT_INDEX]
    for track_offset, (track, suites) in enumerate(track_suites.items()):
        track_records = [record for record in primary_records if record.get("benchmark_track") == track]
        score_tracks: Dict[str, Any] = {}
        stats_tracks: Dict[str, Any] = {}
        component_tracks: Dict[str, Any] = {}
        for score_offset, score_track in enumerate(("strict", "lenient")):
            metrics = _fn(api, "compute_participant_metrics")(
                track_records, participant_ids, suites, iterations, seed + track_offset * 100 + score_offset, score_track
            )
            for participant_offset, participant_id in enumerate(participant_ids):
                participant_records = [r for r in track_records if r.get("participant_id") == participant_id]
                for suite_offset, suite in enumerate(suites):
                    suite_records = [record for record in participant_records if record.get("suite") == suite]
                    metrics[participant_id]["suite_metrics"][suite]["macro_ci"] = _overall_macro_ci(
                        suite_records,
                        [suite],
                        iterations,
                        seed + 7000 + participant_offset * 100 + suite_offset,
                        score_track,
                        api,
                    )
                overall = metrics[participant_id]["overall"]
                rng = random.Random(seed + 5000 + participant_offset + score_offset * 100)
                overall["micro_ci"] = _fn(api, "bootstrap_micro_ci")(
                    participant_records, iterations, rng, score_track=score_track
                )
                overall["macro_ci"] = _overall_macro_ci(
                    participant_records, suites, iterations, seed + 9000 + participant_offset, score_track, api
                )
            stats = _fn(api, "compute_stats")(
                track_records, metrics, participant_ids, suites, iterations, seed + track_offset * 100, score_track
            )
            valid_comparisons: List[Dict[str, Any]] = []
            invalid_comparisons: List[Dict[str, Any]] = []
            for item in stats.get("comparisons", []):
                gate = validity.get((str(item.get("baseline")), track, str(item.get("suite"))))
                if gate and gate.get("valid"):
                    valid_comparisons.append(item)
                else:
                    invalid_comparisons.append({
                        "target": item.get("target"), "baseline": item.get("baseline"), "suite": item.get("suite"),
                        "valid": False, "invalid_reasons": (gate or {}).get("invalid_reasons", ["incomplete_pair"]),
                    })
            present_invalid = {
                (str(item.get("baseline")), str(item.get("suite"))) for item in invalid_comparisons
            }
            for (baseline, validity_track, suite), gate in validity.items():
                if validity_track != track or gate.get("valid") or (baseline, suite) in present_invalid:
                    continue
                invalid_comparisons.append({
                    "target": "s2f-agent",
                    "baseline": baseline,
                    "suite": suite,
                    "valid": False,
                    "invalid_reasons": gate.get("invalid_reasons") or ["incomplete_pair"],
                })
            _holm_adjust(valid_comparisons)
            stats["comparisons"] = valid_comparisons
            stats["invalid_comparisons"] = invalid_comparisons
            score_tracks[score_track] = metrics
            stats_tracks[score_track] = stats
            component_tracks[score_track] = build_component_metrics(
                track_records, participant_ids, suites, score_track
            )
        results[track] = {
            "suites": suites,
            "score_tracks": score_tracks,
            "component_metrics": component_tracks,
            "stats": stats_tracks,
        }
    return results


def build_stability(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    groups: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = {}
    for record in records:
        key = (record["participant_id"], record["benchmark_track"], record["suite"], str(record["case"]["id"]))
        groups.setdefault(key, []).append(record)
    participants: Dict[str, Any] = {}
    for key, values in groups.items():
        participant_id = key[0]
        scored = [value for value in values if value.get("status") == "scored"]
        outcomes = [bool(value.get("scores", {}).get("strict", {}).get("pass")) for value in scored]
        item = participants.setdefault(participant_id, {"case_groups": 0, "fully_stable": 0, "mean_pass_variance": None, "variances": []})
        if len(outcomes) >= 2:
            item["case_groups"] += 1
            proportion = sum(outcomes) / len(outcomes)
            variance = proportion * (1.0 - proportion)
            item["variances"].append(variance)
            if variance == 0.0:
                item["fully_stable"] += 1
    for item in participants.values():
        variances = item.pop("variances")
        item["mean_pass_variance"] = sum(variances) / len(variances) if variances else None
        item["agreement_rate"] = item["fully_stable"] / item["case_groups"] if item["case_groups"] else None
    return {"participants": participants}


def build_efficiency(records: List[Dict[str, Any]], participant_ids: List[str]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for participant_id in participant_ids:
        participant_records = [record for record in records if record.get("participant_id") == participant_id]
        elapsed = sorted(float(record.get("elapsed_ms") or 0) for record in participant_records)
        token_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        for record in participant_records:
            usage = record.get("execution", {}).get("usage") or {}
            token_totals["input_tokens"] += int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            token_totals["output_tokens"] += int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
            token_totals["total_tokens"] += int(usage.get("total_tokens") or 0)
        if not token_totals["total_tokens"]:
            token_totals["total_tokens"] = token_totals["input_tokens"] + token_totals["output_tokens"]
        output[participant_id] = {
            "record_count": len(participant_records),
            "mean_elapsed_ms": sum(elapsed) / len(elapsed) if elapsed else None,
            "median_elapsed_ms": elapsed[len(elapsed) // 2] if elapsed else None,
            "token_usage": token_totals,
        }
    return output


def publication_gate_reasons(
    args: Any,
    protocol: Dict[str, Any],
    protocol_participants: Dict[str, Dict[str, Any]],
    selected_participants: List[str],
    selected_tracks: List[str],
    selected_suites: List[str],
    track_configs: Dict[str, Dict[str, Any]],
    repeat_counts: Dict[str, int],
    coverage: Dict[str, Any],
    git: Dict[str, Any],
    prompt_errors: List[Dict[str, Any]],
    secret_findings: List[str],
    manifest_audit: Dict[str, Any],
    records: List[Dict[str, Any]],
) -> List[str]:
    reasons: List[str] = []
    primary_tracks = [track_id for track_id, config in track_configs.items() if config.get("primary")]
    primary_suites = sorted({suite for track_id in primary_tracks for suite in track_configs[track_id].get("suites", [])})
    if set(selected_participants) != set(protocol_participants.keys()):
        reasons.append("participant_set_does_not_match_protocol")
    if sorted(selected_tracks) != sorted(primary_tracks):
        reasons.append("track_set_does_not_match_primary_protocol")
    if sorted(selected_suites) != primary_suites:
        reasons.append("suite_set_does_not_match_primary_protocol")
    for participant_id in selected_participants:
        config = protocol_participants[participant_id]
        expected_repeats = int(config.get("repeats") or protocol.get("replicates") or 1)
        if repeat_counts.get(participant_id) != expected_repeats:
            reasons.append(f"replicate_count_mismatch:{participant_id}")
    if not coverage.get("complete"):
        reasons.append("coverage_incomplete")
    if not manifest_audit.get("case_study_free"):
        reasons.append("manifest_not_case_study_free_benchmark")
    if args.dry_run:
        reasons.append("dry_run")
    if args.mock_response_dir:
        reasons.append("mock_run")
    publication = protocol.get("publication") or {}
    if publication.get("require_clean_worktree", True) and git.get("dirty"):
        reasons.append("dirty_worktree")
    if publication.get("require_exact_model_snapshot", True):
        for participant_id, config in protocol_participants.items():
            if config.get("kind") == "local_agent":
                continue
            snapshot = str(config.get("model_snapshot") or "")
            if not snapshot or snapshot.lower() in {"unresolved", "latest", "floating"}:
                reasons.append(f"unresolved_model_snapshot:{participant_id}")
                continue
            returned_models = {
                str(record.get("execution", {}).get("response_metadata", {}).get("model"))
                for record in records
                if record.get("participant_id") == participant_id and record.get("status") == "scored"
                and record.get("execution", {}).get("response_metadata", {}).get("model")
            }
            if not returned_models:
                reasons.append(f"response_model_identity_missing:{participant_id}")
            elif returned_models != {snapshot}:
                reasons.append(f"response_model_identity_mismatch:{participant_id}")
    if prompt_errors:
        reasons.append("prompt_leakage_validation_failed")
    if secret_findings:
        reasons.append("secret_scan_failed")
    return sorted(set(reasons))


def scan_artifacts_for_secrets(output_dir: Path) -> List[str]:
    patterns = [
        re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
        re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+(?!<REDACTED>)[^\s\"']+"),
        re.compile(r"/Users/[^/\s]+/"),
        re.compile(r"/home/[^/\s]+/"),
    ]
    findings: List[str] = []
    for directory in ("prompts", "raw_outputs", "case_records"):
        root = output_dir / directory
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(pattern.search(text) for pattern in patterns):
                findings.append(path.relative_to(output_dir).as_posix())
    return findings


def publish_release(output_dir: Path, repo_root: Path, run_manifest: Dict[str, Any], api: Mapping[str, Any]) -> Path:
    run_id = output_dir.name
    release_dir = repo_root / "benchmark/releases" / run_id
    if release_dir.exists():
        raise FileExistsError(f"immutable release already exists: {release_dir}")
    release_dir.mkdir(parents=True)
    required = ("run_manifest.json", "coverage.json", "summary.json", "summary.csv", "stats.json", "table.md", "examples.md")
    checksums: Dict[str, str] = {}
    for name in required:
        source = output_dir / name
        if not source.exists():
            raise FileNotFoundError(f"release artifact missing: {source}")
        shutil.copyfile(source, release_dir / name)
        checksums[name] = sha256_file(release_dir / name)
    (release_dir / "checksums.json").write_text(_fn(api, "dump_json")(checksums) + "\n", encoding="utf-8")
    report_dir = repo_root / "benchmark/reports/manuscript"
    report_dir.mkdir(parents=True, exist_ok=True)
    latest = "\n".join([
        "# Benchmark Results (Latest)", "", f"- Release: `{release_dir.relative_to(repo_root).as_posix()}`",
        f"- Protocol: `{run_manifest.get('protocol_id')}`", f"- Manifest: `{run_manifest.get('manifest_id')}`",
        f"- Generated at (UTC): `{run_manifest.get('completed_at')}`", "",
    ])
    (report_dir / "benchmark-results-latest.md").write_text(latest, encoding="utf-8")
    return release_dir


def _input_hashes(paths: Sequence[Path], repo_root: Path) -> Dict[str, str]:
    output: Dict[str, str] = {}
    for path in paths:
        if path.exists() and path.is_file():
            try:
                key = path.relative_to(repo_root).as_posix()
            except ValueError:
                key = str(path)
            output[key] = sha256_file(path)
    return dict(sorted(output.items()))


def _write_summary_csv(
    path: Path, track_results: Dict[str, Any], participants: List[str], configs: Dict[str, Dict[str, Any]]
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["benchmark_track", "participant_id", "participant_label", "score_track", "suite", "total",
                         "passed", "micro", "macro", "micro_ci_low", "micro_ci_high", "macro_ci_low", "macro_ci_high"])
        for track, track_result in track_results.items():
            for score_track, metrics_by_participant in track_result["score_tracks"].items():
                for participant_id in participants:
                    metrics = metrics_by_participant[participant_id]
                    rows = [(suite, values) for suite, values in metrics["suite_metrics"].items()]
                    rows.append(("overall", metrics["overall"]))
                    for suite, values in rows:
                        micro_ci = values.get("micro_ci") or [None, None]
                        macro_ci = values.get("macro_ci") or [None, None]
                        writer.writerow([track, participant_id, configs[participant_id].get("label", participant_id), score_track,
                                         suite, values.get("total"), values.get("passed"), values.get("micro"), values.get("macro"),
                                         micro_ci[0], micro_ci[1], macro_ci[0], macro_ci[1]])


def render_ci_table(track_results: Dict[str, Any], participant_ids: List[str], configs: Dict[str, Dict[str, Any]]) -> str:
    lines = ["## Confidence Intervals", "", "| Track | Score | Participant | Suite | Micro 95% CI | Macro 95% CI |",
             "| --- | --- | --- | --- | --- | --- |"]
    for track, track_result in track_results.items():
        for score_track, metrics_by_participant in track_result["score_tracks"].items():
            for participant_id in participant_ids:
                metrics = metrics_by_participant[participant_id]
                rows = [(suite, values) for suite, values in metrics["suite_metrics"].items()]
                rows.append(("overall", metrics["overall"]))
                for suite, values in rows:
                    lines.append(
                        "| " + " | ".join([
                            track,
                            score_track,
                            str(configs[participant_id].get("label", participant_id)),
                            suite,
                            _format_ci(values.get("micro_ci")),
                            _format_ci(values.get("macro_ci")),
                        ]) + " |"
                    )
    return "\n".join(lines) + "\n"


def _format_ci(value: Any) -> str:
    if not isinstance(value, list) or len(value) != 2 or value[0] is None or value[1] is None:
        return "n/a"
    return f"[{float(value[0]):.3f}, {float(value[1]):.3f}]"


def run_benchmark_v2(args: Any, api: Mapping[str, Any]) -> int:
    started_at = _fn(api, "iso_utc_now")()
    repo_root = Path(__file__).resolve().parents[2]
    if not args.protocol or not args.manifest:
        raise ValueError("benchmark v2 requires both --protocol and --manifest")

    config_path = _path(repo_root, args.config)
    participants_path = _path(repo_root, args.participants_config)
    protocol_path = _path(repo_root, args.protocol)
    manifest_path = _path(repo_root, args.manifest)
    benchmark_config = _fn(api, "load_yaml")(config_path)
    participants_config = _fn(api, "load_yaml")(participants_path)
    protocol = _fn(api, "load_yaml")(protocol_path)
    manifest = _fn(api, "load_yaml")(manifest_path)
    defaults = benchmark_config.get("defaults") or {}

    participant_map = _fn(api, "get_participant_map")(participants_config)
    track_configs, protocol_participants, protocol_order = load_protocol(protocol, participant_map)
    selected_participants = _fn(api, "parse_csv_arg")(args.participants) or list(protocol_order)
    unknown_participants = [participant_id for participant_id in selected_participants if participant_id not in protocol_participants]
    if unknown_participants:
        raise ValueError(f"participants are not in protocol: {unknown_participants}")
    selected_configs = {participant_id: protocol_participants[participant_id] for participant_id in selected_participants}

    requested_tracks = _fn(api, "parse_csv_arg")(args.track)
    selected_tracks = requested_tracks or [track_id for track_id, config in track_configs.items() if config.get("primary")]
    unknown_tracks = [track_id for track_id in selected_tracks if track_id not in track_configs]
    if unknown_tracks:
        raise ValueError(f"tracks are not in protocol: {unknown_tracks}")
    requested_suites = _fn(api, "parse_csv_arg")(args.suites)
    track_suites: Dict[str, List[str]] = {}
    for track_id in selected_tracks:
        suites = [str(suite) for suite in track_configs[track_id].get("suites", [])]
        if requested_suites:
            suites = [suite for suite in suites if suite in requested_suites]
        if not suites:
            raise ValueError(f"track has no selected suites: {track_id}")
        track_suites[track_id] = suites
    selected_suites = sorted({suite for suites in track_suites.values() for suite in suites})

    include_disabled = bool(protocol.get("include_disabled_skills", defaults.get("include_disabled_skills", False)))
    skills = _fn(api, "load_enabled_skills")(repo_root, include_disabled)
    known_skills = {str(skill["id"]) for skill in skills if skill.get("id")}
    task_contracts_path = repo_root / "registry/task_contracts.yaml"
    task_contracts = _fn(api, "load_yaml")(task_contracts_path)
    input_schema_path = repo_root / "registry/input_schema.yaml"
    input_schema = _fn(api, "load_yaml")(input_schema_path)
    parameter_catalog_path = repo_root / "registry/parameter_catalog.yaml"
    parameter_catalog = _fn(api, "load_yaml")(parameter_catalog_path)
    schema_context = {
        "input_schema": input_schema,
        "task_contracts": task_contracts,
        "parameter_catalog": parameter_catalog,
    }
    known_tasks = set((task_contracts.get("contracts") or {}).keys())
    known_tasks.update(
        str(task)
        for skill in skills
        for task in (skill.get("tasks") or [])
        if isinstance(task, str) and task
    )
    suite_cases, manifest_audit = load_manifest_cases(manifest, repo_root, known_skills, known_tasks, api)
    missing_suites = [suite for suite in selected_suites if suite not in suite_cases]
    if missing_suites:
        raise ValueError(f"selected suites missing from manifest: {missing_suites}")

    repeat_counts = {
        participant_id: int(args.replicates or selected_configs[participant_id].get("repeats") or protocol.get("replicates") or 1)
        for participant_id in selected_participants
    }
    if any(value < 1 for value in repeat_counts.values()):
        raise ValueError("replicates must be at least 1")

    output_dir = _fn(api, "resolve_output_dir")(args.output_dir, benchmark_config, repo_root)
    for directory in ("prompts", "raw_outputs", "case_records"):
        (output_dir / directory).mkdir(parents=True, exist_ok=True)

    family_descriptions = benchmark_config.get("family_descriptions") or {}
    skill_catalog = _fn(api, "format_skill_catalog")(skills, family_descriptions)
    schema_text = _fn(api, "target_json_schema_text")()
    templates: Dict[str, str] = {}
    template_paths: List[Path] = []
    for track_id in selected_tracks:
        template_path = repo_root / "benchmark/prompts" / str(track_configs[track_id].get("prompt_template") or "")
        if not template_path.exists():
            raise FileNotFoundError(f"track prompt template not found: {template_path}")
        templates[track_id] = template_path.read_text(encoding="utf-8")
        template_paths.append(template_path)

    timeout_s = int(args.openai_timeout or protocol.get("openai_timeout_seconds")
                    or defaults.get("openai_timeout_seconds") or 120)
    max_retries = int(
        args.openai_max_retries
        if args.openai_max_retries is not None
        else protocol.get("openai_max_retries", defaults.get("openai_max_retries", 2))
    )
    iterations = int(args.bootstrap_iterations or protocol.get("bootstrap_iterations") or defaults.get("bootstrap_iterations") or 10000)
    base_url = _fn(api, "resolve_openai_base_url")(args, defaults)
    api_key = args.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
    openai_ids = [participant_id for participant_id in selected_participants
                  if _fn(api, "participant_requires_openai")(selected_configs[participant_id])]
    if openai_ids and not args.dry_run and not args.mock_response_dir and not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for selected API participants")

    scorer_sha256 = sha256_text(
        sha256_file(repo_root / "benchmark/tools/eval_benchmark.py") + sha256_file(Path(__file__))
    )
    records: List[Dict[str, Any]] = []
    expected: List[Dict[str, Any]] = []
    prompt_errors: List[Dict[str, Any]] = []
    max_repeats = max(repeat_counts.values())

    for repeat in range(max_repeats):
        for track_id in selected_tracks:
            for suite in track_suites[track_id]:
                for case in suite_cases[suite]:
                    if track_id in {"equal-information-orchestration", "parameter-accuracy"}:
                        context = build_context_bundle(
                            str(case.get("query") or ""), skills, repo_root=repo_root, schema_context=schema_context
                        )
                        context["supplied"] = True
                    else:
                        context = {
                            "retriever": "none",
                            "document_ids": [],
                            "content": "",
                            "content_sha256": sha256_text(""),
                            "supplied": False,
                        }
                    prompt = render_v2_prompt(templates[track_id], track_id, case, skill_catalog, context, schema_text)
                    leakage = validate_rendered_prompt(prompt, track_id, case)
                    if leakage:
                        prompt_errors.append({"track": track_id, "suite": suite, "case_id": case["id"], "errors": leakage})
                    for participant_id in selected_participants:
                        if repeat >= repeat_counts[participant_id]:
                            continue
                        expected.append({"participant_id": participant_id, "benchmark_track": track_id, "suite": suite,
                                         "case_id": str(case["id"]), "repeat_index": repeat})
                        paths = _record_paths(participant_id, track_id, suite, str(case["id"]), repeat)
                        fingerprint = _execution_fingerprint(
                            str(protocol.get("protocol_id")), str(manifest.get("manifest_id")), selected_configs[participant_id],
                            track_id, suite, case, repeat, prompt, scorer_sha256
                        )
                        record_path = output_dir / paths["record"]
                        if args.resume and record_path.exists():
                            existing = json.loads(record_path.read_text(encoding="utf-8"))
                            if existing.get("execution_fingerprint") != fingerprint:
                                raise ValueError(f"resume fingerprint mismatch: {record_path}")
                            records.append(existing)
                            continue
                        if record_path.exists():
                            raise FileExistsError(f"record exists; use --resume or a new output directory: {record_path}")

                        start = time.time()
                        status, raw, error, normalized, execution = execute_case(
                            args, api, repo_root, selected_configs[participant_id], participant_id, track_id, suite, case, prompt,
                            repeat, known_skills, include_disabled, api_key, base_url, timeout_s, max_retries
                        )
                        scores = {
                            score_track: score_case_v2(suite, case, normalized, score_track, api)
                            for score_track in ("strict", "lenient")
                        }
                        if status != "scored":
                            scores = {score_track: {"pass": False, "checks": [{"name": status, "pass": False, "reason": error}]}
                                      for score_track in ("strict", "lenient")}
                        record = {
                            "schema_version": 2,
                            "timestamp": _fn(api, "iso_utc_now")(),
                            "benchmark_track": track_id,
                            "suite": suite,
                            "repeat_index": repeat,
                            "primary_repeat": repeat == PRIMARY_REPEAT_INDEX,
                            "participant_id": participant_id,
                            "participant_label": selected_configs[participant_id].get("label", participant_id),
                            "participant_kind": selected_configs[participant_id].get("kind"),
                            "status": status,
                            "error": sanitize_text(error or "") or None,
                            "elapsed_ms": int((time.time() - start) * 1000),
                            "case": case,
                            "context_bundle": {key: value for key, value in context.items() if key != "content"},
                            "prompt_sha256": sha256_text(prompt),
                            "normalized": normalized,
                            "score": scores["strict"],
                            "scores": scores,
                            "execution": execution,
                            "execution_fingerprint": fingerprint,
                            "prompt_path": paths["prompt"].as_posix(),
                            "raw_output_path": paths["raw"].as_posix(),
                            "record_path": paths["record"].as_posix(),
                        }
                        _fn(api, "write_raw")(output_dir / paths["prompt"], sanitize_text(prompt))
                        _fn(api, "write_raw")(output_dir / paths["raw"], sanitize_text(raw))
                        persisted_record = sanitize_value(record)
                        _fn(api, "write_record")(record_path, persisted_record)
                        records.append(persisted_record)

    coverage = build_coverage(records, expected, selected_participants)
    track_results = compute_track_results(
        records, track_suites, selected_participants, iterations, int(args.seed), coverage, api
    )
    stability = build_stability(records)
    efficiency = build_efficiency(records, selected_participants)
    git = git_metadata(repo_root)
    secret_findings = scan_artifacts_for_secrets(output_dir)
    publish_reasons = publication_gate_reasons(
        args, protocol, protocol_participants, selected_participants, selected_tracks, selected_suites,
        track_configs, repeat_counts, coverage, git, prompt_errors, secret_findings, manifest_audit, records
    )

    source_paths = [_path(repo_root, str(path)) for path in (manifest.get("case_sources") or {}).values()]
    input_paths = [config_path, participants_path, protocol_path, manifest_path, Path(__file__),
                   repo_root / "benchmark/tools/eval_benchmark.py", repo_root / "registry/skills.yaml",
                   input_schema_path, task_contracts_path, parameter_catalog_path,
                   repo_root / "registry/output_contracts.yaml", repo_root / "scripts/run_agent.sh",
                   repo_root / "scripts/route_query.sh", repo_root / "scripts/emit_parameter_claims.py",
                   *template_paths, *source_paths]
    completed_at = _fn(api, "iso_utc_now")()
    run_manifest = {
        "schema_version": 2,
        "benchmark_name": benchmark_config.get("benchmark_name"),
        "protocol_id": protocol.get("protocol_id"),
        "protocol_version": protocol.get("version"),
        "manifest_id": manifest.get("manifest_id"),
        "manifest_version": manifest.get("version"),
        "started_at": started_at,
        "completed_at": completed_at,
        "seed": int(args.seed),
        "participants": selected_participants,
        "participant_configs": sanitize_value(selected_configs),
        "tracks": selected_tracks,
        "suites": selected_suites,
        "repeat_counts": repeat_counts,
        "primary_repeat_index": PRIMARY_REPEAT_INDEX,
        "dry_run": bool(args.dry_run),
        "resume": bool(args.resume),
        "mock_run": bool(args.mock_response_dir),
        "bootstrap_iterations": iterations,
        "openai_base_url": sanitize_text(base_url),
        "openai_timeout_seconds": timeout_s,
        "openai_max_retries": max_retries,
        "manifest_audit": manifest_audit,
        "prompt_validation": {"passed": not prompt_errors, "errors": prompt_errors},
        "secret_scan": {"passed": not secret_findings, "findings": secret_findings},
        "case_order": {
            track: {suite: [str(case["id"]) for case in suite_cases[suite]] for suite in suites}
            for track, suites in track_suites.items()
        },
        "git": git,
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "input_sha256": _input_hashes(input_paths, repo_root),
        "output_dir": sanitize_text(str(output_dir)),
        "publication": {"requested": bool(args.publish), "eligible": not publish_reasons, "gate_reasons": publish_reasons},
    }
    summary = {
        "schema_version": 2,
        "run_manifest": run_manifest,
        "coverage": coverage,
        "tracks": track_results,
        "stability": stability,
        "efficiency": efficiency,
        "record_count": len(records),
    }
    stats = {track: result["stats"] for track, result in track_results.items()}

    (output_dir / "run_manifest.json").write_text(_fn(api, "dump_json")(run_manifest) + "\n", encoding="utf-8")
    (output_dir / "run_metadata.json").write_text(_fn(api, "dump_json")(run_manifest) + "\n", encoding="utf-8")
    (output_dir / "coverage.json").write_text(_fn(api, "dump_json")(coverage) + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(_fn(api, "dump_json")(summary) + "\n", encoding="utf-8")
    (output_dir / "stats.json").write_text(_fn(api, "dump_json")(stats) + "\n", encoding="utf-8")
    _write_summary_csv(output_dir / "summary.csv", track_results, selected_participants, selected_configs)

    table_parts = ["# Benchmark v2 Summary", "", f"- Coverage complete: `{coverage['complete']}`",
                   f"- Publication eligible: `{not publish_reasons}`", ""]
    for track_id, result in track_results.items():
        table_parts.extend([f"## Track: {track_id}", ""])
        rendered = _fn(api, "build_table_markdown")(
            selected_participants, selected_configs, result["score_tracks"], result["suites"], result["stats"]
        )
        table_parts.append(rendered.replace("# Comparative Benchmark Summary\n", "", 1).rstrip())
        table_parts.append("")
    table_parts.append(render_ci_table(track_results, selected_participants, selected_configs).rstrip())
    table_parts.append("")
    (output_dir / "table.md").write_text("\n".join(table_parts).rstrip() + "\n", encoding="utf-8")

    primary_records = [record for record in records if record.get("repeat_index") == PRIMARY_REPEAT_INDEX]
    examples = _fn(api, "choose_examples")(
        primary_records, selected_participants, int(defaults.get("example_limit_per_suite") or 2)
    )
    (output_dir / "examples.md").write_text(_fn(api, "render_examples_markdown")(examples, output_dir), encoding="utf-8")

    if args.publish:
        if publish_reasons:
            print("publish gate failed: " + ", ".join(publish_reasons), file=sys.stderr)
            return 3
        release_dir = publish_release(output_dir, repo_root, run_manifest, api)
        print(f"published immutable release: {release_dir}")

    print(f"benchmark v2 complete: {output_dir}")
    print(f"coverage: scored={coverage['status_counts']['scored']}/{coverage['expected_records']} complete={coverage['complete']}")
    if publish_reasons:
        print("publication gate reasons: " + ", ".join(publish_reasons))
    if not args.dry_run and (coverage["status_counts"]["infrastructure_error"] or coverage["status_counts"]["skipped"]):
        return 2
    return 0
