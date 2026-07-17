# Family Selection

Use this file to choose the embedding backend before writing commands.

## Default recommendation

Start with ESM-2 unless the user names another family.

- Smoke test or CPU-constrained run: `facebook/esm2_t6_8M_UR50D`
- Small production run: `facebook/esm2_t12_35M_UR50D`
- Higher-quality sequence embedding: `facebook/esm2_t33_650M_UR50D`
- Newer local ESMC embedding: `biohub/ESMC-300M` or `biohub/ESMC-600M` with `--backend hf-transformers`
- Biohub Forge ESMC embedding or SAE features: `esmc-300m-2024-12`, `esmc-600m-2024-12`, or `esmc-6b-2024-12` with `--backend biohub-forge`
- Classic ProtTrans embedding: `Rostlab/prot_t5_xl_uniref50`
- Lower-cost T5-style protein embedding: `ElnaggarLab/ankh-base` or `ElnaggarLab/ankh-large`
- Structure-aware embedding: `westlake-repl/SaProt_650M_AF2`

## Model matrix

| Family | Best use | Default checkpoint | Notes |
| --- | --- | --- | --- |
| ESM-2 | General sequence-only per-protein or per-residue embeddings | `facebook/esm2_t6_8M_UR50D` for smoke tests, `facebook/esm2_t33_650M_UR50D` for quality | Stable Hugging Face path; good default. |
| ESMC local | Newer Biohub ESM representations with local Hugging Face checkpoints | `biohub/ESMC-300M` | Requires recent `transformers`; install `esm` from Biohub when the model class is unavailable. |
| ESMC Forge | Biohub ESMC SDK/API, 6B access, all-layer mean hidden states, SAE feature activations | `esmc-300m-2024-12` for light API runs, `esmc-600m-2024-12` for layer sweeps, `esmc-6b-2024-12` for supported 6B workflows | Requires Biohub token in `BIOHUB_API_TOKEN` or `ESM_API_KEY`; do not use for offline runs. |
| ProtT5 | ProtTrans-style embeddings and compatibility with existing ProtT5 downstream models | `Rostlab/prot_t5_xl_uniref50` | T5 encoder workflow; replace rare residues with `X` and space amino acids before tokenization. |
| Ankh | Efficient T5-style protein embeddings | `ElnaggarLab/ankh-base` | Similar preprocessing to ProtT5; choose `ankh-large` when compute allows. |
| SaProt | Structure-aware embeddings from AA+3Di tokens | `westlake-repl/SaProt_650M_AF2` | Do not treat ordinary FASTA as structure-aware input. |

## Selection rules

1. Use ESM-2 when the user only says "protein embeddings" or provides ordinary FASTA.
2. Use local ESMC when the user mentions ESMC or newer Biohub ESM representations but wants local embeddings or a Hugging Face checkpoint.
3. Use ESMC Forge when the user mentions Biohub API, Forge, ESMC 6B, ESMC SAE, or notebook workflows using `esm.sdk`.
4. Use ProtT5 when the user needs ProtTrans compatibility or already has ProtT5 downstream models.
5. Use Ankh when the user wants a smaller T5-style embedding model or explicitly mentions Ankh.
6. Use SaProt only when structure-aware tokens, Foldseek/3Di output, or an explicitly SaProt-based downstream model is in scope.
7. If the user asks for mutation scoring, entropy, or log-likelihood ratios, route to `protein-mutation-effect`.
8. If the user asks for ESM3 generation/evolution, motif scaffolding, guided generation, or GFP design, route to `protein-evolution-generation`.
9. If the user asks for enzyme classification, function prediction, half-life prediction, stability, solubility, or fine-tuning heads, route to `protein-function-property-prediction` after preparing embeddings if needed.

## Layer and representation rules

- Use `--layer last` when the user asks for a normal embedding and does not specify a layer.
- Use `--layer all` when the user asks which layer is best, asks for a layer sweep, or wants embeddings for downstream layer selection.
- Use `--layer <indices>` when the user names layers, for example `--layer 0,12,24`.
- Use `--representation hidden-state` for dense embeddings from ESM-2, ESMC, ProtT5, Ankh, or SaProt.
- Use `--representation sae-feature` only for ESMC Forge with an explicit SAE model name.
- Keep layer sweeps in this skill only through extraction and artifact preparation. Classifier training or regression belongs to a downstream prediction/fine-tuning skill.

## Compute guidance

- For CPU-only smoke tests, use ESM-2 35M or Ankh base.
- For limited single-GPU runs, start with ESM-2 35M/150M or local ESMC 300M.
- For higher-quality representation extraction, use ESM-2 650M, ESMC 600M, ProtT5 XL, or SaProt 650M with GPU.
- For very large FASTA batches, validate first, then run in small batches and write an embedding cache.
- For Biohub Forge runs, budget API credits/tokens before batching and prefer dry-run plus a one-sequence smoke request before large jobs.
