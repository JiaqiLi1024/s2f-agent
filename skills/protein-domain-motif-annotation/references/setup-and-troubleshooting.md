# Setup And Troubleshooting

## Environment Setup

## Before Choosing An Install Path

Check the host first and choose the least disruptive path:

```bash
command -v conda || true
command -v mamba || true
command -v python3 || true
command -v java || true
command -v nextflow || true
command -v docker || true
command -v singularity || true
command -v apptainer || true
command -v emapper.py || true
command -v diamond || true
```

If conda/mamba are absent, prefer installing Miniforge or Miniconda after user approval. Use venv/pip and standalone Nextflow only when the user cannot install a conda-style distribution because of policy, storage, or network constraints.

## Bootstrap Conda/Mamba When Missing

Prefer Miniforge for this skill because it provides `conda` and `mamba` commands with `conda-forge` as the default channel. Use a user-local prefix and avoid root/admin installation.

### Unix-like Systems

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
conda --version
mamba --version
```

Initialize the shell only if the user wants persistent activation:

```bash
"$HOME/miniforge3/bin/conda" init "$(basename "$SHELL")"
```

### Miniconda Alternative

Use Miniconda when the user specifically prefers Anaconda's distribution or institutional policy requires it. After Miniconda is installed, add mamba from conda-forge:

```bash
conda install -n base -c conda-forge mamba
```

### Windows

Use the Miniforge or Miniconda Windows installer. For WSL, use the Linux installer inside the WSL shell.

### InterProScan6

InterProScan6 needs Nextflow 25.04 or later plus Docker, SingularityCE, or Apptainer. It does not require conda/mamba.

#### Path A: conda/mamba available

```bash
mamba create -n interpro
mamba activate interpro
mamba install nextflow=25.10.4 -c bioconda
export JAVA_HOME="$CONDA_PREFIX"
export NXF_JAVA_HOME="$CONDA_PREFIX"
```

#### Path B: conda/mamba missing

Install Miniforge first, then create the environment:

```bash
mamba create -n interpro nextflow=25.10.4 -c bioconda
mamba activate interpro
export JAVA_HOME="$CONDA_PREFIX"
export NXF_JAVA_HOME="$CONDA_PREFIX"
```

#### Path C: conda-style installation blocked

Use an existing Java installation or install Java through the host package manager or HPC module system. Then install Nextflow into a user-writable bin directory:

```bash
mkdir -p "$HOME/.local/bin"
curl -s https://get.nextflow.io | bash
mv nextflow "$HOME/.local/bin/"
export PATH="$HOME/.local/bin:$PATH"
nextflow -version
java -version
```

On HPC, prefer site-provided modules when available:

```bash
module avail nextflow
module avail java
module load java
module load nextflow
```

For container execution, use the runtime that exists on the host. Typical choices:

- Local workstation with Docker: `-profile docker`
- HPC with SingularityCE: `-profile singularity`
- HPC with Apptainer: `-profile apptainer`
- Slurm plus Singularity/Apptainer: `-profile singularity,slurm` or `-profile apptainer,slurm`

Confirm a supported container runtime is available:

```bash
nextflow -version
singularity --version
# or: apptainer --version
# or: docker --version
```

Initialize a small test run before any proteome-scale job. This pre-production run initializes the data directory and pulls/caches the Nextflow container images locally, so the real run is not the first time the host downloads workflow assets:

```bash
nextflow run ebi-pf-team/interproscan6 \
  -r 6.0.1 \
  -profile singularity,test \
  --datadir "$HOME/interproscan6/data" \
  --no-matches-api \
  -w "$HOME/interproscan6/test_work"
```

Prepare stable project directories:

```bash
mkdir -p "$HOME/interproscan6/input" \
         "$HOME/interproscan6/results" \
         "$HOME/interproscan6/work" \
         "$HOME/interproscan6/logs"
```

### eggNOG-mapper

eggNOG-mapper needs Python 3.7 or newer, `wget`, `sqlite`, the eggNOG databases, and a search backend. DIAMOND is the default backend for protein FASTA workflows.

#### Path A: conda/mamba available

```bash
mamba create -n eggnog python=3.9
mamba activate eggnog
mamba install -c bioconda -c conda-forge eggnog-mapper diamond
```

#### Path B: conda/mamba missing

Install Miniforge first, then create the eggNOG-mapper environment:

```bash
mamba create -n eggnog python=3.9 -c conda-forge
mamba activate eggnog
mamba install -c bioconda -c conda-forge eggnog-mapper diamond
```

#### Path C: conda-style installation blocked, Python venv available

```bash
python3 -m venv "$HOME/.venvs/eggnog"
. "$HOME/.venvs/eggnog/bin/activate"
python -m pip install --upgrade pip
python -m pip install eggnog-mapper
```

If `diamond` is not found after installing eggNOG-mapper, first test whether eggNOG-mapper's bundled binaries work. If not, install DIAMOND through the OS package manager, an HPC module, or a downloaded binary:

```bash
diamond version || true
module avail diamond || true
```

#### Confirm commands

```bash
emapper.py --help
diamond version
```

Populate the eggNOG data directory before running production jobs. The production `emapper.py` command must pass this same directory through `--data_dir` or the wrapper's `--eggnog-data-dir`:

```bash
export EGGNOG_DATA_DIR="<EGGNOG_DATA_DIR>"
mkdir -p "$EGGNOG_DATA_DIR"
download_eggnog_data.py --data_dir "$EGGNOG_DATA_DIR"
```

For shared HPC installations, prefer an explicit `--data_dir` over relying on implicit defaults.

## Common Failures

### `nextflow: command not found`

Activate the InterProScan6 environment, load the HPC module, or install Nextflow into `$HOME/.local/bin`. InterProScan6 expects Nextflow 25.04 or later.

### Java errors

If Java came from conda/mamba, export both variables after activation:

```bash
export JAVA_HOME="$CONDA_PREFIX"
export NXF_JAVA_HOME="$CONDA_PREFIX"
```

If conda/mamba are missing, install Miniforge first unless the user cannot use conda-style tooling. If conda-style tooling is blocked, check `java -version` and use the system package manager or module system to install/load a compatible Java runtime.

### Container profile mismatch

Use a profile that matches the installed runtime:

- SingularityCE: `-profile singularity`
- Apptainer: `-profile apptainer`
- Docker: `-profile docker`

Use `,test` only for the bundled test dataset.

### InterProScan6 data directory missing or incomplete

Run a small test workflow first. Do not point production runs at a partially populated or mixed-version data directory unless the user intentionally wants that release.

### eggNOG data directory missing

Stop and ask for the correct data path or run the database download command. Do not silently switch to another eggNOG database.

### `emapper.py` cannot find DIAMOND

Activate the eggNOG environment and confirm `diamond version`. If conda/mamba are missing, install Miniforge first and install `diamond` from Bioconda. If conda-style tooling is blocked, try the bundled eggNOG-mapper binaries first; otherwise install DIAMOND through the OS package manager, HPC module system, or an official binary.

### Resume confusion

Use InterProScan6 `-resume` only with the same input, work directory, version, and data directory. Use eggNOG-mapper `--resume` only when reusing the same output prefix and output directory intentionally.

## Validation Checklist

- Input FASTA exists and is the expected sequence type.
- InterProScan6 run pins `-r` and, when possible, the InterPro data release.
- `--datadir`, `-w`, and output directories are explicit.
- eggNOG-mapper run pins `--data_dir`, `--output_dir`, `-o`, `--itype`, `-m`, and `--cpu`.
- Logs are saved outside temporary directories.
- The final response reports missing hits separately from failed commands.
