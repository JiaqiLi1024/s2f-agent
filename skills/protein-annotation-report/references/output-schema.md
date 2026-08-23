# Output Schema

## Summary TSV

`protein_annotation_summary.tsv` has one row per protein or query.

Core identity columns:

- `query_id`: FASTA record ID, UniProt accession, or provided sequence label.
- `input_type`: `raw_sequence`, `fasta`, `uniprot`, `interproscan6`, `eggnog`, `protein_idr`, `protein_llps`, `protein_degron`, `features_tsv`, or `motifs_tsv`.
- `source_ids`: accessions or ortholog IDs used as evidence.
- `uniprot_accession`, `reviewed`, `protein_name`, `gene_names`, `organism`.

Sequence columns:

- `length`
- `sequence_sha256`
- `molecular_weight_da`
- `gravy`
- `aromaticity`

Annotation columns:

- `predicted_function`
- `subcellular_location`
- `domains`
- `motifs`
- `degrons`
- `interpro_ids`
- `pfam_ids`
- `eggnog_ogs`
- `go_terms`
- `ec_numbers`
- `kegg_ko`
- `pathways`
- `mean_disorder_score`
- `fraction_disordered`
- `n_disordered_residues`
- `n_idr_regions`
- `longest_idr`
- `n_binding_regions`
- `n_linker_regions`
- `pLLPS`
- `mean_aggregation_score`
- `fraction_aggregation_prone`
- `n_aggregation_prone_residues`
- `n_aggregation_regions`
- `n_dpr_regions`
- `n_hotspot_regions`
- `n_degron_candidates`
- `n_terminal_degrons`
- `n_phosphodegrons`
- `feature_count`
- `annotation_sources`
- `warnings`

## Feature TSV

`protein_annotation_features.tsv` has one row per evidence item.

By default, UniProt export keeps functional and structural feature types such as domains, regions, motifs, active/binding sites, PTMs, signal peptides, transmembrane regions, topology, repeats, and coiled coils. Use `--all-uniprot-features` to include variants, conflicts, and every other UniProt feature type.

- `query_id`: protein/query identifier.
- `source`: `UniProtKB`, `InterProScan6:<analysis>`, `eggNOG-mapper`, `protein-idr-disorder-annotation:<source>`, `ELM`, `DEGRONOPEDIA`, `custom`, `local_motif_scan`, `features_tsv`, or `motifs_tsv`.
- `feature_type`: domain, motif, site, region, orthology function, IDR/disordered-binding/linker region, LLPS/aggregation region, degron candidate, or source-native type.
- `start`, `end`, `length`: residue coordinates when available.
- `accession`, `name`, `description`: source identifiers and labels.
- `database`: source database or analysis name.
- `interpro_accession`, `interpro_description`: InterPro match fields when available.
- `go_terms`, `pathways`: source-provided ontology/pathway annotations.
- `score`, `evalue`: source-native confidence fields.
- `evidence`: evidence code, ortholog group, or import note.
- `note`: coordinate or confidence caveat.

For degron imports, the `note` field preserves matched sequence, degron location, regex, UPS/E3 component, license, free-use flag, and references when provided by `protein-degron-annotation`.

## JSON Report

`protein_annotation_report.json` records:

- output paths
- row counts
- source files
- saved raw UniProt JSON paths
- warnings
- errors

Use the JSON report as the machine-readable run status. Use the TSVs for downstream spreadsheet or pipeline use.
