---
name: protein-tm-topology-annotation
description: Predict, import, normalize, and visualize protein transmembrane topology annotations from amino-acid sequences, protein FASTA files, TMHMM outputs, DeepTMHMM outputs, or GFF3 files. Use when Codex needs TM helix, beta-barrel strand, inside/outside/periplasmic state, signal peptide overlap, per-residue topology state tables, TMHMM/DeepTMHMM-style topology plots, or standardized TSV/JSON reports for membrane protein regions.
---

# Protein TM Topology Annotation

## Overview

Use this skill for transmembrane region and topology annotation. It plans or runs TMHMM and DeepTMHMM workflows when local/remote runners are available, imports their GFF3 or text outputs, expands region calls to one row per residue, and writes dependency-light HTML/SVG plots for every protein/source.

Prefer DeepTMHMM for current topology calls, especially when beta-barrel proteins may be present. Keep TMHMM as a legacy alpha-helical comparator or when the user explicitly requests TMHMM-compatible output.

## Workflow

1. Choose input.
- Use `--sequence` or `--fasta` for protein sequence input.
- Use `--deeptmhmm-gff3`, `--tmhmm-gff3`, `--gff3`, or `--tmhmm-output` when predictions already exist.
- Use `--native-plot` to record plot files produced by the upstream service, but still generate standardized plots from parsed states.

2. Choose execution mode.
- Import mode is most reproducible: pass DeepTMHMM or TMHMM GFF3 files and generate normalized outputs.
- TMHMM local execution can be planned or run with `--tmhmm-bin`.
- DeepTMHMM execution is environment-dependent; provide `--deeptmhmm-command-template` with `{input}` and `{outdir}` placeholders when a BioLib or local runner is available.

3. Read references as needed.
- Read `references/tool-selection.md` before deciding between TMHMM and DeepTMHMM.
- Read `references/output-schema.md` before changing output columns.
- Read `references/inference-patterns.md` for common command shapes.
- Read `references/setup-and-troubleshooting.md` when installing or running external tools.

4. Run the wrapper.

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta proteins.fa \
  --deeptmhmm-gff3 results/deeptmhmm/TMRs.gff3 \
  --tmhmm-output results/tmhmm/tmhmm.long.txt \
  --outdir output/protein-tm-topology-annotation/proteins
```

For raw sequence with a local TMHMM command:

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --tools tmhmm \
  --tmhmm-bin tmhmm \
  --execute \
  --outdir output/protein-tm-topology-annotation/query1_tmhmm
```

5. Inspect outputs.
- `protein_tm_topology_summary.tsv`: one row per protein/query.
- `protein_tm_topology_regions.tsv`: normalized TMHMM/DeepTMHMM regions using 1-based closed coordinates.
- `protein_tm_topology_residue_states.tsv`: one row per residue per source.
- `plots/*.html` and `plots/*.svg`: standardized topology state plots for each protein/source.
- `protein_tm_topology_annotation.result.json`: command plan, source files, warnings, errors, and output paths.

## Command Surface

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  [--sequence <AA_SEQUENCE> --sequence-name <LABEL>] \
  [--fasta <PROTEIN_FASTA>] \
  [--tools tmhmm,deeptmhmm] \
  [--tmhmm-gff3 <TMHMM_GFF3>] \
  [--deeptmhmm-gff3 <DEEPTMHMM_GFF3>] \
  [--gff3 <SOURCE:TOPOLOGY_GFF3>] \
  [--tmhmm-output <TMHMM_LONG_OUTPUT>] \
  [--tmhmm-bin tmhmm] \
  [--tmhmm-extra-args "<ARGS>"] \
  [--deeptmhmm-command-template "<COMMAND WITH {input} AND {outdir}>"] \
  [--native-plot <SOURCE:PLOT_FILE>] \
  [--execute] \
  [--outdir <OUTDIR>] \
  [--no-plots] \
  [--allow-ambiguous-aa]
```

## Output Rules

- Use 1-based closed residue coordinates in all normalized region and residue outputs.
- Treat GFF3 `start` and `end` as protein residue coordinates, not genomic coordinates.
- Expand every parsed region into per-residue state calls. Uncovered residues are `unknown`.
- Preserve source provenance through `source`, `evidence`, `attributes`, and `note`.
- Do not infer posterior probabilities from GFF3. GFF3-derived plots are topology state plots; TMHMM posterior probability curves require native probability data or upstream native plots.
- For multi-sequence DeepTMHMM web runs, expect no native web plots; generate per-protein standardized plots from GFF3 instead.
- Treat N-terminal TMHMM helices cautiously because TMHMM documentation warns they can be signal peptides.

## Failure And Recovery

- If DeepTMHMM web/BioLib output contains only GFF3 and no plots, use the wrapper plots as the standardized visualization.
- If TMHMM is unavailable locally, run the wrapper without `--execute` to create a command plan or import existing TMHMM long output.
- If DeepTMHMM command-line usage differs across installations, pass the exact command with `--deeptmhmm-command-template`.
- If GFF3 feature names differ, keep the original type in `evidence`; the parser maps common variants such as `TMhelix`, `transmembrane_helix`, `inside`, `outside`, `periplasmic`, `signal`, and beta-strand terms.

## References

- `references/tool-selection.md`
- `references/output-schema.md`
- `references/inference-patterns.md`
- `references/setup-and-troubleshooting.md`

## Scripts

- `scripts/protein_tm_topology_annotation.py`
