---
name: protein-structure-mutation-effect
description: Score and compare protein substitutions with structure-aware SaProt, ThermoMPNN, ProteinMPNN, and ESM-IF1 workflows from FASTA plus PDB/mmCIF inputs. Use when Codex needs to validate chain and residue numbering, map author residue identifiers to canonical 1-based sequence positions, run/import/plan structural mutation scoring, distinguish thermodynamic ddG from inverse-folding likelihood proxies, or emit auditable normalized mutation tables, long-form scores, manifests, logs, archives, and safe cleanup records.
---

# Protein Structure Mutation Effect

## Follow this workflow

1. Resolve the biological question before choosing a model.
   - Choose ThermoMPNN for single-substitution stability change estimates.
   - Choose SaProt for AA+Foldseek-3Di masked-marginal mutation scores.
   - Choose ProteinMPNN or ESM-IF1 for backbone-conditioned sequence likelihood/log-odds proxies.
   - Never rename an inverse-folding likelihood proxy as ddG, stability, activity, or pathogenicity.
   - Read `references/model-selection-and-scoring.md` before comparing scores.

2. Prepare FASTA and structure inputs.
   - Require a stable protein ID, one canonical sequence, a chain ID, and PDB or mmCIF when a selected model needs structure.
   - Treat mutation positions as 1-based canonical sequence positions unless `--numbering pdb-auth` is explicit.
   - Run `scripts/validate_structure_mutations.py` before model execution.
   - Stop a mutation row on WT mismatch, ambiguous chain mapping, missing residue, or unsupported substitution; do not shift coordinates heuristically.
   - Read `references/coordinates-and-inputs.md` for insertion codes, missing residues, multichain structures, and pLDDT/B-factor handling.

3. Install only the selected backend.
   - Read `references/setup-download-license.md` and pin the recorded source commit plus checkpoint identity.
   - Use `scripts/setup_structure_mutation_env.py --backend <name> --mode plan` first.
   - Prefer separate model environments because SaProt/Foldseek, ThermoMPNN, ProteinMPNN, and archived ESM-IF1 dependencies can conflict.
   - Record source commit, checkpoint checksum, CUDA/PyTorch versions, and accepted license in the run manifest.

4. Choose an adapter state.
   - Use `--mode plan` to validate inputs and write exact adapter commands without running a model.
   - Use `--mode execute` with one `--adapter-command model=...` per configured backend. The command must write a TSV to `{output}`; no shell interpolation is used.
   - Use `--mode import` with one `--import-file model=path.tsv` per precomputed output.
   - Missing structure, missing adapter, or one failed backend must yield per-model `unavailable` or `failed` rows while preserving the rest of the batch.

5. Run the standardized wrapper.

```bash
python skills/protein-structure-mutation-effect/scripts/run_structure_mutation_effect.py \
  --fasta input.fasta --structure structure.pdb --chain A \
  --mutations-file mutations.tsv \
  --models saprot,thermompnn,proteinmpnn,esm-if1 \
  --mode plan --output-dir output/structure-mutation
```

6. Interpret only comparable quantities.
   - Use `effect_axis`, `score_name`, `higher_is`, and model version together.
   - ThermoMPNN's canonical wrapper field is `ddg_kcal_mol`, with positive values interpreted as destabilizing (`higher_is=more_destabilizing`). Confirm an imported file's native convention before mapping it.
   - SaProt log-odds and inverse-folding log-odds use positive values for mutant preference when encoded as `log P(mut)-log P(wt)`.
   - Do not average raw scores across distinct effect axes. Calibrate or rank within model and assay context first.

7. Report auditable artifacts.
   - Treat `run_summary.json` and `manifest.json` as the status source of truth.
   - Return `normalized_mutations.tsv`, `residue_mapping.tsv`, `structure_mutation_scores.tsv`, `commands.sh`, `logs/`, `raw/`, and `intermediate/` when present.
   - Use `--archive-intermediates` before `--cleanup-intermediates`. Cleanup is explicit, limited to known run children, refuses symlinks, and requires a completed archive.
   - Read `references/output-archive-contract.md` for schemas and retention rules.

## Grounded command surface

- `python scripts/validate_structure_mutations.py --fasta protein.fasta --structure model.pdb --chain A --mutations-file mutations.tsv --output-dir validation`
- `python scripts/validate_structure_mutations.py --fasta protein.fasta --structure model.cif --chain A --mutations A2V,D3N --numbering sequence --output-dir validation`
- `python scripts/setup_structure_mutation_env.py --backend saprot --env-name s2f-saprot --source-root external --mode plan --output setup.json`
- `python scripts/run_structure_mutation_effect.py --fasta protein.fasta --structure model.pdb --mutations-file mutations.tsv --models thermompnn --mode import --import-file thermompnn=predictions.csv --output-dir output`
- `python scripts/run_structure_mutation_effect.py --fasta protein.fasta --structure missing.pdb --mutations-file mutations.tsv --models saprot,esm-if1 --mode execute --output-dir output`

## Read references selectively

- Read `references/setup-download-license.md` for official repositories, pinned revisions, checkpoints, dependencies, downloads, and licenses.
- Read `references/coordinates-and-inputs.md` for PDB/mmCIF, chain, auth residue, insertion-code, canonical sequence, mutation-table, and confidence-mask rules.
- Read `references/model-selection-and-scoring.md` for SaProt, ThermoMPNN, ProteinMPNN, and ESM-IF1 applicability and score direction.
- Read `references/output-archive-contract.md` for adapter input, unified output, manifest, status, archive, and cleanup contracts.
- Read `references/troubleshooting.md` after validation, environment, Foldseek, checkpoint, GPU, or adapter failures.

## Scripts

- `scripts/validate_structure_mutations.py` — parse FASTA plus PDB/mmCIF, align chain to canonical sequence, map author residue IDs, and validate mutations.
- `scripts/setup_structure_mutation_env.py` — generate or execute pinned, backend-specific environment/source setup plans.
- `scripts/run_structure_mutation_effect.py` — implement plan/execute/import states and normalized artifacts without fabricating unavailable scores.
- `scripts/smoke_test_structure_mutation_effect.py` — exercise PDB/mmCIF mapping, imports, archive creation, and missing-structure status without downloading a model.
