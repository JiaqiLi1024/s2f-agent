# Conservation Workflow

Use this reference for tool selection and interpretation.

## Pipeline

1. Validate query amino-acid sequence.
2. Obtain homologs from local HMMER, MMseqs2, EBI HMMER, or a user-provided homolog FASTA/MSA.
3. Filter homologs for scope and quality.
4. Build MSA with MAFFT or Biotite, or import an existing alignment.
5. Compute residue conservation on query-mapped positions.
6. Call conserved and variable regions.
7. Write TSV/JSON/plot reports.

## Homolog Scope

Conservation is only meaningful relative to the homolog set. Before scoring, decide whether the user wants:

- Within-species paralog conservation.
- Ortholog conservation across a clade.
- Broad family/domain conservation.
- Taxon-specific conservation for a genome project.

Prefer orthologs when transferring functional interpretation. Include paralogs when the task is family/domain conservation, but label the limitation.

## Homolog Filtering

Use these filters when hit metadata is available:

- Minimum query coverage: usually 0.5 to 0.8.
- Maximum identity: remove near-duplicates when many close sequences dominate the MSA.
- Minimum identity: remove extremely remote hits unless the MSA is manually checked.
- E-value and inclusion threshold: record exact values.
- Taxonomic redundancy: sample representatives across taxa instead of overrepresenting one species group.
- Domain boundaries: do domain-specific conservation if hits only cover one domain.

If only homolog FASTA is provided, deduplicate exact sequences and record that identity/coverage filters were not applied.

## MSA Choice

- Use MAFFT `--auto` for general production MSA.
- Use Biotite progressive MSA for small Python-native workflows or when MAFFT is unavailable.
- Use an existing curated MSA when available.
- Treat equal-length FASTA as already aligned only when that is biologically plausible or explicitly provided.

Do not over-interpret conservation in low-complexity, repeat-rich, or gap-rich regions.

## Scoring

The bundled script computes per-query-position conservation as:

`1 - Shannon_entropy(column residues excluding gaps) / log2(20)`

The output also records:

- `gap_fraction`
- `consensus_residue`
- `consensus_fraction`
- `query_residue_fraction`
- `conservation_grade` from 1 to 9
- `status`: conserved, intermediate, variable, or gap_rich

Default thresholds:

- Conserved: score >= 0.75 and gap fraction <= 0.5.
- Variable: score <= 0.35 and gap fraction <= 0.5.
- Gap-rich: gap fraction > 0.5.
- Region minimum length: 5 residues.

Adjust thresholds for short peptides, small MSAs, or shallow homolog sets.

## Interpretation

- Conserved residues may indicate active sites, ligand-binding residues, structural cores, catalytic residues, domain motifs, or interface residues.
- Conserved regions outside annotated domains are candidates for novel motifs or constrained structural elements.
- Variable regions can indicate lineage-specific adaptation, flexible linkers, IDRs, or poorly aligned segments.
- Conservation alone does not prove function. Combine with `protein-domain-motif-annotation`, `protein-idr-disorder-annotation`, `protein-localization-signal-annotation`, and `protein-structure-visualize` as needed.

## Minimum Evidence Warnings

Add warnings when:

- Fewer than 5 homologs are aligned.
- More than half of the query positions are gap-rich.
- The MSA is created from unfiltered homolog FASTA.
- Query ID was inferred from the first alignment record.
- Local database/release is unknown.
