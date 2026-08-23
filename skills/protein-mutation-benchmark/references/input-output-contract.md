# Input and Output Contract

## Assay Input

Accept CSV or TSV with a header.

Required:

- mutation identity via mutation, mutant, variant_id, variant, or mutations;
- at least one ground-truth field:
  - continuous DMS_score, dms_score, fitness, experimental_score, or target; or
  - binary DMS_score_bin, label, class, or clinical_label.

Recommended:

- assay_id or DMS_id;
- protein_id or UniProt_ID;
- target sequence and release metadata in a separate manifest.

Binary labels accept 0/1, true/false, positive/negative, pathogenic/benign, deleterious/neutral, or active/inactive. Map unusual labels explicitly before evaluation.

## Project Long-form Score Input

Required:

- mutation identity via mutation or variant_id;
- model_id;
- raw_score or a supported score alias.

Recommended:

- protein_id;
- assay_id;
- score_name;
- higher_is with higher/lower or a declared project direction such as more_tolerated, more_sequence_plausible, more_evolutionarily_preferred, more_fit, more_mutant_preferred, more_stable, more_deleterious, more_pathogenic, more_destabilizing, or less_stable.

Minimum interoperable fields are:

| Field | Meaning |
|---|---|
| protein_id | Stable sequence/protein identifier |
| mutation or variant_id | One-based protein mutation identity |
| model_id | Exact model/checkpoint or adapter |
| raw_score | Unmodified numeric model output |

Never overwrite raw_score after score-direction orientation. The aligned table adds oriented_score.

## Alignment Key

The runner aligns on assay_id plus normalized mutation. If both sides have nonempty protein_id, they must match. A missing assay column receives --assay-id or, as a fallback, the assay filename stem. For multi-assay files, require real assay IDs.

## Output Layout

| Artifact | Contract |
|---|---|
| metrics.tsv | Long-form per assay/model/score metric rows |
| summary.json | Overall status, counts, settings, limitations, artifact paths |
| aligned_scores.tsv | Truth, raw score, direction, and oriented score |
| exclusions.tsv | Every unmatched score with a machine-readable reason |
| alignment_report.json | Counts and per-group coverage |
| assay_validation.json | Assay mapping and invalid-row report |
| score_validation.json | Score mapping and invalid-row report |
| manifest.json | Command, Python version, input paths, SHA-256 digests |
| commands.sh | Reproduction command |
| raw/ | Immutable copies of supplied tables |
| intermediate/ | Normalized tables |
| logs/run.log | Concise execution record |

The runner does not silently aggregate across assays or protein families.
