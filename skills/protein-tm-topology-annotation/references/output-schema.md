# Output Schema

## Summary TSV

`protein_tm_topology_summary.tsv` has one row per protein/query.

- `query_id`: FASTA ID, sequence label, or GFF3 seqid.
- `length`: amino-acid sequence length when sequence is available, otherwise max parsed coordinate.
- `sources`: TMHMM, DeepTMHMM, or imported source labels.
- `topology_class`: `alpha_helical_tm`, `beta_barrel_tm`, `signal_peptide_only`, `no_tm_detected`, or `no_prediction`.
- `n_tm_helices`
- `n_beta_strands`
- `n_signal_peptides`
- `n_inside_regions`
- `n_outside_regions`
- `n_periplasmic_regions`
- `n_other_regions`
- `topology_string`: source-qualified interval summary.
- `warnings`

## Regions TSV

`protein_tm_topology_regions.tsv` has one row per parsed topology segment.

- `query_id`
- `source`: `TMHMM`, `DeepTMHMM`, or imported source label.
- `feature_type`: normalized region type such as `TMhelix`, `Beta_strand`, `inside`, `outside`, `periplasmic`, `signal_peptide`, or source-native fallback.
- `start`, `end`, `length`: 1-based closed residue coordinates.
- `score`: GFF3 score if present.
- `strand`, `phase`: preserved from GFF3 when present.
- `evidence`: source-native GFF3 type or TMHMM long-output type.
- `attributes`: GFF3 attributes serialized as `key=value;...`.
- `note`: source file path or parsing note.

## Residue States TSV

`protein_tm_topology_residue_states.tsv` has one row per residue per source.

- `query_id`
- `source`
- `position`: 1-based residue coordinate.
- `residue`: amino acid when sequence is available.
- `state`: normalized state, usually `TMhelix`, `Beta_strand`, `inside`, `outside`, `periplasmic`, `signal_peptide`, `other`, or `unknown`.
- `state_detail`: normalized feature type that assigned the residue.
- `feature_type`
- `feature_id`: GFF3 `ID`/`Name` when available, otherwise `<feature_type>:<start>-<end>`.
- `score`
- `attributes`

## Plots

`plots/*.svg` and `plots/*.html` are standardized topology state plots.

- They show residue coordinate on the x-axis and colored state intervals along a protein-length track.
- They are generated for each protein/source pair.
- They are not posterior probability plots unless native probability data are explicitly supplied by a future parser.

## Result JSON

`protein_tm_topology_annotation.result.json` records:

- command plan
- execution status
- normalized input FASTA
- source GFF3/TMHMM files
- output paths
- row counts
- native plot paths
- warnings
- TMHMM parsed metadata
