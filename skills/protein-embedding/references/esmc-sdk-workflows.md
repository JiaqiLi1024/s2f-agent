# ESMC SDK Workflows

Use this file when a user asks for Biohub ESMC notebooks, Biohub Forge/API execution, ESMC layer sweeps, or ESMC SAE features.

## Notebook-derived scope

The Biohub ESM tutorial notebooks imply these boundaries:

- `embed.ipynb`: in scope. Extract ESMC mean hidden states, per-residue hidden states, and compare layers.
- `esmc_layer_sweep.ipynb`: partly in scope. Extract all-layer embeddings and save artifacts; leave classifier training and evaluation to a downstream function/property skill.
- `esmc_sae_feature_interpretation.ipynb`: partly in scope. Extract SAE activations and rank/store features; leave 3D visualization to a structure-visualization or interpretability workflow.
- `esmc_mutation_scoring.ipynb`: out of scope for this skill except for shared model setup. Route entropy, masked logits, and log-likelihood ratios to `protein-mutation-effect`.
- `esmc_finetune.ipynb`: out of scope after embedding extraction. Route PEFT, classification heads, and regression heads to a prediction/fine-tuning skill.
- ESM3 generation notebooks (`esmprotein`, `esm3_generate`, `esm3_guided_generation`, `gfp_design`): route to protein evolution/generation.
- ESMFold2 and binder design notebooks: route to structure/design skills.

## Backend choice

Use local Hugging Face ESMC when the user wants local reproducibility:

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family esmc \
  --backend hf-transformers \
  --model-id biohub/ESMC-300M \
  --trust-remote-code \
  --embedding-type both \
  --output-dir output/protein-embedding/esmc_hf
```

Use Biohub Forge only when the user explicitly asks for Biohub API/SDK, ESMC 6B, SAE features, or notebook parity:

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --sequence ACDEFGHIKLMNPQRSTVWY \
  --protein-id esmc_forge \
  --model-family esmc \
  --backend biohub-forge \
  --model-id esmc-300m-2024-12 \
  --embedding-type per-protein \
  --layer all \
  --output-dir output/protein-embedding/esmc_forge
```

## Grounded SDK surface

Biohub ESMC client:

```python
from esm.sdk import esmc_client
from esm.sdk.api import ESMProtein, LogitsConfig

model = esmc_client(model="esmc-300m-2024-12", url="https://biohub.ai", token=token)
protein = ESMProtein(sequence=sequence)
protein_tensor = model.encode(protein)
output = model.logits(
    protein_tensor,
    LogitsConfig(return_hidden_states=True, return_mean_hidden_states=True, ith_hidden_layer=-1),
)
```

Layer rules from `LogitsConfig`:

- `return_hidden_states=True` returns per-residue hidden states.
- `return_mean_hidden_states=True` returns mean-pooled hidden states.
- `ith_hidden_layer=-1` requests all supported layers.
- `ith_hidden_layer=<int>` requests one layer.
- Index `0` is the embedding layer.

Use `--layer all` to request all layers for ESMC 300M/600M. Do not request all layers for ESMC 6B through Forge; request one layer such as `--layer 80`.

## SAE features

Use SAE only when the user asks for sparse autoencoder features, interpretable activations, or ESMC SAE.

```python
from esm.sdk.api import SAEConfig

output = model.logits(
    protein_tensor,
    LogitsConfig(
        sae_config=SAEConfig(
            models=["esmc-6b-2024-12-sae-layer60-k64-codebook16384"],
            normalize_features=True,
        )
    ),
)
features = output.sae_outputs["esmc-6b-2024-12-sae-layer60-k64-codebook16384"]
```

Standard script command:

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --sequence ACDEFGHIKLMNPQRSTVWY \
  --protein-id sae_example \
  --model-family esmc \
  --backend biohub-forge \
  --model-id esmc-6b-2024-12 \
  --representation sae-feature \
  --sae-model-name esmc-6b-2024-12-sae-layer60-k64-codebook16384 \
  --embedding-type both \
  --output-dir output/protein-embedding/esmc_sae
```

For 300M SAE models, `normalize_features=True` may be unsupported. Retry with `--no-sae-normalize-features`.

## Output expectations

For hidden-state layer sweeps:

- Single selected layer: `protein_embeddings` and/or `residue_embeddings__<safe_id>`.
- Multiple selected layers: `protein_layer_embeddings` and/or `residue_layer_embeddings__<safe_id>`.
- `run_summary.json` must record `backend`, `representation`, `layer_spec`, `selected_layers`, and `layer_indexing`.

For SAE features:

- Per-residue features: `sae_features__<safe_id>`, shape `[n_residue_tokens, n_sae_features]`.
- Per-protein features: `protein_embeddings`, mean-pooled over residue SAE activations.
- Remove BOS/EOS-like special positions when they appear in returned tensors.

