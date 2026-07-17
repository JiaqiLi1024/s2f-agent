#!/usr/bin/env bash
set -euo pipefail

# DeepLoc 2.1 web submission: https://services.healthtech.dtu.dk/services/DeepLoc-2.1/
# Upload FASTA: skills-testbed/outputs/protein-localization-signal-dryrun/web_submission/deeploc_2_1_input.fasta
# Import downloaded result table with --deeploc-output <FILE>.

# SignalP 6.0 web submission: https://services.healthtech.dtu.dk/services/SignalP-6.0/
# Upload FASTA: skills-testbed/outputs/protein-localization-signal-dryrun/web_submission/signalp_6_0_input.fasta
# Import downloaded result table with --signalp-output <FILE> or GFF3 with --signalp-gff3 <FILE>.

# TargetP 2.0 web submission: https://services.healthtech.dtu.dk/services/TargetP-2.0/
# Upload FASTA: skills-testbed/outputs/protein-localization-signal-dryrun/web_submission/targetp_2_0_input.fasta
# Import downloaded result table with --targetp-output <FILE>.

