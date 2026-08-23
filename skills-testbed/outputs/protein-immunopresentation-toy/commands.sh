#!/usr/bin/env bash
set -euo pipefail

# IEDB legacy Tools-API supports POST for MHC-I binding and processing.
# Review rate limits and privacy before submitting unpublished sequences.
curl --data 'method=netmhcpan_el&sequence_text=<FASTA_OR_SEQUENCE>&allele=HLA-A*02:01,HLA-B*07:02&length=9' 'https://tools-cluster-interface.iedb.org/tools_api/mhci/'

# Next-generation metadata for current MHC-I predictors:
curl -L 'https://api-nextgen-tools.iedb.org/api/v1/mhci'

# Local next-generation pipeline route based on the provided pepline notes:
conda create -n IEDB python=3.10 -y
conda activate IEDB
pip install -r requirements.txt
PIP_CONSTRAINTS=pip_constraints.txt pip install -r requirements.txt
pip install numpy==1.24.4
python fasta_to_json.py input_sequence.fasta output.json
python3 src/tcell_mhci.py -j output.json --split --split-dir ./test/
python IEDB_predict.py job_descriptions.json

# Import downloaded/API/local results back into the standardized report:
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta input_sequence.fasta \
  --api-result-tsv <IEDB_MHCI_TSV> \
  --processing-result-tsv <IEDB_PROCESSING_TSV> \
  --api-result-json <aggregated_result.json> \
  --outdir output/protein-immunopresentation-annotation/<RUN_ID>
