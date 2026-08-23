---
name: protein-immunopresentation-annotation
description: Predict, import, normalize, and report MHC-I immunopresentation candidate annotations from amino-acid sequences or multi-protein FASTA files using local IEDB Next-Generation TC1 workflows, qinti2023/IEDB wrapper outputs, optional IEDB Class I APIs, immunogenicity scores, and protein feature-context overlaps. Use when Codex needs MHC-I peptide generation, HLA allele binder calls, NetMHCpan EL/BA rank or IC50 summaries, antigen-processing support, immunogenicity score import, signal peptide/TM/IDR/domain/conserved-region overlap annotation, or standardized TSV/JSON reports for candidate presented peptides. Do not use as experimental immunogenicity or confirmed ligandome evidence.
---

# Protein Immunopresentation Annotation

## Overview

Use this skill for sequence-first MHC-I immunopresentation candidate annotation:

`protein FASTA -> MHC-I peptides -> IEDB binding/processing/immunogenicity evidence -> protein-context overlap -> candidate grade`.

This skill reports candidate presentation evidence. It does not confirm natural presentation, T cell recognition, immunogenicity, or ligandome detection. Treat final labels as prioritization classes that need validation by ligandome MS, peptide-MHC assays, or T cell assays.

## Workflow

1. Choose input.
- Use `--sequence` and `--sequence-name` for one protein.
- Use `--fasta` for many proteins; IDs become `query_id` values in all TSV outputs.
- Keep FASTA IDs short and stable because IEDB output sometimes reports sequence number rather than full FASTA metadata.

2. Choose HLA alleles and peptide lengths.
- The default allele set is the 27-allele reference set from the user-provided IEDB pipeline notes.
- Default peptide lengths are `8,9,10,11`; use `--peptide-lengths 8,9,10,11,12,13,14` for broader Class I scans.
- Use `--alleles` or repeated `--allele` for project-specific HLA genotypes.

3. Choose evidence mode.
- Use dry-run mode first. The wrapper writes `normalized_input.fasta`, generated peptide tables, `local_iedb/iedb_ng_tc1_input.json`, `local_iedb/local_pipeline_plan.sh`, `api_requests/`, and `commands.sh`.
- Prefer the local IEDB Next-Generation TC1 route when the user has unpublished or private sequences, or when the public API is unstable.
- Use `--execute-local` only when the official IEDB NG TC1 package is installed and the user has provided `--iedb-local-tools-dir`.
- Use `--execute-api` only after the user approves remote submission of sequences to IEDB.
- Use `--local-result-json`, `--api-result-tsv`, `--processing-result-tsv`, `--immunogenicity-result-tsv`, or `--api-result-json` to import IEDB web/API/local pipeline results.
- Use context feature TSV inputs from other protein skills to annotate peptide overlap with signal peptide, TM, IDR, domains, motifs, and conserved regions.

4. Run a dry-run peptide and request plan.

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta proteins.fa \
  --alleles HLA-A*02:01,HLA-B*07:02 \
  --peptide-lengths 8,9,10,11 \
  --outdir output/protein-immunopresentation-annotation/proteins_plan
```

5. Run or import the local IEDB NG TC1 workflow.

The official IEDB NG TC1 package from `https://downloads.iedb.org/nextgen-tools/tcell_mhci/LATEST/` provides `src/tcell_mhci.py`. The current README reports version `0.1.5-beta`; the tarball is about 841 MB. The qinti2023/IEDB repository provides the wrapper workflow (`fasta_to_json.py`, `IEDB_predict.py`, example `aggregate/aggregated_result.json`) but does not include the official `src/tcell_mhci.py` tool. The local execution path therefore requires an unpacked official IEDB Next-Generation TC1 directory.

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta proteins.fa \
  --alleles HLA-A*02:01,HLA-B*07:02 \
  --peptide-lengths 8,9,10,11 \
  --iedb-local-tools-dir /path/to/IEDB_NG_TC1 \
  --execute-local \
  --local-workdir output/protein-immunopresentation-annotation/proteins_iedb_work \
  --outdir output/protein-immunopresentation-annotation/proteins_local
```

Use `--iedb-wrapper-repo /path/to/qinti2023/IEDB` only when reproducing the original qinti `IEDB_predict.py` command sequence; the S2F wrapper can execute the official split job descriptions directly.

If the local run was executed outside this wrapper, import the aggregate JSON:

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta proteins.fa \
  --local-result-json output/protein-immunopresentation-annotation/proteins_iedb_work/aggregate/aggregated_result.json \
  --outdir output/protein-immunopresentation-annotation/proteins_import
```

6. Import IEDB and context outputs.

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta proteins.fa \
  --api-result-tsv results/iedb_mhci.tsv \
  --processing-result-tsv results/iedb_processing.tsv \
  --immunogenicity-result-tsv results/iedb_immunogenicity.tsv \
  --localization-features-tsv output/protein-localization-signal-annotation/proteins/protein_localization_features.tsv \
  --tm-features-tsv output/protein-tm-topology-annotation/proteins/protein_tm_topology_features.tsv \
  --idr-regions-tsv output/protein-idr-disorder-annotation/proteins/protein_idr_regions.tsv \
  --domain-features-tsv output/protein-domain-motif-annotation/proteins/protein_domain_features.tsv \
  --conservation-features-tsv output/protein-conservation-assessment/proteins/protein_conservation_regions.tsv \
  --outdir output/protein-immunopresentation-annotation/proteins
```

7. Execute IEDB API only when approved.

```bash
python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \
  --fasta proteins.fa \
  --alleles HLA-A*02:01,HLA-B*07:02 \
  --binding-predictors netmhcpan_el,netmhcpan_ba \
  --execute-api \
  --execute-processing \
  --outdir output/protein-immunopresentation-annotation/proteins_api
```

## Candidate Grades

- `high_confidence_candidate`: at least one strong binder plus processing support; immunogenicity score is non-negative when provided.
- `weak_candidate`: weak binder, or strong binder without processing support.
- `unlikely`: no strong/weak binding evidence under the configured rank/IC50 thresholds.

Default binder thresholds:

- Strong binder: rank `<= 0.5` or IC50 `<= 50 nM`.
- Weak binder: rank `<= 2.0` or IC50 `<= 500 nM`.

## Outputs

- `mhci_peptides.tsv`: all generated MHC-I peptides with position, length, and sequence.
- `mhci_binding_predictions.tsv`: normalized per peptide/allele binding evidence.
- `mhci_processing_predictions.tsv`: normalized processing evidence.
- `mhci_immunogenicity_predictions.tsv`: normalized immunogenicity score evidence.
- `immunopresentation_candidates.tsv`: final peptide-level candidate table with binder alleles, scores, context overlaps, and grade.
- `protein_immunopresentation_summary.tsv`: one row per protein.
- `protein_immunopresentation_annotation.result.json`: parameters, warnings, counts, and artifact paths.
- `local_iedb/iedb_ng_tc1_input.json`: local IEDB NG TC1 JSON payload modeled on qinti2023/IEDB.
- `local_iedb/local_pipeline_plan.sh`: local split/predict/aggregate/import command plan.
- `local_iedb/local_pipeline_manifest.json`: local prerequisites and expected aggregate output path.
- `api_requests/`: planned IEDB legacy and next-generation payloads.
- `commands.sh`: API and local pipeline command plan.

## References

- Read `references/api-and-local-setup.md` before writing install/API submission commands.
- Read `references/workflow.md` before changing evidence interpretation or candidate grading.
- Read `references/output-schema.md` before changing TSV columns.

## Script

- `scripts/protein_immunopresentation_annotation.py`
