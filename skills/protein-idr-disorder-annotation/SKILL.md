---
name: protein-idr-disorder-annotation
description: Predict and annotate intrinsically disordered regions (IDRs), residue-level disorder scores, disordered binding regions, flexible linkers, redox-sensitive disorder, LLPS/liquid-liquid phase separation features, and aggregation-prone regions from amino-acid sequences, protein FASTA files, or UniProt accessions using metapredict, AIUPred, IUPred3, FuzDrop, AggrescanAI, and optional gget ELM context. Use when Codex needs to set up, run, normalize, visualize, or summarize protein disorder/IDR/LLPS workflows.
---

# Protein IDR Disorder Annotation

## Overview

Use this skill for protein intrinsic disorder and LLPS-adjacent sequence-property workflows. It plans or runs metapredict, AIUPred, IUPred3, FuzDrop, and AggrescanAI paths, then normalizes residue-level scores, IDR regions, LLPS features, aggregation-prone regions, and profile plots into standard TSV/JSON/HTML/SVG outputs.

This skill is for IDR/disorder, disordered binding, linker, redox-sensitive disorder, LLPS, and aggregation-prone-region analysis. Use `protein-domain-motif-annotation` for InterProScan6/eggNOG domain or orthology annotation, and use `protein-annotation-report` when the user wants a broader annotation report that combines IDR/LLPS outputs with UniProt/domain/motif tables.

## Workflow

1. Confirm input and tool scope.
- Use `--sequence` for one raw amino-acid sequence.
- Use `--fasta` for one or more protein FASTA files or proteome-scale runs.
- Use `--uniprot` when IUPred3 REST should be called by accession.
- Use metapredict for fast local IDR/disorder and pLDDT-adjacent disorder confidence workflows.
- Use AIUPred for neural-network disorder, binding, flexible linker, and redox-sensitive predictions.
- Use IUPred3 REST for accession-based IUPred long/short/glob predictions; use a local IUPred3 install for raw sequence batches when available.
- Use FuzDrop for droplet-state/LLPS region evidence; import downloaded JSON unless the user can provide a valid reCAPTCHA token for API submission.
- Use AggrescanAI for residue-level aggregation-prone region evidence; import its Colab/downloaded CSV or run a local runner script when available.

2. Choose execution mode.
- Default to dry-run command planning unless the user explicitly wants to execute.
- Use `--execute` only after checking that required binaries, Python packages, Nextflow, or network access are available.
- For new machines without conda/mamba, prefer a local venv or Miniforge/Miniconda install after user approval; see `references/setup-and-troubleshooting.md`.

3. Read references as needed.
- Read `references/tool-selection.md` before choosing metapredict, AIUPred, IUPred3, or gget ELM.
- Read `references/setup-and-troubleshooting.md` before writing install or environment commands.
- Read `references/output-schema.md` before interpreting TSV outputs.
- Read `references/inference-patterns.md` for concrete command patterns.

4. Run the wrapper.

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools metapredict,aiupred \
  --outdir output/protein-idr-disorder-annotation/proteins
```

Run with execution after dependencies are ready:

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools metapredict,aiupred \
  --aiupred-binding \
  --aiupred-linker \
  --execute \
  --outdir output/protein-idr-disorder-annotation/proteins
```

Use IUPred3 REST for a UniProt accession:

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --uniprot P04637 \
  --tools iupred3 \
  --iupred3-type long \
  --execute \
  --outdir output/protein-idr-disorder-annotation/P04637
```

5. Inspect outputs.
- `protein_idr_summary.tsv`: one row per protein/query.
- `protein_idr_regions.tsv`: one row per called IDR, binding region, linker, or redox-sensitive region.
- `protein_idr_residue_scores.tsv`: residue-level normalized scores.
- `protein_llps_summary.tsv`: LLPS and aggregation summary metrics.
- `protein_llps_features.tsv`: FuzDrop regions and AggrescanAI aggregation-prone regions.
- `plots/*.html` and `plots/*.svg`: built-in profile or feature-map visualizations.
- `protein_idr_disorder_annotation.result.json`: command plan, execution status, warnings, errors, and output paths.

## Command Surface

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  [--sequence <AA_SEQUENCE> --sequence-name <LABEL>] \
  [--fasta <PROTEIN_FASTA>] \
  [--uniprot <ACCESSION>] \
  [--tools metapredict,aiupred,iupred3,fuzdrop,aggrescanai] \
  [--execute] \
  [--outdir <OUTDIR>] \
  [--disorder-threshold 0.5] \
  [--min-region-length 5] \
  [--merge-gap 2] \
  [--metapredict-plot] \
  [--aiupred-mode cli|nextflow] \
  [--aiupred-binding] \
  [--aiupred-linker] \
  [--aiupred-redox] \
  [--aiupred-force-cpu] \
  [--aiupred-profile conda,cpu|docker|docker_cpu] \
  [--iupred3-type long|short|glob] \
  [--iupred3-json <LOCAL_JSON>] \
  [--iupred3-local-bin <BIN>] \
  [--iupred3-local-input-format fasta|table] \
  [--fuzdrop-json <FUZDROP_JSON>] \
  [--fuzdrop-captcha-token <TOKEN>] \
  [--aggrescanai-csv <AGGRESCANAI_CSV>] \
  [--aggrescanai-script <LOCAL_RUNNER>] \
  [--aggrescanai-threshold 0.3] \
  [--no-iupred3-rest] \
  [--no-plots]
```

## Output Rules

- Use 1-based residue coordinates in normalized TSV outputs.
- `--tools` accepts comma or plus separators, for example `metapredict,aiupred` or `metapredict+aiupred+aggrescanai`.
- Treat IDR calls as threshold-derived regions; report the threshold used.
- Do not collapse metapredict, AIUPred, and IUPred3 into a single consensus unless the user asks for consensus.
- Use `metapredict` and `AIUPred` outputs as local predictions; use IUPred3 REST as an accession-based service with network dependency.
- Without a custom `iupred_qt.py` batch wrapper, use `--iupred3-local-input-format fasta`: the script writes one FASTA per record and runs the local IUPred3 binary/script once per sequence.
- Use `--iupred3-local-input-format table` only for local wrappers that expect tab-delimited `identifier<TAB>sequence` input and emit comma-separated IUPred/ANCHOR scores.
- Treat gget ELM output as motif context that can be filtered by disorder, not as an IDR predictor.
- Treat FuzDrop and AggrescanAI evidence as predicted LLPS/aggregation sequence features, not curated experimental annotations.
- Built-in visualizations are dependency-light HTML/SVG files modeled after the IUPred3 profile plot pattern: residue score trace, threshold line, and highlighted predicted regions.

## Failure And Recovery

- If metapredict import or CLI fails after mixed conda/pip installs, rebuild a clean environment with conda-managed Python/numpy/torch before installing metapredict.
- If AIUPred GPU execution is unstable or unavailable, use `--aiupred-force-cpu` for CLI or `--aiupred-profile conda,cpu`/`docker_cpu` for Nextflow.
- If IUPred3 REST fails, retry once; for raw sequences or proteomes use local IUPred3 or AIUPred/metapredict.
- If the user asks for ELM motifs filtered by disorder, run gget ELM separately and combine with `protein-annotation-report` or a downstream join by residue interval.
- If FuzDrop API submission fails because of reCAPTCHA, ask the user to download JSON/results from the FuzDrop web UI and pass `--fuzdrop-json`.
- If AggrescanAI local execution is too heavy, use its Colab output CSV and pass `--aggrescanai-csv`.

## References

- `references/tool-selection.md`
- `references/setup-and-troubleshooting.md`
- `references/output-schema.md`
- `references/inference-patterns.md`

## Scripts

- `scripts/protein_idr_disorder_annotation.py`
