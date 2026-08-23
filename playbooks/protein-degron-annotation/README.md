# Protein Degron Annotation Playbook

Use this playbook for sequence-first degron recognition from unknown proteins, FASTA files, UniProt accessions, ELM degron classes, DEGRONOPEDIA motif data, QCDPred quality-control degron scoring, and custom degron regexes.

## Inputs

- Amino-acid sequence, protein FASTA, or UniProt accession.
- Optional ELM classes TSV: `elms_classes.tsv`.
- Optional DEGRONOPEDIA motif dataset: `DEGRONOPEDIA_degron_dataset.xlsx`.
- Optional original QCDPred raw output table from `QCDpred.py`.
- Optional custom degron regexes.
- Output root and run ID.

## Local ELM And DEGRONOPEDIA Scan

```bash
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py \
  --fasta <PROTEINS_FASTA> \
  --elm-classes-tsv "$HOME/biodata/protein_degron/elms_classes.tsv" \
  --degronopedia-xlsx "$HOME/biodata/protein_degron/DEGRONOPEDIA_degron_dataset.xlsx" \
  --tools elm,degronopedia,qcdpred \
  --outdir output/protein-degron-annotation/<RUN_ID>
```

## QCDPred Only

```bash
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py \
  --sequence <AA_SEQUENCE> \
  --sequence-name <QUERY_ID> \
  --tools qcdpred \
  --qcdpred-threshold 0.85 \
  --qcdpred-padding 8 \
  --outdir output/protein-degron-annotation/<RUN_ID>_qcdpred
```

## Import Original QCDPred Output

```bash
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py \
  --fasta <PROTEINS_FASTA> \
  --tools qcdpred \
  --qcdpred-output <QCDPRED_OUTPUT_TXT> \
  --outdir output/protein-degron-annotation/<RUN_ID>_qcdpred_import
```

## Plan Data Downloads

```bash
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py \
  --sequence <AA_SEQUENCE> \
  --sequence-name <QUERY_ID> \
  --data-dir "$HOME/biodata/protein_degron" \
  --outdir output/protein-degron-annotation/<RUN_ID>_plan
```

Inspect `database_download_plan.sh`; ask the user before executing downloads and preserve license fields.

## Custom Motifs

```bash
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py \
  --sequence <AA_SEQUENCE> \
  --sequence-name <QUERY_ID> \
  --tools custom \
  --custom-degron "MY_DEGRON=R..L" \
  --outdir output/protein-degron-annotation/<RUN_ID>
```

## Merge Into Annotation Report

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --fasta <PROTEINS_FASTA> \
  --degron-result-json output/protein-degron-annotation/<RUN_ID>/protein_degron_annotation.result.json \
  --outdir output/protein-annotation-report/<RUN_ID>
```

## Outputs

- `protein_degron_summary.tsv`: per-query degron candidate summary.
- `protein_degron_features.tsv`: per-candidate degron feature rows.
- `qcdpred_profile.tsv`: QCDPred center-residue profile when QCDPred is requested.
- `protein_degron_annotation.result.json`: run metadata, source paths, warnings, and artifact paths.
- `commands.sh`: command plan.
- `database_download_plan.sh`: data download plan requiring user approval.
