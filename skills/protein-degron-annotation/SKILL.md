---
name: protein-degron-annotation
description: "Identify and report protein degron candidates from amino-acid sequences, protein FASTA files, or UniProt accessions using ELM degron classes, DEGRONOPEDIA degron motif data, and QCDPred quality-control degron scoring. Use when Codex needs degron recognition, degradation signal annotation, N-degron/C-degron detection, phosphodegron candidates, E3 ligase motif candidates, ELM DEG motif scans, DEGRONOPEDIA dataset import, QCDPred/QCAP/QCD interval prediction, DEGRONOPEDIA web-result normalization, or standardized degron TSV/JSON outputs for protein annotation reports."
---

# Protein Degron Annotation

## Overview

Use this skill for sequence-first degron recognition:

`protein sequence -> ELM/DEGRONOPEDIA motif source and/or QCDPred profile -> local scan/prediction or imported web result -> standardized degron summary/features/report`.

This skill detects candidate degron motifs. It does not by itself prove regulated degradation, ubiquitination, phosphorylation, accessibility, or proteasomal turnover. Treat degron calls as sequence evidence that should be interpreted with disorder, conservation, localization/topology, PTM, structural exposure, and experiment context.

## Workflow

1. Choose input.
- Use `--sequence` and `--sequence-name` for one unknown protein.
- Use `--fasta` for one or more proteins.
- Use `--uniprot` when the user gives a UniProt accession and network lookup is acceptable.
- Use `--degronopedia-xlsx` or `--degronopedia-tsv` when the user already downloaded a DEGRONOPEDIA motif dataset or result table.
- Use `--tools qcdpred` when the user asks for QCDPred, QCAP, quality-control degron prediction, or sequence-first degron probability scoring.
- Use `--qcdpred-output` when the user already ran the original `QCDpred.py` and wants the raw five-column profile normalized into the skill outputs.

2. Choose evidence sources.
- Use ELM for ELM classes whose identifiers start with `DEG_` and ELM classes whose names/descriptions explicitly describe degrons.
- Use DEGRONOPEDIA for curated degron motif regexes, degron location, UPS-recognizing components, literature identifiers, and license fields.
- Use QCDPred for 17-aa-window quality-control degron probability scoring. The wrapper includes the published model coefficients and converts high-scoring center residues into merged candidate intervals using `--qcdpred-threshold` and `--qcdpred-padding`.
- Use custom motifs only when the user provides degron patterns or cleavage/context motifs.

3. Confirm environment and database policy.
- Read `references/setup-and-databases.md` before writing install or download commands.
- Prefer a dedicated conda/mamba environment if installing optional tools such as `gget`, `diamond`, `pandas`, or `openpyxl`.
- If conda/mamba are missing, ask before installing Miniforge or Miniconda.
- Do not silently download ELM or DEGRONOPEDIA data. Generate `database_download_plan.sh` and ask the user to approve source, license, and destination first.

4. Run local scanning when database files are present.

```bash
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py \
  --fasta proteins.fa \
  --elm-classes-tsv "$HOME/biodata/protein_degron/elms_classes.tsv" \
  --degronopedia-xlsx "$HOME/biodata/protein_degron/DEGRONOPEDIA_degron_dataset.xlsx" \
  --tools elm,degronopedia,qcdpred \
  --outdir output/protein-degron-annotation/proteins
```

5. Run QCDPred-only prediction when no motif databases are ready.

```bash
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --tools qcdpred \
  --outdir output/protein-degron-annotation/query1_qcdpred
```

6. Create only a data/download plan when database files are not ready.

```bash
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --data-dir "$HOME/biodata/protein_degron" \
  --outdir output/protein-degron-annotation/query1_plan
```

7. Import into the standard annotation report.

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --fasta proteins.fa \
  --degron-result-json output/protein-degron-annotation/proteins/protein_degron_annotation.result.json \
  --outdir output/protein-annotation-report/proteins
```

## DEGRONOPEDIA Web Service

Use the DEGRONOPEDIA web service when the user needs the full server context: disorder, conservation, PTM/mutation context, structural features, PSI, or the tripartite degron model. The public website is not a stable batch API; prefer manual submission and import the downloaded xlsx result when exact web output is required.

Important constraints:

- It accepts UniProt ID, FASTA sequence, or PDB/structure input.
- It is one protein at a time.
- FASTA input must use canonical amino acids and the service documents a 50 to 40,000 amino-acid query range.
- Results can be downloaded as xlsx.
- The full server cannot be downloaded for local execution; the ML PSI component is separately available from the authors.

## QCDPred

Use QCDPred when the user wants sequence-first quality-control degron prediction rather than only curated regex motifs. The bundled script implements the published stand-alone `QCDpred.py` 17-aa logistic regression model directly in Python using the coefficients from the KULL-Centre `papers/2022/degron-predict-Johansson-et-al` repository. It does not require conda, numpy, R, or a database.

Default interpretation:

- Every 17-aa window is scored at its central residue.
- Sequences shorter than 17 aa cannot be scored by QCDPred.
- Residues with score `>= 0.85` are treated as positive centers by default.
- Positive centers are expanded by 8 residues on both sides and contiguous intervals are merged.
- `qcdpred_profile.tsv` preserves the raw center-residue profile, while `protein_degron_features.tsv` stores merged QCDPred candidate intervals.

The KULL-Centre `_2023_Tesei_IDRome` repository contains an R aggregation script that runs `QCDpred.py`, then computes per-IDR QCDPred average, median, and maximum values. This skill ports that aggregation step to Python in `protein_degron_summary.tsv` as `qcdpred_avg_score`, `qcdpred_median_score`, and `qcdpred_max_score`.

## Outputs

- `protein_degron_summary.tsv`: one row per query sequence.
- `protein_degron_features.tsv`: one row per degron candidate; compatible with `protein-annotation-report`.
- `qcdpred_profile.tsv`: one row per QCDPred 17-aa window center residue when `qcdpred` is requested.
- `protein_degron_annotation.result.json`: metadata, warnings, counts, and artifact paths.
- `normalized_input.fasta`: query sequences used for scanning.
- `commands.sh`: reproducible command plan and web/API notes.
- `database_download_plan.sh`: non-executed ELM and DEGRONOPEDIA data download plan.

## Interpretation Rules

- Report motif matches as candidates, not confirmed degrons.
- Preserve source, database, regex, matched sequence, residue coordinates, UPS component/E3 fields, evidence, literature references, and license fields.
- Use 1-based closed residue coordinates.
- Flag phosphodegrons as context-dependent because phosphorylation or other PTM evidence is normally required.
- Treat terminal degrons separately from internal degrons because N-/C-terminal exposure and proteolysis can determine activity.
- Treat QCDPred intervals as quality-control degron probability evidence, not E3-specific motif assignments.
- Combine with `protein-idr-disorder-annotation`, `protein-conservation-assessment`, `protein-localization-signal-annotation`, and `protein-structure-visualize` when the user asks for biological plausibility.

## References

- Read `references/setup-and-databases.md` for ELM/DEGRONOPEDIA download, conda, gget, and license handling.
- Read `references/workflow.md` for source selection, DEGRONOPEDIA web import, and interpretation.
- Read `references/output-schema.md` before changing report columns.

## Script

- `scripts/protein_degron_annotation.py`
