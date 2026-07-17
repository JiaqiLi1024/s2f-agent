# Protein Immunopresentation Annotation Playbook

Use this playbook for MHC-I candidate presentation annotation from protein sequences, multi-protein FASTA files, local IEDB Next-Generation TC1/qinti2023-IEDB outputs, optional IEDB Class I API outputs, and context feature TSVs from other protein skills.

## Dry-Run Local Plan

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta <PROTEINS_FASTA> \
  --alleles 'HLA-A*02:01,HLA-B*07:02' \
  --peptide-lengths 8,9,10,11 \
  --outdir output/protein-immunopresentation-annotation/<RUN_ID>_plan
```

Inspect `local_iedb/iedb_ng_tc1_input.json`, `local_iedb/local_pipeline_plan.sh`, `api_requests/`, and `commands.sh`.

## Execute Local IEDB NG TC1

This requires the official IEDB Next-Generation TC1 package containing `src/tcell_mhci.py`. The current official `LATEST` README reports `0.1.5-beta`, distributed as `IEDB_NG_TC1-0.1.5-beta.tar.gz`. The qinti2023/IEDB repository provides wrapper scripts and example output, not the official tool itself.

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta <PROTEINS_FASTA> \
  --alleles 'HLA-A*02:01,HLA-B*07:02' \
  --peptide-lengths 8,9,10,11 \
  --iedb-local-tools-dir <IEDB_NG_TC1_DIR> \
  --execute-local \
  --local-workdir output/protein-immunopresentation-annotation/<RUN_ID>_iedb_work \
  --outdir output/protein-immunopresentation-annotation/<RUN_ID>_local
```

Add `--iedb-wrapper-repo <qinti2023_IEDB_REPO>` only when reproducing the original qinti `IEDB_predict.py` flow.

## Import Local Aggregate JSON

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta <PROTEINS_FASTA> \
  --local-result-json <IEDB_WORKDIR>/aggregate/aggregated_result.json \
  --outdir output/protein-immunopresentation-annotation/<RUN_ID>_import
```

## Import IEDB Results And Context

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta <PROTEINS_FASTA> \
  --api-result-tsv <IEDB_MHCI_TSV> \
  --processing-result-tsv <IEDB_PROCESSING_TSV> \
  --immunogenicity-result-tsv <IEDB_IMMUNOGENICITY_TSV> \
  --localization-features-tsv <protein_localization_features.tsv> \
  --tm-features-tsv <protein_tm_topology_features.tsv> \
  --idr-regions-tsv <protein_idr_regions.tsv> \
  --domain-features-tsv <protein_domain_features.tsv> \
  --conservation-features-tsv <protein_conservation_regions.tsv> \
  --outdir output/protein-immunopresentation-annotation/<RUN_ID>
```

## Execute IEDB Legacy API

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta <PROTEINS_FASTA> \
  --alleles 'HLA-A*02:01,HLA-B*07:02' \
  --binding-predictors netmhcpan_el,netmhcpan_ba \
  --peptide-lengths 8,9,10,11 \
  --execute-api \
  --execute-processing \
  --outdir output/protein-immunopresentation-annotation/<RUN_ID>_api
```

Only use this after confirming remote sequence submission is acceptable.

## Outputs

- `mhci_peptides.tsv`
- `mhci_binding_predictions.tsv`
- `mhci_processing_predictions.tsv`
- `mhci_immunogenicity_predictions.tsv`
- `immunopresentation_candidates.tsv`
- `protein_immunopresentation_summary.tsv`
- `protein_immunopresentation_annotation.result.json`
- `local_iedb/iedb_ng_tc1_input.json`
- `local_iedb/local_pipeline_plan.sh`
- `local_iedb/local_pipeline_manifest.json`
- `api_requests/`
- `commands.sh`
