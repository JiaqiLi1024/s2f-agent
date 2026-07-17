# Protein Structure Alignment Playbook

Use this playbook when the user wants to compare two protein structures by rigid-body superposition, RMSD, optional TMalign TM-score, PAE plots, intra-protein contact-map changes, cross-protein interface contact maps after forming an aligned hypothetical complex, or local/web Foldseek-based structure similarity search and clustering.

## Runnable Patterns

Two RCSB PDB structures:

```bash
python skills/protein-structure-align/scripts/protein_structure_align.py \
  --pdb1 1AKE \
  --pdb2 4AKE \
  --chain1 A \
  --chain2 A \
  --outdir output/protein-structure-align/1AKE_vs_4AKE
```

AlphaFold model against an experimental structure:

```bash
python skills/protein-structure-align/scripts/protein_structure_align.py \
  --pdb1 1TIM \
  --uniprot2 P00940 \
  --chain1 A \
  --chain2 A \
  --outdir output/protein-structure-align/1TIM_vs_AF_P00940
```

Two local structures:

```bash
python skills/protein-structure-align/scripts/protein_structure_align.py \
  --file1 output/protein-structure/wt/wt.pdb \
  --file2 output/protein-structure/mutant/mutant.pdb \
  --chain1 A \
  --chain2 A \
  --outdir output/protein-structure-align/wt_vs_mutant
```

Domain/core-region comparison:

```bash
python skills/protein-structure-align/scripts/protein_structure_align.py \
  --pdb1 1AKE \
  --pdb2 4AKE \
  --chain1 A \
  --chain2 A \
  --res-start 1 \
  --res-end 180 \
  --outdir output/protein-structure-align/1AKE_vs_4AKE_core
```

AlphaFold PAE plot or local PAE JSON:

```bash
python skills/protein-structure-align/scripts/protein_structure_align.py \
  --pdb1 1TIM \
  --uniprot2 P00940 \
  --chain1 A \
  --chain2 A \
  --pae2 output/pae/AF_P00940_pae.json \
  --outdir output/protein-structure-align/1TIM_vs_AF_P00940
```

Protein-protein interface contact map after aligning two proteins as a hypothetical complex:

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

Foldseek search for similar structures:

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

Foldseek clustering for a set of structures:

```bash
python skills/protein-structure-align/scripts/protein_structure_foldseek.py \
  --mode cluster \
  --query output/protein-structure/structure_set/ \
  --coverage 0.8 \
  --tmscore-threshold 0.6 \
  --outdir output/protein-structure-align/structure_set_foldseek_cluster
```

Foldseek web/API database listing:

```bash
python skills/protein-structure-align/scripts/protein_structure_foldseek_web.py \
  --list-databases \
  --outdir output/protein-structure-align/foldseek_web_databases
```

Foldseek web/API search with local HTML output:

```bash
python skills/protein-structure-align/scripts/protein_structure_foldseek_web.py \
  --query output/protein-structure/query.pdb \
  --database afdb50 \
  --database pdb100 \
  --foldseek-mode 3diaa \
  --confirm-remote-upload \
  --outdir output/protein-structure-align/query_foldseek_web
```

## Decision Guide

- Use `--pdb1/--pdb2` for two RCSB PDB IDs.
- Use `--uniprot1/--uniprot2` when one side should be fetched from AlphaFold DB.
- Use `--file1/--file2` for local PDB or mmCIF files.
- Use `--chain1/--chain2` for multichain structures or structures with different chain IDs. These select source chains used for superposition.
- Use `--res-start/--res-end` for domain-level RMSD or conserved-core alignment.
- Keep `--pairing auto` for most tasks. Use `--pairing order` only when local structures are already residue-order matched but numbering differs.
- Keep `--contact-threshold 5.0` for intra-protein C-alpha contact maps unless the user gives another cutoff.
- Use `--interface-chain1` and `--interface-chain2` when the user asks for a PPI/interface contact map after alignment. These are output chain labels for the hypothetical complex; source chains still come from `--chain1/--chain2`.
- Add `--no-contact-maps` for interface-only tasks so the run does not emit separate internal contact maps for each protein.
- Use `--pae1/--pae2` for local or remote PAE JSON when the source is not automatically resolved from AlphaFold DB.
- Use `--no-tmalign` only when TMalign is unavailable and the user only needs Biopython RMSD/contact outputs.
- Use `protein_structure_foldseek.py --mode search` when the user asks for similar structures or database search; do not force this into pairwise RMSD unless they only gave two specific structures.
- Use `protein_structure_foldseek.py --mode cluster` when the user gives a folder/database of structures and asks for grouping, redundancy reduction, all-vs-all structural similarity, or representatives.
- Use `protein_structure_foldseek_web.py` when the user asks for online Foldseek, web/API service, no local installation, or HTML similarity-search results.
- Add `--multimer` only when the user asks for complex-level Foldseek search or clustering; otherwise keep the monomer modules.
- Run Foldseek immediately only when the binary and target directory/database are already available.
- Ask before installing Foldseek, downloading PDB or AlphaFold/UniProt Foldseek databases, or building large custom indexes.
- If the user asks for similar structures but gives no target database, ask them to choose PDB, AlphaFold/UniProt, or a local structure directory/database.
- For Foldseek web/API, ask before uploading private or sensitive query structures. Use `--confirm-remote-upload` only after the user confirms remote submission is acceptable.
- Use `--list-databases` when the requested Foldseek web database path is unclear. Common structural-search paths include `afdb50`, `afdb-swissprot`, `afdb-proteome`, and `pdb100`.
- Keep `--foldseek-mode 3diaa` by default. Use `tmalign` or `lolalign` only when the user asks for those Foldseek web modes.

## Outputs

- `protein_structure_align.result.json`: run status, inputs, source paths, chain choices, RMSD summary, output paths, warnings, and errors.
- `<PREFIX>.alignment_summary.tsv`: global RMSD and residue-count summary.
- `<PREFIX>.per_residue_rmsd.tsv`: paired residue table with post-superposition C-alpha distance.
- `<PREFIX>.per_residue_rmsd.png/.pdf`: per-residue distance plot.
- `<PREFIX>.contact_map_structure1.png/.pdf/.tsv`, `<PREFIX>.contact_map_structure2.*`, `<PREFIX>.contact_map_delta.*`: intra-protein C-alpha contact maps and gained/lost contacts.
- `<PREFIX>.aligned_complex.pdb`: hypothetical two-chain complex with structure 1 and aligned structure 2.
- `<PREFIX>.aligned_complex_interface_contacts.tsv`, `<PREFIX>.aligned_complex_interface_distances.tsv`, `<PREFIX>.aligned_complex_interface_contact_map.png/.pdf`: cross-protein binary and distance maps after alignment. The contact heatmap follows the provided notebook pattern: DataFrame labels plus `seaborn.heatmap`.
- `<PREFIX>.aligned_complex_interface_distance_clustermap.png/.pdf`: optional distance clustermap matching the notebook's `sns.clustermap(..., metric='euclidean')` pattern when enough interface residues exist.
- `<PREFIX>.tmalign.txt/.tsv`: raw and parsed TMalign output when the binary is available.
- `<PREFIX>.pae_structure1.png/.pdf/.tsv/.json`, `<PREFIX>.pae_structure2.*`: PAE plots and matrices when PAE sources are available.
- `<PREFIX>.superimposed.pdb`: structure 2 in structure 1 coordinates.
- `<PREFIX>.superimposed.html`: optional interactive comparison viewer.
- `protein_structure_foldseek.result.json`: Foldseek run status, command, parameters, outputs, warnings, and errors.
- `<PREFIX>.foldseek_search.tsv` and `<PREFIX>.foldseek_search.top_hits.tsv`: Foldseek tabular search results and parsed top-hit preview.
- `<PREFIX>.foldseek_cluster_clu.tsv` or `<PREFIX>.foldseek_cluster_cluster.tsv`: representative-to-member Foldseek cluster mapping.
- `<PREFIX>.foldseek_cluster_clu.summary.tsv` or `<PREFIX>.foldseek_cluster_cluster.summary.tsv`: per-representative cluster sizes.
- `protein_structure_foldseek_web.result.json`: Foldseek web/API run status, ticket, database choices, output paths, warnings, and errors.
- `<PREFIX>.foldseek_web_result.json`: raw Foldseek web/API result for query entry 0 by default.
- `<PREFIX>.foldseek_web_hits.tsv` and `<PREFIX>.foldseek_web_top_hits.tsv`: flattened alignment hits from the web/API result.
- `<PREFIX>.foldseek_web_results.html`: local HTML report with top hits and links to the web/API result.
- `foldseek_web_databases.json/.tsv/.html`: available Foldseek web database listing.

## Caveats

- This is C-alpha rigid-body superposition, not sequence alignment, flexible alignment, docking, or molecular dynamics.
- TMalign is optional and must be installed as a system binary for TM-score output.
- Foldseek is optional and must be installed as a system binary for structure search or clustering. Use `conda install -c conda-forge -c bioconda foldseek` or pass `--foldseek-bin`.
- Foldseek web/API search does not require local Foldseek or local database downloads, but it uploads the query structure to `search.foldseek.com`.
- Public Foldseek databases can be large; downloading or indexing them is a setup action that requires user confirmation.
- Do not use Foldseek web/API for sensitive unpublished structures unless the user explicitly approves remote upload.
- Foldseek search/cluster outputs are not the same as pairwise RMSD tables. Interpret Foldseek hits by E-value, probability, coverage settings, and TM-score fields when requested.
- PAE is an AlphaFold confidence metric for a predicted structure, not a structural alignment score between two proteins.
- Interface contact maps are computed between structure 1 and aligned structure 2, not within each protein. Use the `aligned_complex_interface_*` files for PPI contacts.
- Default pairing assumes overlapping residue numbering, or residue-number pairing when chains are explicitly selected.
- RMSD is sensitive to domain motion and unmatched regions; use residue ranges for domain-specific interpretation.
- If no common C-alpha pairs are found, specify chains/ranges or use order-based pairing only for already matched structures.
