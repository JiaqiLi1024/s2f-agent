# Evals and Validation Reference

## Overview

The project has two distinct quality-check layers:

- **Structural validation** — scripts that check registry consistency, file existence, and metadata correctness. These are fast and do not invoke the agent.
- **Behavioral evals** — scripts that invoke the live router or agent against curated YAML cases and assert expected outputs. These catch routing drift and groundedness regressions.

## Eval Suites

| Suite | Case file | What it tests | Driving script |
|---|---|---|---|
| Routing | `evals/routing/cases.yaml` | `decision`, `primary_skill`, `confidence` per query | `scripts/validate_routing.sh` |
| Groundedness | `evals/groundedness/cases.yaml` | No fabricated symbols or forbidden substrings in agent output | `scripts/validate_groundedness.sh` |
| Task success | `evals/task_success/cases.yaml` | Plan has minimum `runnable_steps` and `expected_outputs` counts | `scripts/validate_task_success.sh` |

## Comparative Benchmark

The benchmark layer adds quantitative, paper-ready aggregation on top of the same curated eval cases.
It does not replace the three suite validators; it reuses their scoring semantics.

### What it runs

- Case sources: `evals/routing/cases.yaml`, `evals/groundedness/cases.yaml`, `evals/task_success/cases.yaml`
- Main participants: `s2f-agent`, `gpt-4o`, `o3-mini`, `gpt-5`, `gpt-5.5`, `gpt-5.6`
- Controlled ablation (o3-mini only): `direct`, `catalog-only`, `catalog+contracts`
- Score tracks: strict JSON/schema scoring for the main table and lenient deterministic normalization for supplementary fairness analysis.
- ttapi compatibility participant: `gpt-5.5-ttapi-chat` uses the `gpt-5.5` model through Chat Completions JSON mode for proxies where Responses API or older model slugs are temporarily unavailable.
- `gpt-5.6-ttapi-chat` uses the same isolated compatibility path and the dedicated `benchmark/protocols/v2-main-gpt56-ttapi.yaml` protocol; it is not interchangeable with the first-party Responses API participant.

Benchmark assets are centrally managed under `benchmark/`:

- `benchmark/config/benchmark.yaml`
- `benchmark/config/participants.yaml`
- `benchmark/prompts/*.md`
- `benchmark/fixtures/mock_openai/`
- `benchmark/runs/`
- `benchmark/reports/manuscript/`

The versioned v2 extension protocol `benchmark/protocols/v2-main-gpt56.yaml` adds `gpt-5.6` without rewriting the frozen `v2-main.yaml` participant set. It uses the Responses API adapter with `reasoning_effort=medium`, `verbosity=low`, and three repeats; its model snapshot remains unresolved until provider identity is probed.

### Run benchmark

```bash
python3 benchmark/tools/eval_benchmark.py
# or
make eval-benchmark
```

Local-only dry run (no OpenAI calls):

```bash
python3 benchmark/tools/eval_benchmark.py --participants s2f-agent --dry-run
```

ttapi GPT-5.5 proxy run:

```bash
OPENAI_BASE_URL=https://www.a8pi.com/v1 \
python3 benchmark/tools/eval_benchmark.py \
  --participants gpt-5.5-ttapi-chat \
  --openai-timeout 180 \
  --openai-max-retries 2 \
  --no-ablations
```

GPT-5.6 v2 dry-run (no API call):

```bash
python3 benchmark/tools/eval_benchmark.py \
  --protocol benchmark/protocols/v2-main-gpt56.yaml \
  --manifest benchmark/manifests/v2-main.yaml \
  --participants gpt-5.6,s2f-agent \
  --dry-run
```

If OpenAI participants are enabled and `OPENAI_API_KEY` is not set, the script exits with a clear error.

Run fixture-based mock tests for benchmark parser/scorer/retry logic:

```bash
make test-eval-benchmark-mock
```

### Key CLI flags

```bash
python3 benchmark/tools/eval_benchmark.py \
  --participants s2f-agent,gpt-4o,o3-mini \
  --suites routing,groundedness,task_success \
  --output-dir benchmark/runs/manual_001 \
  --seed 7 \
  --openai-base-url https://api.openai.com/v1
```

- `--participants`: comma-separated participant IDs from `participants.yaml`
- `--suites`: comma-separated suite IDs
- `--output-dir`: explicit run directory (otherwise timestamped dir under `benchmark/runs/`)
- `--seed`: seed for bootstrap/statistics reproducibility
- `--dry-run`: skip OpenAI calls and mark OpenAI participants as skipped
- `--openai-base-url`: OpenAI-compatible endpoint override
- `OPENAI_BASE_URL` / `OPENAI_API_BASE`: environment-variable endpoint override, useful for ttapi-compatible runs such as `https://w.ciykj.cn/v1`

### Output artifacts

Each run writes a timestamped directory containing:

- `run_metadata.json`
- `summary.json`
- `summary.csv`
- `table.md`
- `stats.json`
- `examples.md`
- `raw_outputs/{participant}/{suite}/{case_id}.txt`
- `case_records/{participant}/{suite}/{case_id}.json`

### Metric definitions

- Suite micro: pass rate across all scored cases in that suite
- Suite macro: average pass rate across `task` groups; cases without task use `general`
- Overall micro: pass rate across all scored cases from all selected suites
- Overall macro: average of the selected suites' macro metrics

### Statistical reporting

- Micro comparisons use paired exact McNemar tests (`s2f-agent` vs each main baseline), with delta and p-value.
- Micro deltas include bootstrap 95% confidence intervals.
- Macro reports include point estimates plus bootstrap 95% confidence intervals.

### Manuscript usage guidance

Use benchmark-generated `table.md` / `summary.csv` as the source of manuscript numbers.
Do not hand-edit quantitative values in the manuscript text.

## Routing Eval

**Case file:** `evals/routing/cases.yaml`

Each case specifies a query and the expected routing outcome.

```yaml
- id: route_001
  query: "Use $dnabert2 to validate my train/dev/test CSV"
  expected_primary_skill: dnabert2
  expected_secondary_skills: []
  task: fine-tuning

- id: route_006
  query: "Please help me run legacy Torch7 Basset prediction."
  expected_decision: clarify
  expected_clarify_contains: "disabled"
```

Fields:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique case identifier |
| `query` | yes | Free-text query passed to the router |
| `expected_primary_skill` | for route cases | Expected `primary_skill` in router output |
| `expected_secondary_skills` | optional | Expected secondary candidates |
| `task` | optional | Task hint passed with `--task` |
| `expected_decision` | for clarify cases | `route` or `clarify` |
| `expected_clarify_contains` | for clarify cases | Substring expected in `clarify_question` |

Cases whose expected clarification contains `disabled` require disabled
registry entries to be visible. The default validator skips these cases and
reports the skip; use `bash scripts/validate_routing.sh --include-disabled`
to evaluate the complete 20-skill routing corpus.

Run:

```bash
bash scripts/validate_routing.sh
# or
make eval-routing
```

Key output lines:
- `PASS [route_001]` / `FAIL [route_001]`
- Final summary: `N passed, M failed`
- Exit code 0 = all passed, non-zero = at least one failure

## Groundedness Eval

**Case file:** `evals/groundedness/cases.yaml`

Each case specifies a query, the expected primary skill, a required substring that must appear in agent output (confirming grounded content was used), and a forbidden substring that must not appear (catching fabricated symbols).

```yaml
- id: grounded_001
  query: "Help me run AlphaGenome predict_variant on hg38 with REF ALT."
  task: variant-effect
  expected_primary_skill: alphagenome-api
  required_constraint_contains: grounded
  forbidden_substring: unsupported_api_symbol
```

Fields:

| Field | Meaning |
|---|---|
| `required_constraint_contains` | Substring that must appear somewhere in the agent response |
| `forbidden_substring` | Substring that must NOT appear (indicates fabricated content) |

Run:

```bash
bash scripts/validate_groundedness.sh
# or
make eval-groundedness
```

## Task Success Eval

**Case file:** `evals/task_success/cases.yaml`

Each case runs the agent and asserts the normalized plan meets minimum quality thresholds.
For NTv3 case-study flows, keep assertions process-oriented:

- assert command fragments and artifact types (for example `--ntv3-mode prep|train`, `training_history.json`, `best_checkpoint.pt`)
- assert workflow-state indicators when available (for example prep `status=not_executed` vs train `status=completed`)
- do not assert fixed tensor shape values from one execution run

```yaml
- id: task_success_001
  query: "Need variant-effect guidance for hg38 chr12 REF ALT."
  task: variant-effect
  min_runnable_steps: 1
  min_expected_outputs: 1

- id: task_success_005
  query: "...ntv3 track prediction chr19 6700000-6732768..."
  task: track-prediction
  min_runnable_steps: 1
  min_expected_outputs: 3
  required_step_contains: "conda run -n ntv3 python skills/nucleotide-transformer-v3/scripts/run_track_prediction.py"
  required_expected_output_contains: "output/ntv3_results"

- id: task_success_011
  query: "...ntv3 track prediction batch for case-study/track_prediction/bed/Test.interval.bed..."
  task: track-prediction
  min_runnable_steps: 1
  min_expected_outputs: 4
  required_step_contains: "run_track_prediction_bed_batch.py"
  required_expected_output_contains: "ntv3_bed_batch_summary.json"

- id: task_success_013
  query: "...nucleotide-transformer-v3 full-train fine-tuning with sequence,label CSV and CPU constraints..."
  task: fine-tuning
  min_runnable_steps: 1
  min_expected_outputs: 4
  required_step_contains: "--ntv3-mode train"
  required_expected_output_contains: "training_history.json"

- id: task_success_015
  query: "...nucleotide-transformer-v3 fine-tuning prep case-study in case-study-playbooks/fine-tuning..."
  task: fine-tuning
  min_runnable_steps: 1
  min_expected_outputs: 3
  required_step_contains: "--ntv3-mode prep"
  required_expected_output_contains: "eval-metrics.json"

- id: task_success_016
  query: "...borzoi-workflows track prediction on hg38 chr19 with output head..."
  task: track-prediction
  min_runnable_steps: 1
  min_expected_outputs: 2
  required_selected_skill: "borzoi-workflows"
  required_step_contains: "borzoi-workflows-track-prediction-workflow"
```

Fields:

| Field | Meaning |
|---|---|
| `min_runnable_steps` | Minimum number of steps in `plan.runnable_steps` |
| `min_expected_outputs` | Minimum number of entries in `plan.expected_outputs` |
| `required_step_contains` | Substring that must appear in at least one runnable step |
| `required_expected_output_contains` | Substring that must appear in at least one expected output |
| `required_selected_skill` | If set, `plan.selected_skill` must exactly match this skill id |

Run:

```bash
bash scripts/validate_task_success.sh
# or
make eval-task-success
```

Manual NTv3 flow review (recommended in addition to scripted evals):

1. Run prep mode and train mode under `case-study-playbooks/fine-tuning`:
   - `bash case-study-playbooks/fine-tuning/run_fine_tuning_case.sh --skills ntv3 --ntv3-mode prep --data-dir case-study-playbooks/fine-tuning/data`
   - `FINE_TUNING_NTV3_DEVICE=cpu bash case-study-playbooks/fine-tuning/run_fine_tuning_case.sh --skills ntv3 --ntv3-mode train --data-dir case-study-playbooks/fine-tuning/data`
2. Verify artifacts exist under `case-study-playbooks/fine-tuning/<run_id>/ntv3_results`.
3. Inspect JSON fields for process state:
   - prep mode: `status=not_executed`, `planned_train_command`
   - train mode: `status=completed`, `training_history`, `checkpoint_path`
4. Treat JSON field presence and state as pass criteria; do not gate on fixed shape values.

## Structural Validation Scripts

These do not invoke the agent. They check registry and metadata consistency.

| Script | Make target | What it checks |
|---|---|---|
| `validate_registry.sh` | `validate-registry` | Each skill path in `registry/skills.yaml` exists with required files |
| `validate_registry_tracking.sh` | `validate-registry-tracking` | Enabled skills are tracked by git and not `.gitignore`d |
| `validate_skill_metadata.sh` | `validate-skill-metadata` | `skill.yaml` completeness and consistency with registry entries |
| `validate_input_contracts.sh` | `validate-input-contracts` | Task contract keys exist in `input_schema.yaml` and skill metadata |
| `validate_migration_paths.sh` | `validate-migration-paths` | Migrated skills are under `skills/` with no legacy root-level paths |

## Running All Checks

The composite target runs registry + skill metadata + routing validations:

```bash
make validate-agent
```

This is the recommended pre-commit check. Exit code 0 means all structural and routing validations passed.

## How to Add a Case

### Routing case

1. Add an entry to `evals/routing/cases.yaml` following the schema above.
2. Run `bash scripts/validate_routing.sh` — the new case will be evaluated immediately.
3. Confirm the case passes (`PASS [your_id]` in output).

### Groundedness case

1. Add an entry to `evals/groundedness/cases.yaml`.
2. Choose a `required_constraint_contains` value that appears in a grounded response from the target skill.
3. Choose a `forbidden_substring` that would only appear if the agent fabricated content.
4. Run `bash scripts/validate_groundedness.sh` and confirm pass.

### Task success case

1. Add an entry to `evals/task_success/cases.yaml`.
2. Set `min_runnable_steps` and `min_expected_outputs` based on what the output contract defines for that task (see `registry/output_contracts.yaml`).
3. Optionally add `required_step_contains` for a specific command that must appear.
4. Run `bash scripts/validate_task_success.sh` and confirm pass.

## See Also

- [Scripts Reference](./scripts-reference.md) — full flag documentation for all validation scripts
- [Contracts Reference](./contracts.md) — output contract definitions that drive task success thresholds
- `agent/SAFETY.md` — groundedness policy that the groundedness eval enforces
