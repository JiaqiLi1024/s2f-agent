---
name: protein-embedding
description: Use Protein Embedding for extracting protein language model representations from amino-acid sequences, FASTA files, UniProt accessions, or structure-aware protein tokens with ESM-2, ESMC, ProtT5, Ankh, and SaProt. Use when Codex needs protein sequence embeddings, per-protein representations, per-residue embeddings, layer-specific or all-layer hidden states, ESMC Biohub Forge embeddings, ESMC SAE feature activations, FASTA batch embedding, embedding cache creation, or standardized embedding artifacts for downstream protein analysis.
---

# Protein Embedding

## Overview

Use this skill to turn amino-acid sequences, FASTA files, UniProt accessions, or SaProt structure-aware tokens into standardized protein language model embeddings. Keep this skill focused on representation extraction, layer-specific hidden states, ESMC SAE feature artifacts, and embedding cache preparation.

Do not use this skill for mutation-effect scoring, sequence generation, protein function prediction, half-life prediction, structure prediction, or annotation reports except to prepare embeddings for those workflows.

## Follow This Decision Flow

1. Resolve the input type.
- Use `--sequence` for one amino-acid sequence.
- Use `--fasta` for batch embedding or cache creation.
- Use `--uniprot` only when the user gives an accession and sequence retrieval is needed.
- Use SaProt structure-aware input only when the user provides AA+3Di tokens or a prior structure-to-token workflow. Do not assume ordinary FASTA is structure-aware.

2. Validate protein sequences before model work.
- Use `scripts/validate_protein_fasta.py` for FASTA input.
- Keep FASTA IDs stable because they become embedding IDs.
- State how ambiguous or rare residues are handled (`X`, `B`, `Z`, `U`, `O`, `J`).
- Read `references/constraints.md` before accepting very long proteins, mixed alphabets, or SaProt tokens.

3. Choose the model family.
- Use ESM-2 as the default sequence-only backend.
- Use ESMC when the user explicitly wants the newer Biohub ESMC representations or ESMC SAE compatibility.
- Use ProtT5 for classic ProtTrans/T5-style embeddings.
- Use Ankh for lower-cost T5-style protein embeddings.
- Use SaProt only for structure-aware AA+3Di embeddings or clearly labeled AA-only SaProt experiments.
- Read `references/family-selection.md` before recommending a checkpoint.

4. Choose the execution backend.
- Use `--backend hf-transformers` by default for local Hugging Face checkpoints, reproducible caches, and offline-capable runs.
- Use `--backend biohub-forge` only for ESMC SDK/API workflows, ESMC 6B access, or SAE features. Require a Biohub token through `BIOHUB_API_TOKEN` or `ESM_API_KEY`; never print the token.
- Read `references/esmc-sdk-workflows.md` before running Biohub Forge, all-layer ESMC sweeps, or SAE feature extraction.

5. Install and verify the requested model environment before real embedding.
- Read `references/setup-and-troubleshooting.md` for the model-specific installation path.
- Use `scripts/setup_protein_embedding_env.py` to create a venv, install base dependencies, optionally install model-family extras, optionally pre-download the Hugging Face checkpoint, and run a smoke test.
- If the user requests ESM-2 and does not specify a checkpoint, run the setup smoke test with `facebook/esm2_t6_8M_UR50D` before using larger ESM-2 checkpoints.
- Do not install Biohub ESM, SaProt full repo, or Foldseek unless the selected workflow requires them.

6. Choose the embedding target and layer.
- Use `per-protein` for classifiers, clustering, retrieval, and downstream tabular models.
- Use `per-residue` for site-level models, residue annotation, or residue-window features.
- Use `both` when downstream needs are unclear and compute is acceptable.
- Use `--layer last` for a single final-layer embedding, `--layer all` for layer sweeps, or `--layer 0,12,24` for selected layers.
- Use `--representation hidden-state` for dense transformer states. Use `--representation sae-feature` only with ESMC Biohub Forge and an explicit `--sae-model-name`.
- Default pooling is attention-mask-aware mean pooling over non-special tokens.

7. Run the standardized workflow.
- Use `scripts/run_real_protein_embedding_workflow.py` for local Hugging Face embedding extraction, Biohub Forge ESMC embedding, layer extraction, and SAE feature extraction.
- Use `--dry-run` first when dependencies, model access, or sequence validity are uncertain.
- Use `scripts/convert_embedding_table.py` only for per-protein embeddings small enough to inspect as TSV.

8. Report outputs concretely.
- Treat `run_summary.json` as the source of truth for status, model, IDs, sequence lengths, embedding shapes, warnings, and artifact paths.
- For completed runs, report `embeddings.npz`, `protein_embeddings.tsv` when written, per-residue array keys, selected layers, backend, representation type, and BOS/EOS handling.
- For dry runs, report that no model was downloaded or executed.

9. Route out-of-scope requests.
- Mutation-effect scoring belongs in `protein-mutation-effect`.
- Sequence generation or guided evolution belongs in `protein-evolution-generation`.
- Function, half-life, stability, solubility, or property prediction belongs in `protein-function-property-prediction`.
- Structure lookup/folding belongs in `protein-structure-get`.
- Annotation reports belong in `protein-annotation-report`.

## Grounded API/CLI Surface

- `from transformers import AutoTokenizer, AutoModelForMaskedLM`
- `AutoTokenizer.from_pretrained("facebook/esm2_t12_35M_UR50D")`
- `AutoModelForMaskedLM.from_pretrained("facebook/esm2_t12_35M_UR50D")`
- `AutoTokenizer.from_pretrained("biohub/ESMC-300M", trust_remote_code=True)`
- `AutoModelForMaskedLM.from_pretrained("biohub/ESMC-300M", trust_remote_code=True)`
- `from esm.sdk import esmc_client`
- `from esm.sdk.api import ESMProtein, LogitsConfig, SAEConfig`
- `esmc_client(model="esmc-300m-2024-12", url="https://biohub.ai", token=os.environ["BIOHUB_API_TOKEN"])`
- `LogitsConfig(return_hidden_states=True, return_mean_hidden_states=True, ith_hidden_layer=-1)`
- `LogitsConfig(sae_config=SAEConfig(models=["esmc-6b-2024-12-sae-layer60-k64-codebook16384"], normalize_features=True))`
- `from transformers import T5EncoderModel`
- `T5EncoderModel.from_pretrained("Rostlab/prot_t5_xl_uniref50")`
- `T5EncoderModel.from_pretrained("ElnaggarLab/ankh-base")`
- `from transformers import EsmTokenizer, EsmForMaskedLM`
- `EsmTokenizer.from_pretrained("westlake-repl/SaProt_650M_AF2")`
- `EsmForMaskedLM.from_pretrained("westlake-repl/SaProt_650M_AF2")`
- `python skills/protein-embedding/scripts/setup_protein_embedding_env.py --env-dir .venv-protein-embedding --model-family esm2 --download-model --run-smoke-test`
- `python skills/protein-embedding/scripts/validate_protein_fasta.py --fasta input.fasta`
- `python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py --fasta input.fasta --model-family esm2 --embedding-type both --output-dir output/protein-embedding`
- `python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py --fasta input.fasta --model-family esm2 --layer all --embedding-type per-protein --output-dir output/protein-embedding/layers`
- `python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py --sequence ACDEFGHIKLMNPQRSTVWY --model-family esmc --backend biohub-forge --model-id esmc-300m-2024-12 --layer all --embedding-type per-protein --output-dir output/protein-embedding/esmc_forge_layers`
- `python skills/protein-embedding/scripts/convert_embedding_table.py --npz output/protein-embedding/embeddings.npz --output-tsv output/protein-embedding/protein_embeddings.tsv`

## References

- Read `references/family-selection.md` to choose among ESM-2, ESMC, ProtT5, Ankh, and SaProt.
- Read `references/inference-patterns.md` for runnable sequence, FASTA, dry-run, and conversion commands.
- Read `references/esmc-sdk-workflows.md` for Biohub ESMC SDK, layer sweep, SAE feature, and notebook-derived routing patterns.
- Read `references/constraints.md` for alphabet handling, tokenization, sequence length, pooling, and output schema.
- Read `references/setup-and-troubleshooting.md` for dependency, Hugging Face, device, and model-specific failure checks.

## Scripts

- `scripts/setup_protein_embedding_env.py`
- `scripts/validate_protein_fasta.py`
- `scripts/run_real_protein_embedding_workflow.py`
- `scripts/convert_embedding_table.py`
