# s2f Playbooks

This directory is the single entry point for both learning and execution guidance.

## Learning Path

1. [Getting Started](./getting-started/README.md)
2. [Variant-Effect](./variant-effect/README.md)
3. [Embedding](./embedding/README.md)
4. [Track-Prediction](./track-prediction/README.md)
5. [Fine-Tuning](./fine-tuning/README.md)
6. [Environment-Setup](./environment-setup/README.md)
7. [Troubleshooting](./troubleshooting/README.md)

## Protein Learning Path

1. [Protein Embedding](./protein-embedding/README.md)
2. [Structure Lookup](./protein-structure-lookup/README.md), [Visualization](./protein-structure-visualization/README.md), and [Alignment](./protein-structure-alignment/README.md)
3. [Domain/Motif](./protein-domain-motif-annotation/README.md) and [Conservation](./protein-conservation-assessment/README.md)
4. [IDR](./protein-idr-disorder-annotation/README.md), [Localization](./protein-localization-signal-annotation/README.md), and [TM Topology](./protein-tm-topology-annotation/README.md)
5. [Degrons](./protein-degron-annotation/README.md) and [Immunopresentation](./protein-immunopresentation-annotation/README.md)
6. [Mutation Effect](./protein-mutation-effect/README.md) and [Mutation Benchmark](./protein-mutation-benchmark/README.md)
7. [Integrated Protein Annotation Report](./protein-annotation-report/README.md)

## Prerequisites

- Repository cloned locally.
- Bash environment with required tools available.
- Skills linked for discovery:

```bash
./scripts/link_skills.sh
```

Environment variable precheck is enforced for `execute_plan.sh --run` when the routed skill defines env contracts in `skill.yaml`.
Current first-rollout contracts:

- `alphagenome-api`: `ALPHAGENOME_API_KEY`
- `nucleotide-transformer-v3`: `HF_TOKEN`
- `evo2-inference`: one-of `NVCF_RUN_KEY` or `EVO2_API_KEY`

## Expected Outcomes

After completing this playbook set, you should be able to:

- choose the right command (`route_query.sh`, `run_agent.sh`, `execute_plan.sh`)
- read and act on `decision`, `missing_inputs`, and `plan`
- run dry-run plan validation before execution-heavy workflows
- recover from low-confidence routing and missing-input clarify paths

## Command Safety Tip

Use single quotes for queries that contain `$skill` names so your shell does not expand them:

```bash
bash scripts/run_agent.sh --query 'Use $alphagenome-api for variant-effect'
```

## Task Playbooks

- [Variant-Effect Playbook](./variant-effect/README.md)
- [Embedding Playbook](./embedding/README.md)
- [Track-Prediction Playbook](./track-prediction/README.md)
- [Fine-Tuning Playbook](./fine-tuning/README.md)
- [Environment-Setup Playbook](./environment-setup/README.md)
- [Protein Embedding Playbook](./protein-embedding/README.md)
- [Protein Structure Lookup Playbook](./protein-structure-lookup/README.md)
- [Protein Structure Visualization Playbook](./protein-structure-visualization/README.md)
- [Protein Structure Alignment Playbook](./protein-structure-alignment/README.md)
- [Protein Mutation Effect Playbook](./protein-mutation-effect/README.md)
- [Protein Annotation Report Playbook](./protein-annotation-report/README.md)
