# ProteinGym Role, Release, Data, and License

## Identity in S2F

ProteinGym is not an inference backend. Use it after mutation-effect models have emitted scores. It supplies:

- standardized DMS and clinical benchmark tables;
- reference sequences, assay metadata, MSAs, structures, and supervised splits;
- published baseline score matrices;
- official scoring and aggregation code;
- comparison surfaces for reproducibility.

Keep model generation and benchmark evaluation as separate run stages and separate manifests.

## Version Pin

The official repository and download page listed v1.3 as the newest release checked on 2026-07-19. GitHub labels PG_v1.3 as released 2025-04-28. Pin v1.3 in commands and manifests instead of relying on a mutable latest URL. Re-check the official sources before claiming that it remains latest:

- Official repository: https://github.com/OATML-Markslab/ProteinGym
- Official downloads: https://proteingym.org/download
- v1.3 archival release: follow the v1.3 Zenodo link from the repository release section.

## Processed Data Semantics

- Each processed DMS file represents one assay; each processed clinical file represents one clinical protein.
- Substitution files use mutant strings such as A1P:D2N.
- DMS_score is direction-normalized by ProteinGym: higher means better measured protein fitness.
- Clinical tables do not have continuous DMS_score; DMS_score_bin represents benign/pathogenic classification according to the benchmark definition.
- Keep the ProteinGym release's target sequence, UniProt ID, assay ID, and preprocessing notes with every evaluation.

## License and Attribution

The official repository declares an MIT license for the project. Do not assume that this statement erases attribution, citation, privacy, or redistribution conditions of every underlying experimental or clinical source. Preserve assay provenance, consult assays.bib, inspect source-specific terms before redistribution, and cite:

Notin et al. “ProteinGym: Large-Scale Benchmarks for Protein Fitness Prediction and Design.” NeurIPS 2023.

For clinical use, treat outputs as research benchmark results, not diagnostic or patient-level evidence.
