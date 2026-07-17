---
name: protein-domain-motif-annotation
description: Use InterProScan6 and eggNOG-mapper for protein domain, motif, family, orthology, GO, pathway, and functional-site annotation from protein FASTA files. Use when Codex needs to set up, run, resume, troubleshoot, or summarize InterProScan6 or eggNOG-mapper protein annotation workflows.
---

# Protein Domain Motif Annotation

## Overview

Use this skill for protein-sequence annotation workflows centered on InterProScan6 and eggNOG-mapper. InterProScan6 scans protein or nucleotide FASTA against InterPro member-database signatures to annotate families, domains, repeats, and functional sites. eggNOG-mapper annotates proteins through orthology assignment and transfers GO, KEGG, EC, Pfam, COG/category, and free-text functional descriptions.

This is a protein annotation workflow skill. Do not use it for 3D structure retrieval, folding, docking, or localization/topology prediction unless those annotations are already present in InterPro/eggNOG outputs.

## Workflow

1. Confirm the input and scope.
- Require a protein FASTA for normal runs. Use `--nucleic` for InterProScan6 only when the input is nucleotide FASTA.
- Ask whether the user wants InterProScan6, eggNOG-mapper, or both. Use both for draft genome/transcriptome proteome annotation unless runtime is constrained.
- Record the intended output root, run prefix, CPU count, InterProScan6 version, container runtime profile, and eggNOG database path.
- Before writing install commands, check whether `conda`, `mamba`, `python3`, `java`, `nextflow`, `docker`, `singularity`/`apptainer`, `emapper.py`, and `diamond` are available. If conda/mamba are absent, prefer installing Miniforge or Miniconda after user approval; use venv/pip only when conda-style installation is blocked by policy.

2. Choose the tool path.
- Use InterProScan6 for InterPro entries, member database signatures, family/domain/repeat/site matches, GO terms, pathways, JSON/GFF3/TSV output, and genome-scale domain architecture.
- Use eggNOG-mapper for orthology-based functional transfer, GO/KEGG/EC/Pfam/COG annotation, protein descriptions, and broad functional summaries.
- Run InterProScan6 first when a domain/motif map is the primary deliverable; run eggNOG-mapper first when broad functional annotation and orthologs are the primary deliverable.
- Before production InterProScan6 runs, run one `-profile <runtime>,test` smoke test to initialize `--datadir` and pull/cache the Nextflow container images locally.
- Before production eggNOG-mapper runs, populate the local eggNOG database with `download_eggnog_data.py --data_dir <DIR>` and pass the same path through `--eggnog-data-dir` or `--data_dir`.

3. Read references as needed.
- Read `references/setup-and-troubleshooting.md` before writing install, database download, Nextflow, container, or HPC commands.
- Read `references/constraints.md` before interpreting coordinates, versions, database paths, missing hits, or combining outputs.
- Read `references/inference-patterns.md` for concrete commands matching the user's examples.
- Read `references/family-selection.md` when deciding whether InterProScan6, eggNOG-mapper, or both are appropriate.

4. Generate or run commands.
- Use the wrapper script for reproducible command construction and run records:

```bash
python skills/protein-domain-motif-annotation/scripts/run_real_protein_domain_motif_annotation_workflow.py \
  --input proteins.fa \
  --tools both \
  --interpro-profile singularity \
  --interpro-datadir "$HOME/interproscan6/data" \
  --eggnog-data-dir <EGGNOG_DATA_DIR> \
  --outdir output/protein-domain-motif-annotation/proteins
```

- Add `--execute` only when the environment is ready and the user wants to run the workload.
- Without `--execute`, the script writes a dry-run command plan and expected-output contract.

5. Inspect the result JSON first.
- Treat `protein_domain_motif_annotation.result.json` as the source of truth for command lines, status, warnings, errors, discovered outputs, and partial failures.
- Summarize InterProScan6 and eggNOG-mapper outputs separately before making a combined interpretation.
- Use `protein-annotation-report` when the user wants standardized summary/features TSV tables from the InterProScan6 and eggNOG outputs.

## Runtime Dependencies

InterProScan6 requires Nextflow 25.04 or later and a supported container runtime such as Docker, SingularityCE, or Apptainer. It does not technically require conda/mamba, but this skill should prefer a conda-style environment for reproducibility. If conda/mamba are absent, install Miniforge first when the user permits it, then create the InterProScan6 and eggNOG-mapper environments. For conda/mamba Nextflow environments, export `JAVA_HOME="$CONDA_PREFIX"` and `NXF_JAVA_HOME="$CONDA_PREFIX"` when Java is provided by the environment.

eggNOG-mapper requires Python, an installed `emapper.py`, a local eggNOG data directory, and at least one search backend. Use DIAMOND for the common protein FASTA path.

Bootstrap Miniforge when conda/mamba are absent and the user approves:

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

Then create the eggNOG-mapper environment:

```bash
mamba create -n eggnog python=3.9
mamba activate eggnog
mamba install -c bioconda -c conda-forge eggnog-mapper diamond
```

Use this venv fallback only when conda-style installation is not allowed:

```bash
python3 -m venv "$HOME/.venvs/eggnog"
. "$HOME/.venvs/eggnog/bin/activate"
python -m pip install --upgrade pip
python -m pip install eggnog-mapper
```

Then confirm:

```bash
emapper.py --help
diamond version
```

## Command Surface

```bash
python skills/protein-domain-motif-annotation/scripts/run_real_protein_domain_motif_annotation_workflow.py \
  --input <PROTEINS_FASTA> \
  [--tools both|interproscan6|eggnog] \
  [--run-id <LABEL>] \
  [--outdir <OUTDIR>] \
  [--execute] \
  [--interpro-revision 6.0.1] \
  [--interpro-profile singularity|docker|apptainer|singularity,test|docker,test] \
  [--interpro-datadir <DIR>] \
  [--interpro-outdir <DIR>] \
  [--interpro-workdir <DIR>] \
  [--interpro-outprefix <PREFIX>] \
  [--interpro-formats TSV,JSON,GFF3] \
  [--interpro-release <INTERPRO_RELEASE>] \
  [--interpro-max-workers <N>] \
  [--interpro-cpus <N>] \
  [--nucleic] \
  [--no-goterms] \
  [--no-pathways] \
  [--interpro-use-matches-api] \
  [--no-resume] \
  [--eggnog-data-dir <DIR>] \
  [--eggnog-output-dir <DIR>] \
  [--eggnog-output-prefix <PREFIX>] \
  [--eggnog-method diamond|mmseqs|hmmer|no_search] \
  [--eggnog-itype proteins|CDS|genome] \
  [--eggnog-cpu <N>] \
  [--emapper-bin emapper.py] \
  [--nextflow-bin nextflow]
```

## Output Contract

The wrapper always writes:

- `protein_domain_motif_annotation.result.json`: structured status, input, run ID, command plan, warnings, errors, discovered outputs, and expected files.
- `commands.sh`: shell commands for the requested tool path.
- `<tool>.log`: command stdout/stderr when `--execute` is used.

InterProScan6 outputs are expected under `interproscan6/<run_id>/` unless `--interpro-outdir` is provided:

- `<outprefix>.tsv`: concise InterProScan match table.
- `<outprefix>.json`: full annotation JSON.
- `<outprefix>.gff3`: browser/pipeline-friendly annotations.
- Optional `.jsonl` and `.xml` if requested through formats.

eggNOG-mapper outputs are expected under `eggnog/` unless `--eggnog-output-dir` is provided:

- `<prefix>.emapper.annotations`
- `<prefix>.emapper.seed_orthologs`
- `<prefix>.emapper.hits` or backend-specific hit files when produced.
- `<prefix>.emapper.log`

## Grounded CLI Surface

Use only these public command surfaces unless the installed local versions show different help text:

- InterProScan6: `nextflow run ebi-pf-team/interproscan6 -r 6.0.1 -profile <docker|singularity|apptainer>[,test] --datadir <DIR> [--input <FASTA>] [--nucleic] [--goterms] [--pathways] [--formats TSV,JSON,GFF3] [--outdir <DIR>] [--outprefix <PREFIX>] [--maxWorkers <N>] [--cpus <N>] -w <WORKDIR> [-resume]`
- eggNOG-mapper: `emapper.py -i <FASTA> --itype proteins -m diamond --cpu <N> --data_dir <DIR> --output_dir <DIR> -o <PREFIX>`
- Wrapper: `python skills/protein-domain-motif-annotation/scripts/run_real_protein_domain_motif_annotation_workflow.py --help`

## Failure And Recovery

- If `conda` and `mamba` are both missing, ask for approval to install Miniforge or Miniconda before suggesting venv/pip.
- If `nextflow` is missing, activate the InterProScan6 environment or install Nextflow before retrying.
- If container execution fails, verify Docker/Singularity/Apptainer availability and that the selected Nextflow profile matches the runtime.
- If InterProScan6 data or container images are missing, run a small `-profile <runtime>,test` job first to initialize the data directory and warm the local container cache.
- If eggNOG data are missing, run `download_eggnog_data.py --data_dir <DIR>` and populate `--eggnog-data-dir` before running `emapper.py`; do not silently fall back to a different database.
- If `emapper.py` cannot find DIAMOND, activate the eggNOG environment or install DIAMOND from Bioconda.
- If either tool produces no hits, report zero matches as a valid result and check sequence type, database version, and taxonomic scope before treating it as failure.
- Use `-resume` for InterProScan6 and `--resume` for eggNOG-mapper only when the previous output prefix and work/data directories are intentionally being reused.

## References

- `references/setup-and-troubleshooting.md`
- `references/constraints.md`
- `references/inference-patterns.md`
- `references/family-selection.md`

## Scripts

- `scripts/run_real_protein_domain_motif_annotation_workflow.py`
