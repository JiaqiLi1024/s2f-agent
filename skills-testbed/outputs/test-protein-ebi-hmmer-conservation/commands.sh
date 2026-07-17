#!/usr/bin/env bash
set -euo pipefail

# Review paths and database choices before running.
QUERY_FASTA='skills-testbed/outputs/test-protein-ebi-hmmer-conservation/normalized_input.fasta'
OUTDIR='skills-testbed/outputs/test-protein-ebi-hmmer-conservation'

# EBI HMMER API runs on EMBL-EBI hosted databases.
# The database value should be one of: refprot, uniprot, swissprot, pdb, rp15, rp35, rp55, rp75.
# Selected database: refprot
# Use the API only when network access is acceptable and results can be cited with search details.
