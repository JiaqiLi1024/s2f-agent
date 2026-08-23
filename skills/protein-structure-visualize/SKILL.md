---
name: protein-structure-visualize
description: Visualize and analyze an existing protein structure from RCSB PDB, AlphaFold DB, or a local PDB file. Use when Codex needs an interactive 3D protein viewer, residue or secondary-structure highlight HTML, contact map, B-factor or AlphaFold pLDDT plot, secondary-structure summary, heuristic pocket analysis, conservation coloring, or STRING protein-protein interaction network.
---

# Protein Structure Visualize

## Overview

Use this skill after a protein structure source is known. It fetches or reads a structure, parses residues and chains, and produces visual analysis artifacts such as HTML viewers, residue/secondary-structure highlight viewers, contact maps, B-factor/pLDDT plots, secondary-structure tracks, pocket tables, conservation plots, and STRING PPI networks.

This is not a folding, docking, molecular-dynamics, or clinical-interpretation skill. Use `protein-structure-get` first when the user only provides a gene symbol and needs UniProt, RCSB PDB, or AlphaFold DB candidates.

## Workflow

1. Resolve the structure source.
- Use `--pdb-id <PDB_ID>` when the user gives an RCSB PDB ID.
- Use `--uniprot <ACCESSION>` when the user wants the AlphaFold DB model for a UniProt accession.
- Use `--pdb-file <PATH>` when the user provides a local PDB file.
- Exactly one source flag is required.

2. Choose modules.
- Use `--modules all` for broad inspection.
- Use `view` for an interactive py3Dmol HTML viewer.
- Use `contact_map` for C-alpha distance and binary contact matrices.
- Use `bfactor` for experimental B-factor or AlphaFold pLDDT confidence plots.
- Use `secondary` for DSSP/PDB-derived secondary structure summaries.
- Use `highlight` for an HTML viewer that highlights residue sites and/or selected secondary-structure classes.
- Use `pocket` for heuristic pocket-lining residue clusters based on SASA and geometry.
- Use `conservation` for EBI HMMER jackhmmer conservation scores and coloring.
- Use `ppi` for STRING interaction partners; add `--gene <GENE_SYMBOL>`.

3. Run the script and inspect the JSON result first.

```bash
python skills/protein-structure-visualize/scripts/protein_structure_visualize.py \
  --pdb-id 1TUP \
  --modules view,contact_map,bfactor,secondary,pocket \
  --chain A \
  --outdir output/protein-structure-visualize/1TUP
```

## Runtime Dependencies

Install the declared Python dependencies when the active environment does not already provide them:

```bash
python -m pip install -r skills/protein-structure-visualize/requirements.txt
```

The `secondary` module can use the external `mkdssp`/DSSP binary when available. If DSSP is unavailable, the script falls back to HELIX/SHEET records where possible. AlphaFold, ESMFold, and many generated/local PDB files may not include HELIX/SHEET records, so install DSSP when secondary-structure assignment or secondary-structure highlighting is required:

```bash
conda install -c salilab dssp
# or, on Debian/Ubuntu:
apt install dssp
```

The `view`, `pocket` surface viewer, and conservation viewer need `py3Dmol`; tabular and static plot outputs can still be useful without browser interaction.

## Command Surface

```bash
python skills/protein-structure-visualize/scripts/protein_structure_visualize.py \
  (--pdb-id <PDB_ID> | --uniprot <ACCESSION> | --pdb-file <PDB_PATH>) \
  [--modules all|view,contact_map,bfactor,secondary,pocket,conservation,ppi,highlight] \
  [--chain <CHAIN_ID>] \
  [--zoom-start <RESSEQ>] \
  [--zoom-end <RESSEQ>] \
  [--color-scheme spectrum|chain|bfactor] \
  [--highlight-residues <3-D,A:10-K,A:25:ASP>] \
  [--highlight-secondary <H,E,C|helix,sheet,coil>] \
  [--highlight-color <HEX_COLOR>] \
  [--no-highlight-labels] \
  [--contact-threshold <ANGSTROM>] \
  [--top-pockets <N>] \
  [--probe-radius <ANGSTROM>] \
  [--uniprot-for-conservation <ACCESSION>] \
  [--hmmer-iterations <N>] \
  [--gene <GENE_SYMBOL>] \
  [--ppi-species <NCBI_TAXON_ID>] \
  [--ppi-score <0-1000>] \
  [--ppi-limit <N>] \
  --outdir <OUTDIR>
```

Examples:

```bash
python skills/protein-structure-visualize/scripts/protein_structure_visualize.py \
  --uniprot P04637 \
  --modules all \
  --gene TP53 \
  --outdir output/protein-structure-visualize/P04637
```

```bash
python skills/protein-structure-visualize/scripts/protein_structure_visualize.py \
  --pdb-file output/protein-structure/TP53/TP53.P04637.alphafold_model.pdb \
  --modules view,contact_map,bfactor \
  --chain A \
  --zoom-start 90 \
  --zoom-end 290 \
  --outdir output/protein-structure-visualize/TP53_local
```

```bash
python skills/protein-structure-visualize/scripts/protein_structure_visualize.py \
  --pdb-id 1TUP \
  --modules highlight \
  --chain A \
  --highlight-residues A:110-R,A:120-K \
  --highlight-secondary helix,sheet \
  --outdir output/protein-structure-visualize/1TUP_highlight
```

## Output Contract

The script always attempts to write `protein_structure_visualize.result.json` under `--outdir`. Treat this file as the source of truth for run status, requested modules, resolved source, chain choice, generated files, warnings, and fatal errors.

Common outputs:

- `structure_summary.tsv` and `summary.txt`: compact run summary.
- `<PREFIX>.full_view.html` or `<PREFIX>.zoomed_view.html`: interactive 3D viewer, when `view` succeeds.
- `<PREFIX>.highlight.html`: residue and/or secondary-structure highlight viewer, when `highlight` succeeds.
- `<PREFIX>.contact_map.png`, `.pdf`, and `<PREFIX>.ca_distances.tsv`: contact map outputs.
- `<PREFIX>.bfactor.png`, `.pdf`, and `<PREFIX>.bfactor.tsv`: B-factor or AlphaFold pLDDT outputs.
- `<PREFIX>.secondary_structure.png`, `.pdf`, and `.tsv`: secondary-structure outputs.
- `<PREFIX>.pockets.tsv`, `<PREFIX>.pocket_residues.tsv`, `<PREFIX>.sasa_per_residue.tsv`, `<PREFIX>.pockets.png`, `.pdf`, and `<PREFIX>.pocket_surface.html`: pocket outputs.
- `<PREFIX>.conservation_scores.tsv`, `<PREFIX>.conservation.png`, `.pdf`, and `<PREFIX>.conservation.html`: conservation outputs.
- `<PREFIX>.ppi_interactions.tsv`, `<PREFIX>.ppi_network.png`, and `.pdf`: STRING PPI outputs.

## Grounded Data Sources

Use only these public sources unless the user explicitly provides local files or asks to change data sources:

- RCSB PDB file endpoint: `https://files.rcsb.org/download/<PDB_ID>.pdb`
- AlphaFold DB API and files: `https://alphafold.ebi.ac.uk/api/prediction/<ACCESSION>` and `https://alphafold.ebi.ac.uk/files/`
- STRING REST API: `https://string-db.org/api`
- EBI HMMER jackhmmer endpoint for conservation search.

## Failure And Recovery

- If the user gives only a gene symbol, run or recommend `protein-structure-get` first to resolve UniProt/PDB/AlphaFold candidates.
- If `py3Dmol` is unavailable, install requirements or run non-view modules first.
- If secondary-structure highlight returns zero residues, install DSSP/mkdssp or use a PDB file with HELIX/SHEET records. AlphaFold/ESMFold PDB files commonly need DSSP for this.
- If residue highlight uses `3-D` without a chain, the selected `--chain` is used. Chain-qualified formats such as `A:3-D` are safer for multichain structures.
- If `conservation` fails because HMMER or UniRef90 access is unavailable, keep other structure outputs and report the warning from the result JSON.
- If `ppi` is requested without `--gene`, rerun with the gene symbol and the appropriate `--ppi-species`.
- If chain selection fails, use the first available chain and record a warning.
- Treat pocket detection as a heuristic surface/geometry screen, not ligand docking or binding-energy prediction.
