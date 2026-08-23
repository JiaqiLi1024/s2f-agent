---
name: protein-annotation-report
description: Create standardized protein annotation reports from unknown amino-acid sequences, protein FASTA files, UniProt accessions, gene symbols, protein names, InterProScan6 outputs, eggNOG-mapper outputs, protein IDR/disorder/LLPS outputs, protein degron annotation outputs, or existing feature/motif TSV files. Use when Codex needs to fetch UniProt functional annotations, normalize domain/motif/function/IDR/LLPS/AggrescanAI/FuzDrop/degron outputs, or produce publication- and pipeline-ready protein annotation TSV/JSON tables.
---

# Protein Annotation Report

## Overview

Use this skill to turn protein annotation evidence into stable report tables. It complements `protein-domain-motif-annotation`, `protein-idr-disorder-annotation`, and `protein-degron-annotation`: those skills run domain/motif/orthology, IDR/disorder/LLPS, and degron workflows, while this skill fetches UniProt annotations when identifiers are provided and normalizes all evidence into summary and feature TSV outputs.

For unknown amino-acid sequences, first generate sequence-level summary and motif candidates locally. For reliable domains, families, GO, KEGG, and orthology-based function, run `protein-domain-motif-annotation` and pass its InterProScan6/eggNOG outputs into this report skill.

## Workflow

1. Choose the input path.
- Use `--sequence` or `--fasta` for unknown amino-acid sequences.
- Use `--uniprot`, `--gene`, or `--protein-name` when the user provides an identifier or known protein name.
- Use `--annotation-result-json`, `--interpro-tsv`, and `--eggnog-annotations` when domain/motif annotation has already been run.
- Use `--idr-result-json`, `--idr-summary-tsv`, `--idr-regions-tsv`, `--llps-summary-tsv`, and `--llps-features-tsv` when IDR/disorder/LLPS annotation has already been run.
- Use `--degron-result-json` or `--degron-features-tsv` when degron annotation has already been run.
- Use `--features-tsv` and `--motifs-tsv` to import outputs shaped like the earlier protein sequence analysis script.

2. Choose the report mode.
- Unknown sequence only: generate sequence summary and regex motif candidates, then state that InterProScan6/eggNOG are needed for stronger domain/function evidence.
- Unknown sequence plus InterProScan6/eggNOG/IDR/LLPS/degron outputs: merge local sequence, InterPro domains/signatures, eggNOG orthology, GO, EC, KEGG, Pfam, IDR/disordered-binding/linker regions, FuzDrop regions, AggrescanAI aggregation-prone regions, and ELM/DEGRONOPEDIA degron candidates into the report tables.
- Gene, protein name, or UniProt accession: fetch UniProtKB JSON through the UniProt REST API, then emit UniProt summary and feature rows.
- Mixed evidence: keep all sources, preserve source-specific evidence, and avoid overwriting stronger curated UniProt annotations with lower-confidence heuristic motifs.

3. Read references as needed.
- Read `references/output-schema.md` before changing report columns or interpreting output TSVs.
- Read `references/source-priority.md` before merging UniProt, InterProScan6, eggNOG, and heuristic motif evidence.
- Read `references/inference-patterns.md` for command examples.

4. Run the report script.

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --fasta proteins.fa \
  --annotation-result-json output/protein-domain-motif-annotation/proteins/protein_domain_motif_annotation.result.json \
  --idr-result-json output/protein-idr-disorder-annotation/proteins/protein_idr_disorder_annotation.result.json \
  --degron-result-json output/protein-degron-annotation/proteins/protein_degron_annotation.result.json \
  --outdir output/protein-annotation-report/proteins
```

For a known gene or UniProt ID:

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  --gene TP53 \
  --organism human \
  --outdir output/protein-annotation-report/TP53
```

5. Inspect outputs.
- `protein_annotation_summary.tsv`: one row per protein/query.
- `protein_annotation_features.tsv`: one row per feature, domain, motif, site, or orthology/function evidence item.
- `protein_annotation_report.json`: run metadata, source files, warnings, errors, and output paths.

## Command Surface

```bash
python skills/protein-annotation-report/scripts/protein_annotation_report.py \
  [--sequence <AA_SEQUENCE> --sequence-name <LABEL>] \
  [--fasta <PROTEIN_FASTA>] \
  [--uniprot <ACCESSION>] \
  [--gene <GENE_SYMBOL>] \
  [--protein-name <TEXT>] \
  [--organism human|mouse|rat|<NCBI_TAXON_ID>] \
  [--raw-uniprot-json <UNIPROT_JSON>] \
  [--save-raw-uniprot] \
  [--all-uniprot-features] \
  [--interpro-tsv <INTERPROSCAN_TSV>] \
  [--eggnog-annotations <PREFIX.emapper.annotations>] \
  [--idr-summary-tsv <protein_idr_summary.tsv>] \
  [--idr-regions-tsv <protein_idr_regions.tsv>] \
  [--llps-summary-tsv <protein_llps_summary.tsv>] \
  [--llps-features-tsv <protein_llps_features.tsv>] \
  [--degron-features-tsv <protein_degron_features.tsv>] \
  [--features-tsv <FEATURES_TSV>] \
  [--motifs-tsv <MOTIFS_TSV>] \
  [--annotation-result-json <protein_domain_motif_annotation.result.json>] \
  [--idr-result-json <protein_idr_disorder_annotation.result.json>] \
  [--degron-result-json <protein_degron_annotation.result.json>] \
  [--outdir <OUTDIR>] \
  [--run-id <LABEL>] \
  [--no-uniprot] \
  [--allow-ambiguous-aa]
```

## Output Rules

- Use 1-based closed residue coordinates in normalized output whenever the source convention is known.
- Keep source provenance in every feature row through `source`, `database`, `evidence`, and `note`.
- Export functional/structural UniProt feature types by default; add `--all-uniprot-features` when variants, conflicts, and other sequence-record features are needed.
- Treat local regex motif hits as candidates, not confirmed functional sites.
- Treat eggNOG descriptions as orthology-based functional transfer, not direct experimental evidence.
- Treat IDR/disorder regions as threshold-derived predicted sequence features and preserve the source threshold in `note`.
- Treat FuzDrop LLPS regions and AggrescanAI aggregation-prone regions as predicted sequence features, not curated experimental annotations.
- Treat ELM/DEGRONOPEDIA degron matches as candidate degradation signals unless supported by PTM, disorder/accessibility, conservation, localization, structural exposure, or experimental evidence.
- Preserve no-hit/empty-feature cases as valid reports with zero feature rows and warnings when appropriate.

## Failure And Recovery

- If UniProt lookup fails for a gene, retry with `--uniprot` if the accession is known, or use `--fasta --no-uniprot`.
- If a protein name resolves ambiguously, ask for organism or UniProt accession.
- If InterProScan6/eggNOG files are missing, use `protein-domain-motif-annotation` to generate them first.
- If IDR/disorder/LLPS files are missing, use `protein-idr-disorder-annotation` to generate them first.
- If degron files are missing, use `protein-degron-annotation` to generate them first.
- If imported motif TSVs came from the old sequence analysis script, keep the default `--imported-motif-base zero-based-half-open`; use `--imported-motif-base one-based-closed` only for already-normalized motif files.

## References

- `references/output-schema.md`
- `references/source-priority.md`
- `references/inference-patterns.md`

## Scripts

- `scripts/protein_annotation_report.py`
