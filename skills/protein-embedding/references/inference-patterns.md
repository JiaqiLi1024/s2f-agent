# Inference Patterns

Use these commands for standardized protein embedding extraction.

## Install environment before real embedding

Use the setup script when the requested model environment is not already available:

```bash
python skills/protein-embedding/scripts/setup_protein_embedding_env.py \
  --env-dir .venv-protein-embedding \
  --model-family esm2 \
  --model-id facebook/esm2_t6_8M_UR50D \
  --download-model \
  --run-smoke-test \
  --output-dir output/protein-embedding/setup
```

Then use that environment's Python:

```bash
.venv-protein-embedding/bin/python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --sequence ACDEFGHIKLMNPQRSTVWY \
  --protein-id smoke \
  --model-family esm2 \
  --model-id facebook/esm2_t6_8M_UR50D \
  --embedding-type both \
  --device cpu \
  --output-dir output/protein-embedding/esm2_smoke
```

## Validate FASTA first

```bash
python skills/protein-embedding/scripts/validate_protein_fasta.py \
  --fasta proteins.fasta \
  --output-json output/protein-embedding/fasta_validation.json
```

Allow ambiguous residues only when the downstream workflow accepts them:

```bash
python skills/protein-embedding/scripts/validate_protein_fasta.py \
  --fasta proteins.fasta \
  --allow-ambiguous-aa \
  --allow-rare-aa \
  --output-json output/protein-embedding/fasta_validation.json
```

## Dry-run without model download

Use this before any first run on a new FASTA:

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family esm2 \
  --embedding-type both \
  --dry-run \
  --output-dir output/protein-embedding
```

Dry-run validates input, resolves the model id, plans output files, and writes `run_summary.json`; it does not import PyTorch or download a model.

## Single-sequence embedding

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --sequence MEEPQSDPSVEPPLSQETFSDLWKLLPEN \
  --protein-id example_tp53_fragment \
  --model-family esm2 \
  --model-id facebook/esm2_t12_35M_UR50D \
  --embedding-type both \
  --output-dir output/protein-embedding/example
```

## Layer-specific or all-layer embedding

Use a single layer when a downstream model expects a fixed representation:

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --sequence ACDEFGHIKLMNPQRSTVWY \
  --protein-id layer_last \
  --model-family esm2 \
  --model-id facebook/esm2_t6_8M_UR50D \
  --embedding-type both \
  --layer last \
  --output-dir output/protein-embedding/esm2_last_layer
```

Use all layers when the task is layer selection or layer sweep. Multi-layer per-protein output is written as `protein_layer_embeddings` with shape `[n_proteins, n_selected_layers, embedding_dim]`; multi-layer residue output uses `residue_layer_embeddings__<safe_id>`.

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family esm2 \
  --model-id facebook/esm2_t6_8M_UR50D \
  --embedding-type per-protein \
  --layer all \
  --output-dir output/protein-embedding/esm2_all_layers
```

Use comma-separated layer indices when a paper, notebook, or downstream model specifies layers:

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family esm2 \
  --embedding-type both \
  --layer 0,3,6 \
  --output-dir output/protein-embedding/esm2_selected_layers
```

## Batch FASTA embedding

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family esm2 \
  --model-id facebook/esm2_t33_650M_UR50D \
  --embedding-type per-protein \
  --batch-size 2 \
  --output-dir output/protein-embedding/esm2_650m
```

## ESMC embedding

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family esmc \
  --model-id biohub/ESMC-300M \
  --embedding-type per-protein \
  --trust-remote-code \
  --output-dir output/protein-embedding/esmc_300m
```

If `transformers` cannot resolve `model_type=esmc`, install the Biohub ESM package as described in `setup-and-troubleshooting.md`.

## ESMC Biohub Forge hidden states

Use this path for notebook-style ESMC SDK workflows, ESMC 6B, or Biohub-hosted models. Set a token in the shell before running; do not paste the token into commands or reports.

```bash
export BIOHUB_API_TOKEN="..."

python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --sequence ACDEFGHIKLMNPQRSTVWY \
  --protein-id esmc_forge_example \
  --model-family esmc \
  --backend biohub-forge \
  --model-id esmc-300m-2024-12 \
  --embedding-type per-protein \
  --layer all \
  --output-dir output/protein-embedding/esmc_forge_all_layers
```

For a single layer, use the ESMC layer index directly:

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family esmc \
  --backend biohub-forge \
  --model-id esmc-600m-2024-12 \
  --embedding-type both \
  --layer 36 \
  --output-dir output/protein-embedding/esmc_forge_layer36
```

## ESMC SAE feature extraction

Use SAE features only when the user explicitly asks for sparse autoencoder features or interpretable ESMC activations. The SAE model name must match a Biohub-supported SAE checkpoint.

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

SAE per-residue outputs are written as `sae_features__<safe_id>` after removing BOS/EOS-like special positions when present. Per-protein SAE output is mean-pooled over residue feature activations.

## ProtT5 embedding

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family prott5 \
  --model-id Rostlab/prot_t5_xl_uniref50 \
  --replace-rare-aa \
  --embedding-type per-protein \
  --output-dir output/protein-embedding/prott5
```

The script spaces residues for T5-style tokenizers and replaces rare residues with `X` when requested.

## Ankh embedding

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family ankh \
  --model-id ElnaggarLab/ankh-base \
  --embedding-type per-protein \
  --output-dir output/protein-embedding/ankh_base
```

## SaProt embedding

For ordinary amino-acid FASTA, label the run as AA-only:

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta proteins.fasta \
  --model-family saprot \
  --model-id westlake-repl/SaProt_650M_AF2 \
  --saprot-input-mode aa-only \
  --embedding-type per-protein \
  --output-dir output/protein-embedding/saprot_aa_only
```

For structure-aware SaProt tokens, pass `--saprot-input-mode sa-token` and use a FASTA whose sequences already contain combined AA+3Di tokens:

```bash
python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
  --fasta saprot_tokens.fasta \
  --model-family saprot \
  --saprot-input-mode sa-token \
  --embedding-type both \
  --output-dir output/protein-embedding/saprot_sa
```

## Convert per-protein embeddings to TSV

```bash
python skills/protein-embedding/scripts/convert_embedding_table.py \
  --npz output/protein-embedding/embeddings.npz \
  --output-tsv output/protein-embedding/protein_embeddings.tsv
```

Use TSV only for small to moderate embedding tables. Keep `.npz` as the primary artifact for large runs.
