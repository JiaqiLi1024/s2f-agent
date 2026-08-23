# Setup, downloads, licenses, and version freezing

Use `scripts/setup_sequence_mutation_env.py --backend BACKEND --mode plan` before creating anything. Record the emitted commands. Change to `--mode execute` only after checking storage, accelerator, network, and licenses. Keep model caches outside run directories and never clean them with the run cleanup flag.

## Baseline validator and local MSA profile

No third-party Python package is required:

```bash
conda create -n s2f-protein-mutation -y python=3.11
conda run -n s2f-protein-mutation python scripts/validate_protein_mutations.py --help
```

## ESM-1v

Official source: https://github.com/facebookresearch/esm (archived read-only upstream). The five `esm1v_t33_650M_UR90S_[1-5]` checkpoints are downloaded automatically to the PyTorch cache. The released code is MIT licensed; review checkpoint/source notices at the pinned repository state.

```bash
conda create -n s2f-esm1v -y python=3.10 pip
conda run -n s2f-esm1v python -m pip install 'fair-esm==2.0.0' torch
# Optional explicit one-member download/smoke load:
conda run -n s2f-esm1v python -c 'import esm; esm.pretrained.esm1v_t33_650M_UR90S_1()'
```

Pin `fair-esm==2.0.0`, record the torch/CUDA versions, selected ensemble members, and checkpoint hashes/cache paths. Do not install Biohub ESMC into this same environment without a tested lock: both projects import as `esm`.

## ESMC 300M

Official source and instructions: https://github.com/Biohub/esm . Official Hugging Face model IDs include `biohub/ESMC-300M` and the dated `biohub/esmc-300m-2024-12`. Current upstream installation uses the Git repository; the code/models are MIT licensed and Biohub also publishes an acceptable-use policy.

```bash
conda create -n s2f-esmc300m -y python=3.12 pip
# Resolve and record a commit instead of retaining @main for a frozen run.
git ls-remote https://github.com/Biohub/esm.git refs/heads/main
conda run -n s2f-esmc300m python -m pip install \
  'esm@git+https://github.com/Biohub/esm.git@67838dc8ac76f4145613e6cb36c5f3d758542f7c' huggingface_hub
# Biohub/esm declares a moving transformers @main dependency. Reinstall the
# exact fork revision verified with this skill after the SDK installation.
conda run -n s2f-esmc300m python -m pip install --force-reinstall --no-deps \
  "transformers@git+https://github.com/Biohub/transformers.git@ef32577f55da19a4989cd7b22e004dc43a4998cb"
conda run -n s2f-esmc300m hf download biohub/ESMC-300M \
  --revision a59b831785f907e96e6a246b1d142bfb76df31ee
```

Some Hugging Face revisions may require authentication or acceptance of model terms. Put the token in `HF_TOKEN`; never write it to `commands.sh`, logs, or manifests. Use `--local-files-only` after cache population for reproducibility.

## PoET

Official source: https://github.com/OpenProteinAI/PoET . The source is MIT licensed. The approximately 400 MB checkpoint is CC BY-NC-SA 4.0 for academic use; contact the owner for commercial licensing. Upstream requires mamba, conda-lock, an NVIDIA GPU, and creates an environment named `poet`.

```bash
git clone https://github.com/OpenProteinAI/PoET.git third_party/PoET
cd third_party/PoET
git checkout --detach 9b2239be84ee39691ec6ad4184925156f2ac332f
git rev-parse HEAD                 # must report the pinned commit
make create_conda_env              # creates the upstream 'poet' environment
make download_model                # only after accepting weight terms
conda run -n poet python scripts/score.py --help
```

Native scoring uses `scripts/score.py --msa_a3m_path ... --variants_fasta_path ... --output_npy_path ...`. The runner preserves variant order and imports the resulting one-dimensional NPY. Run PoET in its own environment; do not merge its lock with ESM environments.

## AlphaMissense

Official reference implementation and prediction links: https://github.com/google-deepmind/alphamissense . The repository was archived in 2025. Code is Apache-2.0 and released predictions are CC BY 4.0. **Trained model weights are not released.** Therefore this skill performs streaming lookup/import against the official human prediction files; it does not install the reference code and claim inference.

Download the release file from the official links in the repository/Google Cloud release, keep the supplied version (v2023), README, checksum, and license beside the data, then pass the compressed file directly:

```bash
python scripts/run_sequence_mutation_effect.py \
  --fasta human.fasta --mutations-file variants.tsv \
  --models alphamissense --mode import \
  --alphamissense-table /data/alphamissense/AlphaMissense_aa_substitutions.tsv.gz \
  --output-dir run/am
```

## Freeze and audit every backend

Record: environment export/lock, Python/package versions, repository full commit, model ID and revision, file checksum, acquisition date, license URL, device/CUDA versions, runner arguments, and input hashes. A moving branch name or model alias is not a reproducible revision.


The Biohub/esm and PoET commits above were resolved from the official repositories on 2026-07-19. The Biohub/transformers commit was resolved and runtime-verified on 2026-08-23. Re-resolve deliberately when upgrading, then rerun smoke tests and update manifests; do not silently follow a moving alias.
