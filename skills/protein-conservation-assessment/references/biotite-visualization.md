# Biotite MSA And Visualization

Use Biotite for Python-native sequence handling, small progressive MSA runs, and Matplotlib-based sequence graphics.

## Environment

Install Biotite in the dedicated environment:

```bash
conda activate protein-conservation
conda install -c conda-forge biotite matplotlib -y
```

For production MSA, also install MAFFT:

```bash
conda install -c conda-forge -c bioconda mafft -y
```

Biotite can wrap external MSA tools such as MAFFT through `biotite.application.mafft.MafftApp`, but the MAFFT binary still needs to be installed.

## Script Modes

Use Biotite directly for small homolog sets:

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --homolog-fasta homologs.fasta \
  --msa-backend biotite \
  --outdir output/protein-conservation-assessment/query1_biotite
```

Use MAFFT for larger homolog sets:

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --homolog-fasta homologs.fasta \
  --msa-backend mafft \
  --outdir output/protein-conservation-assessment/query1_mafft
```

Use an existing Biotite-generated or MAFFT-generated alignment:

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --alignment alignment.fasta \
  --query-id query1 \
  --outdir output/protein-conservation-assessment/query1_from_msa
```

## Visualization Guidance

Always produce the standardized conservation profile plot from the script when possible. For richer visualizations, use Biotite's `biotite.sequence.graphics` module after the standardized tables are written:

- Alignment plot for a compact selected window.
- Sequence logo for conserved motifs or user-selected regions.
- Feature map after combining conserved regions with InterPro domains or IDR regions.

For long proteins or hundreds of homologs, plot a selected residue window rather than the full alignment.
