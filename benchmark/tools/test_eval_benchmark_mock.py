#!/usr/bin/env python3
"""Fixture-based tests for eval_benchmark.py."""

from __future__ import annotations

import importlib.util
import json
import argparse
import os
import unittest
from pathlib import Path
from unittest import mock


def load_module() -> object:
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "benchmark/tools/eval_benchmark.py"
    spec = importlib.util.spec_from_file_location("eval_benchmark", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_v2_module() -> object:
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "benchmark/tools/eval_benchmark_v2.py"
    spec = importlib.util.spec_from_file_location("eval_benchmark_v2", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvalBenchmarkMockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.fixtures = cls.repo_root / "benchmark/fixtures/mock_openai"
        cls.mod = load_module()
        cls.v2 = load_v2_module()
        cls.known_skills = {"dnabert2", "alphagenome-api", "nucleotide-transformer-v3"}

    def read_fixture(self, name: str) -> str:
        return (self.fixtures / name).read_text(encoding="utf-8")

    def test_valid_json_fixture_normalizes(self) -> None:
        raw = self.read_fixture("valid_response.json")
        normalized = self.mod.normalize_from_raw_text(raw, self.known_skills)
        self.assertEqual(normalized["decision"], "route")
        self.assertEqual(normalized["primary_skill"], "dnabert2")
        self.assertEqual(normalized["validation_errors"], [])

    def test_non_json_fixture_marks_parse_error(self) -> None:
        raw = self.read_fixture("non_json.txt")
        normalized = self.mod.normalize_from_raw_text(raw, self.known_skills)
        self.assertIsNone(normalized["decision"])
        self.assertTrue(normalized["validation_errors"])
        self.assertIn("raw_json_parse_error", normalized["validation_errors"][0])

    def test_missing_fields_fails_task_success_scoring(self) -> None:
        raw = self.read_fixture("missing_fields.json")
        normalized = self.mod.normalize_from_raw_text(raw, self.known_skills)
        case = {
            "id": "task_mock_001",
            "query": "Need embedding plan",
            "task": "embedding",
            "min_runnable_steps": 1,
            "min_expected_outputs": 1,
        }
        score = self.mod.score_task_success_case(case, normalized)
        self.assertFalse(score["pass"])
        by_name = {item["name"]: item for item in score["checks"]}
        self.assertFalse(by_name["plan_non_null"]["pass"])

    def test_unknown_skill_fails_groundedness_scoring(self) -> None:
        raw = self.read_fixture("unknown_skill.json")
        normalized = self.mod.normalize_from_raw_text(raw, self.known_skills)
        case = {
            "id": "grounded_mock_001",
            "query": "Need DNABERT2 embedding workflow",
            "task": "embedding",
            "expected_primary_skill": "dnabert2",
            "required_constraint_contains": "transformers",
            "forbidden_substring": "invented_cli_flag",
        }
        score = self.mod.score_groundedness_case(case, normalized)
        self.assertFalse(score["pass"])
        by_name = {item["name"]: item for item in score["checks"]}
        self.assertFalse(by_name["primary_skill"]["pass"])
        self.assertFalse(by_name["normalization_validation"]["pass"])

    def test_openai_retry_on_429_then_success(self) -> None:
        calls = []

        def fake_request(url, headers, payload, timeout_s):
            calls.append((url, payload.get("model"), payload.get("reasoning_effort")))
            if len(calls) == 1:
                return 429, "{\"error\":\"rate limit\"}"
            content = json.dumps({"decision": "route", "primary_skill": "dnabert2"})
            body = json.dumps({"choices": [{"message": {"content": content}}]})
            return 200, body

        participant = {
            "id": "o3-mini",
            "kind": "openai_chat",
            "model": "o3-mini",
            "reasoning_effort": "medium",
        }
        result = self.mod.call_openai_chat(
            participant=participant,
            prompt="test",
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            timeout_s=5,
            max_retries=1,
            request_fn=fake_request,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(len(calls), 2)

    def test_openai_retry_limit_is_max_retries_plus_first_attempt(self) -> None:
        calls = []

        def fake_request(url, headers, payload, timeout_s):
            calls.append(url)
            return 429, "{\"error\":\"rate limit\"}"

        participant = {
            "id": "gpt-4o",
            "kind": "openai_chat",
            "model": "gpt-4o",
        }
        result = self.mod.call_openai_chat(
            participant=participant,
            prompt="test",
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            timeout_s=5,
            max_retries=1,
            request_fn=fake_request,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(len(calls), 2)

    def test_openai_401_is_not_retried(self) -> None:
        calls = []

        def fake_request(url, headers, payload, timeout_s):
            calls.append(url)
            return 401, "unauthorized"

        result = self.mod.call_openai_chat(
            participant={"id": "mock", "kind": "openai_chat", "model": "mock"},
            prompt="test",
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            timeout_s=5,
            max_retries=2,
            request_fn=fake_request,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "openai_http_401")
        self.assertEqual(len(calls), 1)

    def test_openai_permanent_5xx_exhausts_retries(self) -> None:
        calls = []

        def fake_request(url, headers, payload, timeout_s):
            calls.append(url)
            return 503, "unavailable"

        with mock.patch.object(self.mod.time, "sleep"):
            result = self.mod.call_openai_chat(
                participant={"id": "mock", "kind": "openai_chat", "model": "mock"},
                prompt="test",
                api_key="test-key",
                base_url="https://api.openai.com/v1",
                timeout_s=5,
                max_retries=2,
                request_fn=fake_request,
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "openai_http_503")
        self.assertEqual(result["attempts"], 3)

    def test_o3_mini_payload_includes_reasoning_effort(self) -> None:
        participant = {
            "id": "o3-mini",
            "kind": "openai_chat",
            "model": "o3-mini",
            "reasoning_effort": "medium",
        }
        payload = self.mod.build_openai_payload(participant, prompt="hello")
        self.assertEqual(payload["model"], "o3-mini")
        self.assertEqual(payload["reasoning_effort"], "medium")
        self.assertIn("response_format", payload)

    def test_claude_compat_payloads_use_schema_and_omit_temperature(self) -> None:
        participants = self.mod.get_participant_map(
            self.mod.load_yaml(self.repo_root / "benchmark/config/participants.yaml")
        )
        for participant_id in ("claude-opus-5", "claude-sonnet-5"):
            with self.subTest(participant_id=participant_id):
                participant = participants[participant_id]
                payload = self.mod.build_openai_payload(participant, prompt="hello")
                self.assertEqual(payload["model"], participant_id)
                self.assertNotIn("temperature", payload)
                self.assertEqual(payload["response_format"]["type"], "json_schema")
                self.assertTrue(payload["response_format"]["json_schema"]["strict"])

    def test_openai_base_url_can_come_from_environment(self) -> None:
        args = argparse.Namespace(openai_base_url="")
        defaults = {"openai_base_url": "https://api.openai.com/v1"}
        with mock.patch.dict(os.environ, {"OPENAI_BASE_URL": "https://w.ciykj.cn/v1"}, clear=False):
            self.assertEqual(self.mod.resolve_openai_base_url(args, defaults), "https://w.ciykj.cn/v1")

    def test_openai_base_url_normalizes_relay_host_without_scheme_or_v1(self) -> None:
        args = argparse.Namespace(openai_base_url="www.a8pi.com")
        self.assertEqual(
            self.mod.resolve_openai_base_url(args, {"openai_base_url": ""}),
            "https://www.a8pi.com/v1",
        )

    def test_gpt5_responses_payload_includes_reasoning_and_json_schema(self) -> None:
        participant = {
            "id": "gpt-5.5",
            "kind": "openai_responses",
            "model": "gpt-5.5",
            "reasoning_effort": "medium",
            "verbosity": "low",
        }
        payload = self.mod.build_responses_payload(participant, prompt="hello")
        self.assertEqual(payload["model"], "gpt-5.5")
        self.assertEqual(payload["reasoning"]["effort"], "medium")
        self.assertEqual(payload["text"]["verbosity"], "low")
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertIn("schema", payload["text"]["format"])
        self.assertTrue(payload["text"]["format"]["strict"])
        schema = payload["text"]["format"]["schema"]
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]), set(schema["required"]))

    def test_gpt56_participant_is_in_additive_v2_protocol(self) -> None:
        participants = self.mod.get_participant_map(
            self.mod.load_yaml(self.repo_root / "benchmark/config/participants.yaml")
        )
        protocol = self.mod.load_yaml(self.repo_root / "benchmark/protocols/v2-main-gpt56.yaml")
        _, protocol_participants, order = self.v2.load_protocol(protocol, participants)
        self.assertIn("gpt-5.6", order)
        self.assertEqual(protocol_participants["gpt-5.6"]["kind"], "openai_responses")
        self.assertEqual(protocol_participants["gpt-5.6"]["model"], "gpt-5.6")
        self.assertEqual(protocol_participants["gpt-5.6"]["model_snapshot"], "unresolved")
        self.assertEqual(protocol_participants["gpt-5.6"]["reasoning_effort"], "medium")

    def test_gpt56_ttapi_participant_is_isolated_in_proxy_protocol(self) -> None:
        participants = self.mod.get_participant_map(
            self.mod.load_yaml(self.repo_root / "benchmark/config/participants.yaml")
        )
        protocol = self.mod.load_yaml(self.repo_root / "benchmark/protocols/v2-main-gpt56-ttapi.yaml")
        _, protocol_participants, order = self.v2.load_protocol(protocol, participants)
        self.assertEqual(order, ["s2f-agent", "gpt-5.6-ttapi-chat"])
        proxy = protocol_participants["gpt-5.6-ttapi-chat"]
        self.assertEqual(proxy["kind"], "openai_chat")
        self.assertEqual(proxy["model"], "gpt-5.6")
        self.assertEqual(proxy["provider"], "ttapi")
        self.assertTrue(proxy["proxy_compatibility"])
        self.assertEqual(proxy["model_snapshot"], "unresolved")

    def test_responses_api_extracts_output_text(self) -> None:
        calls = []

        def fake_request(url, headers, payload, timeout_s):
            calls.append((url, payload.get("model")))
            response = {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({"decision": "route", "primary_skill": "dnabert2"}),
                            }
                        ]
                    }
                ]
            }
            return 200, json.dumps(response)

        participant = {
            "id": "gpt-5",
            "kind": "openai_responses",
            "model": "gpt-5",
            "reasoning_effort": "medium",
            "verbosity": "low",
        }
        result = self.mod.call_openai_responses(
            participant=participant,
            prompt="test",
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            timeout_s=5,
            max_retries=1,
            request_fn=fake_request,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["attempts"], 1)
        self.assertIn("\"primary_skill\": \"dnabert2\"", result["raw_text"])

    def test_task_success_scores_selected_group_and_missing_inputs(self) -> None:
        normalized = {
            "decision": "route",
            "primary_skill": "alphagenome-api",
            "secondary_skills": [],
            "clarify_question": None,
            "constraints": [],
            "all_constraints": [],
            "missing_inputs": ["vcf-input"],
            "assumptions": ["selected-required-inputs-group:vcf-batch", "safe"],
            "selected_required_inputs_group": "vcf-batch",
            "plan_selected_skill": "alphagenome-api",
            "runnable_steps": ["python run_alphagenome_vcf_batch.py"],
            "expected_outputs": ["summary.tsv"],
            "validation_errors": [],
            "raw_response": "{}",
            "plan": {
                "task": "variant-effect",
                "selected_skill": "alphagenome-api",
                "assumptions": ["selected-required-inputs-group:vcf-batch", "safe"],
                "required_inputs": ["assembly", "vcf-input"],
                "missing_inputs": ["vcf-input"],
                "constraints": [],
                "runnable_steps": ["python run_alphagenome_vcf_batch.py"],
                "expected_outputs": ["summary.tsv"],
                "fallbacks": [],
                "retry_policy": "single-retry",
            },
        }
        case = {
            "id": "task_mock_002",
            "query": "missing VCF",
            "task": "variant-effect",
            "min_runnable_steps": 1,
            "min_expected_outputs": 1,
            "required_selected_skill": "alphagenome-api",
            "required_selected_inputs_group": "vcf-batch",
            "required_missing_input_contains": "vcf-input",
            "required_assumption_contains": "safe",
            "forbidden_step_contains": "forbidden-command",
        }
        score = self.mod.score_task_success_case(case, normalized, track="strict")
        self.assertTrue(score["pass"])

    def test_task_success_fails_forbidden_step(self) -> None:
        raw = self.read_fixture("valid_response.json")
        normalized = self.mod.normalize_from_raw_text(raw, self.known_skills)
        normalized["plan"] = {
            "task": "embedding",
            "selected_skill": "dnabert2",
            "assumptions": [],
            "required_inputs": [],
            "missing_inputs": [],
            "constraints": [],
            "runnable_steps": ["forbidden-command"],
            "expected_outputs": ["embedding.npz"],
            "fallbacks": [],
            "retry_policy": "single-retry",
        }
        case = {
            "id": "task_mock_003",
            "query": "Need embedding plan",
            "task": "embedding",
            "min_runnable_steps": 1,
            "min_expected_outputs": 1,
            "forbidden_step_contains": "forbidden-command",
        }
        score = self.mod.score_task_success_case(case, normalized, track="strict")
        self.assertFalse(score["pass"])

    def test_latest_report_case_counts_can_use_non_s2f_participant(self) -> None:
        run_metadata = {
            "output_dir": "/tmp/run",
            "generated_at": "2026-05-23T00:00:00Z",
            "suites": ["routing", "groundedness", "task_success"],
            "participants": ["gpt-5.5-ttapi-chat"],
            "seed": 7,
            "openai_base_url": "https://w.ciykj.cn/v1",
            "openai_timeout_seconds": 240,
            "openai_max_retries": 2,
        }
        metrics_by_track = {
            "strict": {
                "gpt-5.5-ttapi-chat": {
                    "suite_metrics": {
                        "routing": {"total": 23},
                        "groundedness": {"total": 8},
                        "task_success": {"total": 23},
                    },
                    "overall": {"total": 54},
                }
            }
        }
        report = self.mod.render_latest_report(run_metadata, metrics_by_track, {}, "# Table\n")
        self.assertIn("- routing: 23", report)
        self.assertIn("- groundedness: 8", report)
        self.assertIn("- task_success: 23", report)
        self.assertIn("- overall: 54", report)

    def test_v2_http_401_is_infrastructure_error(self) -> None:
        api = dict(vars(self.mod))
        api["call_openai_chat"] = lambda *args, **kwargs: {
            "ok": False,
            "error": "openai_http_401",
            "raw_text": "unauthorized",
            "attempts": 1,
        }
        args = argparse.Namespace(dry_run=False, mock_response_dir="")
        status, _, error, _, _ = self.v2.execute_case(
            args=args,
            api=api,
            repo_root=self.repo_root,
            participant={"kind": "openai_chat", "model": "mock-model"},
            participant_id="mock",
            track_id="task-blind-routing",
            suite="routing",
            case={"id": "route_mock", "query": "test"},
            prompt="prompt",
            repeat=0,
            known_skills=self.known_skills,
            include_disabled=False,
            api_key="test-key",
            base_url="https://example.invalid/v1",
            timeout_s=1,
            max_retries=0,
        )
        self.assertEqual(status, "infrastructure_error")
        self.assertEqual(error, "openai_http_401")

    def test_v2_http_200_bad_output_remains_scored_failure(self) -> None:
        api = dict(vars(self.mod))
        api["call_openai_chat"] = lambda *args, **kwargs: {
            "ok": False,
            "error": "openai_response_not_json:no_object_delimiters",
            "raw_text": "not json",
            "attempts": 1,
        }
        args = argparse.Namespace(dry_run=False, mock_response_dir="")
        status, _, _, normalized, _ = self.v2.execute_case(
            args=args,
            api=api,
            repo_root=self.repo_root,
            participant={"kind": "openai_chat", "model": "mock-model"},
            participant_id="mock",
            track_id="task-blind-routing",
            suite="routing",
            case={"id": "route_mock", "query": "test"},
            prompt="prompt",
            repeat=0,
            known_skills=self.known_skills,
            include_disabled=False,
            api_key="test-key",
            base_url="https://example.invalid/v1",
            timeout_s=1,
            max_retries=0,
        )
        self.assertEqual(status, "scored")
        self.assertTrue(normalized["validation_errors"])

    def test_v2_coverage_marks_incomplete_pair_invalid(self) -> None:
        expected = [
            {"participant_id": participant, "benchmark_track": "task-blind-routing", "suite": "routing",
             "case_id": "route_001", "repeat_index": 0}
            for participant in ("s2f-agent", "baseline")
        ]
        records = [
            {"participant_id": "s2f-agent", "benchmark_track": "task-blind-routing", "suite": "routing",
             "repeat_index": 0, "case": {"id": "route_001"}, "status": "scored"},
            {"participant_id": "baseline", "benchmark_track": "task-blind-routing", "suite": "routing",
             "repeat_index": 0, "case": {"id": "route_001"}, "status": "infrastructure_error"},
        ]
        coverage = self.v2.build_coverage(records, expected, ["s2f-agent", "baseline"])
        self.assertFalse(coverage["complete"])
        self.assertEqual(coverage["status_counts"]["infrastructure_error"], 1)
        self.assertTrue(all(not item["valid"] for item in coverage["comparisons"]))

    def test_v2_main_manifest_is_case_study_free_and_deduplicated(self) -> None:
        manifest = self.mod.load_yaml(self.repo_root / "benchmark/manifests/v2-main.yaml")
        skills = self.mod.load_enabled_skills(self.repo_root, include_disabled=False)
        known_skills = {skill["id"] for skill in skills}
        contracts = self.mod.load_yaml(self.repo_root / "registry/task_contracts.yaml")
        known_tasks = set((contracts.get("contracts") or {}).keys())
        known_tasks.update(task for skill in skills for task in skill.get("tasks") or [])
        cases, audit = self.v2.load_manifest_cases(
            manifest, self.repo_root, known_skills, known_tasks, vars(self.mod)
        )
        self.assertEqual(audit["case_count"], 40)
        self.assertTrue(audit["case_study_free"])
        self.assertEqual(audit["duplicate_queries"], 0)
        all_queries = [case["query"].lower() for suite_cases in cases.values() for case in suite_cases]
        self.assertFalse(any("case-study" in query or "case_study" in query for query in all_queries))

    def test_v2_regression_manifest_reports_retained_duplicates_and_case_studies(self) -> None:
        manifest = self.mod.load_yaml(self.repo_root / "benchmark/manifests/v2-regression.yaml")
        skills = self.mod.load_enabled_skills(self.repo_root, include_disabled=False)
        known_skills = {skill["id"] for skill in skills}
        contracts = self.mod.load_yaml(self.repo_root / "registry/task_contracts.yaml")
        known_tasks = set((contracts.get("contracts") or {}).keys())
        known_tasks.update(task for skill in skills for task in skill.get("tasks") or [])
        cases, audit = self.v2.load_manifest_cases(
            manifest, self.repo_root, known_skills, known_tasks, vars(self.mod)
        )
        coupled = sum(
            bool(case["benchmark_metadata"]["case_study_coupled"])
            for suite_cases in cases.values()
            for case in suite_cases
        )
        self.assertEqual(audit["case_count"], 54)
        self.assertEqual(audit["normalized_query_count"], 48)
        self.assertEqual(audit["duplicate_queries"], 6)
        self.assertEqual(coupled, 12)

    def test_v2_task_blind_prompt_does_not_expose_gold_task(self) -> None:
        template = (self.repo_root / "benchmark/prompts/task_blind.md").read_text(encoding="utf-8")
        case = {"id": "route_secret", "query": "Analyze this input", "task": "secret-gold-task"}
        prompt = self.v2.render_v2_prompt(
            template, "task-blind-routing", case, "- dnabert2", {"content": "{}"}, "{}"
        )
        self.assertNotIn("secret-gold-task", prompt)
        self.assertEqual(self.v2.validate_rendered_prompt(prompt, "task-blind-routing", case), [])

    def test_v2_allowed_clarify_can_pass_task_success(self) -> None:
        case = {
            "id": "task_mock_clarify",
            "required_missing_input_contains": "vcf-input",
            "benchmark_metadata": {"allowed_decisions": ["route", "clarify"]},
        }
        normalized = {
            "decision": "clarify",
            "clarify_question": "Which VCF file should I use?",
            "missing_inputs": ["vcf-input"],
            "validation_errors": [],
        }
        score = self.v2.score_case_v2("task_success", case, normalized, "strict", vars(self.mod))
        self.assertTrue(score["pass"])

    def test_v2_strict_routing_rejects_unexpected_secondary(self) -> None:
        case = {
            "id": "route_mock_secondary",
            "expected_decision": "route",
            "expected_primary_skill": "dnabert2",
            "expected_secondary_skills": [],
            "benchmark_metadata": {"allowed_decisions": ["route"]},
        }
        normalized = {
            "decision": "route",
            "primary_skill": "dnabert2",
            "secondary_skills": ["alphagenome-api"],
            "plan_selected_skill": None,
        }
        strict = self.v2.score_case_v2("routing", case, normalized, "strict", vars(self.mod))
        lenient = self.v2.score_case_v2("routing", case, normalized, "lenient", vars(self.mod))
        self.assertFalse(strict["pass"])
        self.assertTrue(lenient["pass"])
        self.assertEqual(strict["components"]["secondary"]["precision"], 0.0)

    def test_parameter_accuracy_binds_value_and_evidence_to_requested_claim(self) -> None:
        case = {
            "id": "parameter_mock_binding",
            "expected_decision": "route",
            "expected_primary_skill": "dnabert2",
            "parameter_name": "learning_rate",
            "expected_parameter_status": "documented",
            "required_parameter_contains": ["3e-5"],
            "required_evidence_contains": ["skills/dnabert2/SKILL.md"],
        }
        normalized = {
            "decision": "route",
            "primary_skill": "dnabert2",
            "clarify_question": None,
            "parameter_claims": [
                {"name": "learning_rate", "value": "1e-4", "status": "documented", "evidence": "skills/dnabert2/SKILL.md:38"},
                {"name": "other", "value": "3e-5", "status": "documented", "evidence": "skills/dnabert2/SKILL.md:38"},
            ],
            "validation_errors": [],
        }
        score = self.mod.score_parameter_accuracy_case(case, normalized)
        self.assertFalse(score["pass"])

    def test_v2_equal_context_strips_case_study_examples(self) -> None:
        skills = self.mod.load_enabled_skills(self.repo_root, include_disabled=False)
        schemas = {
            "input_schema": self.mod.load_yaml(self.repo_root / "registry/input_schema.yaml"),
            "task_contracts": self.mod.load_yaml(self.repo_root / "registry/task_contracts.yaml"),
        }
        bundle = self.v2.build_context_bundle(
            "Use alphagenome on a VCF", skills, repo_root=self.repo_root, schema_context=schemas
        )
        self.assertIn("skill:alphagenome-api:skill.yaml", bundle["document_ids"])
        self.assertNotIn("case-study-playbooks", bundle["content"])

    def test_v2_recursive_sanitizer_redacts_secrets_and_home_paths(self) -> None:
        value = {
            "header": "Authorization: Bearer sk-secretvalue123",
            "path": "/Users/alice/private/output.json",
        }
        sanitized = self.v2.sanitize_value(value)
        serialized = json.dumps(sanitized)
        self.assertNotIn("secretvalue", serialized)
        self.assertNotIn("/Users/alice", serialized)


if __name__ == "__main__":
    unittest.main(verbosity=2)
