# Protein Localization Signal Annotation Playbook

Use this playbook when a task needs protein subcellular localization, membrane association, signal peptide, cleavage-site, TargetP presequence, or secretory-pathway evidence from amino-acid sequences or prediction outputs.

## Inputs

- Amino-acid sequence, protein FASTA, DeepLoc output table, SignalP output table/GFF3, or TargetP output table.
- Tool selection: `deeploc`, `signalp`, `targetp`, or a comma/plus-separated combination.
- Optional organism context: SignalP `eukarya|other`, TargetP `plant|non-plant`.
- Output root and run ID.

## Direct Execution

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --tools deeploc+signalp+targetp \
  --deeploc-command-template "<COMMAND WITH {input} AND {outdir}>" \
  --signalp-command-template "<COMMAND WITH {input} AND {outdir}>" \
  --targetp-command-template "<COMMAND WITH {input} AND {outdir}>" \
  --execute \
  --outdir output/protein-localization-signal-annotation/<RUN_ID>
```

Use this only when local licensed tools or hosted runners are already configured.

## Prepare Web-Submission FASTA

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --tools deeploc+signalp+targetp \
  --outdir output/protein-localization-signal-annotation/<RUN_ID>
```

Upload `web_submission/*.fasta` to the matching DTU service pages, then import downloaded outputs.

## Import Prediction Outputs

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --deeploc-output <DEEPLOC_TABLE> \
  --signalp-output <SIGNALP_TABLE> \
  --targetp-output <TARGETP_TABLE> \
  --outdir output/protein-localization-signal-annotation/<RUN_ID>
```

## Run Existing Local Commands

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --deeploc-command-template "<COMMAND WITH {input} AND {outdir}>" \
  --signalp-command-template "<COMMAND WITH {input} AND {outdir}>" \
  --targetp-command-template "<COMMAND WITH {input} AND {outdir}>" \
  --execute \
  --outdir output/protein-localization-signal-annotation/<RUN_ID>
```

## Inspect Outputs

- `protein_localization_summary.tsv`: one row per protein/query.
- `protein_localization_features.tsv`: localization, membrane, signal peptide, and targeting peptide features.
- `protein_localization_scores.tsv`: source probability rows when available.
- `plots/*.html` and `plots/*.svg`: compact standardized summary.
- `protein_localization_signal_annotation.result.json`: command plan, source files, warnings, errors, and output paths.
