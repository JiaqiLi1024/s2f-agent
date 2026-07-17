# Family Selection

## Use InterProScan6 When

- The user asks for protein domains, motifs, repeats, signatures, families, or functional sites.
- The deliverable includes InterPro, Pfam, PANTHER, SMART, PROSITE, SUPERFAMILY, CDD, or other InterPro member database evidence.
- The user needs GFF3, JSON, JSONL, XML, or TSV output for annotation pipelines.
- The user wants domain architecture across a proteome.

## Use eggNOG-mapper When

- The user asks for orthology-based functional annotation.
- The deliverable includes GO, KEGG, EC, COG/category, Pfam, ortholog groups, or protein descriptions.
- The user has a genome, transcriptome, MAG, or metagenomic gene catalog and wants broad functional annotation.
- The runtime budget favors DIAMOND-based search over the full InterProScan6 signature workflow.

## Use Both When

- The user wants a production proteome annotation.
- The user asks for both domain/motif evidence and orthology-based function.
- The output will feed a genome annotation report, pathway enrichment, or comparative genomics summary.
- One tool's no-hit proteins should be cross-checked by the other tool.

## Defer To Another Skill When

- The user needs 3D structures, AlphaFold DB, PDB coverage, PyMOL, pockets, or contact maps: use protein structure skills.
- The user needs signal peptide, transmembrane topology, subcellular localization, or targeting signals as the primary objective: use a localization/topology skill when available.
- The user needs intrinsic disorder, low complexity, coiled-coil, repeats, or aggregation as the primary objective: use a disorder/composition skill when available.

## Practical Defaults

- Default tool selection: `both`.
- Default InterProScan6 revision: `6.0.1`.
- Default InterProScan6 profile: `singularity` on HPC, `docker` on local Docker hosts.
- Default InterProScan6 formats: `TSV,JSON,GFF3`.
- Default eggNOG-mapper backend: `diamond`.
- Default eggNOG input type for this skill: `proteins`.
