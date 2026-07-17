# Inference Patterns

Use the script from the repository root.

## Full human gene lookup

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --gene TP53 \
  --organism human \
  --modules all \
  --outdir output/protein-structure/TP53
```

## UniProt features and domain map only

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --gene EGFR \
  --modules uniprot,domain_map \
  --outdir output/protein-structure/EGFR
```

## AlphaFold DB model metadata and downloaded mmCIF

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --gene KRAS \
  --modules alphafold \
  --download-structure \
  --download-format cif \
  --outdir output/protein-structure/KRAS
```

## UniProt accession instead of gene symbol

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --uniprot P04637 \
  --modules alphafold,pdb \
  --max-pdb 50 \
  --outdir output/protein-structure/P04637
```

## Hosted ESMFold from amino-acid sequence

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --sequence ACDEFGHIKLMNPQRSTVWY \
  --sequence-name example_peptide \
  --modules esmfold \
  --outdir output/protein-structure/example_peptide
```

## Hosted ESMFold from FASTA file

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --sequence-file input/protein.fasta \
  --sequence-name protein_fasta \
  --modules esmfold \
  --outdir output/protein-structure/protein_fasta
```

## Mouse gene

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --gene Trp53 \
  --organism mouse \
  --modules all \
  --outdir output/protein-structure/Trp53
```
