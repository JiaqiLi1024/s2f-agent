# Model selection and score semantics

Select evidence axes before selecting models. A score is comparable across variants only under the same model, checkpoint, scoring strategy, and preprocessing unless a benchmark calibration says otherwise.

| Model | Identity in this project | Required inputs | Canonical score semantics | Main limitation |
|---|---|---|---|---|
| ESM-1v | sequence-only zero-shot variant scorer | WT sequence, substitutions | masked-marginal log-probability ratio, mutant minus WT; higher usually means more sequence-plausible | five separately trained checkpoints; long-sequence windowing changes context |
| ESMC 300M | sequence-only masked language model | WT sequence, substitutions | masked-token mutant-minus-WT log-probability | not ESM-1v and not automatically ProteinGym-calibrated |
| MSA profile | evolutionary baseline | query-anchored aligned homologs | log frequency or log-odds of mutant versus WT at aligned query column | sensitive to alignment depth, weighting, pseudocount, and query-gap mapping |
| PoET | autoregressive family-conditioned sequence model | sequence family/context prepared by PoET workflow | model-defined sequence or conditional log-likelihood ratio | preprocessing and repository/version must be pinned; not a stability predictor |
| AlphaMissense | imported human missense catalogue | supported human genomic/protein variant identifiers and matching release | published precomputed AlphaMissense score/class | official code release has no public trained weights for arbitrary inference |
| SaProt | structure-aware masked language model | AA+3Di tokens derived from a structure | mutant-minus-WT token log-probability under the selected scoring strategy | Foldseek/3Di generation and low-confidence masking are part of the method |
| ThermoMPNN | structure-conditioned stability model | compatible structure, chain/residue map, substitution | predicted ddG in the model's documented convention | sign convention and units must be copied from the executed revision; do not silently invert |
| ProteinMPNN | inverse-folding sequence designer used as a proxy | backbone structure and chain mapping | conditional mutant-minus-WT log-likelihood | likelihood proxy, not direct experimental fitness or thermodynamic stability |
| ESM-IF1 | inverse-folding language model | structure coordinates and sequence mapping | conditional mutant-minus-WT log-likelihood | likelihood proxy; missing coordinates and chain breaks affect scoring |
| ProteinGym | benchmark/data/evaluation substrate | assay table plus model scores | assay-specific rank/classification metrics and optional percentile/calibration | not a predictor; avoid assay leakage and cross-assay raw-score pooling |

## Selection rules

1. Use at least one sequence/evolution model when only sequence is available.
2. Add an MSA profile only when query-to-alignment columns are validated and alignment depth is reported.
3. Add structure-aware models only when residue mapping is unambiguous; a PDB residue number is not automatically the same as the FASTA position.
4. Use AlphaMissense only for a record covered by the selected precomputed release and record the identifier match.
5. Use ProteinGym after scoring to compare models on the same assay. Report the assay, directionality normalization, exclusions, and metric confidence/coverage.

## Agreement and disagreement

Group evidence by effect_axis. Agreement between ESM-1v and MSA profile is sequence/evolution agreement; agreement between ProteinMPNN and ESM-IF1 is structure-conditioned likelihood agreement. ThermoMPNN adds a distinct stability axis. A disagreement is reportable evidence, not an error to be averaged away.
