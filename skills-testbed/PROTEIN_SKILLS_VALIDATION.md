# Protein skills WSL validation

Validation date: 2026-08-23
Repository state: extracted working tree without `.git` metadata
Runtime: WSL2, NVIDIA GeForce RTX 5070 (12227 MiB), CUDA 12.8 through PyTorch

## Outcome

All 16 protein skills were exercised through their supported local execution, public-service, import, or plan paths. Eleven skills have a directly executed public/local backend and are runtime-ready. Five skills are runtime-ready at the wrapper/import/plan layer but still require separately licensed software, approved remote submission, large reference databases, or model-specific installations for full production backend coverage.

This report does not claim that restricted or very large third-party backends were executed.

## Environments

- `s2f-protein`: Python 3.11.16, PyTorch 2.11.0+cu128, Transformers 5.15.1, fair-esm 2.0.0, metapredict 3.0.2, Biopython 1.88, Biotite 1.6.0, Foldseek 10.941cd33, TM-align 20240303, HMMER 3.4, MAFFT 7.526, DIAMOND 2.2.5.
- `s2f-dssp`: isolated DSSP 4.5.8 environment. The conda-forge DSSP 4.6.1 build installed into the main environment had a `libmcfp` ABI failure and was removed.
- `s2f-esmc300m`: Python 3.12.14, PyTorch 2.11.0+cu128, Biohub/esm 3.3.0 at `67838dc8ac76f4145613e6cb36c5f3d758542f7c`, Biohub/transformers 4.57.6 at `ef32577f55da19a4989cd7b22e004dc43a4998cb`, ESMC checkpoint revision `a59b831785f907e96e6a246b1d142bfb76df31ee`.

GPU checks passed: `torch.cuda.is_available() == True`, device `NVIDIA GeForce RTX 5070`, and a CUDA tensor operation completed successfully.

## Skill matrix

| Skill | Validation performed | Result | Production caveat |
|---|---|---|---|
| `protein-annotation-report` | Raw sequence; real UniProt P04637 REST lookup; UniProt/InterPro/eggNOG fixture import | Ready | Public service availability affects live lookup |
| `protein-conservation-assessment` | Existing MSA; real local `jackhmmer -> MSA -> conservation` run | Ready | Large production databases were not downloaded |
| `protein-degron-annotation` | Real built-in QCDPred scoring | Ready | ELM/DEGRONOPEDIA datasets require explicit data/license review |
| `protein-domain-motif-annotation` | InterProScan6 and eggNOG command-plan generation | Conditional | InterProScan containers/data and eggNOG databases were not downloaded |
| `protein-embedding` | Real ESM-2 8M GPU embedding, per-protein and per-residue, dimension 320 | Ready | Larger checkpoints have higher storage/VRAM cost |
| `protein-idr-disorder-annotation` | Real metapredict 3.0.2 execution; IUPred3/FuzDrop/AggrescanAI fixture import | Ready | AIUPred and hosted services remain optional external backends |
| `protein-immunopresentation-annotation` | Peptide/request plan; IEDB binding/processing/immunogenicity fixture import | Conditional | Official local IEDB package or approved remote sequence submission required |
| `protein-localization-signal-annotation` | DeepLoc/SignalP/TargetP plan; all three fixture imports | Conditional | DTU tools/web services have separate access and license conditions |
| `protein-mutation-benchmark` | ProteinGym-style toy benchmark, 6 metrics | Ready | Full ProteinGym releases were not downloaded |
| `protein-mutation-effect` | All-backend plan; real MSA-profile + AlphaMissense child orchestration | Ready | Model-specific child backends retain their own requirements |
| `protein-sequence-mutation-effect` | Real ESM-1v GPU scoring (1 ensemble member, 2/2 ok); real ESMC-300M GPU scoring (2/2 ok); MSA-profile execution; AlphaMissense import | Ready | PoET weights were not downloaded because of noncommercial terms |
| `protein-structure-align` | Real TM-align on 1AKE vs 4AKE; real Foldseek P04637 self-search with one hit | Ready | Remote Foldseek upload was not used |
| `protein-structure-get` | Real P04637 RCSB/AlphaFold DB lookup and AlphaFold PDB download | Ready | ESMFold remote submission was not used |
| `protein-structure-mutation-effect` | PDB/mmCIF mapping, SaProt/ThermoMPNN imports, score-direction metadata, archive and missing-structure smoke checks | Conditional | SaProt, ThermoMPNN, ProteinMPNN, and ESM-IF1 checkpoints were not installed |
| `protein-structure-visualize` | Viewer, contact map, B-factor, highlight, pocket, and DSSP secondary structure on local/public structures | Ready | STRING/conservation hosted modules depend on public services |
| `protein-tm-topology-annotation` | TMHMM/DeepTMHMM plan; both fixture import paths and plots | Conditional | TMHMM/DeepTMHMM execution requires separately available tools/services |

## Defects found and fixed

1. Modern `mkdssp` accepts mmCIF input, while the structure visualizer passed PDB directly and silently fell back to all-coil assignments. The wrapper now converts parsed PDB structures to a temporary mmCIF file for DSSP. P04637 then produced 48 helix, 65 sheet, and 280 coil residues.
2. metapredict 3.x writes `query, sequence, score_1...score_N` CSV rows. The IDR parser only understood older residue-per-row TSV and reported success with zero scores. It now supports both formats and treats a non-parseable executed disorder output as an error. The real rerun produced 43 residue scores, one IDR (1-43), and two plots.
3. The ESMC setup requested Python 3.11 although the pinned Biohub/esm commit requires Python 3.12. Setup and documentation now use Python 3.12 and explicitly restore a verified Biohub/transformers commit after the upstream moving `@main` dependency.

No DNA skill source was changed by these runtime fixes.

## Framework regressions

- Codex package validation: passed.
- Registry: 24/24.
- Skill metadata: 24/24, zero warnings.
- Canonical input contracts: 24/24, zero warnings.
- Protein CLI initialization: 31/31 `--help`.
- Routing: 47/47.
- Groundedness: 27/27.
- Task success: 41/41.
- Sequence mutation self-executing smoke test: passed.
- Structure mutation smoke test: passed.

`make validate-agent` reaches and passes package and registry validation, then stops at `validate_registry_tracking.sh` because this extracted directory is not a Git work tree. Run that Git-tracking check again after placing the changes in the actual clone.

## Before a PR

1. Apply these changes to a real Git clone and inspect the diff.
2. Re-run `make validate-agent` so registry tracking can execute.
3. Decide whether validation documentation belongs in the PR or remains maintainer evidence.
4. Do not commit model caches, Conda environments, `/tmp` outputs, tokens, licensed databases, or third-party checkpoints.
5. Review licenses before adding PoET, IEDB, SignalP/TargetP/DeepLoc, TMHMM/DeepTMHMM, InterProScan, eggNOG, or structure-aware model assets.
