# Protein Mutation Effect Playbook

Use this playbook for protein-level substitutions. Genomic chromosome, assembly, REF, and ALT requests remain in the genomic variant-effect playbook.

## 1. Validate and plan first

    python skills/protein-mutation-effect/scripts/run_protein_mutation_effect.py \
      --fasta skills-testbed/inputs/protein-mutation-effect/toy.fasta \
      --mutations-file skills-testbed/inputs/protein-mutation-effect/mutations.tsv \
      --models esm1v,esmc-300m,msa-profile,saprot,thermompnn,poet,proteinmpnn,esm-if1,alphamissense \
      --mode plan \
      --output-dir output/protein-mutation-effect/toy-plan

This validates 1-based positions and WT residues before any model download. Models missing MSA, structure, or lookup tables remain as unavailable status rows.

## 2. Sequence/evolution execution

Read the component setup reference first and use its model-specific environment.

    conda run -n s2f-esm1v python \
      skills/protein-sequence-mutation-effect/scripts/run_sequence_mutation_effect.py \
      --fasta output/protein-mutation-effect/toy-plan/inputs/normalized_sequences.fasta \
      --mutations-file output/protein-mutation-effect/toy-plan/inputs/normalized_mutations.tsv \
      --models esm1v \
      --mode execute \
      --output-dir output/protein-mutation-effect/toy-sequence

Run ESMC separately in its `s2f-esmc300m` environment with `--models esmc-300m`; ESM-1v and Biohub ESMC both import as `esm`, so do not combine their incompatible dependency sets without a tested lock.

For MSA profile scoring, add --msa and record query-row identity, query-to-column mapping, sequence weighting, and pseudocount. For PoET, pin repository and preprocessing revisions. For AlphaMissense, pass a compatible precomputed catalogue; do not attempt arbitrary-protein inference.

## 3. Structure-aware execution

First validate FASTA to PDB or mmCIF chain mapping. PDB auth residue numbers and insertion codes are not the canonical FASTA index.

    conda run -n s2f-saprot python \
      skills/protein-structure-mutation-effect/scripts/run_structure_mutation_effect.py \
      --fasta <WT_FASTA> \
      --structure <STRUCTURE_PDB_OR_MMCIF> \
      --mutations-file <NORMALIZED_MUTATIONS_TSV> \
      --models saprot,thermompnn,proteinmpnn,esm-if1 \
      --mode plan \
      --output-dir output/protein-mutation-effect/toy-structure

SaProt needs AA+3Di tokens and documented low-confidence masking. ThermoMPNN is the stability axis. ProteinMPNN and ESM-IF1 provide structure-conditioned sequence likelihood proxies, not direct thermodynamic stability.

## 4. Import existing scores

    python skills/protein-mutation-effect/scripts/run_protein_mutation_effect.py \
      --fasta skills-testbed/inputs/protein-mutation-effect/toy.fasta \
      --mutations-file skills-testbed/inputs/protein-mutation-effect/mutations.tsv \
      --models esm1v,thermompnn \
      --mode import \
      --import-scores skills-testbed/inputs/protein-mutation-effect/import_scores.tsv \
      --output-dir output/protein-mutation-effect/toy-import

Imported rows retain score name, direction, effect axis, revision, and source path.

## 5. ProteinGym evaluation

    python skills/protein-mutation-benchmark/scripts/run_proteingym_benchmark.py \
      --assay-data skills/protein-mutation-benchmark/references/fixtures/toy_dms.csv \
      --scores skills/protein-mutation-benchmark/references/fixtures/toy_scores.tsv \
      --output-dir output/protein-mutation-benchmark/toy

ProteinGym is used here to evaluate or calibrate model outputs. Compare within assay and report exclusions and coverage.

## 6. Archive and cleanup

Use --archive-intermediates on a completed run to create a compressed audit artifact. Use --cleanup-intermediates only as a separate explicit action after checking scores, summary, manifest, logs, and archive. Cleanup never removes model caches or raw source data.

## Reporting checklist

Report input sequence/version, numbering convention, variants, requested and completed models, model/checkpoint revisions, score names and directions, effect axes, failures/unavailable reasons, ProteinGym assay/release if used, output paths, verification level, and the fact that results are computational evidence rather than clinical conclusions.
