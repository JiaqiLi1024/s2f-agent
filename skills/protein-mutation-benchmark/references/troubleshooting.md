# Troubleshooting

## Missing Required Columns

- Inspect the header and validation report's column_mapping.
- Pass explicit flags such as --assay-mutation-column, --assay-score-column, --score-value-column, or --score-model-column.
- Do not rename a clinical label to DMS_score.

## No Aligned Rows

- Confirm both tables use the same assay ID.
- For a single assay lacking ID columns, pass --assay-id.
- Check one-based mutation notation and multi-mutation separators.
- Check that protein IDs refer to the same target sequence.
- For indels, use the release's indel identity fields rather than substitution notation.

## Metrics Are Not Computed

- Spearman needs at least two nonconstant continuous truth and score values.
- ROC-AUC needs both binary classes.
- MCC needs --classification-threshold and a nondegenerate confusion matrix.
- NDCG needs at least two rows and nonzero relevance.
- Inspect each metrics.tsv reason value; do not replace unavailable values with zero.

## Score Appears Reversed

Check higher_is in the input. Correct the adapter contract based on model semantics, not observed test correlation. The aligned table preserves raw_score and shows oriented_score.

## Download Fails

- Generate and inspect commands.sh without --execute.
- Verify the pinned release and asset against https://proteingym.org/download.
- Confirm disk space for both archive and extracted data.
- Retry into a new directory or verify the partial file digest before reuse.

## Official and Local Results Differ

Local metrics are per assay. Official reproduction may include completeness checks, UniProt aggregation, function-category aggregation, bootstrap uncertainty, and release-specific scripts. Use the pinned official repository's scoring scripts before claiming exact leaderboard reproduction.
