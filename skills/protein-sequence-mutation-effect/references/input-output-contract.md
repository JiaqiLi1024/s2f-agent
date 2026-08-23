# Input and output contract

## FASTA

Use canonical uppercase amino acids only (`ACDEFGHIKLMNPQRSTVWY`). IDs are the first whitespace-delimited token after `>`, must be unique, and become `protein_id`. Sequence coordinates are 1-based. The validator rejects gaps and ambiguous residues in WT FASTA. A3M lowercase insertions are removed only while reading `--msa`.

## Mutation table

TSV is preferred. Minimum schema:

```text
protein_id	variant_id	mutation_group
P12345	P12345_A42V	A42V
P12345	P12345_double	A42V:G55D
```

Accepted aliases include ProteinGym `mutant`, `mutation`, `protein_variant`, `sequence_id`, and `uniprot_id`. Accepted mutation syntax is one-letter `A42V`, HGVS-protein-like `p.Ala42Val`, or a colon/comma-delimited group. Normalized output always uses colon-delimited one-letter substitutions. A position may occur once per group. `mutated_sequence`, if supplied, must equal the sequence generated from FASTA.

The standardized `normalized_mutations.tsv` columns are:

- `protein_id`, `variant_id`, `mutation_group`
- `mutation_count`, `positions`, `mutated_sequence`
- `status`, `error`

## MSA

Accept aligned FASTA or A3M. All aligned records must have equal length after removing A3M lowercase insertions. For each scored protein, exactly one aligned record must ungap to the WT sequence; exact ID is preferred. `-` and `.` are gaps. Noncanonical residues are ignored in profile counts. MSA profile scoring records alignment depth and pseudocount.

PoET requires an A3M of homologs for one WT family per native execution. Do not combine unrelated proteins into one invocation.

## Imported scores

For generic TSV/CSV import, provide `variant_id` (preferred) or `mutation_group`, plus `raw_score`, `score`, or `model_score`. PoET NPY import must be one-dimensional and exactly match normalized input order. AlphaMissense lookup recognizes `uniprot_id`/`protein_id`, `protein_variant`, `am_pathogenicity`, and `am_class` with common aliases.

## Long-form scores

Required columns:

```text
protein_id variant_id mutation_group model_id score_name effect_axis raw_score higher_is status error
```

Additional columns are `score_unit`, `aggregation`, and `evidence_source`. `raw_score` is blank unless `status=ok`. Status values include `ok`, `planned`, `unavailable`, `not_found`, `failed`, and `invalid_input`.

## Run artifacts

```text
<output-dir>/
  normalized_mutations.tsv
  scores.tsv
  run_summary.json
  manifest.json
  commands.sh
  logs/run.log
  raw/
  intermediate/
  intermediates.tar.gz          # when requested
```

`manifest.json` contains hashes for source inputs and durable artifacts. `run_summary.json` contains model list, mode, status counts, software versions, coordinate convention, and warnings. `commands.sh` contains no credentials.
