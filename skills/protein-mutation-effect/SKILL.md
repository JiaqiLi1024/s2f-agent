---
name: protein-mutation-effect
description: Orchestrate protein missense and multi-substitution effect scoring across ESM-1v, ESMC 300M, MSA profiles, PoET, AlphaMissense lookup, SaProt, ThermoMPNN, ProteinMPNN, and ESM-IF1. Use when Codex must validate amino-acid substitutions against a wild-type sequence, select compatible sequence- or structure-aware models, run or plan reproducible scoring, import precomputed scores, preserve intermediates, or format multi-model results without conflating incompatible score meanings. Do not use for genomic REF/ALT variants.
---

# Protein Mutation Effect

## Overview

Use this skill as the orchestration layer above three component skills:

- protein-sequence-mutation-effect runs sequence/evolution models and AlphaMissense lookup.
- protein-structure-mutation-effect runs structure-conditioned models.
- protein-mutation-benchmark evaluates outputs against ProteinGym-compatible assays.

ProteinGym is the benchmark and calibration substrate, not a predictive model. Never average raw scores across different effect_axis values.

## Follow This Workflow

1. Separate protein substitutions from genomic variants.
   - Accept protein forms such as A42V, p.Ala42Val, and grouped substitutions such as A42V:G55D.
   - Route chromosome/assembly/REF/ALT requests to genomic variant-effect instead.

2. Normalize before installing or downloading models.
   - Run scripts/normalize_protein_mutations.py.
   - Require exactly one wild-type sequence per protein and validate every WT residue at its 1-based sequence position.
   - Preserve the user's original notation while emitting canonical one-letter substitutions.

3. Read references/model-selection.md and choose evidence axes.
   - Sequence plausibility: ESM-1v, ESMC 300M, MSA profile, PoET.
   - Human missense prior: AlphaMissense precomputed lookup only.
   - Structure-aware plausibility: SaProt, ProteinMPNN, ESM-IF1.
   - Stability proxy: ThermoMPNN predicted ddG; retain its declared sign convention.
   - Benchmark calibration: ProteinGym assay metrics and ranks.

4. Read references/environment-and-installation.md before setup.
   - Keep a light shared orchestration environment separate from model-specific environments when dependency sets conflict.
   - Pin code revisions and checkpoint identifiers in run_manifest.json.
   - Do not claim AlphaMissense arbitrary-protein inference; its official public repository does not publish trained weights.

5. Choose an execution state explicitly.
   - plan: validate inputs and write exact commands without model execution or download.
   - execute: invoke available component runners and record per-model success or failure.
   - import: normalize externally computed long-form score tables.
   - Import only rows matching this run's protein_id, variant_id, mutation_group, and requested model; reject cross-run or duplicate identities.
   - Missing weights, credentials, structure, MSA, or optional packages must produce unavailable status, never a fabricated numeric score.

6. Run the orchestrator. A minimal plan command is:

    python skills/protein-mutation-effect/scripts/run_protein_mutation_effect.py --fasta proteins.fasta --mutation P53:A42V --models esm1v,esmc-300m,msa-profile,saprot,thermompnn,poet,proteinmpnn,esm-if1,alphamissense --mode plan --output-dir output/protein-mutation-effect

   Add --structure input.pdb, --msa homologs.a3m, or --alphamissense-table AlphaMissense_hg38.tsv.gz only when required. PoET execute also needs --poet-repo plus an optional --poet-python. Structure plans validate residue mapping and default to minimum 0.8 mapped coverage and 0.9 mapped identity; override only with --min-structure-coverage and --min-structure-identity after documenting why.

   Use --archive-intermediates to retain a compressed audit trail. Use --cleanup-intermediates only after inspecting final tables; cleanup is explicit and restricted to the run's intermediate directory.

7. Interpret outputs by axis and direction.
   - Use protein_mutation_scores.tsv as the canonical long table.
   - Compare models only after checking score_name, effect_axis, higher_is, model revision, and status.
   - Report agreement, disagreement, missing evidence, and assay-specific calibration. Do not label a variant pathogenic from these scores alone.

## Output Contract

Every run writes:

- inputs/normalized_sequences.fasta
- inputs/normalized_mutations.tsv
- protein_mutation_scores.tsv
- protein_mutation_summary.json
- run_manifest.json
- commands.sh
- logs, raw, and intermediate directories while applicable

The long table contains at least protein_id, variant_id, mutation_group, mutation, model_id, score_name, effect_axis, raw_score, higher_is, status, and error. Read references/canonical-io.md for the full schema.

## References

- Read references/model-selection.md for model identity, intended use, prerequisites, and score semantics.
- Read references/canonical-io.md for accepted mutation formats and output schemas.
- Read references/environment-and-installation.md before creating environments or downloading checkpoints/data.
- Read references/run-lifecycle.md for manifests, archives, cleanup, retries, and reporting.

## Scripts

- scripts/normalize_protein_mutations.py
- scripts/run_protein_mutation_effect.py
