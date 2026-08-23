#!/usr/bin/env python3
"""Run, import, or plan structure-aware protein mutation-effect adapters."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import tarfile
from collections import Counter
from pathlib import Path

from validate_structure_mutations import (
    CANONICAL_AA, MAPPING_FIELDS, MUTATION_FIELDS, MUTATION_RE,
    parse_fasta, read_mutations, validate_inputs, write_tsv,
)

MODELS = ("saprot", "thermompnn", "proteinmpnn", "esm-if1")
MODEL_META = {
    "saprot": {
        "score_name": "masked_log_odds", "effect_axis": "structure_language_model_preference",
        "score_unit": "natural_log_odds", "higher_is": "more_mutant_preferred",
    },
    "thermompnn": {
        "score_name": "ddg_kcal_mol", "effect_axis": "thermodynamic_stability_change",
        "score_unit": "kcal/mol", "higher_is": "more_destabilizing",
    },
    "proteinmpnn": {
        "score_name": "conditional_log_odds", "effect_axis": "backbone_conditioned_sequence_preference",
        "score_unit": "natural_log_odds", "higher_is": "more_mutant_preferred",
    },
    "esm-if1": {
        "score_name": "conditional_log_likelihood_ratio", "effect_axis": "backbone_conditioned_sequence_preference",
        "score_unit": "natural_log_likelihood_ratio", "higher_is": "more_mutant_preferred",
    },
}
SCORE_FIELDS = [
    "protein_id", "variant_id", "mutation_group", "mutation", "chain",
    "canonical_position", "wt", "alt", "model_id", "model_version",
    "score_name", "effect_axis", "raw_score", "score_unit", "higher_is",
    "status", "error", "source_path",
]


def sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_key_values(values: list[str], label: str) -> dict[str, str]:
    output: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"{label} must use model=value syntax: {value}")
        key, item = value.split("=", 1)
        key = key.strip().lower()
        if key not in MODELS:
            raise ValueError(f"unsupported model in {label}: {key}")
        output[key] = item.strip()
    return output


def read_table(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines:
        raise ValueError(f"empty adapter output: {path}")
    delimiter = "\t" if "\t" in lines[0] else ","
    return [dict(row) for row in csv.DictReader(lines, delimiter=delimiter)]


def bash_command(parts: list[str]) -> str:
    rendered = [str(part) for part in parts]
    if rendered and re.match(r"^[A-Za-z]:[\\/]", rendered[0]):
        drive = rendered[0][0].lower()
        suffix = rendered[0][2:].replace("\\", "/").lstrip("/")
        rendered[0] = f"/mnt/{drive}/{suffix}"
    return shlex.join(rendered)


def sequence_only_mutations(fasta: Path, mutations_file: Path, chain: str) -> tuple[str, str, list[dict]]:
    protein_id, sequence = parse_fasta(fasta)
    rows = read_mutations(mutations_file, None, protein_id, chain, "sequence")
    normalized: list[dict] = []
    for index, source in enumerate(rows, start=1):
        mutation = (source.get("mutation") or "").strip().upper()
        match = MUTATION_RE.fullmatch(mutation)
        errors: list[str] = []
        wt, position, alt = "", 0, ""
        if match:
            wt, position, alt = match.group(1), int(match.group(2)), match.group(3)
        if not match or wt not in CANONICAL_AA or alt not in CANONICAL_AA or wt == alt:
            errors.append("invalid_substitution_syntax")
        if not (1 <= position <= len(sequence)):
            errors.append("canonical_position_out_of_range")
        elif wt and sequence[position - 1] != wt:
            errors.append("fasta_wt_mismatch")
        row_protein = (source.get("protein_id") or protein_id).strip()
        if row_protein != protein_id:
            errors.append("protein_id_mismatch")
        row_chain = (source.get("chain") or chain).strip()
        variant_id = (source.get("variant_id") or f"variant_{index}").strip()
        normalized.append({
            "protein_id": protein_id, "variant_id": variant_id,
            "mutation_group": (source.get("mutation_group") or variant_id).strip(),
            "mutation": mutation, "chain": row_chain, "numbering": "sequence",
            "canonical_position": position or "", "auth_seq_id": "", "insertion_code": "",
            "wt": wt, "alt": alt, "pdb_aa": "", "mean_bfactor": "",
            "validation_status": "valid" if not errors else "invalid",
            "error": ";".join(errors),
        })
    return protein_id, sequence, normalized


def base_score_row(mutation: dict, model: str, version: str, status: str,
                   error: str = "", source_path: str = "") -> dict:
    meta = MODEL_META[model]
    return {
        "protein_id": mutation["protein_id"], "variant_id": mutation["variant_id"],
        "mutation_group": mutation["mutation_group"], "mutation": mutation["mutation"],
        "chain": mutation["chain"], "canonical_position": mutation["canonical_position"],
        "wt": mutation["wt"], "alt": mutation["alt"], "model_id": model,
        "model_version": version, "score_name": meta["score_name"],
        "effect_axis": meta["effect_axis"], "raw_score": "",
        "score_unit": meta["score_unit"], "higher_is": meta["higher_is"],
        "status": status, "error": error, "source_path": source_path,
    }


def score_alias(row: dict) -> tuple[str, str]:
    for key in ("raw_score", "score", "mut_value", "ddG", "ddg", "log_odds", "llr"):
        value = row.get(key)
        if value not in {None, ""}:
            return key, str(value)
    return "", ""


def normalize_adapter_output(model: str, version: str, path: Path,
                             mutations: list[dict], completed_status: str) -> list[dict]:
    imported = read_table(path)
    by_key = {(row["variant_id"], row["mutation"]): row for row in mutations}
    by_mutation: dict[str, list[dict]] = {}
    for row in mutations:
        by_mutation.setdefault(row["mutation"], []).append(row)
    output: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for source in imported:
        mutation_name = (source.get("mutation") or source.get("mut_info") or "").strip().upper()
        variant_id = (source.get("variant_id") or "").strip()
        target = by_key.get((variant_id, mutation_name)) if variant_id else None
        if target is None and len(by_mutation.get(mutation_name, [])) == 1:
            target = by_mutation[mutation_name][0]
        if target is None:
            continue
        key = (target["variant_id"], target["mutation"])
        score_source_name, value = score_alias(source)
        row = base_score_row(target, model, version, completed_status, source_path=str(path.resolve()))
        if not value:
            row["status"] = "failed"
            row["error"] = "adapter_output_missing_score"
        else:
            try:
                numeric = float(value)
                if not (numeric == numeric and abs(numeric) != float("inf")):
                    raise ValueError
                row["raw_score"] = format(numeric, ".12g")
            except ValueError:
                row["status"] = "failed"
                row["error"] = f"adapter_score_not_finite:{value}"
        for field in ("score_name", "effect_axis", "score_unit", "higher_is"):
            if source.get(field):
                row[field] = source[field]
        if score_source_name and not source.get("score_name"):
            row["source_score_name"] = score_source_name
        if source.get("status") in {"failed", "unavailable", "invalid_input"}:
            row["status"] = source["status"]
            row["error"] = source.get("error") or row["error"]
            row["raw_score"] = ""
        output.append(row)
        seen.add(key)
    for mutation in mutations:
        key = (mutation["variant_id"], mutation["mutation"])
        if key not in seen:
            output.append(base_score_row(
                mutation, model, version, "unavailable",
                error="adapter_output_missing_mutation", source_path=str(path.resolve()),
            ))
    return output


def archive_and_cleanup(output_dir: Path, do_archive: bool, do_cleanup: bool) -> dict:
    result = {"archive_created": False, "archive_path": "", "cleaned": []}
    archive_path = output_dir / "archive" / "intermediates.tar.gz"
    children = [output_dir / "raw", output_dir / "intermediate", output_dir / "logs"]
    if do_archive:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "w:gz") as archive:
            for child in children:
                if child.exists():
                    archive.add(child, arcname=child.name, recursive=True)
        if not archive_path.is_file() or archive_path.stat().st_size == 0:
            raise RuntimeError("intermediate archive was not created")
        result.update({"archive_created": True, "archive_path": str(archive_path.resolve())})
    if do_cleanup:
        if not do_archive or not archive_path.is_file() or archive_path.stat().st_size == 0:
            raise ValueError("--cleanup-intermediates requires a successful --archive-intermediates in this run")
        root = output_dir.resolve()
        for child in children:
            if not child.exists():
                continue
            if child.is_symlink():
                raise ValueError(f"refusing to clean symlink: {child}")
            resolved = child.resolve()
            if resolved.parent != root or resolved == root:
                raise ValueError(f"refusing unsafe cleanup target: {resolved}")
            shutil.rmtree(resolved)
            result["cleaned"].append(str(resolved))
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasta", required=True, type=Path)
    parser.add_argument("--structure", type=Path, help="PDB, CIF, or mmCIF; absent/unreadable produces per-model unavailable rows")
    parser.add_argument("--mutations-file", required=True, type=Path)
    parser.add_argument("--models", required=True, help="Comma-separated: saprot,thermompnn,proteinmpnn,esm-if1")
    parser.add_argument("--mode", required=True, choices=("plan", "execute", "import"))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--chain", default="A")
    parser.add_argument("--numbering", choices=("sequence", "pdb-auth"), default="sequence")
    parser.add_argument("--adapter-command", action="append", default=[], metavar="MODEL=COMMAND")
    parser.add_argument("--import-file", action="append", default=[], metavar="MODEL=PATH")
    parser.add_argument("--model-version", action="append", default=[], metavar="MODEL=VERSION")
    parser.add_argument("--archive-intermediates", action="store_true")
    parser.add_argument("--cleanup-intermediates", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Return nonzero if any requested model row fails or is unavailable")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        models = [item.strip().lower() for item in args.models.split(",") if item.strip()]
        if not models or any(model not in MODELS for model in models):
            raise ValueError(f"--models must be drawn from: {','.join(MODELS)}")
        models = list(dict.fromkeys(models))
        commands = parse_key_values(args.adapter_command, "--adapter-command")
        imports = parse_key_values(args.import_file, "--import-file")
        versions = parse_key_values(args.model_version, "--model-version")
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("raw", "intermediate", "logs"):
        (output_dir / name).mkdir(exist_ok=True)
    structure_error = ""
    structure_available = bool(args.structure and args.structure.is_file())
    validation_summary: dict = {}
    try:
        if structure_available:
            validation_dir = output_dir / "intermediate" / "validation"
            validation_summary = validate_inputs(
                args.fasta, args.structure, args.chain, args.mutations_file,
                None, args.numbering, validation_dir,
            )
            normalized = read_table(validation_dir / "normalized_mutations.tsv")
            shutil.copy2(validation_dir / "normalized_mutations.tsv", output_dir / "normalized_mutations.tsv")
            shutil.copy2(validation_dir / "residue_mapping.tsv", output_dir / "residue_mapping.tsv")
            protein_id, sequence = parse_fasta(args.fasta)
        else:
            structure_error = "structure_not_provided_or_not_found"
            protein_id, sequence, normalized = sequence_only_mutations(args.fasta, args.mutations_file, args.chain)
            write_tsv(output_dir / "normalized_mutations.tsv", normalized, MUTATION_FIELDS)
            write_tsv(output_dir / "residue_mapping.tsv", [], MAPPING_FIELDS)
    except Exception as exc:
        structure_available = False
        structure_error = f"structure_validation_failed:{exc}"
        try:
            protein_id, sequence, normalized = sequence_only_mutations(args.fasta, args.mutations_file, args.chain)
            write_tsv(output_dir / "normalized_mutations.tsv", normalized, MUTATION_FIELDS)
            write_tsv(output_dir / "residue_mapping.tsv", [], MAPPING_FIELDS)
        except Exception as input_exc:
            print(json.dumps({"status": "error", "error": str(input_exc)}, indent=2))
            return 1

    audit_commands: list[str] = []
    scores: list[dict] = []
    for model in models:
        model_version = versions.get(model, "unrecorded")
        valid_mutations = [row for row in normalized if row["validation_status"] == "valid"]
        invalid_mutations = [row for row in normalized if row["validation_status"] != "valid"]
        for mutation in invalid_mutations:
            scores.append(base_score_row(mutation, model, model_version, "invalid_input", mutation["error"]))
        if not structure_available:
            for mutation in valid_mutations:
                scores.append(base_score_row(mutation, model, model_version, "unavailable", structure_error))
            continue
        if args.mode == "plan":
            for mutation in valid_mutations:
                scores.append(base_score_row(mutation, model, model_version, "planned", "adapter_not_executed"))
            command = commands.get(model)
            if command:
                audit_commands.append(command)
            continue
        if args.mode == "import":
            source_text = imports.get(model)
            if not source_text:
                for mutation in valid_mutations:
                    scores.append(base_score_row(mutation, model, model_version, "unavailable", "import_file_not_configured"))
                continue
            source = Path(source_text)
            if not source.is_file():
                for mutation in valid_mutations:
                    scores.append(base_score_row(mutation, model, model_version, "unavailable", f"import_file_not_found:{source}"))
                continue
            raw_dir = output_dir / "raw" / model
            raw_dir.mkdir(parents=True, exist_ok=True)
            copied = raw_dir / source.name
            if source.resolve() != copied.resolve():
                shutil.copy2(source, copied)
            scores.extend(normalize_adapter_output(model, model_version, copied, valid_mutations, "imported"))
            continue
        command_template = commands.get(model)
        if not command_template:
            for mutation in valid_mutations:
                scores.append(base_score_row(mutation, model, model_version, "unavailable", "adapter_command_not_configured"))
            continue
        raw_dir = output_dir / "raw" / model
        intermediate_dir = output_dir / "intermediate" / model
        raw_dir.mkdir(parents=True, exist_ok=True)
        intermediate_dir.mkdir(parents=True, exist_ok=True)
        adapter_output = raw_dir / "adapter_output.tsv"
        placeholders = {
            "fasta": str(args.fasta.resolve()), "structure": str(args.structure.resolve()),
            "chain": args.chain, "mutations": str((output_dir / "normalized_mutations.tsv").resolve()),
            "output": str(adapter_output.resolve()), "raw_dir": str(raw_dir.resolve()),
            "intermediate_dir": str(intermediate_dir.resolve()),
        }
        try:
            command = [token.format(**placeholders) for token in shlex.split(command_template)]
        except (KeyError, ValueError) as exc:
            for mutation in valid_mutations:
                scores.append(base_score_row(mutation, model, model_version, "failed", f"invalid_adapter_template:{exc}"))
            continue
        audit_commands.append(bash_command(command))
        try:
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
            (output_dir / "logs" / f"{model}.stdout.log").write_text(completed.stdout, encoding="utf-8")
            (output_dir / "logs" / f"{model}.stderr.log").write_text(completed.stderr, encoding="utf-8")
        except FileNotFoundError as exc:
            completed = None
            failure = f"adapter_executable_not_found:{exc}"
        else:
            failure = f"adapter_exit_{completed.returncode}" if completed.returncode else ""
        if failure or not adapter_output.is_file():
            if not failure:
                failure = "adapter_did_not_write_output"
            for mutation in valid_mutations:
                scores.append(base_score_row(mutation, model, model_version, "failed", failure))
        else:
            try:
                scores.extend(normalize_adapter_output(model, model_version, adapter_output, valid_mutations, "completed"))
            except Exception as exc:
                for mutation in valid_mutations:
                    scores.append(base_score_row(mutation, model, model_version, "failed", f"adapter_output_error:{exc}"))

    commands_path = output_dir / "commands.sh"
    with commands_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("#!/usr/bin/env bash\nset -euo pipefail\n" + "\n".join(audit_commands) + ("\n" if audit_commands else ""))
    scores_path = output_dir / "structure_mutation_scores.tsv"
    write_tsv(scores_path, scores, SCORE_FIELDS)
    manifest = {
        "schema_version": 1, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": args.mode, "protein_id": protein_id, "sequence_length": len(sequence),
        "models": models, "structure_available": structure_available,
        "structure_error": structure_error, "chain": args.chain, "numbering": args.numbering,
        "inputs": {
            "fasta": {"path": str(args.fasta.resolve()), "sha256": sha256(args.fasta)},
            "structure": {"path": str(args.structure.resolve()) if args.structure else "", "sha256": sha256(args.structure)},
            "mutations_file": {"path": str(args.mutations_file.resolve()), "sha256": sha256(args.mutations_file)},
        },
        "model_versions": versions, "adapter_commands_configured": sorted(commands),
        "import_files_configured": imports, "validation": validation_summary,
        "archive": {},
    }
    archive_result: dict = {}
    try:
        archive_result = archive_and_cleanup(output_dir, args.archive_intermediates, args.cleanup_intermediates)
    except Exception as exc:
        manifest["archive"] = {"status": "failed", "error": str(exc)}
        (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    manifest["archive"] = archive_result
    counts = Counter(row["status"] for row in scores)
    if args.mode == "plan" and counts.get("planned"):
        overall = "planned"
    elif counts.get("failed") or counts.get("invalid_input") or counts.get("unavailable"):
        overall = "partial" if counts.get("completed") or counts.get("imported") else "unavailable"
    else:
        overall = "completed"
    summary = {
        "status": overall, "mode": args.mode, "protein_id": protein_id,
        "requested_models": models, "mutation_count": len(normalized),
        "score_row_count": len(scores), "status_counts": dict(sorted(counts.items())),
        "structure_available": structure_available, "structure_error": structure_error,
        "executed_adapters": [model for model in models if any(row["model_id"] == model and row["status"] == "completed" for row in scores)],
        "heavy_model_execution_verified": False,
        "heavy_model_verification_note": "The wrapper verifies adapter exit and output schema, not the identity of an external model process.",
        "artifacts": {
            "normalized_mutations_tsv": str((output_dir / "normalized_mutations.tsv").resolve()),
            "residue_mapping_tsv": str((output_dir / "residue_mapping.tsv").resolve()),
            "scores_tsv": str(scores_path.resolve()), "commands_sh": str(commands_path.resolve()),
            "manifest_json": str((output_dir / "manifest.json").resolve()),
            "run_summary_json": str((output_dir / "run_summary.json").resolve()),
        },
        "archive": archive_result,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and any(row["status"] in {"failed", "unavailable", "invalid_input"} for row in scores):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
