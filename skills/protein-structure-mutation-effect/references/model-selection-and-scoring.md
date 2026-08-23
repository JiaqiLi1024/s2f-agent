# Model selection and scoring semantics

| Model | Required representation | Canonical score | `effect_axis` | `higher_is` | Interpretation boundary |
|---|---|---|---|---|---|
| SaProt | amino acid + Foldseek 3Di tokens; confidence mask when applicable | `masked_log_odds` | `structure_language_model_preference` | `more_mutant_preferred` | Zero-shot sequence/structure-token preference, not ddG |
| ThermoMPNN | protein structure and point substitution | `ddg_kcal_mol` | `thermodynamic_stability_change` | `more_destabilizing` | Canonical wrapper uses mutant minus WT free-energy change; confirm imported source convention |
| ProteinMPNN | backbone, chain context, native and mutant sequence | `conditional_log_odds` | `backbone_conditioned_sequence_preference` | `more_mutant_preferred` | Inverse-folding/design likelihood proxy, not a direct stability predictor |
| ESM-IF1 | backbone coordinates plus native/mutant sequences | `conditional_log_likelihood_ratio` | `backbone_conditioned_sequence_preference` | `more_mutant_preferred` | Inverse-folding likelihood proxy; repository scoring averages log-likelihood across residues |

## SaProt

Generate Foldseek 3Di states from a compatible structure and interleave each amino acid with its 3Di token. SaProt's official repository exposes a mutation prediction helper and supports multiple mutations, but the exact checkpoint and input token convention must be recorded. When an AlphaFold structure is used, apply the official pLDDT masking recommendation (default threshold 70 unless the checkpoint/workflow says otherwise). A positive canonical `masked_log_odds = log P(mut)-log P(wt)` favors the mutant under the model; it does not prove higher biological fitness.

## ThermoMPNN

Use for point substitutions when the question is structural stability. Emit the native output and a canonical `ddg_kcal_mol` field. This skill defines canonical ddG as `G_mutant - G_wildtype`, so positive means destabilizing and negative means stabilizing. If an upstream CSV uses the opposite sign, transform it only after documenting `source_score_name`, `source_higher_is`, and the sign conversion. Do not use the point-mutant model for deletions or grouped substitutions.

## ProteinMPNN

Use conditional or unconditional backbone-conditioned probabilities for a residue-level log-odds proxy. Prefer the probability outputs rather than comparing generated-sequence header scores when possible. Define `conditional_log_odds = log P(mutant residue | backbone/context) - log P(WT residue | backbone/context)`. ProteinMPNN's reported sequence `score` is a negative log probability and lower is better; do not mix it directly with the positive-is-mutant-preferred log-odds field.

## ESM-IF1

The official ESM repository supplies `score_log_likelihoods.py` for sequences conditioned on a structure. For a mutation group, compare mutant and WT sequences under the same chain/backbone: `LLR = log P(mutant sequence | backbone) - log P(WT sequence | backbone)`. The official CSV score is average conditional log-likelihood per residue, so preserve whether a score is average or summed. ESM-IF1 is archived with the ESM repository and may require an older dependency environment.

## Cross-model use

Keep one row per model, mutation group, score name, checkpoint, and structure. Rank or calibrate within a defined evaluation set before ensemble use. Never average ThermoMPNN ddG with SaProt or inverse-folding log-odds. Disagreement is evidence to inspect structure provenance, conservation, solvent exposure, confidence, oligomeric context, and assay phenotype—not an error to hide.
