# Protein Domain Motif Annotation Playbook

Use this playbook when a task needs InterProScan6, eggNOG-mapper, or both for protein FASTA annotation.

## Inputs

- Protein FASTA path.
- Tool selection: `both`, `interproscan6`, or `eggnog`.
- InterProScan6 data directory and Nextflow container profile when InterProScan6 is requested.
- eggNOG data directory when eggNOG-mapper is requested.
- Output root and run ID.

## Default Dry Run

```bash
python skills/protein-domain-motif-annotation/scripts/run_real_protein_domain_motif_annotation_workflow.py \
  --input <PROTEINS_FASTA> \
  --tools both \
  --run-id <RUN_ID> \
  --interpro-profile singularity \
  --interpro-datadir <INTERPRO_DATA_DIR> \
  --eggnog-data-dir <EGGNOG_DATA_DIR> \
  --outdir output/protein-domain-motif-annotation/<RUN_ID>
```

Inspect:

- `output/protein-domain-motif-annotation/<RUN_ID>/protein_domain_motif_annotation.result.json`
- `output/protein-domain-motif-annotation/<RUN_ID>/commands.sh`

## Execute After Validation

Add `--execute` only after confirming local environments and database paths:

```bash
python skills/protein-domain-motif-annotation/scripts/run_real_protein_domain_motif_annotation_workflow.py \
  --input <PROTEINS_FASTA> \
  --tools both \
  --run-id <RUN_ID> \
  --interpro-profile singularity \
  --interpro-datadir <INTERPRO_DATA_DIR> \
  --eggnog-data-dir <EGGNOG_DATA_DIR> \
  --outdir output/protein-domain-motif-annotation/<RUN_ID> \
  --execute
```

## Interpret Outputs

- Use InterProScan6 outputs for domain architecture, families, repeats, and functional sites.
- Use eggNOG-mapper outputs for orthology-based function, GO, KEGG, EC, COG/category, and descriptions.
- Report no-hit proteins separately from failed commands.
- Include tool versions, data directories, run ID, CPU counts, and output paths in the final summary.
