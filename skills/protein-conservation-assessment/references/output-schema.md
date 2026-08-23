# Output Schema

All protein residue coordinates are 1-based query positions.

## `protein_conservation_summary.tsv`

- `query_id`: query sequence ID used for residue mapping.
- `query_length`: ungapped query length.
- `alignment_sequence_count`: number of aligned sequences including query.
- `homolog_sequence_count`: number of aligned sequences excluding query.
- `alignment_length`: MSA column count.
- `search_backend`: none, local-hmmer, ebi-hmmer, or mmseqs.
- `target_database`: local target DB path or hosted database token.
- `msa_backend`: auto, mafft, biotite, or none.
- `mean_conservation_score`: mean residue conservation score.
- `mean_gap_fraction`: mean query-position gap fraction.
- `fraction_conserved`: fraction of query residues classified as conserved.
- `fraction_variable`: fraction of query residues classified as variable.
- `fraction_gap_rich`: fraction of query residues classified as gap-rich.
- `n_conserved_residues`: count of conserved query residues.
- `n_variable_residues`: count of variable query residues.
- `n_conserved_regions`: count of conserved contiguous regions.
- `longest_conserved_region`: longest conserved region length.
- `conserved_threshold`: threshold used for conserved site calls.
- `variable_threshold`: threshold used for variable site calls.
- `warnings`: semicolon-separated run warnings.

## `protein_conservation_sites.tsv`

- `query_id`
- `position`
- `residue`
- `alignment_column`
- `n_sequences`
- `n_non_gap`
- `gap_fraction`
- `consensus_residue`
- `consensus_fraction`
- `query_residue_fraction`
- `entropy`
- `conservation_score`
- `conservation_grade`
- `status`
- `note`

## `protein_conserved_regions.tsv`

- `query_id`
- `region_type`: conserved or variable.
- `start`
- `end`
- `length`
- `mean_conservation_score`
- `mean_gap_fraction`
- `max_conservation_score`
- `min_conservation_score`
- `evidence`
- `note`

## `protein_conservation_assessment.result.json`

The JSON result records:

- `status`
- `parameters`
- `query_id`
- `artifacts`
- `warnings`
- `summary`

Keep TSV files as the stable downstream interface for `protein-annotation-report`.
