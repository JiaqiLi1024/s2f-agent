---
name: protein-mutation-benchmark
description: Use Protein Mutation Benchmark to validate, align, and evaluate protein mutation-effect scores against ProteinGym or ProteinGym-like DMS and clinical tables. Use when Codex needs to download a pinned ProteinGym asset, audit assay schemas, compare zero-shot or supervised model scores, compute per-assay Spearman/ROC-AUC/MCC/NDCG diagnostics, prevent benchmark leakage, or produce reproducible metrics and exclusion reports. Treat ProteinGym as benchmark/data/evaluation infrastructure, never as a prediction model.
---

# Protein Mutation Benchmark

## Keep the Role Boundary Explicit

Treat ProteinGym as a versioned benchmark, data catalog, reference schema, baseline-score collection, and evaluation substrate. Do not list it as a mutation-effect predictor and do not emit a ProteinGym score. A model such as ESM-1v, ESMC, SaProt, PoET, ProteinMPNN, or ESM-IF1 produces scores; this skill aligns and evaluates those scores.

## Follow This Workflow

1. Classify the benchmark before downloading data.
   - Distinguish substitution from indel.
   - Distinguish DMS regression/ranking from clinical classification.
   - Distinguish zero-shot evaluation from supervised training/evaluation.
   - Read references/benchmark-taxonomy.md.

2. Pin the release and asset.
   - Default to pinned v1.3; verify the official release page before calling any version “latest.”
   - Use scripts/fetch_proteingym_data.py --list.
   - Generate a command first. Add --execute only after confirming asset size, storage, network policy, and data terms.
   - Record SHA-256 after download or require a trusted expected digest.
   - Read references/proteingym-release-data-license.md and references/data-acquisition.md.

3. Validate both sides before evaluation.
   - Require mutation, mutant, or variant_id and either DMS_score or a binary label on the assay side.
   - Require mutation or variant_id, model_id, and raw_score or score on the model side.
   - Preserve assay_id and protein_id when available.
   - Declare whether higher or lower raw model scores indicate stronger fitness/benefit; the runner orients lower-is-better values without overwriting raw scores.
   - Use scripts/validate_proteingym_table.py for standalone validation.
   - Read references/input-output-contract.md.

4. Align on assay and mutation identity.
   - Run one assay file at a time when assay IDs are absent.
   - Use an explicit --assay-id for renamed or merged tables.
   - Exclude, do not guess, unmatched mutations, duplicate normalized keys, nonnumeric values, and conflicting protein IDs.
   - Inspect assay_validation.json, score_validation.json, aligned_scores.tsv, exclusions.tsv, and alignment_report.json.

5. Compute only applicable metrics.
   - Use per-assay Spearman for continuous DMS fitness.
   - Use ROC-AUC only when binary labels contain both classes.
   - Compute MCC only with an explicit oriented-score threshold.
   - Use NDCG only as a labeled local top-ranking diagnostic. Do not present it as an official leaderboard metric.
   - Never average incomparable raw scores or pool mutation rows across assays before computing assay-level metrics.
   - Read references/metrics-interpretation.md.

6. Protect evaluation integrity.
   - Keep test labels unavailable to model fitting, prompt selection, threshold selection, checkpoint selection, and score-direction selection.
   - Use ProteinGym-provided supervised split files when reproducing supervised benchmarks.
   - Deduplicate homologs and assay/protein identities according to the chosen protocol.
   - Read references/splits-and-leakage.md.

7. Preserve a reproducible run.
   - Use scripts/run_proteingym_benchmark.py.
   - Keep raw/, intermediate/, logs/, commands.sh, manifest.json, and formatted outputs by default.
   - Use --archive-intermediates to tar the exact run's intermediate/ before removal.
   - Use --cleanup-intermediates only when normalized tables are not needed. Cleanup never targets input files or directories outside the run.
   - Read references/archive-cleanup.md.

8. Report limitations.
   - State release, asset, benchmark regime, mutation type, assay count, aligned/excluded row counts, metric definitions, threshold source, and any unavailable metric.
   - Do not turn benchmark performance into clinical evidence or a claim about an individual variant.

## Grounded CLI Surface

Validate a DMS table:

    python skills/protein-mutation-benchmark/scripts/validate_proteingym_table.py \
      --kind assay \
      --input assay.csv \
      --output-tsv output/normalized_assay.tsv \
      --report-json output/assay_validation.json

Validate project long-form scores:

    python skills/protein-mutation-benchmark/scripts/validate_proteingym_table.py \
      --kind scores \
      --input protein_mutation_scores.tsv \
      --output-tsv output/normalized_scores.tsv \
      --report-json output/score_validation.json

Run the benchmark:

    python skills/protein-mutation-benchmark/scripts/run_proteingym_benchmark.py \
      --assay-data assay.csv \
      --scores protein_mutation_scores.tsv \
      --assay-id MY_ASSAY \
      --classification-threshold 0 \
      --output-dir output/proteingym/MY_ASSAY

Generate a pinned download command without downloading:

    python skills/protein-mutation-benchmark/scripts/fetch_proteingym_data.py \
      --asset dms-substitutions \
      --version v1.3 \
      --output-dir downloads/proteingym-v1.3

## References

- Read references/proteingym-release-data-license.md for role, release, official sources, and license boundaries.
- Read references/benchmark-taxonomy.md before choosing substitution/indel, DMS/clinical, or zero-shot/supervised.
- Read references/data-acquisition.md before any network or large-data operation.
- Read references/input-output-contract.md when adapting columns or consuming artifacts.
- Read references/metrics-interpretation.md before computing or reporting metrics.
- Read references/splits-and-leakage.md for evaluation integrity.
- Read references/archive-cleanup.md before deleting intermediates.
- Read references/troubleshooting.md after validation, alignment, or metric failures.

## Scripts

- scripts/fetch_proteingym_data.py
- scripts/validate_proteingym_table.py
- scripts/run_proteingym_benchmark.py
- scripts/proteingym_utils.py
