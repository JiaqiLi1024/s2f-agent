#!/usr/bin/env bash
set -euo pipefail

# Review licenses and obtain user approval before running this script.
# ELM data are distributed under the ELM academic/non-commercial license.
# DEGRONOPEDIA degron licenses vary by source; inspect the license columns before commercial use.
DB_DIR="${HOME}/biodata/protein_degron"
mkdir -p "$DB_DIR"

curl -L --fail --retry 3 --retry-delay 5 --max-time 180 -o "$DB_DIR/elms_classes.tsv" http://elm.eu.org/elms/elms_index.tsv
curl -L --fail --retry 3 --retry-delay 5 --max-time 180 -o "$DB_DIR/elm_instances.tsv" 'http://elm.eu.org/instances.tsv?q=*&taxon=&instance_logic='
curl -L --fail --retry 3 --retry-delay 5 --max-time 180 -o "$DB_DIR/elm_instances.fasta" 'http://elm.eu.org/instances.fasta?q=*&taxon=&instance_logic='
curl -L --fail --retry 3 --retry-delay 5 --max-time 180 -o "$DB_DIR/elm_interaction_domains.tsv" http://elm.eu.org/interactiondomains.tsv
curl -L --fail --retry 3 --retry-delay 5 --max-time 180 -o "$DB_DIR/DEGRONOPEDIA_degron_dataset.xlsx" https://degronopedia.com/degronopedia/download/data/DEGRONOPEDIA_degron_dataset.xlsx/
