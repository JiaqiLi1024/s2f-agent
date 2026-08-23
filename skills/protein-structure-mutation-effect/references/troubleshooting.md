# Troubleshooting

## Validation fails

- **WT mismatch against FASTA:** verify isoform and whether the reported mutation uses mature-protein, construct, UniProt, or PDB numbering.
- **No mapped structure residue:** inspect missing loops and chain selection; do not offset all positions until one mutation fits.
- **Insertion code ambiguity:** supply `auth_seq_id` and `insertion_code` as separate table fields.
- **mmCIF chain absent:** check `auth_asym_id` versus `label_asym_id`; the parser prefers author IDs.
- **Low alignment identity:** confirm that FASTA and structure represent the same construct and that engineered tags were handled explicitly.

## SaProt fails

- Run `foldseek version` and verify the binary path passed to the adapter.
- Ensure 3Di tokens were generated from the same chain and coordinate mapping used for mutations.
- Use pLDDT masking only when B factors actually store pLDDT.
- Check checkpoint directory versus single `.pt` file expectations; the official mutation model expects a configured checkpoint directory.

## ThermoMPNN fails

- Confirm the official checkpoint exists and the PDB has required backbone atoms.
- Verify PyTorch CUDA build separately; the upstream environment file may resolve a CPU build.
- Use the original point-mutant repository for single substitutions and ThermoMPNN-D only for explicitly supported double-mutant runs.
- Verify the source CSV's ddG sign before import.

## ProteinMPNN fails

- Confirm selected weight folder and model name agree.
- Distinguish CA-only from full-backbone weights.
- Inspect chain sorting and slash-separated multichain FASTA conventions.
- Prefer saved probability arrays for residue log-odds; header `score` is negative log probability.

## ESM-IF1 fails

- Pin the archived ESM source and a compatible Python/PyTorch stack.
- Confirm N, CA, and C coordinates exist for the selected chain.
- Run WT and mutant FASTA through the same structure and chain settings.
- Preserve whether the official output is mean log-likelihood per residue or a derived summed value.

## Wrapper status is unavailable

This is expected when structure is absent, an execute adapter command was not configured, or an import file is missing. Read `run_summary.json` and per-row `error`; the wrapper deliberately writes status rows instead of fabricating scores or aborting unrelated backends.
