---
name: protein-conservation-assessment
description: "Assess evolutionary conservation for unknown protein sequences from a sequence-first workflow: validate amino-acid input, find or import homologous sequences, build or import an MSA, compute residue-level, conserved-region, and whole-protein conservation scores, and write standardized TSV/JSON/plot reports. Use when Codex needs protein conservation, homolog search, jackhmmer/HMMER, MMseqs2, MAFFT, Biotite-based MSA or visualization, conserved residues, conserved regions, variable residues, ortholog/homolog support, or sequence-first conservation reports for protein FASTA or amino-acid sequences."
---

# Protein Conservation Assessment

## Overview

Use this skill for sequence-first evolutionary conservation assessment:

`unknown protein sequence -> homolog search or homolog import -> MSA -> residue/region/protein conservation scoring -> standardized report`.

Use `protein-structure-visualize` when the primary task is coloring an existing PDB/AlphaFold structure by conservation. Use this skill first when homolog discovery, MSA generation, residue tables, and sequence-level reports are the primary deliverable.

## Workflow

1. Choose input.
- Use `--sequence` and `--sequence-name` for a single unknown protein.
- Use `--fasta` for one or more query proteins.
- Use `--homolog-fasta` when homologs are already available.
- Use `--alignment` when a trusted aligned FASTA or Stockholm MSA already exists.
- Use `--query-id` when the MSA contains multiple sequences and a specific query should receive residue coordinates.

2. Choose homolog source.
- Prefer an existing project-specific protein FASTA when the user has a relevant taxonomic scope.
- Use local HMMER/jackhmmer against a user-approved local database for sensitive homolog discovery.
- Use MMseqs2 for fast homolog search against large local databases, then export hit sequences to FASTA before MSA.
- Use EBI HMMER only when hosted execution and its database/release provenance are acceptable.

3. Confirm environment and database policy.
- Read `references/setup-and-databases.md` before installing software or planning database downloads.
- Create a dedicated conda/mamba environment for this skill.
- Ask the user before downloading large databases. Confirm database choice, destination directory, expected size, and whether a specific `protein.fasta` should be used instead.
- Do not hard-code personal example paths; prefer user-provided paths or a neutral project directory such as `$HOME/biodata/protein_conservation`.

4. Build or import MSA.
- Use Biotite for Python-native small MSA workflows and plotting helpers when available.
- Use MAFFT for production protein MSA, either directly or through Biotite's MAFFT application interface.
- Treat equal-length homolog FASTA as a prealigned MSA only when that assumption is explicitly acceptable.

5. Compute and report conservation.
- The bundled script computes normalized Shannon-entropy conservation scores for query-mapped residues.
- Coordinates in `protein_conservation_sites.tsv` and `protein_conserved_regions.tsv` are 1-based query residue positions.
- Conserved/variable region thresholds must be recorded in the result JSON and summary TSV.

## Quick Start

Score an existing MSA:

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --alignment query_homologs.aligned.fasta \
  --query-id query1 \
  --outdir output/protein-conservation-assessment/query1
```

Score homolog FASTA and let the script use MAFFT or Biotite when available:

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --homolog-fasta homologs.fasta \
  --msa-backend auto \
  --outdir output/protein-conservation-assessment/query1
```

Plan local jackhmmer search and database setup without running heavy commands:

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --search-backend local-hmmer \
  --target-db /path/to/protein_database.fasta \
  --db-choice swissprot \
  --db-dir "$HOME/biodata/protein_conservation" \
  --outdir output/protein-conservation-assessment/query1_plan
```

Run local jackhmmer only after the database path is valid and the user wants execution:

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --sequence "MSEQUENCE..." \
  --sequence-name query1 \
  --search-backend local-hmmer \
  --target-db /path/to/protein_database.fasta \
  --execute \
  --outdir output/protein-conservation-assessment/query1
```

## References

- Read `references/setup-and-databases.md` for conda environment setup, missing conda/mamba handling, and database download planning.
- Read `references/workflow.md` for tool selection, homolog filtering, MSA, and interpretation rules.
- Read `references/output-schema.md` before changing report columns.
- Read `references/biotite-visualization.md` when using Biotite for MSA wrappers, alignment plots, or sequence logos.

## Outputs

- `protein_conservation_summary.tsv`: one row per query conservation assessment.
- `protein_conservation_sites.tsv`: one row per query residue.
- `protein_conserved_regions.tsv`: conserved and variable contiguous regions.
- `alignment.fasta`: aligned sequences used for scoring.
- `homologs.filtered.fasta`: deduplicated homolog/query FASTA when homolog input exists.
- `commands.sh`: local search/import command plan.
- `database_download_plan.sh`: non-executed database download plan for user review.
- `plots/conservation_profile.svg`, `.png`, `.html`: compact conservation profile when plotting dependencies are available.
- `protein_conservation_assessment.result.json`: parameters, warnings, output paths, and summary.

## Failure And Recovery

- If no homologs or MSA exist, generate command and database download plans instead of fabricating conservation scores.
- If `mafft` and Biotite are unavailable, import an existing MSA with `--alignment`.
- If UniRef90 is too large for the user's machine, start with Swiss-Prot, UniRef50, Reference Proteomes, or a taxon-specific protein FASTA.
- If a query has many paralogs, report homolog scope as a limitation and prefer curated ortholog/homolog sets when interpreting functional conservation.
- If conservation is needed on a structure, run this skill first for sequence scores, then pass the sites/regions to `protein-structure-visualize` for 3D mapping.

## Script

- `scripts/protein_conservation_assessment.py`
