# Inference Patterns

## Unknown Sequence

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --sequence "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY" \
  --sequence-name unknown_protein \
  --outdir output/protein-annotation-report/unknown_protein
```

For stronger domain/function evidence, first run `protein-domain-motif-annotation`, then combine:

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --fasta proteins.fa \
  --annotation-result-json output/protein-domain-motif-annotation/proteins/protein_domain_motif_annotation.result.json \
  --outdir output/protein-annotation-report/proteins
```

When IDR/disorder annotation is also available, pass both result JSON files:

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --fasta proteins.fa \
  --annotation-result-json output/protein-domain-motif-annotation/proteins/protein_domain_motif_annotation.result.json \
  --idr-result-json output/protein-idr-disorder-annotation/proteins/protein_idr_disorder_annotation.result.json \
  --outdir output/protein-annotation-report/proteins
```

## Direct InterProScan6 And eggNOG Files

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --fasta proteins.fa \
  --interpro-tsv results/interproscan6/proteins.tsv \
  --eggnog-annotations results/eggnog/proteins.emapper.annotations \
  --outdir output/protein-annotation-report/proteins
```

## Direct IDR Files

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --idr-summary-tsv output/protein-idr-disorder-annotation/proteins/protein_idr_summary.tsv \
  --idr-regions-tsv output/protein-idr-disorder-annotation/proteins/protein_idr_regions.tsv \
  --outdir output/protein-annotation-report/proteins_idr
```

## Direct IDR And LLPS Files

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --idr-summary-tsv output/protein-idr-disorder-annotation/proteins/protein_idr_summary.tsv \
  --idr-regions-tsv output/protein-idr-disorder-annotation/proteins/protein_idr_regions.tsv \
  --llps-summary-tsv output/protein-idr-disorder-annotation/proteins/protein_llps_summary.tsv \
  --llps-features-tsv output/protein-idr-disorder-annotation/proteins/protein_llps_features.tsv \
  --outdir output/protein-annotation-report/proteins_idr_llps
```

## UniProt Accession

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --uniprot P04637 \
  --outdir output/protein-annotation-report/P04637
```

Export every UniProt feature, including variants and sequence conflicts, only when needed:

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --uniprot P04637 \
  --all-uniprot-features \
  --outdir output/protein-annotation-report/P04637_all_features
```

## Gene Symbol

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --gene TP53 \
  --organism human \
  --outdir output/protein-annotation-report/TP53
```

## Protein Name

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --protein-name "tumor protein p53" \
  --organism human \
  --outdir output/protein-annotation-report/tumor_protein_p53
```

## Existing Sequence Analysis Outputs

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --features-tsv results/features.tsv \
  --motifs-tsv results/motifs.tsv \
  --outdir output/protein-annotation-report/imported
```
