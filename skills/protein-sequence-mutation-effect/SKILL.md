---
name: protein-sequence-mutation-effect
description: Validate and score protein amino-acid substitutions with sequence and evolutionary evidence from ESM-1v, ESMC 300M, MSA profiles, PoET, and AlphaMissense precomputed predictions. Use for zero-shot protein mutation-effect scoring, missense prioritization, ProteinGym-style mutation tables, multi-substitution groups, model setup or score import, and reproducible sequence-model runs; do not use for genomic-coordinate consequence annotation or clinical diagnosis.
---

# Protein sequence mutation effect

Turn a FASTA plus protein substitutions into validated, auditable scores. Keep model-native axes separate; never average pathogenicity, evolutionary preference, and language-model likelihood without an explicit calibration method.

## Workflow

1. Read [input-output-contract.md](references/input-output-contract.md). Normalize `A42V`, `p.Ala42Val`, and groups such as `A42V:G55D`; verify 1-based coordinates and WT residues before downloading a model.
2. Read [model-selection.md](references/model-selection.md). Select the smallest evidence set that answers the question.
3. Read [setup-downloads-and-licenses.md](references/setup-downloads-and-licenses.md) before installing or downloading. Use separate pinned environments for ESM-1v, ESMC, and PoET unless compatibility has been tested.
4. Run `scripts/validate_protein_mutations.py` first. Stop on invalid IDs, alphabet, coordinates, duplicate positions, or WT mismatches.
5. Run `scripts/run_sequence_mutation_effect.py` in `plan`, `execute`, or `import` mode. Missing optional files or unavailable backends must produce a status row, never an invented score.
6. Inspect `scores.tsv`, `run_summary.json`, `manifest.json`, `commands.sh`, and `logs/run.log`. Preserve score names and `higher_is` direction.
7. Archive intermediates for an important run. Cleanup is restricted to the run's `raw/` and `intermediate/` directories and requires `--archive-intermediates --cleanup-intermediates`.

## Quick start

Validate and score an aligned MSA locally:

```bash
python scripts/validate_protein_mutations.py \
  --fasta input.fasta --mutations-file mutations.tsv \
  --output normalized_mutations.tsv

python scripts/run_sequence_mutation_effect.py \
  --fasta input.fasta --mutations-file mutations.tsv \
  --models msa-profile --mode execute --msa homologs.a3m \
  --output-dir results/msa
```

Look up released AlphaMissense predictions:

```bash
python scripts/run_sequence_mutation_effect.py \
  --fasta human.fasta --mutations-file mutations.tsv \
  --models alphamissense --mode import \
  --alphamissense-table AlphaMissense_aa_substitutions.tsv.gz \
  --output-dir results/alphamissense
```

Create commands without downloads:

```bash
python scripts/run_sequence_mutation_effect.py \
  --fasta input.fasta --mutations-file mutations.tsv \
  --models esm-1v,esmc-300m,poet --mode plan \
  --msa homologs.a3m --output-dir results/plan
```

## Model rules

- Use ESM-1v or ESMC masked-marginal log-odds as sequence plausibility evidence, not calibrated pathogenicity.
- Use MSA profile log-odds only when the aligned query maps exactly to submitted WT. Record depth and pseudocount.
- Use PoET only with an MSA and GPU-supported native environment. In `import` mode, preserve checkpoint and command provenance.
- Treat AlphaMissense as lookup/import. The official repository does not release trained weights for arbitrary new inference. Require an unambiguous released-human-variant match.
- Sum component log-odds for a multi-substitution group only as a labeled independence approximation; do not imply epistasis was modeled.

## Modes and failures

- `plan`: validate, write commands and `planned` rows, and perform no model download.
- `execute`: run implemented adapters. Emit `unavailable` or `failed` per model/variant when prerequisites are absent; continue other models.
- `import`: import standardized or model-native scores. Validate variant keys and never silently reorder rows.

Read [scoring-semantics.md](references/scoring-semantics.md) before comparing outputs. Read [archive-cleanup-troubleshooting.md](references/archive-cleanup-troubleshooting.md) for provenance, safe cleanup, and recovery.
