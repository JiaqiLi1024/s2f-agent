#!/usr/bin/env bash
set -euo pipefail

# Review paths and database choices before running.
QUERY_FASTA='skills-testbed/outputs/protein-conservation-assessment-plan-default/normalized_input.fasta'
OUTDIR='skills-testbed/outputs/protein-conservation-assessment-plan-default'

# No search backend selected. Provide --homolog-fasta or --alignment for scoring.
