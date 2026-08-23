# Protein IDR Disorder Annotation Playbook

Use this playbook when a task needs intrinsic disorder, IDR, disordered binding, linker, redox-sensitive disorder, LLPS, FuzDrop, AggrescanAI, aggregation-prone regions, or residue-profile visualization from protein sequences, FASTA files, or UniProt accessions.

## Inputs

- Amino-acid sequence, protein FASTA, or UniProt accession.
- Tool selection: `metapredict`, `aiupred`, `iupred3`, `fuzdrop`, `aggrescanai`, or a comma/plus-separated combination.
- Optional thresholds, region length, and merge gap.
- Output root and run ID.

## Dry Run

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --tools metapredict,aiupred \
  --outdir output/protein-idr-disorder-annotation/<RUN_ID>
```

## Execute metapredict

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --tools metapredict \
  --execute \
  --outdir output/protein-idr-disorder-annotation/<RUN_ID>
```

## Execute AIUPred CLI

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --tools aiupred \
  --aiupred-binding \
  --aiupred-linker \
  --aiupred-force-cpu \
  --execute \
  --outdir output/protein-idr-disorder-annotation/<RUN_ID>
```

## Execute IUPred3 REST

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --uniprot <ACCESSION> \
  --tools iupred3 \
  --iupred3-type long \
  --execute \
  --outdir output/protein-idr-disorder-annotation/<ACCESSION>
```

## Inspect Outputs

- `protein_idr_summary.tsv`: one row per protein/query.
- `protein_idr_regions.tsv`: one row per IDR/binding/linker/redox region.
- `protein_idr_residue_scores.tsv`: residue-level normalized scores.
- `protein_llps_summary.tsv`: one row per protein/query with pLLPS and aggregation metrics.
- `protein_llps_features.tsv`: FuzDrop and AggrescanAI region features.
- `plots/*.html` and `plots/*.svg`: residue score profiles or LLPS feature maps.
- `protein_idr_disorder_annotation.result.json`: command plan, source files, warnings, errors, and output paths.

## Import LLPS Evidence

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --tools fuzdrop+aggrescanai \
  --fuzdrop-json <FUZDROP_JSON> \
  --aggrescanai-csv <AGGRESCANAI_CSV> \
  --execute \
  --outdir output/protein-idr-disorder-annotation/<RUN_ID>
```

## Local IUPred3 Without Batch Wrapper

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --tools iupred3 \
  --iupred3-local-bin <IUPRED3_SCRIPT> \
  --iupred3-local-input-format fasta \
  --execute \
  --outdir output/protein-idr-disorder-annotation/<RUN_ID>
```
