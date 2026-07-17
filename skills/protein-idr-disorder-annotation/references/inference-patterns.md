# Inference Patterns

## Dry Run For FASTA

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools metapredict,aiupred \
  --outdir output/protein-idr-disorder-annotation/proteins
```

## Execute metapredict

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools metapredict \
  --execute \
  --outdir output/protein-idr-disorder-annotation/metapredict
```

## Execute AIUPred CLI

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools aiupred \
  --aiupred-binding \
  --aiupred-linker \
  --aiupred-force-cpu \
  --execute \
  --outdir output/protein-idr-disorder-annotation/aiupred
```

## Execute AIUPred Nextflow

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools aiupred \
  --aiupred-mode nextflow \
  --aiupred-profile conda,cpu \
  --aiupred-binding \
  --aiupred-linker \
  --execute \
  --outdir output/protein-idr-disorder-annotation/aiupred_nextflow
```

## IUPred3 REST By UniProt Accession

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --uniprot P04637 \
  --tools iupred3 \
  --iupred3-type long \
  --execute \
  --outdir output/protein-idr-disorder-annotation/P04637_iupred3
```

## Import Existing IUPred3 JSON

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --iupred3-json iupred3.P04637.long.json \
  --tools iupred3 \
  --outdir output/protein-idr-disorder-annotation/imported_iupred3
```

## Local IUPred3 Table Wrapper

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools iupred3 \
  --iupred3-local-bin iupred3_qt.py \
  --iupred3-local-input-format table \
  --execute \
  --outdir output/protein-idr-disorder-annotation/iupred3_local
```

## Local IUPred3 Without A Batch Wrapper

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools iupred3 \
  --iupred3-local-bin /path/to/iupred3.py \
  --iupred3-local-input-format fasta \
  --execute \
  --outdir output/protein-idr-disorder-annotation/iupred3_local_single
```

## Import FuzDrop JSON

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --tools fuzdrop \
  --fuzdrop-json fuzdrop_result.json \
  --execute \
  --outdir output/protein-idr-disorder-annotation/fuzdrop
```

## Import AggrescanAI CSV

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --tools aggrescanai \
  --aggrescanai-csv aggrescanai_results.csv \
  --execute \
  --outdir output/protein-idr-disorder-annotation/aggrescanai
```

## Combined IDR And LLPS Features With Plots

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --uniprot P04637 \
  --tools iupred3+aggrescanai+fuzdrop \
  --aggrescanai-csv aggrescanai_results_P04637.csv \
  --fuzdrop-json fuzdrop_P04637.json \
  --execute \
  --outdir output/protein-idr-disorder-annotation/P04637_idr_llps
```

## Single Raw Sequence

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --sequence "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY" \
  --sequence-name test_protein \
  --tools metapredict,aiupred \
  --outdir output/protein-idr-disorder-annotation/test_protein
```
