# Protein Annotation Report Playbook

Use this playbook when a task needs standardized protein annotation TSV/JSON outputs from sequences, UniProt identifiers, InterProScan6, eggNOG-mapper, IDR/LLPS outputs, degron outputs, or imported feature/motif tables.

## Inputs

- One or more of: amino-acid sequence, protein FASTA, UniProt accession, gene symbol, protein name, InterProScan6 TSV, eggNOG `.emapper.annotations`, `protein_domain_motif_annotation.result.json`, `protein_idr_disorder_annotation.result.json`, `protein_llps_summary.tsv`, `protein_llps_features.tsv`, `protein_degron_annotation.result.json`, or `protein_degron_features.tsv`.
- Optional organism/taxon for gene or protein-name lookup.
- Output root and run ID.

## Unknown Sequence

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --sequence <AA_SEQUENCE> \
  --sequence-name <RUN_ID> \
  --outdir output/protein-annotation-report/<RUN_ID>
```

For reliable domain and orthology evidence, run `protein-domain-motif-annotation` first, then:

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --fasta <PROTEINS_FASTA> \
  --annotation-result-json <protein_domain_motif_annotation.result.json> \
  --outdir output/protein-annotation-report/<RUN_ID>
```

## UniProt/Gene/Protein Name

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --gene <GENE_SYMBOL> \
  --organism human \
  --outdir output/protein-annotation-report/<GENE_SYMBOL>
```

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --uniprot <ACCESSION> \
  --outdir output/protein-annotation-report/<ACCESSION>
```

## Existing Annotation Outputs

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --fasta <PROTEINS_FASTA> \
  --interpro-tsv <INTERPROSCAN_TSV> \
  --eggnog-annotations <PREFIX.emapper.annotations> \
  --outdir output/protein-annotation-report/<RUN_ID>
```

## Existing IDR/LLPS Outputs

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --idr-result-json <protein_idr_disorder_annotation.result.json> \
  --outdir output/protein-annotation-report/<RUN_ID>
```

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --llps-summary-tsv <protein_llps_summary.tsv> \
  --llps-features-tsv <protein_llps_features.tsv> \
  --outdir output/protein-annotation-report/<RUN_ID>
```

## Existing Degron Outputs

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --fasta <PROTEINS_FASTA> \
  --degron-result-json <protein_degron_annotation.result.json> \
  --outdir output/protein-annotation-report/<RUN_ID>
```

## Inspect Outputs

- `protein_annotation_summary.tsv`: one row per protein/query.
- `protein_annotation_features.tsv`: one row per feature/domain/motif/function evidence item.
- `protein_annotation_report.json`: status, output paths, source files, warnings, and errors.
