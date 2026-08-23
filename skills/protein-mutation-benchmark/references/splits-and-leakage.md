# Splits and Data Leakage

## Leakage Checklist

Before scoring a held-out benchmark, verify that:

- DMS_score and DMS_score_bin were not used to tune prompts, templates, score direction, thresholds, checkpoints, ensembles, or hyperparameters;
- supervised preprocessing was fitted only on each training fold;
- duplicated variants were not present across train and test;
- homologous proteins, assay replicates, and multiple assays for one UniProt ID were handled according to the declared protocol;
- MSA construction did not include engineered assay variants or test labels;
- structure templates and database snapshots are recorded;
- model pretraining overlap is disclosed when known, rather than guessed away.

## Zero-shot Protocol

Freeze the model adapter and score definition before opening labels. Declare any ensemble weights a priori. Evaluate complete model coverage; missing difficult mutants can bias results.

## Supervised Protocol

Use the matching ProteinGym cross-validation asset:

- substitution singles;
- substitution multiples;
- indels.

Run feature normalization, threshold selection, and calibration inside training data only. Report each fold and the aggregation rule. Do not use the test fold as early stopping data.

## Development Fixtures

Toy fixtures test software, not scientific performance. They may be inspected freely. Clearly separate fixture smoke tests from held-out benchmark evaluation in output paths and reports.
