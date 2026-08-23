# Metrics and Interpretation

## Spearman

Compute average ranks for ties and Pearson correlation between truth ranks and oriented model-score ranks. Use within a DMS assay. Return not_computed for fewer than two rows or constant values.

ProteinGym's official leaderboard performs additional UniProt- and functional-category-level aggregation. A local per-assay result is not a reproduced leaderboard result.

## ROC-AUC

Use continuous oriented scores and binary labels. Return not_computed when only one label class is present. AUC is threshold-free but does not establish calibration or clinical utility.

## MCC

MCC requires binary predictions. This skill never learns a threshold from evaluation labels. Supply --classification-threshold from a preregistered rule or a separate validation set. If no threshold is supplied, the MCC row is retained with status not_computed and a reason.

## NDCG

NDCG measures quality near the top of a ranked list.

- rank mode converts DMS scores to average-rank relevance, making relevance nonnegative and scale-insensitive;
- raw-clipped mode uses max(DMS_score, 0);
- --ndcg-k limits the ranking depth.

These modes are transparent local diagnostics. For exact ProteinGym leaderboard reproduction, use the pinned official release scoring scripts and configuration.

## Score Direction

ProteinGym DMS_score is higher-fitness after direction normalization. Model scores must declare higher_is:

- higher: oriented_score equals raw_score;
- lower: oriented_score equals negative raw_score.
- Project directions more_tolerated, more_sequence_plausible, more_evolutionarily_preferred, more_fit, more_mutant_preferred, and more_stable map to higher.
- Project directions more_deleterious, more_pathogenic, more_destabilizing, and less_stable map to lower.

Do not choose direction by whichever gives better test-set performance.

## Aggregation

The official repository describes aggregation by UniProt ID and functional category to reduce bias from proteins with multiple assays. Do not substitute a naive arithmetic mean when claiming official benchmark reproduction. Report assay coverage and exclusions for every model.
