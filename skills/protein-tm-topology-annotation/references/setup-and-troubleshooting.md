# Setup And Troubleshooting

## Runtime Precheck

```bash
python --version
command -v tmhmm || true
command -v biolib || true
```

The wrapper itself uses only the Python standard library. External predictors are needed only when running predictions rather than importing existing outputs.

## TMHMM

TMHMM 2.0 is distributed by DTU Health Tech. The web service also provides downloadable binaries for supported platforms.

Use local TMHMM only when licensing and platform requirements are satisfied:

```bash
tmhmm proteins.fa > tmhmm.long.txt
```

Then normalize:

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta proteins.fa \
  --tmhmm-output tmhmm.long.txt \
  --outdir output/protein-tm-topology-annotation/tmhmm
```

If TMHMM native graphics or probability files are available, keep them as source artifacts with `--native-plot`.

## DeepTMHMM

DeepTMHMM is available through the DTU Health Tech web service and BioLib mirror. The DTU page states that multi-sequence submissions do not generate native plots, so use the wrapper to create per-protein HTML/SVG plots from GFF3.

Recommended reproducible pattern:

1. Run DeepTMHMM through the available web, BioLib, or local route.
2. Download or locate the GFF3 output.
3. Normalize with `--deeptmhmm-gff3`.

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta proteins.fa \
  --deeptmhmm-gff3 TMRs.gff3 \
  --outdir output/protein-tm-topology-annotation/deeptmhmm
```

If a command-line runner is installed and tested:

```bash
python skills/protein-tm-topology-annotation/scripts/protein_tm_topology_annotation.py \
  --fasta proteins.fa \
  --tools deeptmhmm \
  --deeptmhmm-command-template "<COMMAND USING {input} AND OPTIONAL {outdir}>" \
  --execute \
  --outdir output/protein-tm-topology-annotation/deeptmhmm
```

## Common Failures

- Empty region TSV: check that the GFF3 uses protein IDs matching the FASTA IDs and has 9 tab-delimited columns.
- State plot exists but has no residue letters: provide the original FASTA, not only GFF3.
- DeepTMHMM command runs but no GFF3 is found: inspect the DeepTMHMM output directory and pass the GFF3 explicitly with `--deeptmhmm-gff3`.
- TMHMM probability plot is requested from GFF3 only: explain that GFF3 has discrete intervals, not posterior probabilities; generate the state plot and preserve any native probability plot if available.
