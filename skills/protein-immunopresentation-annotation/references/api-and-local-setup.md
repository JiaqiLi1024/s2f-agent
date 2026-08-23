# API And Local Setup

Use this reference before submitting sequences to IEDB or installing the local next-generation tools.

Prefer the local route for unpublished or private sequences. Keep the API route as a fallback for public sequences or quick checks.

## Remote Submission Policy

IEDB API execution sends protein sequences to a remote service. Ask before submitting unpublished, proprietary, clinical, or patient-derived sequences. Run without `--execute-api` first to generate local peptide tables and API request payloads.

## IEDB Analysis Resource Tools-API

The IEDB Analysis Resource documents REST-style POST access for MHC-I binding and MHC-I processing. The public examples use:

- MHC-I binding: `https://tools-cluster-interface.iedb.org/tools_api/mhci/`
- MHC-I processing: `https://tools-cluster-interface.iedb.org/tools_api/processing/`
- Parameters: `method`, `sequence_text`, `allele`, `length`; processing also accepts `proteasome`.

Documented Class I binding methods include `recommended`, `netmhcpan_el`, `netmhcpan_ba`, `consensus`, `ann`, `smmpmbec`, `smm`, `comblib_sidney2008`, `netmhccons`, `pickpocket`, and `netmhcstabpan`. Use `netmhcpan_el` for eluted-ligand rank and `netmhcpan_ba` for binding-affinity/IC50-style evidence.

The API supports FASTA-formatted multiple sequences in `sequence_text`. The wrapper writes `api_requests/iedb_legacy_requests.jsonl` with one request per predictor and peptide length.

## IEDB Next-Generation Metadata

The next-generation metadata endpoint is:

```bash
curl -L https://api-nextgen-tools.iedb.org/api/v1/mhci
```

It reports parameters `input_sequence_text`, `alleles`, `peptide_length_range`, and `predictors`, plus available predictors such as `netmhcpan_el`, `netmhcpan_ba`, `basic_processing`, `netchop`, `netctl`, `netctlpan`, and `immunogenicity`.

If a stable next-generation POST endpoint is available in the user environment, pass it through `--api-url` and keep the generated `api_requests/iedb_nextgen_request.json` with the run.

## Local Next-Generation TC1 Workflow

The official IEDB download README for `https://downloads.iedb.org/nextgen-tools/tcell_mhci/LATEST/README` currently reports `IEDB_NG_TC1-0.1.5-beta`. The `LATEST` directory contains:

- `IEDB_NG_TC1-0.1.5-beta.tar.gz` at `https://downloads.iedb.org/nextgen-tools/tcell_mhci/LATEST/IEDB_NG_TC1-0.1.5-beta.tar.gz`
- `MD5SUM` at `https://downloads.iedb.org/nextgen-tools/tcell_mhci/LATEST/MD5SUM`
- `README`

The tarball is large, about 841 MB in the current directory listing, so ask before downloading it on the user's machine.

Official install outline:

```bash
mkdir -p ~/iedb_tools
curl -L -O https://downloads.iedb.org/nextgen-tools/tcell_mhci/LATEST/IEDB_NG_TC1-0.1.5-beta.tar.gz
curl -L -O https://downloads.iedb.org/nextgen-tools/tcell_mhci/LATEST/MD5SUM
tar -xvzf IEDB_NG_TC1-0.1.5-beta.tar.gz -C ~/iedb_tools
cd ~/iedb_tools/ng_tc1-0.1.5-beta
python3 -m venv ~/venvs/tc1
source ~/venvs/tc1/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
PIP_CONSTRAINTS=pip_constraints.txt pip install -r requirements.txt
./configure
```

The README documents Linux 64-bit, Python 3.8+, `tcsh`, and `gawk` as prerequisites. Docker is optional for MHC-NP and MHCflurry. It also notes NetCTL path sensitivity: keep the full tool path under 57 characters if NetCTL will be used.

The qinti2023/IEDB wrapper repository documents this wrapper workflow:

```bash
mamba create -n IEDB python=3.10
mamba activate IEDB
pip install -r requirements.txt
PIP_CONSTRAINTS=pip_constraints.txt pip install -r requirements.txt
pip install numpy==1.24.4

python fasta_to_json.py input_sequence.fasta output.json
python3 src/tcell_mhci.py -j output.json --split --split-dir ./test/
python IEDB_predict.py job_descriptions.json
```

The qinti2023/IEDB repository contains wrapper scripts and example output, but it does not include the official `src/tcell_mhci.py` program. The official IEDB NG TC1 tarball is the source for `src/tcell_mhci.py`. Provide the unpacked official package directory as `--iedb-local-tools-dir`.

If conda/mamba are missing, ask before installing Miniforge or Miniconda. Do not run system package installation silently. If conda is available, a dedicated `IEDB` environment with Python 3.10 is acceptable; otherwise use the official venv approach.

The skill wrapper writes a qinti-compatible input JSON:

- `local_iedb/iedb_ng_tc1_input.json`
- `local_iedb/local_pipeline_plan.sh`
- `local_iedb/local_pipeline_manifest.json`

Dry-run:

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta input_sequence.fasta \
  --alleles HLA-A*02:01,HLA-B*07:02 \
  --outdir output/protein-immunopresentation-annotation/run_plan
```

Execute local jobs only after the official IEDB package path is known:

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta input_sequence.fasta \
  --iedb-local-tools-dir /path/to/IEDB_NG_TC1 \
  --execute-local \
  --local-workdir output/protein-immunopresentation-annotation/run_iedb_work \
  --outdir output/protein-immunopresentation-annotation/run_local
```

The wrapper includes its own job runner because the qinti2023/IEDB `IEDB_predict.py` example calculates workers as `os.cpu_count() - 128`, which can be invalid on smaller machines. `--iedb-wrapper-repo` is optional and only needed when reproducing the original qinti `IEDB_predict.py` command sequence.

The local pipeline can produce `aggregate/aggregated_result.json`, whose `results[*].table_columns` and `results[*].table_data` can be imported with:

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta input_sequence.fasta \
  --local-result-json aggregate/aggregated_result.json \
  --outdir output/protein-immunopresentation-annotation/imported
```

The importer understands combined qinti/IEDB next-generation columns such as `core.peptide`, `core.start`, `binding.netmhcpan_el.percentile`, `binding.netmhcpan_ba.ic50`, `processing.basic_processing.total_score`, and `immunogenicity.score`.

## Reproducibility

Record:

- IEDB endpoint or local tool version.
- Predictor names and versions when available.
- HLA allele list.
- Peptide length list.
- Binding rank and IC50 thresholds.
- Whether processing and immunogenicity scores were executed, imported, or missing.
- Source paths for context feature overlaps.
