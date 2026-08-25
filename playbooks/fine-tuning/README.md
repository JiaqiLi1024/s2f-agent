# Fine-Tuning Playbook

## Purpose

Provide a contract-aligned orchestration pattern for fine-tuning requests.

## Use This When

- The user asks for training setup and command planning.
- The user needs dataset contract checks before training.
- The user wants mode-aware NTv3 prep vs full training execution.

## Required Inputs (Canonical Keys)

Required task-contract keys:

- `task-objective`
- `dataset-schema`
- `compute-constraints`

Optional context that improves execution quality:

- preferred model family
- expected evaluation metrics
- checkpoint initialization preference
- target output head (`bigwig` or `annotation`) for NTv3-style workflows

## Skill Selection Heuristics

1. `dnabert2` and `nucleotide-transformer-v3` are co-primary candidates for fine-tuning.
2. If the query explicitly mentions one skill/model path, route to that skill.
3. If the query is generic CSV fine-tuning and evidence is close, return `decision=clarify` and ask the user to choose `dnabert2` or `nucleotide-transformer-v3`.
4. `bpnet-skill` is preferred for BPNet 2.x profile-prediction training stacks.
5. `basset-workflows` remains legacy-only.

## Runbook (Minimal Reproducible Commands)

Text output:

```bash
bash scripts/run_agent.sh \
  --task fine-tuning \
  --query 'Use $dnabert2 for binary classification fine-tuning with CSV labels and compute budget' \
  --format text
```

JSON output:

```bash
bash scripts/run_agent.sh \
  --task fine-tuning \
  --query 'Use $nucleotide-transformer-v3 for fine-tuning prep with dataset schema sequence,label and CPU constraints' \
  --format json
```

Dry-run execution validation:

```bash
bash scripts/execute_plan.sh \
  --task fine-tuning \
  --query 'Use $nucleotide-transformer-v3 for full-train fine-tuning with dataset schema sequence,label and CPU constraints; require training_history.json and best_checkpoint.pt' \
  --format text
```

## NTv3 Dual-Mode (Prep / Train)

Execution entrypoint is under `case-study-playbooks/fine-tuning`.

Prep mode (planning artifacts only):

```bash
bash case-study-playbooks/fine-tuning/run_fine_tuning_case.sh \
  --skills ntv3 \
  --ntv3-mode prep \
  --data-dir case-study-playbooks/fine-tuning/data
```

Train mode (full training):

```bash
FINE_TUNING_NTV3_DEVICE=cpu \
bash case-study-playbooks/fine-tuning/run_fine_tuning_case.sh \
  --skills ntv3 \
  --ntv3-mode train \
  --data-dir case-study-playbooks/fine-tuning/data
```

## Learn (Step-by-step + checkpoints + common failures)

Step 1: build a fine-tuning plan.

```bash
bash scripts/run_agent.sh \
  --task fine-tuning \
  --query 'Use $nucleotide-transformer-v3 for full-train fine-tuning with dataset schema sequence,label and CPU constraints' \
  --format json
```

Expected checkpoint:

- `decision: route` or focused `clarify`
- `required_inputs` includes `task-objective`, `dataset-schema`, `compute-constraints`
- NTv3 full-train plan step includes `--ntv3-mode train`

Step 2: verify mode-specific expected outputs.

Prep acceptance:

- `train-command.sh`
- `eval-metrics.json`

Train acceptance:

- `eval-metrics.json`
- `training_history.json`
- `model_output/best_checkpoint.pt`

Step 3: validate dry-run execution path.

```bash
bash scripts/execute_plan.sh \
  --task fine-tuning \
  --query 'Use $nucleotide-transformer-v3 for fine-tuning prep with dataset schema sequence,label and CPU constraints' \
  --format text
```

Common failure signatures and quick fixes:

- `missing_inputs` includes `dataset-schema` -> state required columns and split assumptions.
- `missing_inputs` includes `compute-constraints` -> specify CPU/GPU budget and memory limits.
- `decision=clarify` for generic CSV request -> choose `dnabert2` or `nucleotide-transformer-v3` explicitly.
- NTv3 train on MPS -> switch to CPU (`FINE_TUNING_NTV3_DEVICE=cpu`); MPS is fail-fast in this flow.

## Clarify & Retry

1. Read `missing_inputs` for any missing required key.
2. Clarify `task-objective`, `dataset-schema`, and `compute-constraints` explicitly.
3. For NTv3, clarify `prep` vs `train` mode explicitly.
4. Re-run with concrete mode and schema details.

## Related Playbooks

- [Getting Started](../getting-started/README.md)
- [Troubleshooting](../troubleshooting/README.md)
