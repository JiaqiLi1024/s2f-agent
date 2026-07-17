# Inference Patterns

## Import DeepTMHMM GFF3

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta proteins.fa \
  --tools deeptmhmm \
  --deeptmhmm-gff3 results/deeptmhmm/TMRs.gff3 \
  --outdir output/protein-tm-topology-annotation/proteins_deeptmhmm
```

## Import TMHMM Long Output

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta proteins.fa \
  --tools tmhmm \
  --tmhmm-output results/tmhmm/tmhmm.long.txt \
  --outdir output/protein-tm-topology-annotation/proteins_tmhmm
```

## Compare TMHMM And DeepTMHMM

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta proteins.fa \
  --tools tmhmm+deeptmhmm \
  --tmhmm-output results/tmhmm/tmhmm.long.txt \
  --deeptmhmm-gff3 results/deeptmhmm/TMRs.gff3 \
  --outdir output/protein-tm-topology-annotation/proteins_compare
```

## Run Local TMHMM

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta proteins.fa \
  --tools tmhmm \
  --tmhmm-bin tmhmm \
  --execute \
  --outdir output/protein-tm-topology-annotation/proteins_tmhmm
```

## Run DeepTMHMM With A Known Command Template

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta proteins.fa \
  --tools deeptmhmm \
  --deeptmhmm-command-template "biolib run DTU/DeepTMHMM --fasta {input}" \
  --execute \
  --outdir output/protein-tm-topology-annotation/proteins_deeptmhmm
```

If the local DeepTMHMM command writes to a specific output directory, include `{outdir}` in the template if supported by that runner.

## Raw Single Sequence

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --tools tmhmm \
  --tmhmm-output tmhmm.long.txt \
  --outdir output/protein-tm-topology-annotation/query1
```
