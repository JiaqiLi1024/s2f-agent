# Output Schema

All coordinates are 1-based closed query residue positions.

## `protein_degron_summary.tsv`

- `query_id`: query sequence identifier.
- `input_type`: raw_sequence, fasta, raw_fasta_sequence, or uniprot.
- `length`: query protein length.
- `sequence_sha256`: SHA-256 checksum of the amino-acid sequence.
- `tools`: comma-separated source list requested by the run.
- `elm_degron_hits`: number of ELM degron candidate matches.
- `degronopedia_hits`: number of DEGRONOPEDIA candidate matches.
- `qcdpred_hits`: number of merged QCDPred candidate intervals.
- `qcdpred_avg_score`: mean of all QCDPred center-residue scores for the query.
- `qcdpred_median_score`: median of all QCDPred center-residue scores for the query.
- `qcdpred_max_score`: maximum QCDPred center-residue score for the query.
- `custom_degron_hits`: number of custom motif matches.
- `n_degron_candidates`: total candidate rows.
- `n_terminal_degrons`: N-terminal or C-terminal candidate count.
- `n_internal_degrons`: internal candidate count.
- `n_phosphodegrons`: candidates whose source/name/type indicates phosphodegron behavior.
- `n_unique_motifs`: unique motif names matched.
- `warnings`: query-scoped warnings.

## `protein_degron_features.tsv`

The first 18 columns are compatible with `protein-annotation-report` feature rows:

- `query_id`
- `source`
- `feature_type`
- `start`
- `end`
- `length`
- `accession`
- `name`
- `description`
- `database`
- `interpro_accession`
- `interpro_description`
- `go_terms`
- `pathways`
- `score`
- `evalue`
- `evidence`
- `note`

Degron-specific extension columns:

- `matched_sequence`: exact sequence matched by the regex.
- `degron_location`: N-terminus, C-terminus, Internal, or source-native location.
- `degron_regex`: regex used for detection.
- `e3_ligase_or_ups_component`: known UPS-recognizing components or E3 ligase context when provided by the source.
- `license`: source license field, especially from DEGRONOPEDIA.
- `free_for_any_use`: source commercial/free-use flag when available.
- `references`: DOI, PMID, or source reference text.

For QCDPred rows:

- `source` is `QCDPred`.
- `feature_type` is `quality_control_degron_candidate`.
- `score` is the maximum QCDPred score among center residues inside the merged interval.
- `degron_regex` is empty because QCDPred is a composition-based probability model, not a regex motif database.
- `note` stores threshold, padding, tile length, positive center residues, interval mean score, and interval median score.

## `qcdpred_profile.tsv`

Produced when `--tools qcdpred` or `--qcdpred-output` is used.

- `query_id`: query sequence identifier.
- `tile_sequence`: 17-aa peptide tile.
- `score`: QCDPred degron probability for that tile.
- `central_aa`: residue at the tile center.
- `residue`: 1-based center-residue coordinate.
- `profile_source`: `native_python_qcdpred_model` or the imported QCDPred output filename.

## `protein_degron_annotation.result.json`

The JSON result records:

- `skill`
- `status`
- `run_id`
- `created_utc`
- `parameters`
- `counts`
- `artifacts`
- `warnings`

Keep `protein_degron_features.tsv` as the stable downstream interface for `protein-annotation-report`.
