# Protein Mutation Benchmark Playbook

ProteinGym occupies the benchmark layer of this project. It supplies curated assays, standardized directionality conventions, evaluation splits, and comparison metrics; it is not another mutation-effect predictor.

## Workflow

1. Select one pinned ProteinGym release and asset class: substitution or indel; DMS or clinical; zero-shot or supervised.
2. Download only the needed asset with the component downloader in plan mode first. Record the release, URL, checksum, and license.
3. Validate assay and score schemas independently.
4. Align by assay identity plus mutation or variant key. Keep unmatched and duplicate rows in exclusion reports.
5. Orient scores for metrics without overwriting raw scores.
6. Compute per-assay, per-model metrics. Spearman is the default continuous DMS metric; classification metrics require labels and an explicit threshold where applicable.
7. Report coverage, exclusions, directionality, leakage controls, and exact code revision.

## Toy evaluation

    python skills/protein-mutation-benchmark/scripts/run_proteingym_benchmark.py \
      --assay-data skills/protein-mutation-benchmark/references/fixtures/toy_dms.csv \
      --scores skills/protein-mutation-benchmark/references/fixtures/toy_scores.tsv \
      --output-dir output/protein-mutation-benchmark/toy

## Leakage rules

Do not tune on the test assay. For supervised evaluation, preserve the official split and check protein, assay, and homolog overlap. Do not infer general performance from one assay. Do not pool raw DMS values across assays without the declared normalization used by the benchmark protocol.

## Expected artifacts

The run must include metrics.tsv, summary.json, aligned rows, exclusions, validation reports, commands, logs, manifest, and any explicitly retained intermediates. A model without sufficient aligned rows receives a not-computed reason instead of a synthetic metric.
