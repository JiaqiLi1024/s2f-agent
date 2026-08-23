# Constraints

Use this file before accepting unusual protein inputs, long sequences, or structure-aware workflows.

## Input alphabet

Default canonical amino acids:

```text
ACDEFGHIKLMNPQRSTVWY
```

Common ambiguous or unknown residues:

- `X`: unknown residue; allowed with a warning.
- `B`: ambiguous `D/N`; require `--allow-ambiguous-aa` or replace with `X`.
- `Z`: ambiguous `E/Q`; require `--allow-ambiguous-aa` or replace with `X`.
- `J`: ambiguous `I/L`; require `--allow-ambiguous-aa` or replace with `X`.
- `U`: selenocysteine; require `--allow-rare-aa` or replace with `X` for T5-style models.
- `O`: pyrrolysine; require `--allow-rare-aa` or replace with `X` for T5-style models.

For ProtT5 and Ankh, replace `U`, `Z`, `O`, and `B` with `X` unless the downstream model explicitly requires a different policy.

## SaProt input boundary

SaProt 35M and 650M are intended for structure-aware AA+3Di tokens. Ordinary amino-acid FASTA can be run only as an AA-only experiment and should be labeled as such.

Rules:

- Use `--saprot-input-mode sa-token` only when the input already contains SaProt combined tokens.
- Use `--saprot-input-mode aa-only` only when the user explicitly wants AA-only SaProt behavior.
- Do not invent Foldseek/3Di tokens from amino-acid sequence alone.
- If a structure must be converted to 3Di, use a separate structure/Foldseek workflow first.

## Embedding types

- `per-protein`: one vector per sequence; default for classifiers, clustering, search, and property predictors.
- `per-residue`: one matrix per sequence; default for residue-level downstream tasks.
- `both`: write both outputs when the downstream task is not yet known.

Default pooling is attention-mask-aware mean pooling over non-special tokens. Use `cls` or `bos` only for models and downstream tasks that were trained with those conventions.

## Layer selection

Use `--layer last` for one final-layer representation. Use `--layer all` when the downstream task is a layer sweep or when no layer is known to be best. Use comma-separated indices such as `--layer 0,12,24` when the user asks for specific layers.

Layer conventions:

- Hugging Face `hidden_states` follows the model output tuple; index `0` is usually the embedding layer and the last index is the final transformer state.
- Biohub ESMC `LogitsConfig.ith_hidden_layer` uses index `0` as the embedding layer.
- ESMC 300M exposes layers `0..30`, ESMC 600M exposes `0..36`, and ESMC 6B exposes `0..80`; Forge all-layer requests are not supported for ESMC 6B.
- Record `layer_spec`, `selected_layers`, `available_layer_count`, and `layer_indexing` in `run_summary.json`.

## Biohub Forge boundary

Use `--backend biohub-forge` only when the user explicitly asks for Biohub ESMC, Forge/API execution, ESMC 6B, or SAE features.

Rules:

- Require `BIOHUB_API_TOKEN` or `ESM_API_KEY`; never print token values.
- Do not use `--local-files-only` with Forge.
- Use `--representation sae-feature` only with `--model-family esmc`, `--backend biohub-forge`, and an explicit `--sae-model-name`.
- SAE feature outputs are model-derived activations, not experimentally validated annotations.

## Output schema

The real workflow writes:

- `embeddings.npz`
  - `protein_embeddings`: float array `[n_proteins, embedding_dim]` when per-protein output is requested for one selected layer or SAE feature pooling.
  - `protein_layer_embeddings`: float array `[n_proteins, n_selected_layers, embedding_dim]` when per-protein output is requested for multiple layers.
  - `protein_ids`: string array `[n_proteins]`.
  - `selected_layers`: integer array `[n_selected_layers]` when layer output has multiple layers.
  - `residue_embeddings__<safe_id>`: float array `[n_residue_tokens, embedding_dim]` when per-residue output is requested for one layer.
  - `residue_layer_embeddings__<safe_id>`: float array `[n_selected_layers, n_residue_tokens, embedding_dim]` when per-residue output is requested for multiple layers.
  - `sae_features__<safe_id>`: float array `[n_residue_tokens, n_sae_features]` when ESMC SAE feature extraction is requested.
- `protein_embeddings.tsv`: optional readable table for per-protein embeddings.
- `run_summary.json`: source-of-truth metadata.

`run_summary.json` must include:

- `skill_id`
- `status`
- `input`
- `model_family`
- `model_id`
- `backend`
- `representation`
- `embedding_type`
- `pooling`
- `layer_spec`
- `selected_layers`
- `layer_indexing`
- `protein_count`
- `sequence_lengths`
- `embedding_dim`
- `outputs`
- `warnings`

## Length and memory

- Validate all sequences before downloading a model.
- For long proteins, reduce `--batch-size` before truncating.
- If truncation is unavoidable, state the truncation policy and record it in `run_summary.json`.
- Do not silently split a protein into chunks unless the user explicitly wants chunk-level embeddings.
- Do not use per-residue output for large proteomes unless storage requirements are acceptable.

## Interpretation limits

Embedding vectors are model representations, not experimental annotations. Do not present them as confirmed function, localization, half-life, stability, or pathogenicity evidence.
