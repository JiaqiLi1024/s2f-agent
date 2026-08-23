#!/usr/bin/env bash
set -euo pipefail

# Example local scan after reviewing/downloading ELM and DEGRONOPEDIA data:
python skills/protein-degron-annotation/scripts/protein_degron_annotation.py --fasta <PROTEINS_FASTA> --elm-classes-tsv "$DB_DIR/elms_classes.tsv" --degronopedia-xlsx "$DB_DIR/DEGRONOPEDIA_degron_dataset.xlsx" --outdir output/protein-degron-annotation/<RUN_ID>

# ELM hosted API exists but must be rate-limited: UniProt <= 1 query per 3 minutes; raw sequence <= 1 query per minute.
# Prefer local ELM TSV scans for batch annotation and reproducibility.
# DEGRONOPEDIA is an online service with one-protein-at-a-time submissions; import its downloaded xlsx output when manual web analysis is needed.
