#!/usr/bin/env bash
set -euo pipefail

# metapredict
metapredict-predict-disorder skills-testbed/outputs/protein-idr-disorder-plus-tools-dryrun/normalized_input.fasta -o skills-testbed/outputs/protein-idr-disorder-plus-tools-dryrun/metapredict/metapredict_disorder.tsv
metapredict-predict-idrs skills-testbed/outputs/protein-idr-disorder-plus-tools-dryrun/normalized_input.fasta -o skills-testbed/outputs/protein-idr-disorder-plus-tools-dryrun/metapredict/metapredict_idrs.tsv

# aiupred
aiupred -i skills-testbed/outputs/protein-idr-disorder-plus-tools-dryrun/normalized_input.fasta -o skills-testbed/outputs/protein-idr-disorder-plus-tools-dryrun/aiupred/aiupred.tsv

