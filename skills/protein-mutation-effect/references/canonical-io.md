# Canonical input and output contract

## Sequence input

Accept exactly one of --sequence or --fasta. FASTA identifiers are stable protein_id values. Uppercase the sequence and remove whitespace. Standard scoring accepts the 20 canonical amino acids; model-specific handling of X, B, Z, J, U, and O must be explicit.

## Mutation input

Residue positions are 1-based relative to the validated full WT sequence.

Accepted single substitutions:

- A42V
- p.Ala42Val
- P53:A42V when the prefix matches a FASTA ID

Use one repeated --mutation per variant. Within one multi-mutant variant, join substitutions with a colon, for example A42V:G55D. A mutation table may contain:

| column | required | meaning |
|---|---:|---|
| protein_id | for multi-FASTA | FASTA identifier |
| variant_id | no | stable user identifier |
| mutation_group or mutation | yes | one single or grouped substitution |

Canonicalization rejects out-of-range positions, repeated positions in a group, no-op substitutions, non-substitution HGVS, and WT residue mismatches.

## Canonical long score table

protein_mutation_scores.tsv contains one row per variant/model/score:

| column | meaning |
|---|---|
| protein_id, variant_id, mutation_group | normalized identity |
| mutation | per-substitution identity; equals mutation_group for group-level scores |
| model_family, model_id, model_revision | provenance |
| score_name | exact backend score name |
| effect_axis | sequence_plausibility, evolutionary_profile, structure_conditioned_likelihood, stability, human_missense_prior, or benchmark_calibration |
| native_effect_axis | original backend axis retained when effect_axis is canonicalized |
| raw_score, score_unit | original numeric output and unit |
| higher_is | more_tolerated, more_deleterious, more_stable, less_stable, or backend-defined text |
| native_higher_is | original backend direction retained when higher_is is canonicalized |
| status | completed, planned, imported, unavailable, failed, or excluded |
| error | empty on success; machine-readable explanation otherwise |
| source_path | raw or imported artifact |

Never fill raw_score for planned, unavailable, failed, or excluded rows. Keep raw score precision; presentation rounding belongs in a separate report.

Import mode validates protein_id, variant_id, mutation_group, and requested model identity. Unknown or duplicate identities make the import invalid; requested variant/model pairs missing from an otherwise valid import receive excluded status with missing_imported_score.

## Summary

protein_mutation_summary.json records counts by model/status/axis, warnings, and artifact paths. It may include within-model ranks or ProteinGym-derived percentiles, but it must not create an uncalibrated cross-axis average.
