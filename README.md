# s2f-agent

`s2f-agent` is a sequence-to-function skill-routing agent for computational genomics and protein analysis. It turns open-ended research questions into deterministic, runnable plans across 24 enabled skills, while keeping DNA/genome and protein input, model, output, and fallback contracts explicitly separated.

[![CI](https://github.com/JiaqiLiZju/s2f-agent/actions/workflows/agent-ci.yml/badge.svg)](https://github.com/JiaqiLiZju/s2f-agent/actions/workflows/agent-ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Shell](https://img.shields.io/badge/shell-bash-lightgrey)

## Start Here

Fresh-machine bootstrap (recommended):

```bash
./scripts/bootstrap.sh
# or
make bootstrap
```

One-time persistent setup (keeps envs and model caches across sessions):

```bash
./scripts/bootstrap.sh \
  --persistent-root "${XDG_CACHE_HOME:-$HOME/.cache}/s2f-agent" \
  --prefetch-models

# load the generated runtime env in new shells
source "${XDG_CACHE_HOME:-$HOME/.cache}/s2f-agent/env.sh"
```

Equivalent Make target:

```bash
make bootstrap-persistent PREFETCH_MODELS=1
```

First run after bootstrap:

```bash
./scripts/link_skills.sh
./scripts/route_query.sh --query "Use \$dnabert2 to validate my train/dev/test CSV files"
./scripts/run_agent.sh --query "Need variant-effect guidance for chr12 REF/ALT"
./scripts/smoke_test.sh --skills-dir "${CODEX_HOME:-$HOME/.codex}/skills"
```

## Table of Contents

- [Functional Capabilities](#functional-capabilities)
- [Application Scenarios](#application-scenarios)
- [Skill Catalog](#skill-catalog)
- [Repository Structure](#repository-structure)
- [Routing and Agent Runtime](#routing-and-agent-runtime)
- [Installation and Deployment](#installation-and-deployment)
- [Validation and Troubleshooting](#validation-and-troubleshooting)
- [Contributing](#contributing)
- [Star History](#star-history)

## Functional Capabilities

| Capability | What it enables | Entry points |
| --- | --- | --- |
| Skill-grounded execution | Domain-specific guidance for genomics and protein model families and workflows | `skills/*/SKILL.md`, `skills-dev/*/SKILL.md`, [`docs/skills-reference.md`](./docs/skills-reference.md) |
| Deterministic routing | Ranked skill selection with `route` / `clarify` decision and confidence | `scripts/route_query.sh`, `registry/routing.yaml`, [`docs/routing.md`](./docs/routing.md) |
| Canonical input schema | Shared canonical input keys, aliases, and coordinate conventions | `registry/input_schema.yaml`, `scripts/validate_input_contracts.sh`, [`docs/input-schema.md`](./docs/input-schema.md) |
| Task-contract checks | Detects missing required inputs before execution guidance | `scripts/run_agent.sh`, `registry/task_contracts.yaml`, [`docs/contracts.md`](./docs/contracts.md) |
| Plan standardization | Emits normalized task plans with runnable steps and expected outputs | `scripts/run_agent.sh`, `registry/output_contracts.yaml`, `registry/recovery_policies.yaml`, [`docs/contracts.md`](./docs/contracts.md) |
| Plan execution | Dry-run or execute generated steps and verify expected outputs | `scripts/execute_plan.sh`, [`docs/scripts-reference.md`](./docs/scripts-reference.md) |
| Cross-skill playbook mapping | Maps user intent to reusable task playbooks | `playbooks/*/README.md`, [`docs/architecture.md`](./docs/architecture.md) |
| Reproducible environment setup | Standardized stack provisioning and one-step bootstrap | `scripts/provision_stack.sh`, `scripts/bootstrap.sh`, `Makefile`, [`docs/scripts-reference.md`](./docs/scripts-reference.md) |
| Validation and regression checks | Registry, metadata, migration, and routing consistency checks | `scripts/validate_*.sh`, `make validate-agent`, [`docs/evals.md`](./docs/evals.md) |

## Application Scenarios

| Scenario | Typical objective | Primary skills | Playbook | Docs |
| --- | --- | --- | --- | --- |
| Variant-effect analysis | Compare REF vs ALT impact or prioritize variants | `alphagenome-api`, `borzoi-workflows`, `gpn-models`, `evo2-inference` | [`variant-effect`](./playbooks/variant-effect/README.md) | [`contracts`](./docs/contracts.md), [`input-schema`](./docs/input-schema.md) |
| Embedding and representation | Produce sequence embeddings for downstream analyses | `dnabert2`, `nucleotide-transformer-v3`, `nucleotide-transformer`, `evo2-inference` | [`embedding`](./playbooks/embedding/README.md) | [`contracts`](./docs/contracts.md), [`input-schema`](./docs/input-schema.md) |
| Track prediction workflows | Run sequence-to-signal prediction with model-appropriate constraints | `alphagenome-api`, `nucleotide-transformer-v3`, `borzoi-workflows`, `segment-nt` | [`track-prediction`](./playbooks/track-prediction/README.md) | [`contracts`](./docs/contracts.md), [`input-schema`](./docs/input-schema.md) |
| Fine-tuning and training setup | Prepare schemas, training configs, and model-specific run paths | `dnabert2`, `nucleotide-transformer-v3`, `bpnet`, `basset-workflows` | [`fine-tuning`](./playbooks/fine-tuning/README.md) | [`contracts`](./docs/contracts.md), [`input-schema`](./docs/input-schema.md) |
| Protein representation | Generate per-protein or per-residue embeddings without entering the genomic embedding workflow | `protein-embedding` | [`protein-embedding`](./playbooks/protein-embedding/README.md) | [`contracts`](./docs/contracts.md) |
| Protein structure analysis | Retrieve, visualize, align, and compare public or user-supplied structures | `protein-structure-get`, `protein-structure-visualize`, `protein-structure-align` | [`protein-structure-lookup`](./playbooks/protein-structure-lookup/README.md) | [`skills`](./docs/skills-reference.md) |
| Protein sequence annotation | Combine domains, conservation, degrons, immunopresentation, IDR, localization, TM topology, and reports | protein annotation skills | [`protein-annotation-report`](./playbooks/protein-annotation-report/README.md) | [`contracts`](./docs/contracts.md) |
| Protein mutation analysis | Keep sequence, evolutionary, structure, stability, human-prior, and benchmark axes distinct | `protein-mutation-effect` and child/benchmark skills | [`protein-mutation-effect`](./playbooks/protein-mutation-effect/README.md) | [`contracts`](./docs/contracts.md) |
| Environment bring-up and migration | Build reproducible stacks and verify operational readiness | `skill-factory` plus stack-specific skills | [`environment-setup`](./playbooks/environment-setup/README.md) | [`scripts-reference`](./docs/scripts-reference.md), [`architecture`](./docs/architecture.md) |

## Skill Catalog

The repository currently includes **27** packaged skills: **24 enabled** by default and **3 disabled development skills**.

Status definition:

- `Stable`: canonical package in `skills/<skill-id>/`
- `Dev`: in-progress package in `skills-dev/<skill-id>/`
- default routing/install/validation only include `enabled=true` skills in `registry/skills.yaml` (use `--include-disabled` to opt in)

| Skill ID | Status | Path | Best for | Explicit invocation | Docs |
| --- | --- | --- | --- | --- | --- |
| `alphagenome-api` | Stable | `skills/alphagenome-api` | AlphaGenome setup, variant-effect, interval/track prediction, plotting, troubleshooting | `$alphagenome-api` | [`SKILL.md`](./skills/alphagenome-api/SKILL.md) · [`references/`](./skills/alphagenome-api/references/) |
| `basset-workflows` | Dev | `skills-dev/basset-workflows` | Legacy Basset Torch7 preprocessing, prediction, interpretation, SAD | `$basset-workflows` | [`SKILL.md`](./skills-dev/basset-workflows/SKILL.md) · [`references/`](./skills-dev/basset-workflows/references/) |
| `bpnet` | Dev | `skills-dev/bpnet` | BPNet preprocessing, train/predict/SHAP, motif integration | `$bpnet` | [`SKILL.md`](./skills-dev/bpnet/SKILL.md) · [`references/`](./skills-dev/bpnet/references/) |
| `borzoi-workflows` | Stable | `skills/borzoi-workflows` | Borzoi setup, tutorials, variant scoring, interpretation | `$borzoi-workflows` | [`SKILL.md`](./skills/borzoi-workflows/SKILL.md) · [`references/`](./skills/borzoi-workflows/references/) |
| `dnabert2` | Stable | `skills/dnabert2` | Embeddings, GUE evaluation, CSV validation, fine-tuning | `$dnabert2` | [`SKILL.md`](./skills/dnabert2/SKILL.md) · [`references/`](./skills/dnabert2/references/) |
| `evo2-inference` | Stable | `skills/evo2-inference` | Evo 2 setup, checkpoint choice, inference, deployment | `$evo2-inference` | [`SKILL.md`](./skills/evo2-inference/SKILL.md) · [`references/`](./skills/evo2-inference/references/) |
| `gpn-models` | Stable | `skills/gpn-models` | GPN-family framework selection and usage | `$gpn-models` | [`SKILL.md`](./skills/gpn-models/SKILL.md) · [`references/`](./skills/gpn-models/references/) |
| `nucleotide-transformer` | Dev | `skills-dev/nucleotide-transformer` | Classic NT v1/v2 JAX inference, tokenization, embeddings | `$nucleotide-transformer` | [`SKILL.md`](./skills-dev/nucleotide-transformer/SKILL.md) · [`references/`](./skills-dev/nucleotide-transformer/references/) |
| `nucleotide-transformer-v3` | Stable | `skills/nucleotide-transformer-v3` | NTv3 inference, species conditioning, mode-aware fine-tuning (`prep`/`train`) | `$nucleotide-transformer-v3` | [`SKILL.md`](./skills/nucleotide-transformer-v3/SKILL.md) · [`references/`](./skills/nucleotide-transformer-v3/references/) |
| `segment-nt` | Stable | `skills/segment-nt` | SegmentNT-family segmentation inference and scaling logic | `$segment-nt` | [`SKILL.md`](./skills/segment-nt/SKILL.md) · [`references/`](./skills/segment-nt/references/) |
| `skill-factory` | Stable | `skills/skill-factory` | Scaffold and validate consistent skill packages from specs | `$skill-factory` | [`SKILL.md`](./skills/skill-factory/SKILL.md) · [`references/`](./skills/skill-factory/references/) |

### Protein skills (enabled by default)

| Skill ID | Best for | Explicit invocation |
| --- | --- | --- |
| `protein-structure-get` | UniProt/PDB/AlphaFold DB retrieval and bounded ESMFold requests | `$protein-structure-get` |
| `protein-structure-visualize` | structure views, confidence, contacts, pockets, highlights | `$protein-structure-visualize` |
| `protein-structure-align` | RMSD/superposition, interfaces, Foldseek search and clustering | `$protein-structure-align` |
| `protein-domain-motif-annotation` | InterProScan6 and eggNOG domain/orthology annotation | `$protein-domain-motif-annotation` |
| `protein-conservation-assessment` | homolog search, MSA, conservation scoring and reports | `$protein-conservation-assessment` |
| `protein-degron-annotation` | ELM/DEGRONOPEDIA/QCDPred degron candidates | `$protein-degron-annotation` |
| `protein-immunopresentation-annotation` | MHC-I processing/binding candidate annotation | `$protein-immunopresentation-annotation` |
| `protein-annotation-report` | normalized evidence integration and reporting | `$protein-annotation-report` |
| `protein-idr-disorder-annotation` | IDR/disorder, linker, LLPS and aggregation predictions | `$protein-idr-disorder-annotation` |
| `protein-localization-signal-annotation` | DeepLoc, SignalP and TargetP normalization | `$protein-localization-signal-annotation` |
| `protein-tm-topology-annotation` | DeepTMHMM/TMHMM topology normalization | `$protein-tm-topology-annotation` |
| `protein-embedding` | ESM2/ESMC/ProtT5/Ankh/SaProt protein embeddings | `$protein-embedding` |
| `protein-mutation-effect` | canonical multi-model protein mutation orchestration | `$protein-mutation-effect` |
| `protein-sequence-mutation-effect` | sequence/evolutionary missense scoring | `$protein-sequence-mutation-effect` |
| `protein-structure-mutation-effect` | structure-aware mutation scoring and residue mapping | `$protein-structure-mutation-effect` |
| `protein-mutation-benchmark` | ProteinGym-compatible benchmarking and calibration | `$protein-mutation-benchmark` |

Reference notes used during skill development are in [`Readme/`](./Readme/).

## Repository Structure

```text
s2f-agent/
├── agent/                  # orchestrator identity, routing and safety policy
├── registry/               # skills index, tags, routing/task/output/recovery contracts
├── skills/                 # canonical stable skill packages
├── skills-dev/             # in-progress skill packages
├── playbooks/              # task-level runbooks plus step-by-step learning guides
├── evals/                  # routing + groundedness + task-success evaluation cases
├── docs/                   # architecture and design notes
├── scripts/                # setup, routing, orchestration, validation tooling
├── Readme/                 # source notes and upstream references
└── README.md
```

Architecture details: [`docs/architecture.md`](./docs/architecture.md).

## Routing and Agent Runtime

The `s2f` agent turns open-ended genomic and protein requests into deterministic, inspectable execution plans.

What it does on each query:

1. infer (or accept) task intent
2. rank skill candidates and emit `route` or `clarify`
3. validate required task inputs
4. generate a normalized `plan` contract
5. support dry-run or execution of plan steps

### Route vs Run vs Execute

| Command | Use when | Primary output |
| --- | --- | --- |
| `scripts/route_query.sh` | You only need routing confidence and skill ranking | `decision`, `confidence`, primary/secondary skills |
| `scripts/run_agent.sh` | You need full orchestration (routing + input checks + plan) | structured agent response with `plan` |
| `scripts/execute_plan.sh` | You want to dry-run or run generated `plan.runnable_steps` | execution summary + expected output verification |

### If You Only Run 3 Commands

```bash
./scripts/route_query.sh --query "Need variant-effect guidance for hg38 chr12 REF ALT" --format json
./scripts/run_agent.sh --task variant-effect --query 'Use $alphagenome-api variant-effect on hg38 chr12 REF A ALT G' --format json
./scripts/execute_plan.sh --task variant-effect --query 'Use $alphagenome-api variant-effect on hg38 chr12 REF A ALT G'
```

Protein example:

```bash
./scripts/run_agent.sh --task protein-embedding --query 'Use $protein-embedding on proteins.fa for per-residue ESM2 embeddings' --format json
./scripts/run_agent.sh --task protein-sequence-mutation-effect --query 'Use $protein-sequence-mutation-effect with WT FASTA proteins.fa and mutations.tsv' --format json
```

Note: use single quotes around queries containing `$skill` to avoid shell expansion.

### Happy-Path Example (Variant-Effect)

1. Route the request:
```bash
./scripts/route_query.sh --query "Need variant-effect guidance around chr12 with REF/ALT." --format text
```
Expected checkpoint: `decision=route` or `decision=clarify` with a focused clarify question.

2. Build a full plan:
```bash
./scripts/run_agent.sh --task variant-effect --query 'Use $alphagenome-api variant-effect on hg38 chr12 REF A ALT G' --format json
```
Expected checkpoint: `primary_skill=alphagenome-api`, `missing_inputs=[]`, non-null `plan`.

3. Validate plan execution path (dry-run):
```bash
./scripts/execute_plan.sh --task variant-effect --query 'Use $alphagenome-api variant-effect on hg38 chr12 REF A ALT G' --format text
```
Expected checkpoint: `dry_run=1`, `failed=0`, `verify_failed=0`.

### Agent Output Fields

| Field | Meaning | Why it matters |
| --- | --- | --- |
| `decision` | `route` or `clarify` | tells you whether execution can proceed immediately |
| `primary_skill` | selected lead skill | confirms routing target |
| `missing_inputs` | required inputs not found in query | drives clarify questions and assumption risk |
| `plan` | normalized execution contract | source of runnable steps and expected outputs |
| `clarify_question` | focused follow-up question | shortest path to unblock low-confidence routing |

### Link Map (Contracts vs Learning)

Contract-first references:

- [`playbooks/variant-effect/README.md`](./playbooks/variant-effect/README.md)
- [`playbooks/embedding/README.md`](./playbooks/embedding/README.md)
- [`playbooks/track-prediction/README.md`](./playbooks/track-prediction/README.md)
- [`playbooks/fine-tuning/README.md`](./playbooks/fine-tuning/README.md)
- [`playbooks/environment-setup/README.md`](./playbooks/environment-setup/README.md)
- [`registry/input_schema.yaml`](./registry/input_schema.yaml)

Learning in playbooks:

- [`playbooks/README.md`](./playbooks/README.md)
- [`playbooks/getting-started/README.md`](./playbooks/getting-started/README.md)
- [`playbooks/variant-effect/README.md`](./playbooks/variant-effect/README.md)
- [`playbooks/embedding/README.md`](./playbooks/embedding/README.md)
- [`playbooks/track-prediction/README.md`](./playbooks/track-prediction/README.md)
- [`playbooks/fine-tuning/README.md`](./playbooks/fine-tuning/README.md)
- [`playbooks/environment-setup/README.md`](./playbooks/environment-setup/README.md)
- [`playbooks/troubleshooting/README.md`](./playbooks/troubleshooting/README.md)

Open the local interactive console:

```bash
./scripts/agent_console.sh
```

## Installation and Deployment

This repository can be used in two layers:

- **Codex skills only**: install the packaged skill folders so Codex can route to them immediately.
- **Full s2f runtime**: also provision Python environments and model stacks for local execution.

For extended Codex/plugin notes, see [`docs/codex-install.md`](./docs/codex-install.md).

### Prerequisites

- Bash and Git.
- Node.js/npm only if installing with `npx skills`.
- Python 3.10+ for local runtime provisioning.
- Conda only for the `evo2-full` path.
- NVIDIA GPU + CUDA only for local Evo 2 GPU paths (`evo2-light` / `evo2-full`).

### 1. Recommended: install with `npx skills`

List the skills published by this repository:

```bash
npx --yes skills add JiaqiLiZju/s2f-agent --list -a codex --full-depth
```

Install the stable Codex skill set:

```bash
npx --yes skills add JiaqiLiZju/s2f-agent \
  -a codex -g -y --copy --full-depth \
  --skill alphagenome-api \
  --skill borzoi-workflows \
  --skill dnabert2 \
  --skill evo2-inference \
  --skill gpn-models \
  --skill nucleotide-transformer-v3 \
  --skill segment-nt \
  --skill skill-factory
```

Restart Codex after installing or updating skills.

### 2. Local checkout install

Use this path when you have cloned the repo and want deterministic local installation without `npx`.

The default Codex skills directory is:

```bash
${CODEX_HOME:-$HOME/.codex}/skills
```

Copy all enabled, registry-listed skills:

```bash
./scripts/link_skills.sh --copy
# or
make link-skills COPY_SKILLS=1
```

For development, symlink instead of copying so edits are picked up after restarting Codex:

```bash
./scripts/link_skills.sh --force
```

Useful variants:

```bash
./scripts/link_skills.sh --list
./scripts/link_skills.sh --skills-dir "$HOME/.codex/skills" --copy --force
./scripts/link_skills.sh --copy alphagenome-api borzoi-workflows dnabert2
./scripts/link_skills.sh --include-disabled
```

### 3. Provision software stacks

Installing skills gives Codex the workflow knowledge. Provisioning installs optional runnable model stacks for local execution.

One-step default install: skills + `alphagenome` + `gpn` + `nt-jax` + smoke test.

```bash
./scripts/bootstrap.sh
# or
make bootstrap
```

Provision individual stacks:

```bash
./scripts/provision_stack.sh alphagenome
./scripts/provision_stack.sh gpn
./scripts/provision_stack.sh nt-jax
./scripts/provision_stack.sh ntv3-hf
./scripts/provision_stack.sh borzoi
```

One-time persistent install (keeps deploy envs and caches in a stable location):

```bash
./scripts/bootstrap.sh \
  --persistent-root "${XDG_CACHE_HOME:-$HOME/.cache}/s2f-agent" \
  --prefetch-models
```

After first setup, load the generated env in new shells:

```bash
source "${XDG_CACHE_HOME:-$HOME/.cache}/s2f-agent/env.sh"
```

Optional one-step variants:

```bash
./scripts/bootstrap.sh --with-ntv3-hf
./scripts/bootstrap.sh --with-borzoi
./scripts/bootstrap.sh --with-evo2-light
./scripts/bootstrap.sh --with-evo2-full
```

Equivalent Make targets:

```bash
make bootstrap-ntv3-hf
make bootstrap-borzoi
make bootstrap-evo2-light
make bootstrap-evo2-full
make bootstrap-persistent
```

Prefetch model parameters separately (if environments are already prepared):

```bash
make prefetch-models
# or
./scripts/prefetch_models.sh --deploy-root "${XDG_CACHE_HOME:-$HOME/.cache}/s2f-agent/deploy"
```

One-click cleanup for configured environments and temporary files:

```bash
make clean-runtime
# or
./scripts/clean_runtime.sh --yes
```

Use dry-run first if you want to preview deletions:

```bash
./scripts/clean_runtime.sh --dry-run
```

### 3. Optional Evo 2 paths

Evo 2 light (requires hardware-specific torch install command before `flash-attn`):

```bash
export TORCH_INSTALL_CMD='$VENV_PYTHON -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cu128'
./scripts/provision_stack.sh evo2-light
```

Evo 2 full (active conda environment):

```bash
conda create -n evo2-full python=3.11 -y
conda activate evo2-full
./scripts/provision_stack.sh evo2-full
```

Hosted Evo 2 API path (recommended on macOS or without NVIDIA GPU):

```bash
export NVCF_RUN_KEY='your_run_key'
python skills/evo2-inference/scripts/run_hosted_api.py --num-tokens 8 --top-k 1
```

Full hosted workflow with output plots:

```bash
export NVCF_RUN_KEY='your_run_key'
python skills/evo2-inference/scripts/run_real_evo2_workflow.py --output-dir skills/evo2-inference/results
```

### 4. Optional hardware-specific JAX override

```bash
export JAX_INSTALL_CMD='$VENV_PYTHON -m pip install jax[cuda12]'
./scripts/provision_stack.sh nt-jax
```

## Validation and Troubleshooting

Baseline smoke checks:

```bash
./scripts/smoke_test.sh --skills-dir "${CODEX_HOME:-$HOME/.codex}/skills"
```

Registry and metadata checks:

```bash
./scripts/validate_codex_package.sh
./scripts/validate_registry.sh
./scripts/validate_registry_tracking.sh
./scripts/validate_skill_metadata.sh
./scripts/validate_migration_paths.sh
```

Routing checks and full validation bundle:

```bash
./scripts/validate_routing.sh
./scripts/validate_groundedness.sh
./scripts/validate_task_success.sh
make validate-agent
```

Optional Make shortcuts:

```bash
make validate-registry
make validate-registry-tracking
make validate-skill-metadata
make validate-migration-paths
make eval-routing
make eval-groundedness
make eval-task-success
make eval-benchmark
make test-eval-benchmark-mock
make smoke-lite
make route-query QUERY='Need variant-effect guidance' TASK='variant-effect'
make run-agent QUERY='Help me run AlphaGenome predict_variant with RNA output'
make execute-plan QUERY='Need track-prediction plan for human hg38 interval' TASK='track-prediction'
```

Comparative benchmark notes:

- `make eval-benchmark` runs `s2f-agent,gpt-4o,o3-mini` by default and requires `OPENAI_API_KEY`.
- Local-only benchmark smoke check: `python3 benchmark/tools/eval_benchmark.py --participants s2f-agent --dry-run`.
- Benchmark section root: `benchmark/` (tools/config/prompts/fixtures/runs/reports are centrally managed here).

CI workflow entry:

```bash
.github/workflows/agent-ci.yml
```

Extended smoke test with explicit environment imports:

```bash
./scripts/smoke_test.sh \
  --skills-dir "${CODEX_HOME:-$HOME/.codex}/skills" \
  --alphagenome-python /path/to/alphagenome/bin/python \
  --gpn-python /path/to/gpn/bin/python \
  --nt-python /path/to/nt-jax/bin/python \
  --ntv3-python /path/to/ntv3-hf/bin/python \
  --borzoi-python /path/to/borzoi/bin/python \
  --evo2-python /path/to/evo2-light/bin/python
```

When a workflow fails, start from the skill's `references/` folder and then check routing/task configuration under `registry/`.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for how to add skills, run validation, and submit pull requests.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=JiaqiLiZju/s2f-agent&type=Date)](https://star-history.com/#JiaqiLiZju/s2f-agent&Date)
