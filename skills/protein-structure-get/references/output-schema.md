# Output Schema

`protein_structure_get.result.json` is the primary machine-readable artifact.

Top-level fields:

- `status`: `ok`, `partial`, or `error`
- `query`: requested gene, UniProt accession, sequence metadata, organism, modules, limits, and optional PyMOL settings
- `resolved`: UniProt accession, entry name, protein name, gene name, organism, sequence length, reviewed status, and UniProt URL; or sequence source metadata for ESMFold runs
- `modules`: per-module status records for `uniprot`, `pdb`, `alphafold`, `domain_map`, and `esmfold`
- `outputs`: file paths written by the run
- `warnings`: non-fatal issues
- `errors`: fatal or module-level errors

Expected TSV outputs:

- `protein_structure_summary.tsv`: one row per run
- `<TARGET>.<ACCESSION>.features.tsv`: UniProt feature rows
- `<TARGET>.<ACCESSION>.pdb_structures.tsv`: RCSB PDB rows
- `<TARGET>.<ACCESSION>.alphafold.tsv`: AlphaFold DB metadata row
- `<TARGET>.esmfold.tsv`: hosted ESMFold metadata row
- `<TARGET>.esmfold.pdb`: hosted ESMFold PDB output
- `<TARGET>.sequence.fasta`: normalized sequence submitted to ESMFold
- `<LABEL>.pymol.pml`: PyMOL script when `--pymol` or `--run-pymol` is requested
- `<LABEL>.pymol.pse`, `<LABEL>.pymol.png`, and `<LABEL>.pymol.log`: optional PyMOL-rendered outputs when `--run-pymol` succeeds

Stable output columns for `features.tsv`:

`type`, `description`, `start`, `end`, `length`

Stable output columns for `pdb_structures.tsv`:

`pdb_id`, `title`, `method`, `resolution_A`, `n_protein_chains`, `n_atoms`, `pubmed_id`, `authors`, `deposition_date`, `rcsb_url`

Stable output columns for `alphafold.tsv`:

`alphafold_id`, `uniprot_accession`, `gene`, `organism`, `seq_length`, `model_created`, `latest_version`, `pdb_url`, `cif_url`, `pae_image_url`, `alphafold_page`

Stable output columns for `esmfold.tsv`:

`sequence_name`, `sequence_length`, `sequence_sha256`, `model_source`, `api_url`, `pdb_path`, `fasta_path`, `generated_utc`, `mean_confidence_raw`, `min_confidence_raw`, `max_confidence_raw`, `confidence_scale`, `mean_confidence_0_100`, `n_atoms`
