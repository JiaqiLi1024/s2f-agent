# Setup And Troubleshooting

## Environment Check

```bash
command -v python || true
command -v pip || true
command -v conda || true
command -v mamba || true
command -v metapredict-predict-disorder || true
command -v metapredict-predict-idrs || true
command -v aiupred || true
command -v nextflow || true
command -v gget || true
```

## No Conda Or Mamba Installed

Prefer a user-local installation after the user approves downloads. Avoid `sudo` unless the user explicitly requests a system-wide install.

Miniforge route:

```bash
curl -L -o "$HOME/Downloads/Miniforge3.sh" https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh
bash "$HOME/Downloads/Miniforge3.sh" -b -p "$HOME/miniforge3"
. "$HOME/miniforge3/etc/profile.d/conda.sh"
conda config --set channel_priority strict
conda install -n base -c conda-forge mamba
```

Micromamba route:

```bash
curl -L micro.mamba.pm/install.sh | bash
. "$HOME/.bashrc" 2>/dev/null || true
. "$HOME/.zshrc" 2>/dev/null || true
micromamba --version
```

On Linux x86_64, use the matching Miniforge installer URL instead of the macOS arm64 installer. On managed HPC systems, prefer an existing module or user-local micromamba root such as `$HOME/micromamba`.

## metapredict

Use a clean environment and keep numpy/PyTorch in one package ecosystem.

```bash
conda create -n metapredict-idr python=3.11 -c conda-forge
conda activate metapredict-idr
conda install -c conda-forge -c pytorch numpy pytorch scipy cython matplotlib
python -m pip install metapredict
metapredict-predict-disorder --help
```

If conda/mamba are unavailable and the user approves a user-local Python environment:

```bash
python -m venv "$HOME/.venvs/metapredict-idr"
. "$HOME/.venvs/metapredict-idr/bin/activate"
python -m pip install --upgrade pip
python -m pip install metapredict
```

If GPU/CUDA is involved, install PyTorch for the matching CUDA version before installing metapredict.

## AIUPred CLI

```bash
python -m venv "$HOME/.venvs/aiupred"
. "$HOME/.venvs/aiupred/bin/activate"
python -m pip install --upgrade pip
python -m pip install git+https://github.com/doszilab/AIUPred.git
aiupred --help
```

For CPU-only runs:

```bash
aiupred -i proteins.fa -o aiupred.tsv --force-cpu
```

For binding and linker prediction:

```bash
aiupred -i proteins.fa -o aiupred.tsv -b -l --force-cpu
```

## AIUPred Nextflow

Use this when a workflow-managed environment or Docker/Conda profile is preferred:

```bash
nextflow run doszilab/AIUPred -r master -profile test,conda
nextflow run doszilab/AIUPred -r master -profile conda,cpu --input proteins.fa --outdir results/aiupred
nextflow run doszilab/AIUPred -r master -profile docker_cpu --input proteins.fa --outdir results/aiupred
```

Add binding/linker:

```bash
nextflow run doszilab/AIUPred -r master -profile conda,cpu \
  --input proteins.fa \
  --outdir results/aiupred \
  --aiupred.predict_binding true \
  --aiupred.predict_linker true
```

## IUPred3

For UniProt accessions, use the REST API through the wrapper:

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --uniprot P04637 \
  --tools iupred3 \
  --execute \
  --outdir output/protein-idr-disorder-annotation/P04637
```

For local IUPred3 source archives, keep local changes outside the downloaded upstream file when possible. If a custom batch wrapper is required, record the wrapper path through `--iupred3-local-bin` and preserve exact command lines in `commands.sh`.

For custom wrappers that accept tab-delimited `identifier<TAB>sequence` input and emit `Identifier`, `Sequence`, comma-separated `IUPred_scores`, and optional comma-separated `ANCHOR_scores`, use:

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools iupred3 \
  --iupred3-local-bin iupred3_qt.py \
  --iupred3-local-input-format table \
  --execute \
  --outdir output/protein-idr-disorder-annotation/iupred3_local
```

When no custom batch wrapper is available, use the default `fasta` local mode. The wrapper writes one single-record FASTA per input record and runs the local IUPred3 script once per sequence:

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools iupred3 \
  --iupred3-local-bin /path/to/iupred3.py \
  --iupred3-local-input-format fasta \
  --execute \
  --outdir output/protein-idr-disorder-annotation/iupred3_local
```

## FuzDrop

FuzDrop web submission may require reCAPTCHA, so the robust pipeline path is to import downloaded JSON results:

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --tools fuzdrop \
  --fuzdrop-json fuzdrop_result.json \
  --execute \
  --outdir output/protein-idr-disorder-annotation/fuzdrop
```

If the user provides a valid reCAPTCHA token from a browser session, the wrapper can attempt API submission with `--fuzdrop-captcha-token`, but this should not be treated as a guaranteed unattended mode.

## AggrescanAI

AggrescanAI is notebook-first and can require ProtT5, TensorFlow/Keras, PyTorch/Transformers, and model downloads. Prefer importing the CSV downloaded from its Colab workflow:

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --tools aggrescanai \
  --aggrescanai-csv aggrescanai_results.csv \
  --execute \
  --outdir output/protein-idr-disorder-annotation/aggrescanai
```

If a local runner is available:

```bash
python skills/protein-idr-disorder-annotation/scripts/protein_idr_disorder_annotation.py \
  --fasta proteins.fa \
  --tools aggrescanai \
  --aggrescanai-script /path/to/aggrescanai_runner.py \
  --execute \
  --outdir output/protein-idr-disorder-annotation/aggrescanai
```

## gget ELM

```bash
python -m pip install --upgrade gget
gget setup elm
gget elm -o gget_elm_results <AA_SEQUENCE>
```

Use gget ELM output as motif evidence and intersect with IDR regions after disorder prediction.
