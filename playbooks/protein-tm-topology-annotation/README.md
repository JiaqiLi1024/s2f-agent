# Protein TM Topology Annotation Playbook

Use this playbook when a task needs transmembrane helix, beta-barrel, inside/outside/periplasmic topology, per-residue topology states, or TMHMM/DeepTMHMM-style plots from protein sequences or prediction outputs.

## Inputs

- Amino-acid sequence, protein FASTA, TMHMM long output, TMHMM GFF3, DeepTMHMM GFF3, or generic topology GFF3.
- Optional tool selection: `tmhmm`, `deeptmhmm`, or both.
- Optional native plot artifacts to record.
- Output root and run ID.

## Import DeepTMHMM

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --tools deeptmhmm \
  --deeptmhmm-gff3 <DEEPTMHMM_GFF3> \
  --outdir output/protein-tm-topology-annotation/<RUN_ID>
```

## Import TMHMM

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --tools tmhmm \
  --tmhmm-output <TMHMM_LONG_OUTPUT> \
  --outdir output/protein-tm-topology-annotation/<RUN_ID>
```

## Compare Both Tools

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta <PROTEIN_FASTA> \
  --tools tmhmm+deeptmhmm \
  --tmhmm-output <TMHMM_LONG_OUTPUT> \
  --deeptmhmm-gff3 <DEEPTMHMM_GFF3> \
  --outdir output/protein-tm-topology-annotation/<RUN_ID>
```

## Inspect Outputs

- `protein_tm_topology_summary.tsv`: one row per protein/query.
- `protein_tm_topology_regions.tsv`: normalized topology intervals.
- `protein_tm_topology_residue_states.tsv`: one row per residue per source.
- `plots/*.html` and `plots/*.svg`: standardized topology state plots.
- `protein_tm_topology_annotation.result.json`: command plan, source files, warnings, errors, and output paths.
