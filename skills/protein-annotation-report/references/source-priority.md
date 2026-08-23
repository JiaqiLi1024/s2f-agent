# Source Priority

Use the following order when interpreting annotations:

1. Curated UniProtKB/Swiss-Prot annotations for known accessions.
2. InterProScan6 InterPro member database matches for domains, repeats, families, and functional sites.
3. eggNOG-mapper orthology-based functional transfer for broad function, GO, EC, KEGG, COG/category, and Pfam summaries.
4. Existing imported `features.tsv` and `motifs.tsv`, preserving source notes.
5. Local regex motif candidates from raw sequence or FASTA input.

## Unknown Sequences

For a novel amino-acid sequence with no accession:

- Run local sequence summary and motif scan for a first-pass report.
- Use InterProScan6 and eggNOG-mapper for functional/domain evidence.
- Do not present regex motifs as confirmed functional annotation.
- If sequence length or alphabet is abnormal, report the warning and avoid overinterpretation.

## Known Proteins

For gene symbols, protein names, or UniProt accessions:

- Prefer reviewed UniProt entries.
- Require organism/taxon context when the gene/protein name is ambiguous.
- Keep UniProt features as 1-based closed coordinates.
- Use InterPro/eggNOG as complementary evidence rather than replacing curated UniProt comments.

## Coordinate Conventions

Normalized output should use 1-based closed residue coordinates when source conventions are known.

- UniProt features: 1-based closed.
- InterProScan TSV: protein residue positions from the source output.
- Imported old `motifs.tsv`: default conversion assumes 0-based half-open from Python regex output.
- eggNOG functional rows: no residue coordinates.
