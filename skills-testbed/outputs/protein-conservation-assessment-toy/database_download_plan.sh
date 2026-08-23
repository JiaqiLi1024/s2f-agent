#!/usr/bin/env bash
set -euo pipefail

# Do not run this script until the user has approved the database choice, size, and destination.
DB_DIR="${HOME}/biodata/protein_conservation"
mkdir -p "$DB_DIR"

# No database selected. Re-run with --db-choice swissprot|uniref90|uniref50|uniprot-reference-proteomes|custom.
