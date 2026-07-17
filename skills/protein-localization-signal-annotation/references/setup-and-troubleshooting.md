# Setup And Troubleshooting

## Execution Priority

Use the first available path:

1. **Local licensed command**: fastest and fully automatic after setup. Use command templates and `--execute`.
2. **Programmatic hosted runner**: use BioLib or another supported runner when the specific DTU app is available and the user has credentials/configuration.
3. **DTU web import**: create FASTA files, submit through the web UI, then import downloaded result tables.

The public DTU service pages document web submission and downloadable/local software, but this wrapper does not assume a stable public unauthenticated API for DeepLoc 2.1, SignalP 6.0, or TargetP 2.0.

## DTU Web Submission

DeepLoc 2.1, SignalP 6.0, and TargetP 2.0 all accept protein FASTA through DTU Health Tech service pages. The wrapper writes service-specific FASTA files under `web_submission/` and records the URLs in `commands.sh`.

- DeepLoc 2.1: `https://services.healthtech.dtu.dk/services/DeepLoc-2.1/`
- SignalP 6.0: `https://services.healthtech.dtu.dk/services/SignalP-6.0/`
- TargetP 2.0: `https://services.healthtech.dtu.dk/services/TargetP-2.0/`

After the web job finishes, download summary/probability tables and import them with `--deeploc-output`, `--signalp-output`, or `--targetp-output`.

## BioLib Or Hosted Runner

SignalP 6.0 has an official BioLib mirror linked from the DTU page. BioLib documentation says applications can be run from the website or programmatically through terminal/Python, but actual access may require login/API configuration and not every DTU service is guaranteed to be mirrored.

Use a command template rather than hard-coding BioLib syntax:

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta proteins.fa \
  --tools signalp \
  --signalp-command-template "<BIOLIB_OR_HOSTED_RUNNER_COMMAND_WITH_{input}_AND_{outdir}>" \
  --execute \
  --outdir output/protein-localization-signal-annotation/signalp_biolib
```

When adding a concrete BioLib command, verify it once on the user's machine and keep tokens or credentials outside command logs.

## Local Software

DTU local downloads can require academic license forms, institutional eligibility, or non-commercial terms. Do not script automatic downloads unless the user has already obtained the package and agreed to the license.

Recommended setup pattern:

```bash
mamba create -n protein-localization python=3.10
mamba activate protein-localization
python -m pip install --upgrade pip
```

Install packages only from user-provided local archives or official source they have permission to use:

```bash
python -m pip install /path/to/signalp_package.whl
python -m pip install /path/to/deeploc_package.whl
tar -xf /path/to/targetp-2.0.Linux.tar.gz -C "$HOME/biosoft/targetp-2.0"
```

Then verify commands manually:

```bash
command -v signalp6 || true
command -v deeploc2 || true
command -v targetp || true
```

Use command templates for local runners:

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --fasta proteins.fa \
  --deeploc-command-template "<DEEPLOC COMMAND WITH {input} AND {outdir}>" \
  --signalp-command-template "<SIGNALP COMMAND WITH {input} AND {outdir}>" \
  --targetp-command-template "<TARGETP COMMAND WITH {input} AND {outdir}>" \
  --execute \
  --outdir output/protein-localization-signal-annotation/local_run
```

The wrapper discovers TSV/CSV/TXT files in the command output directory after execution and tries to parse them.

## Direct Prediction From A User Sequence

The skill can directly return predictions from a raw sequence only when at least one executable backend is configured:

```bash
python skills/protein-localization-signal-annotation/scripts/protein_localization_signal_annotation.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --tools signalp+targetp \
  --signalp-command-template "<SIGNALP COMMAND WITH {input} AND {outdir}>" \
  --targetp-command-template "<TARGETP COMMAND WITH {input} AND {outdir}>" \
  --execute \
  --outdir output/protein-localization-signal-annotation/query1_direct
```

If no executable backend is configured, the skill still validates the sequence and creates ready-to-submit FASTA files, but it cannot honestly claim prediction results until output files are imported.

## Input Validation

- Minimum length defaults to 10 amino acids, matching the DTU service pages.
- Use `--sanitize-invalid-to-x` when sequences contain invalid alphabetic symbols and web-server compatibility matters.
- Use `--allow-ambiguous-aa` to allow common non-standard/ambiguous residues. TargetP 2.0 officially allows `X`; other non-standard residues may be converted by the web server.
- DeepLoc is for protein sequences, not nucleotide sequences.

## Interpretation Cautions

- SignalP predicts signal peptides in the narrow sense: entry into the secretory pathway, not final secretion.
- TargetP predicts N-terminal targeting presequences; use the Plant organism group for plastid-containing organisms.
- DeepLoc provides broad eukaryotic localization and membrane association, but transmembrane topology still requires `protein-tm-topology-annotation`.
- For eukaryotic proteins with signal peptides, final localization may depend on ER retention, Golgi/lysosome sorting, transmembrane segments, GPI anchors, or other signals.
