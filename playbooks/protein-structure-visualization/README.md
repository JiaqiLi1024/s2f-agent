# Protein Structure Visualization Playbook

## When To Use

Use `protein-structure-visualize` when the structure source is already known:

- RCSB PDB ID, such as `1TUP`
- UniProt accession for AlphaFold DB, such as `P04637`
- Local PDB file path

If the user provides only a gene symbol, run `protein-structure-get` first to resolve UniProt, RCSB PDB, and AlphaFold DB candidates.

## Minimal Commands

RCSB PDB structure:

```bash
python skills/protein-structure-visualize/scripts/protein_structure_visualize.py \
  --pdb-id 1TUP \
  --modules view,contact_map,bfactor,secondary,pocket \
  --chain A \
  --outdir output/protein-structure-visualize/1TUP
```

AlphaFold DB structure:

```bash
python skills/protein-structure-visualize/scripts/protein_structure_visualize.py \
  --uniprot P04637 \
  --modules view,contact_map,bfactor,conservation \
  --outdir output/protein-structure-visualize/P04637
```

PPI network:

```bash
python skills/protein-structure-visualize/scripts/protein_structure_visualize.py \
  --uniprot P04637 \
  --modules ppi \
  --gene TP53 \
  --outdir output/protein-structure-visualize/TP53_ppi
```

Residue and secondary-structure highlight HTML:

```bash
python skills/protein-structure-visualize/scripts/protein_structure_visualize.py \
  --pdb-id 1TUP \
  --modules highlight \
  --chain A \
  --highlight-residues A:110-R,A:120-K \
  --highlight-secondary helix,sheet \
  --outdir output/protein-structure-visualize/1TUP_highlight
```

## Outputs To Inspect

Always inspect `protein_structure_visualize.result.json` first. It records status, requested modules, selected chain, generated files, warnings, and fatal errors.

Typical artifact groups:

- HTML: full or zoomed py3Dmol viewer.
- Highlight HTML: selected residue sites with labels such as `A:110-R`, plus selected helix/sheet/coil regions.
- Plots: contact map, B-factor/pLDDT, secondary structure, pockets, conservation, PPI network.
- Tables: C-alpha distances, B-factor/pLDDT, secondary structure, pocket residues, SASA per residue, conservation scores, STRING interactions.

## Interpretation Rules

- B-factor in experimental PDB structures is not the same as AlphaFold pLDDT.
- Pocket output is a heuristic SASA/geometric screen, not ligand docking.
- Conservation and PPI outputs depend on public network services and can fail independently of structure parsing.
- If the requested chain is absent, the script uses the first available chain and records a warning.
- If `--highlight-residues` omits chain IDs, the selected `--chain` is used.
- Secondary-structure highlighting needs DSSP/mkdssp or HELIX/SHEET records in the PDB file; otherwise selected classes may have zero hits.
- AlphaFold, ESMFold, and many generated/local PDB files commonly lack HELIX/SHEET records. Install DSSP for secondary-structure assignment when using those files:
  `conda install -c salilab dssp` or `apt install dssp`.
