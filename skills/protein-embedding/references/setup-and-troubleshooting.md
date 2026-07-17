# Setup And Troubleshooting

Use this file when installing dependencies, preparing a model cache, choosing a device, or recovering from model-loading failures.

## Required setup flow

When a user asks to embed with a named model family, do the setup in this order:

1. Create or reuse a dedicated environment.
2. Install the base protein-embedding stack.
3. Install only the model-family extras that are required.
4. Validate the input sequence or FASTA.
5. Pre-download the requested checkpoint when the user wants the model installed locally.
6. Run a smoke test with a short sequence before processing the user's full input.
7. Save and inspect `setup_summary.json` and `run_summary.json`.

Preferred automated setup:

```bash
python skills/protein-embedding/scripts/setup_protein_embedding_env.py \
  --env-dir .venv-protein-embedding \
  --model-family esm2 \
  --download-model \
  --run-smoke-test \
  --output-dir output/protein-embedding/setup
```

Use the venv Python for real embedding after setup:

```bash
.venv-protein-embedding/bin/python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family esm2 \
  --embedding-type per-protein \
  --output-dir output/protein-embedding/esm2
```

## Base environment

Manual setup:

```bash
python -m venv .venv-protein-embedding
.venv-protein-embedding/bin/python -m pip install --upgrade pip
.venv-protein-embedding/bin/python -m pip install \
  "torch" \
  "transformers>=4.40" \
  "huggingface_hub" \
  "numpy"
```

Use a CUDA-enabled PyTorch build for GPU runs. On macOS, use `--device mps` only after verifying the model and dtype support it; otherwise use `--device cpu`.

## Model installation matrix

| Family | Required packages | Default install/checkpoint command | Smoke-test policy |
| --- | --- | --- | --- |
| ESM-2 | `torch`, `transformers`, `huggingface_hub`, `numpy` | `--model-family esm2 --model-id facebook/esm2_t6_8M_UR50D --download-model` | Always test with `facebook/esm2_t6_8M_UR50D` first. |
| ESMC local | base stack; often Biohub `esm` package for newest classes | Add `--include-biohub-esm`; use `biohub/ESMC-300M` | Test only if model download size/runtime is acceptable. |
| ESMC Forge | base stack plus Biohub `esm` SDK; Biohub token | Add `--include-biohub-esm`; use `--backend biohub-forge --model-id esmc-300m-2024-12` | Run dry-run first, then one short API request. |
| ProtT5 | base stack; `sentencepiece` may be required by tokenizer in some environments | Use `Rostlab/prot_t5_xl_uniref50`; add `--replace-rare-aa` for runs | Prefer dry-run or small single-sequence test before batch. |
| Ankh | base stack; T5 encoder path | Use `ElnaggarLab/ankh-base` first | Prefer `ankh-base` before `ankh-large`. |
| SaProt | base stack for Hugging Face checkpoint; full SaProt repo and Foldseek only for structure-to-3Di conversion | Use `westlake-repl/SaProt_650M_AF2`; label AA-only runs | Do not download full SaProt/Foldseek unless structure-aware tokens are required. |

## ESM-2

Automated lightweight setup and real smoke test:

```bash
python skills/protein-embedding/scripts/setup_protein_embedding_env.py \
  --env-dir .venv-protein-embedding-esm2 \
  --model-family esm2 \
  --model-id facebook/esm2_t6_8M_UR50D \
  --download-model \
  --run-smoke-test \
  --output-dir output/protein-embedding/setup-esm2
```

Hugging Face API surface:

```python
from transformers import AutoTokenizer, AutoModelForMaskedLM

tokenizer = AutoTokenizer.from_pretrained("facebook/esm2_t6_8M_UR50D")
model = AutoModelForMaskedLM.from_pretrained("facebook/esm2_t6_8M_UR50D")
```

After the smoke test, use a larger checkpoint only if compute allows:

- `facebook/esm2_t12_35M_UR50D`
- `facebook/esm2_t30_150M_UR50D`
- `facebook/esm2_t33_650M_UR50D`

## ESMC

Automated local Hugging Face setup:

```bash
python skills/protein-embedding/scripts/setup_protein_embedding_env.py \
  --env-dir .venv-protein-embedding-esmc \
  --model-family esmc \
  --model-id biohub/ESMC-300M \
  --include-biohub-esm \
  --download-model \
  --output-dir output/protein-embedding/setup-esmc
```

Manual extra package:

```bash
.venv-protein-embedding-esmc/bin/python -m pip install \
  "esm@git+https://github.com/Biohub/esm.git@main"
```

Hugging Face API surface:

```python
from transformers import AutoTokenizer, AutoModelForMaskedLM

tokenizer = AutoTokenizer.from_pretrained("biohub/ESMC-300M", trust_remote_code=True)
model = AutoModelForMaskedLM.from_pretrained("biohub/ESMC-300M", trust_remote_code=True)
```

If `transformers` cannot resolve `model_type=esmc`, upgrade `transformers` and install Biohub `esm`.

## ESMC Biohub Forge and SAE

Use this path for Biohub-hosted ESMC SDK notebooks, ESMC 6B, or SAE feature extraction. It does not use `--local-files-only` and requires a token.

Install SDK support:

```bash
python skills/protein-embedding/scripts/setup_protein_embedding_env.py \
  --env-dir .venv-protein-embedding-esmc-forge \
  --model-family esmc \
  --include-biohub-esm \
  --verify-biohub-token-env BIOHUB_API_TOKEN \
  --output-dir output/protein-embedding/setup-esmc-forge
```

Set the token outside command history when possible:

```bash
export BIOHUB_API_TOKEN="..."
```

The script also accepts `ESM_API_KEY`, matching the Biohub SDK default. Prefer `BIOHUB_API_TOKEN` for this skill so the token source is explicit in `run_summary.json` without logging the token value.

Forge API surface:

```python
from esm.sdk import esmc_client
from esm.sdk.api import ESMProtein, LogitsConfig, SAEConfig

model = esmc_client(model="esmc-300m-2024-12", url="https://biohub.ai", token=token)
protein_tensor = model.encode(ESMProtein(sequence="ACDEFGHIKLMNPQRSTVWY"))
output = model.logits(
    protein_tensor,
    LogitsConfig(return_hidden_states=True, return_mean_hidden_states=True, ith_hidden_layer=-1),
)
```

SAE API surface:

```python
output = model.logits(
    protein_tensor,
    LogitsConfig(
        sae_config=SAEConfig(
            models=["esmc-6b-2024-12-sae-layer60-k64-codebook16384"],
            normalize_features=True,
        )
    ),
)
```

Troubleshooting:

- Missing token: set `BIOHUB_API_TOKEN` or `ESM_API_KEY`; never paste token values into reports.
- SAE normalization error for 300M SAE models: retry with `--no-sae-normalize-features`.
- ESMC 6B all-layer request failure: request a single layer such as `--layer 80`; Forge all-layer hidden states are not supported for 6B.
- API timeouts: increase `--timeout-sec`, reduce batch size, or run one sequence first.

## ProtT5

Automated setup:

```bash
python skills/protein-embedding/scripts/setup_protein_embedding_env.py \
  --env-dir .venv-protein-embedding-prott5 \
  --model-family prott5 \
  --model-id Rostlab/prot_t5_xl_uniref50 \
  --download-model \
  --output-dir output/protein-embedding/setup-prott5
```

Manual dependency fallback:

```bash
.venv-protein-embedding-prott5/bin/python -m pip install sentencepiece protobuf
```

Use T5 encoder models for embeddings:

```python
from transformers import AutoTokenizer, T5EncoderModel

tokenizer = AutoTokenizer.from_pretrained("Rostlab/prot_t5_xl_uniref50", do_lower_case=False)
model = T5EncoderModel.from_pretrained("Rostlab/prot_t5_xl_uniref50")
```

Run embedding with rare-residue replacement:

```bash
.venv-protein-embedding-prott5/bin/python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family prott5 \
  --replace-rare-aa \
  --output-dir output/protein-embedding/prott5
```

## Ankh

Automated setup:

```bash
python skills/protein-embedding/scripts/setup_protein_embedding_env.py \
  --env-dir .venv-protein-embedding-ankh \
  --model-family ankh \
  --model-id ElnaggarLab/ankh-base \
  --download-model \
  --output-dir output/protein-embedding/setup-ankh
```

Hugging Face API surface:

```python
from transformers import AutoTokenizer, T5EncoderModel

tokenizer = AutoTokenizer.from_pretrained("ElnaggarLab/ankh-base")
model = T5EncoderModel.from_pretrained("ElnaggarLab/ankh-base")
```

Use `ElnaggarLab/ankh-large` only when compute and download size are acceptable.

## SaProt

Automated Hugging Face setup:

```bash
python skills/protein-embedding/scripts/setup_protein_embedding_env.py \
  --env-dir .venv-protein-embedding-saprot \
  --model-family saprot \
  --model-id westlake-repl/SaProt_650M_AF2 \
  --download-model \
  --output-dir output/protein-embedding/setup-saprot
```

Hugging Face API surface:

```python
from transformers import EsmTokenizer, EsmForMaskedLM

tokenizer = EsmTokenizer.from_pretrained("westlake-repl/SaProt_650M_AF2")
model = EsmForMaskedLM.from_pretrained("westlake-repl/SaProt_650M_AF2")
```

Structure-aware SaProt needs AA+3Di tokens. For full structure-to-token conversion, install the SaProt repository and Foldseek separately:

```bash
git clone https://github.com/westlake-repl/SaProt.git
cd SaProt
conda create -n SaProt python=3.10
conda activate SaProt
bash environment.sh
```

Only add this full SaProt/Foldseek path when the user needs structure-aware token generation. Ordinary sequence embedding should be explicitly labeled `--saprot-input-mode aa-only`.

## Hugging Face access and transport

- Use `huggingface-cli login` for gated or rate-limited checkpoints.
- Use `--local-files-only` when models are already cached and network access is unavailable.
- For offline setup validation, combine `--download-model --local-files-only --run-smoke-test` so `snapshot_download(..., local_files_only=True)` verifies cache presence and the smoke test does not issue network requests.
- If downloads fail with Xet transport errors, retry with `HF_HUB_DISABLE_XET=1` or pass `--hf-disable-xet` to the setup script.
- If model download is not possible during planning, run setup without `--download-model` and run embedding with `--dry-run`.

## Device failures

- CUDA out-of-memory: reduce `--batch-size`, choose a smaller checkpoint, or switch to per-protein only.
- MPS errors: retry with `--device cpu`.
- T5 model decoder errors: use `T5EncoderModel`, not `AutoModelForSeq2SeqLM`, for embeddings.
- Missing hidden states: pass `output_hidden_states=True` or use the script, which requests hidden states for masked-LM families.

## Verification checklist

After environment setup:

- `setup_summary.json` exists and has `status=ok`.
- The recorded Python path points inside the selected venv.
- If `--download-model` was used, the Hugging Face snapshot step succeeded.
- If `--run-smoke-test` was used, the smoke output has `run_summary.json` with `status=ok`.

After a real run:

- `run_summary.json` exists and has `status=ok`.
- `embeddings.npz` exists.
- `protein_embeddings` shape is `[protein_count, embedding_dim]` for per-protein output.
- Multi-layer runs have `selected_layers` in `run_summary.json` and `protein_layer_embeddings` or `residue_layer_embeddings__<safe_id>` in `embeddings.npz`.
- Per-residue output keys are listed under `outputs.residue_embedding_keys`.
- SAE runs have `representation=sae-feature` and list `sae_model_name` in `outputs`.
- Warnings are reviewed, especially SaProt AA-only and rare-residue replacement warnings.
