---
name: protein-structure-get
description: Retrieve protein structure context for a gene symbol, UniProt accession, or amino-acid sequence. Resolves UniProt, collects UniProt features, lists mapped RCSB PDB structures, checks AlphaFold Protein Structure Database entries, optionally renders domain maps/downloads AlphaFold models, creates PyMOL visualization scripts, and can submit valid amino-acid sequences to the hosted ESMFold API for PDB prediction. Use when Codex needs gene-to-protein-structure lookup, protein domain maps, PDB coverage, AlphaFold DB availability, ESMFold sequence-to-structure prediction, PyMOL setup for retrieved models, or structure retrieval from public protein databases.
---

# Protein Structure Get

## Overview

Use this skill to turn a gene symbol, UniProt accession, or amino-acid sequence into auditable protein-structure context. It retrieves the canonical UniProt entry, UniProt feature annotations, mapped RCSB PDB structures, and AlphaFold DB structure metadata; it can also render a linear domain map, download AlphaFold mmCIF/PDB models, create PyMOL visualization scripts for local structure outputs, or submit a validated sequence to the hosted ESMFold API for PDB output.

This is a retrieval and hosted-API structure acquisition skill. Do not use it to run AlphaFold locally, align structures, dock ligands, run molecular dynamics, or make clinical claims.

## Workflow

1. Resolve the user target.
- Prefer `--gene <symbol>` with `--organism human` unless the user states another species.
- Use `--uniprot <accession>` only when the user gives a UniProt accession or gene-symbol resolution is ambiguous.
- Use `--sequence <AA_SEQUENCE>` or `--sequence-file <FASTA_OR_TEXT>` only when the user provides an amino-acid sequence for hosted ESMFold prediction.
- Use NCBI taxon IDs for non-human organisms when a common alias is not enough.

2. Choose modules.
- Default to `--modules all` for broad structure context.
- Use `uniprot` for protein metadata and features.
- Use `pdb` for experimental structures mapped to the UniProt accession.
- Use `alphafold` for AlphaFold DB model metadata and structure URLs.
- Use `domain_map` only when a visual domain/feature schematic is useful.
- Use `esmfold` only with `--sequence` or `--sequence-file`; sequence-mode `--modules all` is treated as `esmfold`.
- Add `--download-structure` when the user asks to save the AlphaFold structure file.
- Add `--pymol` when the user asks for PyMOL visualization. This writes a `.pml` script for ESMFold outputs or downloaded AlphaFold models. Use `--run-pymol` only when PyMOL is installed and a `.pse/.png` output is needed.

3. Run the script.

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --gene TP53 \
  --organism human \
  --modules all \
  --outdir output/protein-structure/TP53
```

4. Inspect `protein_structure_get.result.json` first. Treat it as the source of truth for status, resolved accession, warnings, output files, and partial failures.

## Runtime Dependencies

Install the declared scientific Python stack when the active environment does not already provide it:

```bash
python -m pip install -r skills/protein-structure-get/requirements.txt
```

PyMOL is an optional external program. The script can always write `.pml` scripts, but `--run-pymol` requires `pymol` on `PATH` or a path passed with `--pymol-bin`.

## Command Surface

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  (--gene <GENE_SYMBOL> | --uniprot <ACCESSION> | --sequence <AA_SEQUENCE> | --sequence-file <PATH>) \
  [--sequence-name <LABEL>] \
  [--organism human|mouse|rat|NCBI_TAXON_ID] \
  [--modules all|uniprot,pdb,alphafold,domain_map,esmfold] \
  [--max-pdb 20] \
  [--download-structure] \
  [--download-format cif|pdb|both] \
  [--esmfold-min-length 15] \
  [--esmfold-max-length 400] \
  [--allow-ambiguous-aa] \
  [--pymol] \
  [--run-pymol] \
  [--pymol-bin pymol] \
  [--pymol-color-mode chain|confidence] \
  [--pymol-highlight-residues A:42,A:57] \
  [--timeout-sec 30] \
  --outdir <OUTDIR>
```

Examples:

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --gene EGFR \
  --outdir output/protein-structure/EGFR
```

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --gene Trp53 \
  --organism mouse \
  --modules uniprot,alphafold \
  --download-structure \
  --outdir output/protein-structure/Trp53
```

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --uniprot P04637 \
  --modules alphafold,pdb \
  --max-pdb 50 \
  --outdir output/protein-structure/P04637
```

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --sequence ACDEFGHIKLMNPQRSTVWY \
  --sequence-name example_peptide \
  --modules esmfold \
  --pymol \
  --outdir output/protein-structure/example_peptide
```

```bash
python skills/protein-structure-get/scripts/protein_structure_get.py \
  --uniprot P04637 \
  --modules alphafold \
  --pymol \
  --pymol-color-mode confidence \
  --pymol-highlight-residues A:175,A:248 \
  --outdir output/protein-structure/P04637_pymol
```

## Output Contract

The script always writes:

- `protein_structure_get.result.json`: structured run record with `status`, `query`, `resolved`, `modules`, `outputs`, and `warnings`.
- `protein_structure_summary.tsv`: one-row summary table.
- `summary.txt`: compact human-readable summary.

Module outputs:

- UniProt: `<TARGET>.<ACCESSION>.features.tsv`
- RCSB PDB: `<TARGET>.<ACCESSION>.pdb_structures.tsv`
- AlphaFold DB: `<TARGET>.<ACCESSION>.alphafold.tsv`
- Domain map: `<TARGET>.<ACCESSION>.domain_map.png` and `.pdf`, only when `domain_map` is requested.
- Downloaded structure: `<TARGET>.<ACCESSION>.alphafold_model.cif` and/or `.pdb`, only with `--download-structure`.
- ESMFold: `<TARGET>.esmfold.pdb`, `<TARGET>.sequence.fasta`, and `<TARGET>.esmfold.tsv`, only when `esmfold` is requested with sequence input.
- PyMOL: `<LABEL>.pymol.pml` when `--pymol` or `--run-pymol` is requested. With `--run-pymol`, the script also attempts `<LABEL>.pymol.pse`, `<LABEL>.pymol.png`, and `<LABEL>.pymol.log`.

## Grounded API Surface

Use only these public endpoints unless you verify an alternative against current official documentation:

- UniProt REST: `https://rest.uniprot.org/uniprotkb/search` and `https://rest.uniprot.org/uniprotkb/<accession>`
- AlphaFold DB API: `https://alphafold.ebi.ac.uk/api/prediction/<accession>`
- RCSB Search API: `https://search.rcsb.org/rcsbsearch/v2/query`
- RCSB Data GraphQL: `https://data.rcsb.org/graphql`
- Hosted ESMFold API: `https://api.esmatlas.com/foldSequence/v1/pdb/`

## Failure And Recovery

- If gene resolution fails, ask for organism, alias, or UniProt accession.
- If AlphaFold returns 404 or an empty list, report `alphafold_available=false`; do not treat this as a failed run.
- If RCSB returns no structures, report zero PDB mappings; do not invent experimental structures.
- If imports fail, install `requirements.txt` before retrying.
- If a network request times out, retry once with a larger `--timeout-sec` or a configured proxy environment.
- For ESMFold sequence input, validate that the sequence is 15-400 amino acids and uses canonical one-letter amino-acid codes unless `--allow-ambiguous-aa` is explicitly requested.
- If the hosted ESMFold API returns HTTP 413, reduce the sequence length to 400 aa or split the protein into domains.

## References

- Read [references/inference-patterns.md](references/inference-patterns.md) for common commands.
- Read [references/constraints.md](references/constraints.md) for scope limits and interpretation rules.
- Read [references/api-sources.md](references/api-sources.md) for the public API surfaces used by the script.
- Read [references/output-schema.md](references/output-schema.md) before changing result fields.
