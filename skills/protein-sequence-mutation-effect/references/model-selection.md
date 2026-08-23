# Model selection

| Model | Required input | Native evidence | Choose when | Do not claim |
|---|---|---|---|---|
| ESM-1v (1–5 member ensemble) | WT FASTA | WT-context marginal log-odds `log P(alt)-log P(ref)` | General zero-shot substitution ranking; ProteinGym-compatible baseline | Calibrated fitness, stability, or pathogenicity |
| ESMC 300M | WT FASTA | Masked-context log-odds | Current compact masked language-model evidence; sequences up to checkpoint context | Direct comparability with ESM-1v or a supervised assay score |
| MSA profile | Query-matched aligned FASTA/A3M | Column-frequency log-odds with recorded pseudocount | Transparent conservation evidence; offline/reproducible baseline | Pairwise epistasis or phylogeny correction |
| PoET | WT-family MSA plus variant FASTA, native checkpoint, NVIDIA GPU | Family-conditioned full-variant native score | Multi-mutation ranking when a relevant MSA exists | CPU support; commercial-use permission from the academic checkpoint license |
| AlphaMissense v2023 | Released human prediction table plus unambiguous protein substitution | Precomputed pathogenicity score | Human missense lookup/prioritization | New arbitrary-protein inference or clinical diagnosis |

## Minimal panels

- Fast, fully local baseline: `msa-profile`.
- Sequence-model consensus: `esm-1v,esmc-300m`, preserving separate score columns.
- Family-aware multi-mutant analysis: `poet` plus an MSA profile quality check.
- Human clinical-research lookup: `alphamissense` plus independent sequence/evolution evidence.

## Multi-substitution policy

ESM and MSA adapters sum single-site log-odds computed against WT context. This is an independence approximation. PoET scores the full mutated sequence and may capture context among substitutions. AlphaMissense lookup rejects multi-substitution groups. Never present the simple sum as an epistatic prediction.

## Practical constraints

ESM-1v members have 650M parameters each; use one member for a smoke test and five only when the ensemble is needed. ESMC 300M still requires model-weight storage and substantial RAM/VRAM. PoET's official implementation requires an NVIDIA GPU and was tested upstream on a 40 GB A100; reduce batch size for lower VRAM, but do not promise compatibility.
