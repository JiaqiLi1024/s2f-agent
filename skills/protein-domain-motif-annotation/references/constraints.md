# Constraints

## Scope

- Treat this skill as a sequence annotation workflow, not a structure or localization workflow.
- Use protein FASTA for the normal path. Use InterProScan6 `--nucleic` only when the input FASTA is nucleotide sequence.
- Do not infer biological function from a single weak match without reporting the source tool, database/signature, score/e-value when available, and match coverage.

## Versioning And Reproducibility

- Pin InterProScan6 with `-r`, for example `-r 6.0.1`.
- Pin the InterPro data release with `--interpro <release>` when reproducibility matters. `latest` is convenient but less reproducible.
- Record eggNOG-mapper version and eggNOG database directory in the result JSON or final report.
- Keep InterProScan6 and eggNOG outputs separate before merging summaries; they use different evidence models.

## Coordinates

- Treat protein residue coordinates as tool-native amino acid positions.
- Report InterProScan6 and eggNOG-mapper coordinates exactly as emitted unless a downstream format requires conversion.
- When combining with genome/GFF annotations, explicitly state the translation model and coordinate conversion method.

## Data And Runtime

- InterProScan6 is a Nextflow/container workflow. It may download workflow code and database files and may create a large work directory.
- eggNOG-mapper requires a local eggNOG data directory. DIAMOND is the default backend for protein FASTA runs in this skill.
- When conda/mamba are unavailable, prefer installing Miniforge or Miniconda with user approval, then run the same mamba/conda environment commands. Use standalone Nextflow plus Python venv/pip only when conda-style installation is blocked.
- Proteome-scale jobs can be long-running. Prefer explicit `--cpu`, `--interpro-max-workers`, `--interpro-cpus`, `--interpro-workdir`, and output directories.
- Do not delete Nextflow work directories automatically; they may be required for `-resume`.

## Interpretation

- No-match results are valid outcomes. Check input sequence type, database versions, and search scope before treating no matches as a failure.
- InterProScan6 is stronger for domain architecture, families, repeats, and functional sites.
- eggNOG-mapper is stronger for orthology-based functional transfer and broad GO/KEGG/EC summaries.
- Overlapping InterPro and eggNOG Pfam or GO evidence should be summarized as corroborating evidence, not as independent experimental validation.
