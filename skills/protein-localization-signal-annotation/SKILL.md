---
name: protein-localization-signal-annotation
description: Predict, import, normalize, and summarize protein subcellular localization and targeting-signal annotations from amino-acid sequences, protein FASTA files, DeepLoc 2.1 outputs, SignalP 6.0 outputs, or TargetP 2.0 outputs. Use when Codex needs eukaryotic subcellular localization, membrane association, sorting signals, signal peptides, cleavage sites, mitochondrial/chloroplast/thylakoid transit peptides, secretory-pathway evidence, or standardized TSV/JSON reports for unknown protein sequences.
---

# Protein Localization Signal Annotation

## Overview

Use this skill for sequence-based protein localization and targeting-signal workflows. It plans or imports DeepLoc 2.1, SignalP 6.0, and TargetP 2.0 predictions, validates amino-acid FASTA input, and writes standardized summary, feature, score, JSON, and simple HTML/SVG plot outputs.

Use `protein-tm-topology-annotation` for transmembrane topology, DeepTMHMM/TMHMM residue states, beta-barrel topology, or inside/outside topology as the primary task. Use this skill when the primary task is whole-protein localization or N-terminal targeting signals.

## Workflow

1. Choose input.
- Use `--sequence` or `--fasta` for unknown protein sequences.
- Use `--deeploc-output`, `--signalp-output`, `--signalp-gff3`, or `--targetp-output` when DTU web/local predictions already exist.
- Keep sequence IDs short and stable because they become `query_id` values in all TSVs.

2. Choose tools.
- Use DeepLoc 2.1 for eukaryotic multi-label subcellular localization, membrane association, and sorting-signal evidence.
- Use SignalP 6.0 for signal peptide type and cleavage-site prediction.
- Use TargetP 2.0 for N-terminal SP, mTP, cTP, and lTP presequence prediction; set `--targetp-organism plant` for plastid-containing organisms and `non-plant` otherwise.

3. Choose execution mode.
- Direct local execution is preferred when the user has already installed or obtained licensed DeepLoc/SignalP/TargetP software; use `--deeploc-command-template`, `--signalp-command-template`, or `--targetp-command-template`.
- Programmatic service execution may be possible through BioLib or another hosted runner when the specific app is available and credentials are configured; pass the exact invocation through a command template.
- Import mode is the fallback: submit to DTU web or run software outside Codex, then import result tables.
- Without command templates, the wrapper writes web-submission FASTA files and `commands.sh` with service URLs and import instructions.

4. Read references as needed.
- Read `references/tool-selection.md` before deciding tool combinations.
- Read `references/output-schema.md` before changing output columns.
- Read `references/inference-patterns.md` for command examples.
- Read `references/setup-and-troubleshooting.md` for local software and DTU web submission constraints.

5. Run the wrapper.

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --tools deeploc,signalp,targetp \
  --outdir output/protein-localization-signal-annotation/query1
```

After importing downloaded DTU result files:

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta proteins.fa \
  --deeploc-output results/deeploc/results.tsv \
  --signalp-output results/signalp/prediction_results.txt \
  --targetp-output results/targetp/prediction_results.txt \
  --outdir output/protein-localization-signal-annotation/proteins
```

6. Inspect outputs.
- `protein_localization_summary.tsv`: one row per protein/query.
- `protein_localization_features.tsv`: localization, membrane association, sorting-signal, signal-peptide, or targeting-peptide features.
- `protein_localization_scores.tsv`: source probabilities and scores when present.
- `plots/*.html` and `plots/*.svg`: compact standardized run summary.
- `protein_localization_signal_annotation.result.json`: command plan, source files, warnings, errors, and output paths.

## Command Surface

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  [--sequence <AA_SEQUENCE> --sequence-name <LABEL>] \
  [--fasta <PROTEIN_FASTA>] \
  [--tools deeploc,signalp,targetp] \
  [--deeploc-output <DEEPLOC_TABLE>] \
  [--signalp-output <SIGNALP_TABLE>] \
  [--signalp-gff3 <SIGNALP_GFF3>] \
  [--targetp-output <TARGETP_TABLE>] \
  [--deeploc-command-template "<COMMAND WITH {input} AND {outdir}>"] \
  [--signalp-command-template "<COMMAND WITH {input} AND {outdir}>"] \
  [--targetp-command-template "<COMMAND WITH {input} AND {outdir}>"] \
  [--deeploc-model fast|slow] \
  [--deeploc-format short|long] \
  [--signalp-mode fast|slow] \
  [--signalp-organism eukarya|other] \
  [--targetp-organism plant|non-plant] \
  [--targetp-format short|long] \
  [--execute] \
  [--outdir <OUTDIR>] \
  [--no-plots] \
  [--allow-ambiguous-aa] \
  [--sanitize-invalid-to-x]
```

## Output Rules

- Use 1-based closed residue coordinates when cleavage-site or GFF3-derived intervals are available.
- Treat DeepLoc localizations as predicted multi-label localization evidence, not curated experimental annotation.
- Treat SignalP and TargetP signal/presequence calls as N-terminal targeting-signal predictions. SignalP alone supports secretory pathway entry, not final secretion.
- Preserve source provenance in every row through `source`, `evidence`, and `note`.
- Keep DTU web outputs as source files when possible; wrapper parsing is intentionally permissive because downloaded table headers can vary.
- For transmembrane topology or beta-barrel state plots, route to `protein-tm-topology-annotation` and merge later in `protein-annotation-report` if needed.

## Failure And Recovery

- If local DTU tools or BioLib runners are unavailable, run without `--execute`, upload `web_submission/*.fasta` to the service pages, then import downloaded output files.
- If DeepLoc output is long/graphical only, download or export the summary/probability table before importing.
- If SignalP predicts a signal peptide, do not conclude final extracellular localization without DeepLoc, TargetP, TM topology, GPI-anchor, and retention-signal context.
- If TargetP organism context is unclear, use `non-plant` unless the organism has chloroplasts/plastids.
- If sequences contain non-standard residues, prefer `--sanitize-invalid-to-x` for web-server compatibility and record the warning.

## References

- `references/tool-selection.md`
- `references/output-schema.md`
- `references/inference-patterns.md`
- `references/setup-and-troubleshooting.md`

## Scripts

- `scripts/protein_localization_signal_annotation.py`
