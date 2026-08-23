# Tool Selection

## DeepTMHMM

Use DeepTMHMM when the user asks for current transmembrane topology annotation, beta-barrel detection, proteome-scale topology, or both alpha-helical and beta-barrel membrane proteins.

- DeepTMHMM predicts topology over all domains of life and covers alpha-helical and beta-barrel proteins.
- The DTU web service notes that if more than one sequence is submitted, no native web plots are made. Generate standardized per-protein plots from GFF3 in that case.
- Prefer importing DeepTMHMM GFF3 with `--deeptmhmm-gff3` when the user has web or BioLib results.
- Use `--deeptmhmm-command-template` only when the exact local/BioLib command is known in that environment.

Common outputs to preserve:

- GFF3 region file.
- Native web/BioLib plots if available for single-sequence jobs.
- Any summary text produced by the service.

## TMHMM

Use TMHMM when the user explicitly asks for TMHMM, wants a legacy comparator, or has existing TMHMM long output.

- TMHMM 2.0 is useful for alpha-helical TM segments, inside/outside topology, and legacy reproducibility.
- TMHMM long output contains predicted segments such as `inside`, `outside`, and `TMhelix`.
- TMHMM plots contain posterior probabilities for inside/outside/TM helix. These probabilities are not recoverable from GFF3 or long segment output alone.
- N-terminal TMHMM helices can represent signal peptides; preserve the warning if present.

## Plot Choice

- If native plots are available, record them with `--native-plot`.
- Always generate standardized HTML/SVG state plots from parsed GFF3/long output.
- Do not label GFF3-derived state plots as posterior probability plots.
