# Inference Patterns

## Wrapper Dry Run

Use this first to produce `commands.sh` and a result JSON without launching heavy workflows:

```bash
python skills/protein-domain-motif-annotation/scripts/run_real_protein_domain_motif_annotation_workflow.py \
  --input ./01_translation/M_caribbica.longest.table12.proteins.fa \
  --tools both \
  --run-id M_caribbica_table12 \
  --interpro-profile singularity \
  --interpro-datadir "$HOME/interproscan6/data" \
  --eggnog-data-dir <EGGNOG_DATA_DIR> \
  --outdir output/protein-domain-motif-annotation/M_caribbica_table12
```

Add `--execute` after confirming the environments, data directories, and container runtime:

```bash
python skills/protein-domain-motif-annotation/scripts/run_real_protein_domain_motif_annotation_workflow.py \
  --input ./01_translation/M_caribbica.longest.table12.proteins.fa \
  --tools both \
  --run-id M_caribbica_table12 \
  --interpro-profile singularity \
  --interpro-datadir "$HOME/interproscan6/data" \
  --eggnog-data-dir <EGGNOG_DATA_DIR> \
  --outdir output/protein-domain-motif-annotation/M_caribbica_table12 \
  --execute
```

## InterProScan6 Test Run

Run this once before production to initialize `--datadir` and pull/cache the selected runtime's container images locally.

With conda/mamba:

```bash
mamba create -n interpro
mamba activate interpro
mamba install nextflow=25.10.4 -c bioconda
export JAVA_HOME="$CONDA_PREFIX"
export NXF_JAVA_HOME="$CONDA_PREFIX"
```

If conda/mamba are missing, bootstrap Miniforge first:

```bash
case "$(uname)" in
  Linux) MINIFORGE_OS="Linux" ;;
  Darwin) MINIFORGE_OS="MacOSX" ;;
  *) echo "Unsupported OS for this installer snippet"; exit 1 ;;
esac
curl -L -o Miniforge3.sh \
  "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-${MINIFORGE_OS}-$(uname -m).sh"
bash Miniforge3.sh -b -p "$HOME/miniforge3"
source "$HOME/miniforge3/etc/profile.d/conda.sh"
source "$HOME/miniforge3/etc/profile.d/mamba.sh"
conda config --set auto_activate_base false
```

Then create the InterProScan6 environment:

```bash
mamba create -n interpro nextflow=25.10.4 -c bioconda
mamba activate interpro
export JAVA_HOME="$CONDA_PREFIX"
export NXF_JAVA_HOME="$CONDA_PREFIX"
```

If conda-style installation is blocked:

```bash
mkdir -p "$HOME/.local/bin"
curl -s https://get.nextflow.io | bash
mv nextflow "$HOME/.local/bin/"
export PATH="$HOME/.local/bin:$PATH"
java -version
nextflow -version
```

Then run:

```bash
nextflow run ebi-pf-team/interproscan6 \
  -r 6.0.1 \
  -profile singularity,test \
  --datadir "$HOME/interproscan6/data" \
  --no-matches-api \
  -w "$HOME/interproscan6/test_work"
```

## InterProScan6 Production Run

```bash
mkdir -p "$HOME/interproscan6/input" \
         "$HOME/interproscan6/results" \
         "$HOME/interproscan6/work" \
         "$HOME/interproscan6/logs"

export IPS6_HOME="$HOME/interproscan6"
export INPUT="$IPS6_HOME/input/M_caribbica.longest.table12.proteins.fa"
export DATA="$IPS6_HOME/data"
export OUT="$IPS6_HOME/results/M_caribbica_table12"
export WORK="$IPS6_HOME/work/M_caribbica_table12"
export LOG="$IPS6_HOME/logs/M_caribbica_table12.log"
mkdir -p "$OUT" "$WORK"

nextflow run ebi-pf-team/interproscan6 \
  -r 6.0.1 \
  -profile singularity \
  --input "$INPUT" \
  --datadir "$DATA" \
  --no-matches-api \
  --goterms \
  --pathways \
  --formats TSV,JSON,GFF3 \
  --outdir "$OUT" \
  --outprefix M_caribbica.longest.table12 \
  --maxWorkers 4 \
  --cpus 4 \
  -w "$WORK" \
  -resume \
  2>&1 | tee "$LOG"
```

## eggNOG-mapper Protein Run

With conda/mamba:

```bash
mamba create -n eggnog python=3.9
mamba activate eggnog
mamba install -c bioconda -c conda-forge eggnog-mapper diamond
```

If conda/mamba are missing, bootstrap Miniforge as above, then use:

```bash
mamba create -n eggnog python=3.9 -c conda-forge
mamba activate eggnog
mamba install -c bioconda -c conda-forge eggnog-mapper diamond
```

If conda-style installation is blocked:

```bash
python3 -m venv "$HOME/.venvs/eggnog"
. "$HOME/.venvs/eggnog/bin/activate"
python -m pip install --upgrade pip
python -m pip install eggnog-mapper
```

Run:

```bash
emapper.py \
  -i ./01_translation/M_caribbica.longest.table12.proteins.fa \
  --itype proteins \
  -m diamond \
  --cpu 32 \
  --data_dir <EGGNOG_DATA_DIR> \
  --output_dir ./03_function/eggnog/ \
  -o M_caribbica_table12
```

## Expected Outputs To Inspect

InterProScan6:

- `<outprefix>.tsv`
- `<outprefix>.json`
- `<outprefix>.gff3`
- workflow log and Nextflow work directory

eggNOG-mapper:

- `<prefix>.emapper.annotations`
- `<prefix>.emapper.seed_orthologs`
- `<prefix>.emapper.hits` when produced
- `<prefix>.emapper.log`

## Summary Pattern

When both tools finish, report:

- number of input proteins
- number and fraction with InterProScan6 matches
- top InterPro entries, Pfam domains, repeats, and functional sites
- number and fraction with eggNOG ortholog assignments
- top GO terms, KEGG pathways/modules, EC numbers, COG categories
- proteins with no annotation from either tool
- versions, database paths/releases, CPU counts, and run directories
