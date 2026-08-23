# Protein Embedding Playbook

Use this playbook for amino-acid sequence embeddings. Genomic intervals and DNA foundation-model embeddings remain in the genomic [Embedding Playbook](../embedding/README.md).

## Required inputs

- `sequence-or-fasta`: raw amino-acid sequence, FASTA path, or a resolvable UniProt accession
- `embedding-target`: `per-protein`, `per-residue`, or `both`

Recommended optional inputs include model family/checkpoint, backend, layer selection, pooling strategy, compute constraints, and output directory.

## Contract boundary

Protein and genomic embedding plans are separate. A protein request must never fall back to DNABERT2, Evo 2, Nucleotide Transformer, a genomic interval, or a BED workflow.

Default behavior:

- use local Hugging Face ESM-2 when no protein model family is selected
- validate the amino-acid alphabet before downloading a model
- use attention-mask-aware mean pooling for per-protein output
- exclude BOS/EOS tokens from per-residue output
- preserve FASTA identifiers and record model revision, layer, pooling, sequence lengths, and array shapes

## Plan and validate

    bash scripts/run_agent.sh \
      --task protein-embedding \
      --query 'Use $protein-embedding to generate per-protein ESM-2 embeddings from protein FASTA proteins.fa' \
      --format json

    python skills/protein-embedding/scripts/validate_protein_fasta.py \
      --fasta proteins.fa

Dry-run before a new model download or hosted request:

    python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
      --fasta proteins.fa \
      --model-family esm2 \
      --embedding-type per-protein \
      --dry-run \
      --output-dir output/protein-embedding/run-001

## Execute

    python skills/protein-embedding/scripts/run_real_protein_embedding_workflow.py \
      --fasta proteins.fa \
      --model-family esm2 \
      --embedding-type both \
      --output-dir output/protein-embedding/run-001

Use Biohub Forge only when the user explicitly selects that backend and supplies a token through `BIOHUB_API_TOKEN` or `ESM_API_KEY`. Never print the token.

## Expected outputs

Treat `run_summary.json` as the source of truth:

- `run_summary.json`
- `embeddings.npz`
- optional `protein_embeddings.tsv`
- validation and warning fields
- per-residue keys and shapes when requested

## Recovery

1. Clarify protein sequence/FASTA and embedding target.
2. Dry-run with a small ESM-2 checkpoint before a large download.
3. Reduce all-layer or per-residue output to last-layer per-protein output when memory is insufficient.
4. Switch only among compatible protein embedding families.
5. Use cached/local-only model files when network access is unavailable.

Do not route protein embedding failures to genomic embedding skills.
