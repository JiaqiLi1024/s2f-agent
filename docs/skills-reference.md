# Skill Catalog

Individual `SKILL.md` files are the operational source of truth for each registered skill. This page is the orientation catalog for choosing a skill.

## Stable Skills (enabled by default)

| Skill ID | Family | Tasks | Key triggers | Path | Docs |
|---|---|---|---|---|---|
| `alphagenome-api` | api-variant-prediction | variant-effect, track-prediction, interval-prediction, plotting, troubleshooting | alphagenome, dna_client, predict_variant, predict_interval | `skills/alphagenome-api` | [SKILL.md](../skills/alphagenome-api/SKILL.md) |
| `alphagenome-research` | local-regulatory-model-inference | environment-setup, interval-prediction, track-prediction, variant-effect, interpretation | alphagenome-research, create_from_kaggle, create_from_huggingface | `skills/alphagenome-research` | [SKILL.md](../skills/alphagenome-research/SKILL.md) |
| `basenji-workflows` | quantitative-regulatory-activity | preprocessing, training, prediction, variant-effect, attribution, motif-analysis | basenji, basenji_train, basenji_sad, basenji_sed | `skills/basenji-workflows` | [SKILL.md](../skills/basenji-workflows/SKILL.md) |
| `bpnet-skill` | profile-prediction-and-attribution | environment-setup, preprocessing, training, prediction, attribution, motif-analysis, troubleshooting | bpnet model, bpnet 2, bpnet-train, bpnet-predict, bpnet-shap, modisco, finemo | `skills/bpnet-skill` | [SKILL.md](../skills/bpnet-skill/SKILL.md) |
| `borzoi-workflows` | sequence-to-signal | environment-setup, track-prediction, variant-effect, interpretation, tutorial-playbooks | borzoi, westminster, baskerville, human_gtex | `skills/borzoi-workflows` | [SKILL.md](../skills/borzoi-workflows/SKILL.md) |
| `caduceus-inference` | rc-equivariant-dna-language-models | embedding, forward, variant-effect, fine-tuning, training | caduceus, caduceus-ps, rcps, caduceus VEP | `skills/caduceus-inference` | [SKILL.md](../skills/caduceus-inference/SKILL.md) |
| `chrombpnet-skill` | bias-factorized-accessibility-modeling | environment-setup, preprocessing, bias-model-training, training, prediction, attribution, motif-analysis, footprinting, troubleshooting | chrombpnet, bias factorized, chrombpnet_nobias, pred_bw, contribs_bw | `skills/chrombpnet-skill` | [SKILL.md](../skills/chrombpnet-skill/SKILL.md) |
| `dnabert2` | transformer-embedding-and-finetuning | embedding, gue-evaluation, fine-tuning, csv-validation | dnabert2, zhihan1996/DNABERT-2-117M, gue | `skills/dnabert2` | [SKILL.md](../skills/dnabert2/SKILL.md) |
| `evo2-inference` | genome-language-model-inference | environment-setup, forward, embedding, generation, hosted-api | evo2, nvcf, flash-attn | `skills/evo2-inference` | [SKILL.md](../skills/evo2-inference/SKILL.md) |
| `gpn-models` | phylogenetic-language-models | framework-selection, loading, training, variant-scoring | gpn, phylogpn, gpn-star | `skills/gpn-models` | [SKILL.md](../skills/gpn-models/SKILL.md) |
| `hyenadna-inference` | long-context-dna-language-models | embedding, forward, fine-tuning, training | hyenadna, LongSafari, CharacterTokenizer, hyenadna-large-1m | `skills/hyenadna-inference` | [SKILL.md](../skills/hyenadna-inference/SKILL.md) |
| `nucleotide-transformer-v3` | transformers-ntv3 | environment-setup, embedding, fine-tuning, track-prediction, troubleshooting | ntv3, species-conditioning, post-trained, bigwig, annotation | `skills/nucleotide-transformer-v3` | [SKILL.md](../skills/nucleotide-transformer-v3/SKILL.md) |
| `pangolin-workflows` | tissue-specific-splice-prediction | environment-setup, variant-effect, prediction, troubleshooting | pangolin, tissue-specific splice, score_cutoff | `skills/pangolin-workflows` | [SKILL.md](../skills/pangolin-workflows/SKILL.md) |
| `segment-nt` | segmentation-heads | segmentation-inference, rescaling-factor, constraints, troubleshooting | segmentnt, segmentenformer, segmentborzoi | `skills/segment-nt` | [SKILL.md](../skills/segment-nt/SKILL.md) |
| `sei-workflows` | chromatin-profile-sequence-class | environment-setup, prediction, variant-effect, interpretation, training | sei, sequence class, chromatin profiles | `skills/sei-workflows` | [SKILL.md](../skills/sei-workflows/SKILL.md) |
| `skill-factory` | skilling-and-scaffolding | skill-scaffold, skill-registry-update, skill-template-generation, skill-validation | skill-factory, scaffold-skill, create-skill, generate-skill | `skills/skill-factory` | [SKILL.md](../skills/skill-factory/SKILL.md) |
| `spliceai-workflows` | splice-site-prediction | environment-setup, variant-effect, prediction, interpretation, troubleshooting | spliceai, DS_AG, DS_AL, splice variant | `skills/spliceai-workflows` | [SKILL.md](../skills/spliceai-workflows/SKILL.md) |

## Dev Skills (disabled by default)

Dev skills require `--include-disabled` to participate in routing, linking, and validation.

| Skill ID | Family | Tasks | Key triggers | Path | Docs |
|---|---|---|---|---|---|
| `basset-workflows` | legacy-cnn-regulatory | preprocessing, training, prediction, interpretation | basset, torch7, sad | `skills-dev/basset-workflows` | [SKILL.md](../skills-dev/basset-workflows/SKILL.md) |
| `bpnet` | profile-prediction-and-attribution | preprocessing, training, prediction, attribution | bpnet, shap, motif | `skills-dev/bpnet` | [SKILL.md](../skills-dev/bpnet/SKILL.md) |
| `nucleotide-transformer` | jax-haiku-transformers | environment-setup, tokenization, embedding, attention-analysis | nucleotide-transformer, nt-jax, 6-mer | `skills-dev/nucleotide-transformer` | [SKILL.md](../skills-dev/nucleotide-transformer/SKILL.md) |

## Skill Families

| Family | Description |
|---|---|
| `api-variant-prediction` | Cloud API-based variant-effect and interval/track prediction (AlphaGenome). Requires `ALPHAGENOME_API_KEY`. |
| `local-regulatory-model-inference` | Local AlphaGenome model creation and sequence, interval, track, and variant inference. |
| `sequence-to-signal` | Sequence-to-track prediction with multi-species Borzoi models. Strong for interval-based variant scoring and tissue-resolved track outputs. |
| `bias-factorized-accessibility-modeling` | ChromBPNet training and interpretation for base-resolution ATAC-seq or DNase-seq profiles with explicit enzyme-bias factorization. |
| `transformer-embedding-and-finetuning` | DNABERT-2 transformer for embeddings, GUE evaluation, and supervised fine-tuning from CSV. |
| `genome-language-model-inference` | Evo 2 large genome language model. Supports local GPU and hosted NVCF API paths. |
| `phylogenetic-language-models` | GPN family (GPN, PhyloGPN, GPN-Star) using multiple sequence alignments for variant scoring. |
| `transformers-ntv3` | NTv3 species-conditioned transformer. Supports embedding, track prediction, and mode-aware fine-tuning workflows (`prep` planning + `train` full run) for bigwig/annotation/CSV objectives. |
| `segmentation-heads` | SegmentNT family (SegmentNT, SegmentEnformer, SegmentBorzoi) for genomic element segmentation with rescaling constraints. |
| `legacy-cnn-regulatory` | Classic Basset CNN (Torch7) for regulatory prediction and SAD analysis. Dev only. |
| `profile-prediction-and-attribution` | BPNet profile prediction with SHAP-based attribution and external motif integration. The stable `bpnet-skill` supersedes the disabled `bpnet` draft. |
| `jax-haiku-transformers` | Classic NT v1/v2 JAX/Haiku inference with 6-mer tokenization. Dev only. |
| `skilling-and-scaffolding` | Tooling for scaffolding and registering consistent skill packages from specs. |
| `quantitative-regulatory-activity` | Basenji binned regulatory activity prediction, variant scores, and mutagenesis. |
| `rc-equivariant-dna-language-models` | Caduceus Hugging Face and benchmark embedding workflows with reverse-complement equivariance. |
| `long-context-dna-language-models` | HyenaDNA single-nucleotide long-context embeddings and Hydra training. |
| `tissue-specific-splice-prediction` | Pangolin splice-site strength prediction with transcript annotation context. |
| `chromatin-profile-sequence-class` | Sei chromatin profiles, sequence-class projections, and variant effects. |
| `splice-site-prediction` | SpliceAI splice delta annotation for VCF and custom sequence scoring. |

## Fine-Tuning Routing Notes

- `dnabert2` and `nucleotide-transformer-v3` are co-primary fine-tuning candidates.
- Explicit skill/model mentions take priority (`$dnabert2`, `$nucleotide-transformer-v3`, NTv3 model ids).
- Generic CSV fine-tuning queries with close evidence now return `decision=clarify` to ask which path should lead.
- Explicit NTv3 requests produce mode-aware plans (`prep` vs `train`) with mode-specific artifact expectations.

## Including Disabled Skills

All operational scripts (`link_skills.sh`, `route_query.sh`, `run_agent.sh`, `validate_*.sh`, `smoke_test.sh`) exclude disabled skills by default. To opt in:

```bash
bash scripts/link_skills.sh --include-disabled
bash scripts/route_query.sh --query "..." --include-disabled
bash scripts/validate_routing.sh --include-disabled
```

## Skill Discovery

`registry/skills.yaml` is the single source of truth for all operational scripts. The `enabled` field is enforced at runtime — a skill not listed or listed with `enabled: false` will not be routed to, linked, or validated by default.

To check that all enabled skill paths resolve correctly:

```bash
bash scripts/validate_registry.sh
# or
make validate-registry
```

## See Also

- [Routing Reference](./routing.md) — how the router selects among skills
- [Architecture](./architecture.md) — layer overview and migration notes
- `registry/skills.yaml` — authoritative skill index
