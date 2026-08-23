# Inference Patterns

## Direct Execution With Configured Backends

When local licensed tools or hosted runners are configured, use command templates and `--execute`:

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --tools deeploc+signalp+targetp \
  --deeploc-command-template "<DEEPLOC COMMAND WITH {input} AND {outdir}>" \
  --signalp-command-template "<SIGNALP COMMAND WITH {input} AND {outdir}>" \
  --targetp-command-template "<TARGETP COMMAND WITH {input} AND {outdir}>" \
  --execute \
  --outdir output/protein-localization-signal-annotation/query1_direct
```

## Create Web-Submission Inputs

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --tools deeploc+signalp+targetp \
  --outdir output/protein-localization-signal-annotation/query1
```

Upload the FASTA files under `web_submission/` to the matching DTU services, then rerun with downloaded output tables.

## Import DeepLoc, SignalP, And TargetP Tables

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta proteins.fa \
  --deeploc-output results/deeploc/deeploc_results.tsv \
  --signalp-output results/signalp/prediction_results.txt \
  --targetp-output results/targetp/prediction_results.txt \
  --outdir output/protein-localization-signal-annotation/proteins
```

## Import SignalP GFF3

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta proteins.fa \
  --tools signalp \
  --signalp-gff3 results/signalp/prediction_results.gff3 \
  --outdir output/protein-localization-signal-annotation/signalp_gff3
```

## Run Existing Local Commands

Use command templates when the user already has licensed/local runners installed. Exact commands vary by package version and installation:

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta proteins.fa \
  --deeploc-command-template "deeploc2 --fasta {input} --output {outdir}" \
  --signalp-command-template "signalp6 --fastafile {input} --output_dir {outdir} --organism {signalp_organism} --mode {signalp_mode}" \
  --targetp-command-template "targetp -fasta {input} -org {targetp_organism} -prefix {outdir}/targetp" \
  --execute \
  --outdir output/protein-localization-signal-annotation/local_run
```

Keep tool-specific syntax in the template rather than hard-coding it into the wrapper.

## Plant Targeting Signals

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta plant_proteins.fa \
  --tools deeploc,targetp \
  --targetp-organism plant \
  --outdir output/protein-localization-signal-annotation/plant_proteins
```
