# Output Schema

## Summary TSV

`protein_idr_summary.tsv` has one row per protein/query.

- `query_id`: FASTA ID, sequence label, or UniProt accession.
- `length`: amino-acid sequence length when known.
- `sources`: score sources contributing to the summary.
- `mean_disorder_score`: mean normalized disorder score across parsed disorder tracks.
- `fraction_disordered`: fraction of parsed residues above the disorder threshold.
- `n_disordered_residues`: count of residues above threshold.
- `n_idr_regions`: threshold-derived IDR count.
- `longest_idr`: length of the longest threshold-derived IDR.
- `n_binding_regions`: count of threshold-derived disordered binding regions.
- `n_linker_regions`: count of threshold-derived flexible linker regions.
- `warnings`: query-specific warnings.

## Regions TSV

`protein_idr_regions.tsv` has one row per called region.

- `query_id`
- `source`: metapredict, AIUPred, IUPred3, IUPred3-local, or imported source.
- `region_type`: `idr`, `disordered_binding_region`, `flexible_linker`, `redox_plus_idr`, or `redox_minus_idr`.
- `start`, `end`, `length`: 1-based residue coordinates.
- `mean_score`, `max_score`
- `threshold`
- `evidence`: source score track used for region calling.

## Residue Scores TSV

`protein_idr_residue_scores.tsv` has one row per residue score.

- `query_id`
- `source`
- `score_type`: `disorder`, `binding`, `linker`, `redox_plus_disorder`, `redox_minus_disorder`, `experimental_disorder`, `aggregation`, `llps_propensity`, or `plddt`.
- `position`: 1-based residue coordinate.
- `residue`
- `score`
- `threshold`
- `above_threshold`

## Result JSON

`protein_idr_disorder_annotation.result.json` records:

- command plan
- execution status
- normalized input FASTA
- output paths
- row counts
- warnings
- errors

Use the JSON file as the machine-readable status source.

## LLPS Summary TSV

`protein_llps_summary.tsv` has one row per protein/query with LLPS and aggregation evidence.

- `query_id`
- `length`
- `sources`: FuzDrop, AggrescanAI, or imported source.
- `pLLPS`: FuzDrop droplet-state probability when available.
- `mean_aggregation_score`
- `fraction_aggregation_prone`
- `n_aggregation_prone_residues`
- `n_aggregation_regions`
- `n_dpr_regions`
- `n_hotspot_regions`
- `n_dor_regions`
- `n_ddr_regions`
- `n_cdr_regions`
- `warnings`

## LLPS Features TSV

`protein_llps_features.tsv` has one row per LLPS or aggregation region.

- `query_id`
- `source`
- `feature_type`: `aggregation_prone_region`, `droplet_promoting_region`, `fuzdrop_hotspot`, `droplet_organizing_region`, `droplet_destabilizing_region`, `context_dependent_region`, or `llps_prone_region`.
- `start`, `end`, `length`
- `score`
- `threshold`
- `evidence`
- `note`

## Plots

`plots/*.svg` and `plots/*.html` are built-in visualizations. Score plots show residue position on the x-axis, normalized score on the y-axis, the source threshold as a dashed line, and called regions as shaded spans. Feature-map plots are emitted when only feature intervals are available.
