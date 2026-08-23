---
name: protein-structure-align
description: Align, compare, search, and cluster protein structures from RCSB PDB, AlphaFold DB, Foldseek web/API, or local PDB/mmCIF files. Use when Codex needs to superimpose two structures, compute global RMSD or TMalign TM-score, inspect per-residue C-alpha distances, compare intra-protein contact maps, build an aligned hypothetical two-chain complex and compute cross-protein interface contact maps, plot AlphaFold predicted aligned error (PAE), compare apo/holo or WT/mutant conformations, compare AlphaFold models against experimental structures, or use local Foldseek or Foldseek web/API for fast structure similarity search, database search, all-vs-all structural comparison, HTML search reports, or clustering of one protein or a set of proteins.
---

# Protein Structure Align

## Overview

Use this skill when already available protein structures must be compared geometrically or searched by structure similarity. For pairwise comparison, `protein_structure_align.py` fetches or reads both structures, pairs C-alpha atoms, superimposes structure 2 onto structure 1, and writes RMSD tables, optional TMalign TM-score output, paired intra-protein contact-map heatmaps, optional aligned-complex interface contact maps, AlphaFold PAE plots when available, an aligned PDB, an optional HTML viewer, and a result JSON.

For many-vs-database search, many-vs-many search, or clustering with a local binary, use `protein_structure_foldseek.py`. It wraps the external Foldseek binary instead of reimplementing Foldseek.

For web-based Foldseek similarity search without installing Foldseek or downloading a local database, use `protein_structure_foldseek_web.py`. It submits a query structure to the Foldseek web/API service, polls the ticket, fetches results, writes TSV/JSON, and renders a local HTML report. Use it only after confirming the query structure can be uploaded to the public Foldseek service.

For single-structure lookup, use `protein-structure-get`. For single-structure visualization, contact maps, pockets, secondary structure, residue highlighting, conservation, or PPI networks, use `protein-structure-visualize`.

## Workflow

1. Resolve both structure sources:
   - Use `--pdb1` / `--pdb2` for RCSB PDB IDs.
   - Use `--uniprot1` / `--uniprot2` for AlphaFold DB structures by UniProt accession.
   - Use `--file1` / `--file2` for local `.pdb`, `.cif`, or `.mmcif` files.
2. Set `--chain1` and `--chain2` when comparing specific chains, especially for multichain PDB entries.
3. Set `--res-start` and `--res-end` when the user asks for a domain or conserved core region.
4. Keep `--pairing auto` unless residue numbering differs; use `--pairing order` only when filtered structures are expected to correspond residue-by-residue by order.
5. Use the default `--contact-threshold 5.0` for paired intra-protein C-alpha contact-map comparison unless the user gives another distance cutoff.
6. For a protein-protein interface map after alignment, use `--chain1/--chain2` to select the source chains to superimpose, then pass `--interface-chain1 A --interface-chain2 B` to label the aligned hypothetical complex. Add `--no-contact-maps` when the user only wants the cross-protein interface matrix, not separate intra-protein contact maps.
7. Let PAE run automatically for AlphaFold DB sources, or pass local/remote PAE JSON with `--pae1` and `--pae2`.
8. For local Foldseek similarity search, pass `--mode search --query <QUERY_STRUCTURE_OR_DIR> --target <TARGET_DB_OR_DIR>` to `protein_structure_foldseek.py`.
9. For Foldseek clustering, pass `--mode cluster --query <STRUCTURE_DIR_OR_DB>` to `protein_structure_foldseek.py`.
10. Use `--multimer` only for complex-level Foldseek search/cluster where chain composition matters.
11. For web/API Foldseek search, pass `--query <QUERY_STRUCTURE>` and one or more `--database` values to `protein_structure_foldseek_web.py`; default database is `afdb50`.
12. Inspect the result JSON first, then use the TSV, plots, PDB, HTML, or Foldseek output artifacts as needed.

## Foldseek Run Policy

Run Foldseek directly only when all of these are true:

- The Foldseek binary is already available on `PATH` or the user provided `--foldseek-bin`.
- The query structure, structure directory, FASTA, or Foldseek DB path is available.
- For `--mode search`, the target structure directory or prepared Foldseek DB is available.

Do not silently install Foldseek, download PDB/AlphaFold databases, or build large Foldseek indexes. These operations can take substantial time, disk, RAM, and network bandwidth. Ask for user confirmation first and make the choice explicit: PDB experimental structures, AlphaFold/UniProt predicted structures, or a user-provided local structure directory/database.

When the user only says "find similar structures for <protein/gene/accession>", first use `protein-structure-get` to obtain or resolve the query structure if needed, then check for Foldseek and an existing target. If either Foldseek or the target database is missing, stop at a clear setup choice instead of starting installation or database download.

Use the Foldseek web/API path when the user wants an online search, does not want local Foldseek/database setup, or asks for a web/HTML similarity-search result. This path does not require a local Foldseek binary or local public database download, but it uploads the query structure to `search.foldseek.com`. Ask for confirmation before submitting private, unpublished, proprietary, or otherwise sensitive structures. After confirmation, run `protein_structure_foldseek_web.py` with `--confirm-remote-upload`.

## Runtime

Install declared Python dependencies when the active environment does not already provide them:

```bash
python -m pip install -r skills/protein-structure-align/requirements.txt
```

`py3Dmol` is only required for the interactive HTML viewer. If it is unavailable, the script still writes RMSD tables, plots, aligned PDB, and result JSON with a warning.

TMalign is an optional external binary, not a Python package. When `TMalign` is on `PATH`, the script runs it and parses TM-scores. If it is not available, the script writes a warning and keeps the Biopython RMSD/contact/PAE outputs.

```bash
conda install -c bioconda tmalign
# or install TMalign separately and pass:
# --tmalign-bin /path/to/TMalign
```

Foldseek is an optional external binary, not a Python package. It is required only for structure similarity search and clustering:

```bash
conda install -c conda-forge -c bioconda foldseek
# or install a precompiled Foldseek binary and pass:
# --foldseek-bin /path/to/foldseek
```

Run the installation command only after the user confirms installing Foldseek in the active environment.

Foldseek web/API search requires only the Python dependencies in `requirements.txt` plus network access. It does not install Foldseek locally:

```bash
python skills/protein-structure-align/scripts/protein_structure_foldseek_web.py \
  --list-databases \
  --outdir output/protein-structure-align/foldseek_web_databases
```

## Command Surface

```bash
python skills/protein-structure-align/scripts/protein_structure_align.py \
  (--pdb1 <PDB_ID> | --uniprot1 <ACCESSION> | --file1 <PATH>) \
  (--pdb2 <PDB_ID> | --uniprot2 <ACCESSION> | --file2 <PATH>) \
  [--chain1 <CHAIN_ID>] \
  [--chain2 <CHAIN_ID>] \
  [--res-start <RESSEQ>] \
  [--res-end <RESSEQ>] \
  [--pairing auto|chain_resseq|resseq|order] \
  [--close-threshold <ANGSTROM>] \
  [--divergence-threshold <ANGSTROM>] \
  [--contact-threshold <ANGSTROM>] \
  [--no-contact-maps] \
  [--interface-chain1 <CHAIN_ID>] \
  [--interface-chain2 <CHAIN_ID>] \
  [--interface-contact-threshold <ANGSTROM>] \
  [--pae1 <PAE_JSON_PATH_OR_URL>] \
  [--pae2 <PAE_JSON_PATH_OR_URL>] \
  [--no-pae] \
  [--tmalign-bin <TMalign_PATH_OR_NAME>] \
  [--no-tmalign] \
  [--no-viewer] \
  [--prefix <PREFIX>] \
  --outdir <OUTDIR>
```

Examples:

```bash
python skills/protein-structure-align/scripts/protein_structure_align.py \
  --pdb1 1AKE \
  --pdb2 4AKE \
  --chain1 A \
  --chain2 A \
  --outdir output/protein-structure-align/1AKE_vs_4AKE
```

```bash
python skills/protein-structure-align/scripts/protein_structure_align.py \
  --pdb1 1TIM \
  --uniprot2 P00940 \
  --chain1 A \
  --chain2 A \
  --outdir output/protein-structure-align/1TIM_vs_AF_P00940
```

```bash
python skills/protein-structure-align/scripts/protein_structure_align.py \
  --file1 output/protein-structure/wt/wt.pdb \
  --file2 output/protein-structure/mutant/mutant.pdb \
  --chain1 A \
  --chain2 A \
  --res-start 50 \
  --res-end 350 \
  --outdir output/protein-structure-align/wt_vs_mutant
```

```bash
python skills/protein-structure-align/scripts/protein_structure_align.py \
  --file1 output/proteinA/model.pdb \
  --file2 output/proteinB/model.pdb \
  --chain1 A \
  --chain2 A \
  --no-contact-maps \
  --interface-chain1 A \
  --interface-chain2 B \
  --interface-contact-threshold 5.0 \
  --outdir output/protein-structure-align/proteinA_proteinB_interface
```

Foldseek structure search:

```bash
python skills/protein-structure-align/scripts/protein_structure_foldseek.py \
  --mode search \
  --query output/protein-structure/query.pdb \
  --target output/protein-structure/database/ \
  --coverage 0.8 \
  --evalue 1e-3 \
  --outdir output/protein-structure-align/query_foldseek_search
```

Foldseek search against a prepared PDB database:

```bash
foldseek databases PDB output/foldseek-db/pdb output/foldseek-db/tmp
python skills/protein-structure-align/scripts/protein_structure_foldseek.py \
  --mode search \
  --query output/protein-structure/query.pdb \
  --target output/foldseek-db/pdb \
  --outdir output/protein-structure-align/query_vs_pdb_foldseek
```

Use `foldseek databases PDB ...` or `foldseek databases Alphafold/UniProt ...` only after the user confirms which database to download. For a smaller custom target, prefer a user-provided local directory of PDB/mmCIF files or a prebuilt Foldseek DB.

Foldseek clustering:

```bash
python skills/protein-structure-align/scripts/protein_structure_foldseek.py \
  --mode cluster \
  --query output/protein-structure/structure_set/ \
  --coverage 0.8 \
  --tmscore-threshold 0.6 \
  --outdir output/protein-structure-align/structure_set_foldseek_cluster
```

Foldseek web/API search with local HTML report:

```bash
python skills/protein-structure-align/scripts/protein_structure_foldseek_web.py \
  --query output/protein-structure/query.pdb \
  --database afdb50 \
  --database pdb100 \
  --foldseek-mode 3diaa \
  --confirm-remote-upload \
  --outdir output/protein-structure-align/query_foldseek_web
```

Use `--foldseek-mode tmalign` or `--foldseek-mode lolalign` when the user explicitly wants those Foldseek web alignment modes. Use `--download-archive` when the user also wants the API result archive.

## Output Contract

The script always attempts to write `protein_structure_align.result.json` under `--outdir`. Treat it as the source of truth for run status, source resolution, chain/pairing choices, global RMSD, output paths, warnings, and fatal errors.

Common outputs:

- `<PREFIX>.alignment_summary.tsv`: global RMSD, paired C-alpha count, threshold counts, max and median per-residue distance.
- `<PREFIX>.per_residue_rmsd.tsv`: paired residues and post-superposition C-alpha distance.
- `<PREFIX>.per_residue_rmsd.png` and `.pdf`: per-residue distance plot.
- `<PREFIX>.contact_map_structure1.png/.pdf/.tsv`, `<PREFIX>.contact_map_structure2.*`, and `<PREFIX>.contact_map_delta.*`: paired intra-protein C-alpha contact maps using `--contact-threshold`; skip with `--no-contact-maps` for interface-only runs.
- `<PREFIX>.aligned_complex.pdb`: hypothetical complex containing structure 1 as `--interface-chain1` and aligned structure 2 as `--interface-chain2`.
- `<PREFIX>.aligned_complex_interface_contacts.tsv`, `<PREFIX>.aligned_complex_interface_distances.tsv`, and `<PREFIX>.aligned_complex_interface_contact_map.png/.pdf`: cross-protein C-alpha contacts between structure 1 and aligned structure 2 using `--interface-contact-threshold`. The contact heatmap follows the notebook style: `pandas.DataFrame` plus `seaborn.heatmap` with a viridis palette.
- `<PREFIX>.aligned_complex_interface_distance_clustermap.png/.pdf`: optional seaborn distance clustermap when the interface matrix has at least two rows and columns.
- `<PREFIX>.tmalign.txt` and `<PREFIX>.tmalign.tsv`: raw and parsed TMalign output when the binary is available.
- `<PREFIX>.pae_structure1.png/.pdf/.tsv/.json` and `<PREFIX>.pae_structure2.*`: PAE plots when an AlphaFold DB PAE URL or local PAE JSON is available.
- `<PREFIX>.superimposed.pdb`: structure 2 transformed into structure 1 coordinates.
- `<PREFIX>.superimposed.html`: optional interactive viewer with structure 1 in blue, structure 2 in red, and divergent residues highlighted.
- `summary.txt`: compact human-readable summary.

Foldseek outputs:

- `protein_structure_foldseek.result.json`: run status, selected Foldseek mode/module, command, thresholds, output paths, warnings, and errors.
- `<PREFIX>.foldseek_search.tsv`: tabular Foldseek search results for `--mode search`, using `--format-output` fields.
- `<PREFIX>.foldseek_search.top_hits.tsv`: parsed top-hit preview for tabular search output.
- `<PREFIX>.foldseek_cluster_clu.tsv` or `<PREFIX>.foldseek_cluster_cluster.tsv`: representative-to-member cluster mapping for `--mode cluster`.
- `<PREFIX>.foldseek_cluster_clu.summary.tsv` or `<PREFIX>.foldseek_cluster_cluster.summary.tsv`: per-representative member counts.
- Foldseek may also write representative/all-member FASTA files or multimer reports depending on the selected mode and Foldseek version.

Foldseek web/API outputs:

- `protein_structure_foldseek_web.result.json`: run status, API base, ticket, selected databases, mode, output paths, warnings, and errors.
- `<PREFIX>.foldseek_web_result.json`: raw API result for query entry 0 by default.
- `<PREFIX>.foldseek_web_hits.tsv` and `<PREFIX>.foldseek_web_top_hits.tsv`: flattened web/API alignments.
- `<PREFIX>.foldseek_web_results.html`: local HTML report with top hits plus links to the Foldseek web result and API result endpoints.
- `foldseek_web_databases.json/.tsv/.html`: database listing when `--list-databases` is used.
- `<PREFIX>.foldseek_web_result_archive.tar.gz`: optional API download when `--download-archive` is used.

## Grounded Data Sources

Use only these public sources unless the user provides local files or asks to change data sources:

- RCSB PDB file endpoint: `https://files.rcsb.org/download/<PDB_ID>.pdb`
- AlphaFold DB API and files: `https://alphafold.ebi.ac.uk/api/prediction/<ACCESSION>` and `https://alphafold.ebi.ac.uk/files/`
- Foldseek CLI and output semantics: `https://github.com/steineggerlab/foldseek`
- Foldseek web server: `https://search.foldseek.com`
- Foldseek web/API database endpoint: `https://search.foldseek.com/api/databases`
- MMseqs2/Foldseek app API docs and example client: `https://search.mmseqs.com/docs/` and `https://github.com/soedinglab/MMseqs2-App`

## Failure And Recovery

- If the user gives only one structure, ask for the second structure or run `protein-structure-get` first if the missing side is a gene/protein query.
- If no common C-alpha pairs are found, specify `--chain1/--chain2`, use `--res-start/--res-end`, or switch to `--pairing order` for already matched local structures.
- If chain IDs differ between structures, pass both chains explicitly; `--pairing auto` then pairs by residue number.
- If residue numbering differs substantially, align a domain/core range or use a sequence/structure alignment tool outside this skill before interpreting RMSD.
- If global RMSD is high but only a small domain should match, rerun with a residue range for that domain.
- If TMalign is unavailable, install it or pass `--no-tmalign`; RMSD and contact maps still run.
- If Foldseek is unavailable, install it, pass `--foldseek-bin`, or use `protein_structure_foldseek_web.py` for an online search after remote-upload confirmation; pairwise RMSD/contact/PAE workflows still run without Foldseek.
- If Foldseek search is requested but no target DB/directory is available, ask whether to use PDB, AlphaFold/UniProt, or a local target; do not download a public Foldseek database without confirmation.
- If Foldseek web/API search is requested, list databases with `--list-databases` when the requested web database path is unclear; common paths include `afdb50`, `afdb-swissprot`, `afdb-proteome`, and `pdb100`.
- If a Foldseek web/API run fails with rate-limit, maintenance, or timeout status, keep the local JSON/summary and retry later or switch to local Foldseek.
- If the structure is sensitive, do not use Foldseek web/API; use local Foldseek against a local or user-approved database instead.
- If the user wants a structural database search or clustering rather than two-structure RMSD, use `protein_structure_foldseek.py`, not `protein_structure_align.py`.
- If the user provides a directory of structures for Foldseek search, use it as `--query` when those are query proteins and as `--target` when it is the database to search.
- If an interface contact map is requested for two separate proteins, do not interpret `<PREFIX>.contact_map_structure1.*` or `<PREFIX>.contact_map_structure2.*` as the PPI map; use `<PREFIX>.aligned_complex_interface_*` outputs.
- If PAE is requested for non-AlphaFold/local structures, pass `--pae1` and/or `--pae2` pointing to an AlphaFold-style PAE JSON.
- If `py3Dmol` is unavailable, keep TSV/PDB/plot outputs and report that the HTML viewer was skipped.
