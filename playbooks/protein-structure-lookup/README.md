# Protein Structure Lookup Playbook

Use this playbook when the user provides a gene symbol, UniProt accession, or amino-acid sequence and wants public protein-structure context or hosted ESMFold structure output.

## Minimal Step

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --gene <GENE_SYMBOL> \
  --organism human \
  --modules all \
  --outdir output/protein-structure/<GENE_SYMBOL>
```

## Hosted ESMFold From Sequence

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --sequence <AA_SEQUENCE> \
  --sequence-name <LABEL> \
  --modules esmfold \
  --outdir output/protein-structure/<LABEL>
```

For FASTA input:

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --sequence-file <PROTEIN_FASTA> \
  --sequence-name <LABEL> \
  --modules esmfold \
  --outdir output/protein-structure/<LABEL>
```

## Contract

- Resolve gene to UniProt accession.
- Retrieve UniProt features.
- Retrieve RCSB PDB structures mapped to the UniProt accession.
- Retrieve AlphaFold DB metadata.
- For sequence input, validate amino-acid alphabet and 15-400 aa length, then submit to hosted ESMFold.
- Write `protein_structure_get.result.json` and summary TSV/TXT outputs.

## Clarify When

- The gene symbol is ambiguous across organisms.
- The sequence is shorter than 15 aa, longer than 400 aa, or contains unsupported residue codes.
- The user asks for a structure file but does not specify whether a predicted AlphaFold model is acceptable.
- The user wants local AlphaFold, structural alignment, docking, molecular dynamics, or clinical interpretation.
