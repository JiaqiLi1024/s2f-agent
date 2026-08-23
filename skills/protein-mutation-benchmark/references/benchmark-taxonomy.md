# Benchmark Taxonomy

Choose one value on each axis before evaluation.

## Mutation Type

### Substitutions

- Use canonical one-based mutant strings such as A23V.
- Join multiple substitutions with a colon, such as A23V:C40Y.
- Verify each wild-type residue against the release target sequence.
- Sequence models and inverse-folding models commonly support this regime.

### Indels

- Use the processed ProteinGym indel table's mutated_sequence and indel metadata.
- Do not force an indel into the substitution grammar.
- Confirm that a model actually scores variable-length sequences; a substitution-only adapter is not an indel baseline.
- Evaluate indels separately from substitutions.

## Ground Truth

### DMS

- Continuous DMS_score supports within-assay ranking/regression.
- DMS_score_bin supports assay-defined classification diagnostics.
- Assay scales are not interchangeable. Compute within assay first.

### Clinical

- Ground truth is a benign/pathogenic label, not a continuous fitness value.
- Use classification metrics and preserve the clinical benchmark's labeling provenance.
- Do not infer clinical utility from benchmark AUC alone.

## Training Regime

### Zero-shot

- Do not fit model parameters, score direction, thresholds, prompt choices, or model selection on the benchmark test labels.
- A predeclared ensemble is acceptable only when its construction does not use held-out labels.

### Supervised

- Use the release-provided cross-validation folds for reproduction.
- Fit preprocessing and calibration inside each training fold.
- Keep homologous sequence handling and fold identity in the manifest.
- Report fold-level metrics before aggregation.

Do not compare supervised and zero-shot results as though they used the same information budget.
