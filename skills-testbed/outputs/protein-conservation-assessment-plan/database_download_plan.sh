#!/usr/bin/env bash
set -euo pipefail

# Do not run this script until the user has approved the database choice, size, and destination.
DB_DIR='/tmp/protein_conservation_db'
mkdir -p "$DB_DIR"

# Swiss-Prot is small enough for testing and reviewed-sequence searches.
curl -L -o "$DB_DIR/uniprot_sprot.fasta.gz" https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz
gunzip -k "$DB_DIR/uniprot_sprot.fasta.gz"
# Use --target-db "$DB_DIR/uniprot_sprot.fasta"
