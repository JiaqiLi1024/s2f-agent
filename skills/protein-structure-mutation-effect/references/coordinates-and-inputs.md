# Coordinate and input contract

## Canonical files

Use one FASTA record unless a higher-level orchestrator has already split the batch. Preserve its identifier as `protein_id`. Accept `.pdb`, `.cif`, or `.mmcif` structures. Select exactly one polymer chain per validation run.

Mutation-table TSV columns:

| Column | Required | Meaning |
|---|---:|---|
| `protein_id` | no | Must match FASTA ID when present |
| `variant_id` | no | Stable row/group ID; generated when absent |
| `mutation_group` | no | Group for simultaneous substitutions |
| `mutation` | yes | Canonical `WT<1-based position>ALT`, for example `A42V` |
| `chain` | no | Structure chain; CLI `--chain` is fallback |
| `numbering` | no | `sequence` (default) or `pdb-auth` |
| `auth_seq_id` | for insertion-code auth mode | PDB/mmCIF author residue number |
| `insertion_code` | no | Author insertion code, preserved separately |

For CLI input, use comma-separated `A42V,G91D`; optionally prefix a chain as `B:A42V`. Do not encode an insertion code by squeezing it into the mutation string. Use table columns instead.

## Mapping rules

1. Parse ATOM records, ignore alternate locations other than blank or `A`, and preserve `(chain, auth_seq_id, insertion_code)` as the structure residue key.
2. Convert standard three-letter amino-acid names to one-letter codes. Mark nonstandard residues `X`; never guess their WT identity.
3. Align the structure-chain sequence to canonical FASTA using deterministic global alignment. A canonical position can map to zero or one structure residue; multiple possible chain alignments are not silently resolved.
4. Emit every canonical position to `residue_mapping.tsv`, including residues absent from the structure.
5. Validate WT first against FASTA and again against the mapped structure residue. Missing coordinates produce `missing_structure_residue`; a mismatch produces `structure_wt_mismatch`.
6. Treat canonical sequence positions as 1-based. PDB `auth_seq_id` is an opaque author coordinate and may be negative, discontinuous, or repeated with insertion codes.

## PDB versus mmCIF

Use `auth_asym_id`, `auth_seq_id`, and `pdbx_PDB_ins_code` when available in mmCIF. Fall back to label fields only when author fields are absent. Preserve both selected chain and author coordinate in outputs. Do not assume label sequence IDs equal FASTA positions.

## Confidence and SaProt masking

AlphaFold-style PDB/mmCIF files often store pLDDT in the B-factor field. Record mean residue B-factor. For SaProt workflows, replace the 3Di character for positions with pLDDT below the configured threshold (commonly 70) using SaProt's mask convention. Do not apply a pLDDT threshold to experimental crystallographic B factors; require the caller to declare that B-factor values represent pLDDT.

## Structural scope

- ThermoMPNN supports point-mutation ddG prediction in its primary repository; route double mutations to the distinct ThermoMPNN-D implementation and label its version separately.
- Score grouped mutations only with backends that explicitly support the group. Do not sum single-mutant ddG or log-odds as if interactions were absent.
- ProteinMPNN and ESM-IF1 condition on a backbone. Missing atoms, chain breaks, alternate assemblies, or predicted structures can change the score; record provenance.
