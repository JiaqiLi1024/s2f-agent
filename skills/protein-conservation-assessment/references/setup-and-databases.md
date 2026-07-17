# Setup And Databases

Use this reference before installing software, running homolog searches, or downloading protein databases.

## Dedicated Conda Environment

Prefer a separate environment for this skill:

```bash
conda create -n protein-conservation python=3.11 -y
conda activate protein-conservation
conda install -c conda-forge -c bioconda biotite matplotlib numpy mafft hmmer mmseqs2 diamond seqkit -y
```

If `mamba` is available, it can replace `conda` for faster solving. Keep this environment separate from InterProScan, eggNOG, IDR, and localization environments because bioinformatics packages often pin different dependency versions.

## Missing Conda Or Mamba

If neither `conda` nor `mamba` exists:

1. Ask the user whether to install Miniforge or Miniconda.
2. Confirm installation location, usually `$HOME/miniforge3` or `$HOME/miniconda3`.
3. Do not run an installer silently.
4. After installation, create the `protein-conservation` environment above.

Use a plain Python virtual environment only when conda-style installation is blocked, because `hmmer`, `mafft`, and `mmseqs2` are easiest to install from Bioconda.

## Database Choice

Ask before downloading any public database. Confirm:

- Which database: Swiss-Prot, UniRef90, UniRef50, UniProt Reference Proteomes, or a custom/taxon-specific protein FASTA.
- Destination directory, for example `$HOME/biodata/protein_conservation`, `/localdata/<USER>/protein_conservation`, or a project data directory.
- Available disk space.
- Whether the user already has a specific `protein.fasta` to use for alignment/search instead of downloading a public database.

Recommended defaults:

- **Small test run**: Swiss-Prot.
- **General broad homolog search**: UniRef90 if disk/network budget is acceptable.
- **Broader but smaller remote-homolog sampling**: UniRef50.
- **Taxon-aware conservation**: user-provided protein FASTA or taxonomic Reference Proteome subset.
- **Project-specific comparative analysis**: the user's curated proteomes or ortholog FASTA.

The wrapper writes `database_download_plan.sh`. Treat it as a review artifact; do not execute it until the user approves the database and destination.

## Local HMMER Search

Use local jackhmmer when a local protein FASTA is available:

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --search-backend local-hmmer \
  --target-db "$HOME/biodata/protein_conservation/uniprot_sprot.fasta" \
  --hmmer-iterations 3 \
  --evalue 1e-4 \
  --cpu 16 \
  --execute \
  --outdir output/protein-conservation-assessment/query1
```

The script imports the Stockholm MSA written by jackhmmer and maps scores to the query.

## MMseqs2 Search

Use MMseqs2 for fast first-pass search or when searching a very large local database. MMseqs2 returns hit tables; export matching target sequences to FASTA before MSA/scoring.

```bash
mmseqs easy-search query.fasta target_db_or_fasta mmseqs_hits.m8 tmp \
  --threads 16 -e 1e-4 \
  --format-output query,target,pident,alnlen,mismatch,gapopen,qstart,qend,tstart,tend,evalue,bits
```

Then create a homolog FASTA from accepted hits and run:

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --homolog-fasta homologs.fasta \
  --msa-backend auto \
  --outdir output/protein-conservation-assessment/query1
```

## EBI HMMER

EBI HMMER can run hosted searches against server-side databases. The commonly used default token is `refprot`, UniProt Reference Proteomes. Other documented tokens include `uniprot`, `swissprot`, `pdb`, `rp15`, `rp35`, `rp55`, and `rp75`.

Use hosted search only when network execution, EBI queue time, and service database provenance are acceptable. Record search details and database release when citing results.

## Reproducibility

Record these values in reports or methods sections:

- Database name, local path, download date, and release if known.
- Search backend and version (`jackhmmer -h`, `mmseqs version`, `mafft --version`).
- E-value/inclusion thresholds, iteration count, and CPU count.
- MSA backend and command.
- Homolog filtering criteria and query ID.
