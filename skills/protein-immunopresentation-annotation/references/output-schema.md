# Output Schema

All residue coordinates are 1-based closed positions on the input protein sequence.

## `mhci_peptides.tsv`

- `query_id`: input protein identifier.
- `protein_length`: full protein length.
- `peptide_start`: peptide start coordinate.
- `peptide_end`: peptide end coordinate.
- `peptide_length`: peptide length.
- `peptide_sequence`: generated MHC-I peptide.

## `mhci_binding_predictions.tsv`

- `query_id`
- `peptide_start`
- `peptide_end`
- `peptide_length`
- `peptide_sequence`
- `allele`: HLA allele.
- `predictor`: IEDB method/predictor name.
- `rank`: percentile rank when available.
- `score`: predictor score when available.
- `ic50_nm`: IC50 in nM when available.
- `binder_level`: `strong`, `weak`, or `none`.
- `raw_source`: imported or executed source file.
- `raw_columns_json`: source row preserved as JSON.

## `mhci_processing_predictions.tsv`

- `proteasome_score`
- `tap_score`
- `mhc_binding_score`
- `processing_score`
- `total_score`
- `processing_support`: `yes` when processing/total score evidence is present, otherwise `unknown`.

Other columns mirror the binding table identifiers.

## `mhci_immunogenicity_predictions.tsv`

- `immunogenicity_score`: imported IEDB immunogenicity score when available.

Other columns mirror the peptide identifiers.

## `immunopresentation_candidates.tsv`

Core columns:

- `query_id`
- `protein_length`
- `peptide_start`
- `peptide_end`
- `peptide_length`
- `peptide_sequence`
- `allele_count_tested`
- `strong_binding_alleles`
- `weak_binding_alleles`
- `best_el_rank`
- `best_ba_rank`
- `best_rank`
- `best_score`
- `best_ic50_nm`
- `best_binding_predictor`
- `processing_support`
- `processing_score`
- `proteasome_score`
- `tap_score`
- `mhc_binding_score`
- `total_score`
- `immunogenicity_score`
- `overlaps_signal_peptide`
- `overlaps_tm`
- `overlaps_idr`
- `overlaps_domain`
- `overlaps_conserved_region`
- `context_features`
- `candidate_grade`
- `evidence`
- `note`

Candidate grades are prioritization labels, not experimental assertions.

## `protein_immunopresentation_summary.tsv`

One row per protein:

- peptide counts
- prediction counts
- strong/weak/high-confidence/weak/unlikely candidate counts
- allele, peptide-length, and predictor settings
- query-scoped warnings

## `protein_immunopresentation_annotation.result.json`

Records:

- `skill`
- `status`
- `run_id`
- `created_utc`
- `parameters`
- `counts`
- `artifacts`
- `warnings`

Common artifact keys:

- `normalized_input_fasta`
- `local_iedb_input_json`
- `local_pipeline_plan_sh`
- `local_pipeline_manifest_json`
- `local_workdir` when `--execute-local` is used.
- `local_aggregated_result_json` when local execution succeeds.
- `iedb_legacy_requests_jsonl`
- `iedb_nextgen_request_json`
- `commands_sh`

`local-result-json` imports from qinti/IEDB aggregate output are split into binding, processing, and immunogenicity tables. Combined columns such as `binding.netmhcpan_el.percentile`, `binding.netmhcpan_ba.ic50`, `processing.basic_processing.total_score`, and `immunogenicity.score` are normalized into the standard TSV columns above.
