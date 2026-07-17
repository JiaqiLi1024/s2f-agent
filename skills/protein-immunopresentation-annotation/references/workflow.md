# Workflow

## Evidence Sources

Use generated peptide rows for coordinate tracking only. They are not presentation evidence by themselves.

Prefer local IEDB Next-Generation TC1 execution or imported local aggregate output when the user provides unpublished/private sequences or reports API instability. The expected local aggregate format is qinti/IEDB next-generation JSON with `results[*].table_columns` and `results[*].table_data`.

IEDB's current TC1 README describes split/aggregate as an experimental workflow. When using it, keep `job_descriptions.json`, per-job logs, and `aggregate/aggregated_result.json` with the report so failed or partial jobs can be audited.

Use MHC-I binding predictions for allele-specific binder evidence:

- Strong binder: rank `<= 0.5` or IC50 `<= 50 nM`.
- Weak binder: rank `<= 2.0` or IC50 `<= 500 nM`.
- Report NetMHCpan EL and BA ranks separately when both are available.

Use processing predictions as support for the antigen-presentation pathway:

- Proteasomal cleavage contributes to C-terminal peptide generation.
- TAP transport contributes to peptide delivery into the ER.
- Combined/total processing scores are supportive evidence and should not override poor binding.

Use immunogenicity scores as optional prioritization evidence, not confirmation.

Use context overlaps to explain biology:

- Signal peptide overlap may indicate secretory-pathway/N-terminal region context.
- TM overlap flags hydrophobic membrane segments.
- IDR overlap can support accessibility/flexibility.
- Domain overlap can indicate structured functional regions.
- Conserved-region overlap can support cross-ortholog prioritization or caution depending on project goals.

## Candidate Ranking

Assign:

1. `high_confidence_candidate` when a peptide has at least one strong-binding allele plus processing support and non-negative immunogenicity score if provided.
2. `weak_candidate` when a peptide has weak binding, or strong binding without processing support.
3. `unlikely` when no strong/weak binding evidence is present under configured thresholds.

Never call rows "confirmed epitopes", "confirmed immunogenic", or "naturally presented" unless the user provides ligandome MS, peptide-MHC binding assay, or T cell assay evidence.

## Batch FASTA Handling

For many-protein FASTA files:

- Run a dry-run first and inspect `mhci_peptides.tsv`, `local_iedb/iedb_ng_tc1_input.json`, `local_iedb/local_pipeline_plan.sh`, and `api_requests/`.
- Prefer project-specific allele lists over the 27-allele default when patient/sample HLA genotypes are known.
- Keep raw API/local outputs with the run so `seq_num` or sequence-index-only outputs can be traced back.
- Consider splitting very large FASTA submissions outside Codex if the local IEDB jobs are too large or the remote service times out.

## Integration With Other Protein Skills

Use these outputs as context TSVs:

- `protein-localization-signal-annotation`: signal peptides and targeting signals.
- `protein-tm-topology-annotation`: transmembrane helices or inside/outside states.
- `protein-idr-disorder-annotation`: IDR/disorder regions.
- `protein-domain-motif-annotation`: domains and motifs.
- `protein-conservation-assessment`: conserved regions.

Pass their feature/region TSVs with the matching `--*-features-tsv` or `--*-regions-tsv` flags.
