# Tool Selection

## metapredict

Use metapredict for fast local disorder/IDR prediction from raw sequences or FASTA files. It is the best default for high-throughput IDR screening when a Python environment with compatible PyTorch/numpy is available.

Notes:

- Current official default is metapredict V3.
- The package provides both CLI tools and a Python API.
- Avoid mixing pip-installed PyTorch/numpy with conda-installed PyTorch/numpy in the same environment.
- Use graphing commands only when the user asks for plots.

## AIUPred

Use AIUPred when the user needs AIUPred-specific disorder, binding, flexible linker, or redox-sensitive predictions.

Modes:

- CLI: `aiupred -i <FASTA> -o <TSV> [-b] [-l] [-r] [--force-cpu]`
- Nextflow: `nextflow run doszilab/AIUPred -r <release> -profile <conda|docker|docker_cpu> --input <FASTA> --outdir <DIR>`

Prefer CLI for simple local runs. Prefer Nextflow for reproducible batch runs, containers, or workflow-managed environments.

## IUPred3

Use IUPred3 when the user asks specifically for IUPred long/short disorder or structured-domain mode.

- REST API works well for UniProt accessions.
- Raw amino-acid sequences and proteome batches are better handled through local IUPred3, metapredict, or AIUPred.
- Local IUPred3 scripts can be used through `--iupred3-local-bin`.
- Use `--iupred3-local-input-format fasta` when the local script handles one FASTA at a time; the wrapper writes one FASTA per record and loops over the batch.
- Use `--iupred3-local-input-format table` only for tab-delimited identifier/sequence batch wrappers.
- `long` is the default global disorder mode.
- `short` targets short disordered segments.
- `glob` identifies putative structured/globular domains.

## FuzDrop

Use FuzDrop when the user asks for LLPS, droplet-state, pLLPS, or droplet-promoting/hotspot regions.

- Prefer importing downloaded FuzDrop JSON with `--fuzdrop-json`.
- API submission exists behind the FuzDrop web app and may require a manually obtained reCAPTCHA token; use `--fuzdrop-captcha-token` only when the user provides one.
- Normalize FuzDrop `pLLPS`, DPR, hotspot, DOR, DDR, and CDR regions into `protein_llps_summary.tsv` and `protein_llps_features.tsv`.

## AggrescanAI

Use AggrescanAI when the user asks for aggregation-prone regions (APRs) or aggregation propensity around IDRs/LLPS.

- Prefer importing the downloaded Colab CSV with `--aggrescanai-csv`.
- A local runner can be provided with `--aggrescanai-script`; expect heavy dependencies such as ProtT5, PyTorch/Transformers, TensorFlow/Keras, and model downloads.
- Default aggregation threshold is `0.3`, matching the public notebook visualization threshold.

## gget ELM

Use gget ELM to find Eukaryotic Linear Motifs and then overlay/filter them by IDR intervals. Do not treat gget ELM as a disorder predictor.

Typical chain:

1. Run IDR prediction with this skill.
2. Run `gget setup elm` once if needed.
3. Run `gget elm` for motif detection.
4. Intersect ELM motif coordinates with `protein_idr_regions.tsv`.
