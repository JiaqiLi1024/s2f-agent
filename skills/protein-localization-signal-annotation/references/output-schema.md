# Output Schema

## Summary TSV

`protein_localization_summary.tsv` has one row per protein/query.

- `query_id`: FASTA ID or provided sequence label.
- `length`: amino-acid sequence length when known.
- `sources`: contributing prediction sources.
- `deeploc_top_localization`: first/top DeepLoc localization call.
- `deeploc_localizations`: all parsed DeepLoc localization calls.
- `deeploc_membrane_association`: parsed DeepLoc membrane classes.
- `deeploc_signals`: DeepLoc sorting-signal calls when present.
- `signalp_prediction`: SignalP class, such as `Sec/SPI`, `Tat/SPI`, or `Other`.
- `signalp_signal_peptide`: `yes` or `no`.
- `signalp_cleavage_site`: parsed cleavage site or boundary when available.
- `signalp_probability`: SignalP score/probability when available.
- `targetp_prediction`: TargetP class, such as `SP`, `mTP`, `cTP`, `lTP`, or `Other`.
- `targetp_presequence`: `yes` or `no`.
- `targetp_cleavage_site`: parsed presequence cleavage site when available.
- `targetp_probability`: TargetP score/probability when available.
- `integrated_localization`: conservative synthesis from DeepLoc first, then TargetP/SignalP hints.
- `secretory_pathway_evidence`: compact evidence string from DeepLoc/SignalP/TargetP.
- `warnings`: input or parser warnings.

## Feature TSV

`protein_localization_features.tsv` has one row per localization or targeting feature.

- `query_id`
- `source`: `DeepLoc-2.1`, `SignalP-6.0`, `TargetP-2.0`, or native source from imported GFF3.
- `feature_type`: `subcellular_location`, `membrane_association`, `sorting_signal`, `signal_peptide`, `mitochondrial_transit_peptide`, `chloroplast_transit_peptide`, `thylakoid_luminal_transit_peptide`, or source-native fallback.
- `start`, `end`, `length`: 1-based coordinates when available.
- `label`: source label or prediction class.
- `score`: source-native probability/score when available.
- `evidence`: source field or parser evidence.
- `note`: parser caveat, source attributes, or coordinate interpretation.

## Score TSV

`protein_localization_scores.tsv` has one row per source probability or score.

- `query_id`
- `source`
- `score_type`: `localization_probability`, `membrane_probability`, `signalp_probability`, or `targetp_probability`.
- `label`: class label.
- `score`
- `threshold`
- `above_threshold`

## Result JSON

`protein_localization_signal_annotation.result.json` records:

- command plan and web-submission FASTA paths
- execution status
- output paths
- source files
- native plot paths
- row counts
- warnings
- errors

Use TSV files for downstream tables. Use JSON as the machine-readable run status.
