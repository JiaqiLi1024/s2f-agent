# Scoring semantics

## ESM-1v

The runner masks the target WT position and computes masked-context marginal log-odds for each substitution:

`log P(alt at i | WT sequence with i masked) - log P(ref at i | WT sequence with i masked)`

For an N-member ensemble it averages member scores. For a group it sums site scores, labeled as an independence approximation. Higher means the alternate residue is more plausible under the model, not necessarily experimentally beneficial.

## ESMC 300M

The runner masks one WT position at a time and computes alternate-minus-reference log probability from the masked-token logits. Group values sum independently masked WT-context values. ESMC and ESM-1v use the same masked-marginal strategy here, but their checkpoint families, tokenizers, training data, and raw magnitudes are not interchangeable.

## MSA profile

At alignment column `i`, with canonical-residue count `c(a)`, valid depth `N`, pseudocount `alpha`, and alphabet size 20:

`p(a) = (c(a)+alpha)/(N+20*alpha)`

The substitution score is `log p(alt)-log p(ref)`. Group scores sum columns. Higher means greater alignment-column preference. The baseline does not correct sequence redundancy, phylogeny, or residue coupling.

## PoET

Preserve the native score and upstream row order. Upstream describes the score as useful for fitness ranking and reports positive correlation with ProteinGym fitness, so `higher_is=more_fit`. Do not rename it to probability or compare its magnitude directly with log-odds. PoET evaluates the full variant sequence conditioned on the supplied family MSA.

## AlphaMissense

`am_pathogenicity` is a released, precomputed human missense pathogenicity score. Higher means more pathogenic. Preserve `am_class` in evidence provenance. Do not transform its classes into clinical assertions, and do not use a sequence-only match when multiple proteins/isoforms could match.

## Cross-model comparison

Join rows by `protein_id + variant_id + mutation_group`, never by row number except the explicitly ordered PoET NPY import. Compare ranks within a model and protein/assay. If calibration is needed, fit and validate it on a held-out, leakage-controlled dataset such as a ProteinGym split. Never average raw values across different `effect_axis` values.
