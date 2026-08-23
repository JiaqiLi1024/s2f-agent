# Tool Selection

## DeepLoc 2.1

Use DeepLoc 2.1 when the user asks for eukaryotic subcellular localization, membrane association, or broad sorting-signal context.

- Predicts multi-label localization classes such as nucleus, cytoplasm, extracellular, mitochondrion, cell membrane, ER, chloroplast, Golgi, lysosome/vacuole, and peroxisome.
- Predicts membrane association classes such as peripheral, transmembrane, lipid anchor, and soluble.
- Requires protein FASTA input and is not for nucleic-acid sequences.
- Use `--deeploc-model fast` for high-throughput and `slow` for higher-quality small runs.

## SignalP 6.0

Use SignalP 6.0 when the user asks for signal peptide, secretory signal, or cleavage-site prediction.

- Predicts signal peptides and cleavage sites across domains of life.
- `--signalp-organism eukarya` restricts eukaryotic runs to Sec/SPI signal peptides; `other` supports bacterial/archaeal signal peptide types.
- SignalP predicts entry into the secretory pathway, not final localization.
- Use slow mode when accurate signal-peptide region boundaries matter.

## TargetP 2.0

Use TargetP 2.0 when the user asks for N-terminal targeting peptides or organelle import signals.

- Predicts SP, mitochondrial transit peptide (mTP), chloroplast transit peptide (cTP), and thylakoid luminal transit peptide (lTP).
- Use `--targetp-organism plant` for plastid-containing organisms and `non-plant` otherwise.
- Complements SignalP: SignalP is stronger for signal peptide type/cleavage details; TargetP helps distinguish mitochondrial/chloroplast/thylakoid targeting.

## Boundary With TM Topology

Use `protein-tm-topology-annotation` instead when the primary request is:

- TM helix or beta-barrel detection
- inside/outside/periplasmic topology
- residue-level topology state plots
- DeepTMHMM/TMHMM GFF3 normalization

For complete localization interpretation, run both skills and merge outputs in `protein-annotation-report`.
