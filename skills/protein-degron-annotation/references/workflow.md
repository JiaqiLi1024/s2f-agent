# Workflow

## Source Selection

Use ELM when:

- The user asks for ELM degron classes, `DEG_` motifs, destruction boxes, KEN boxes, N-degrons, C-degrons, phosphodegrons, or E3-ligase-binding degrons.
- A lightweight local regex scan is sufficient.
- The user wants reproducible batch annotation from a FASTA.

Use DEGRONOPEDIA dataset scanning when:

- The user wants a broad curated degron motif collection.
- The user needs degron location, UPS-recognizing components, references, and license fields.
- A local batch scan is needed without submitting sequences to the web server.

Use QCDPred when:

- The user asks for QCDPred, QCD, QCAP, quality-control degrons, or degron probability from sequence composition.
- The query sequence is at least 17 amino acids long.
- Motif databases are unavailable but a sequence-first degron probability estimate is still useful.
- The user provides an existing QCDPred raw output table that should be normalized into the standard degron report.

Use the DEGRONOPEDIA web server when:

- The user needs the full server context rather than only regex matches.
- Inputs include a structure, user MSA, custom proteolysis motifs, or explicit desire for PSI/tripartite-model outputs.
- The user can manually submit one protein and download the xlsx result.

Use custom motifs when:

- The user has project-specific degron motifs, proteolytic exposure motifs, or literature-derived regexes not yet in the public datasets.

## Recommended Pipeline

1. Normalize sequence input and write `normalized_input.fasta`.
2. Generate `database_download_plan.sh` every time, even when files already exist.
3. If local ELM/DEGRONOPEDIA files are present, scan regexes with overlapping matches.
4. If QCDPred is requested, compute or import the 17-aa center-residue profile, summarize average/median/max scores, and merge positive centers into intervals.
5. Preserve source-specific fields in `protein_degron_features.tsv`.
6. Interpret hits by category:
- N-terminal or C-terminal degrons may require exposure by processing, translation start state, or proteolysis.
- Phosphodegrons may require phosphorylation evidence.
- Internal degrons may require disorder, accessibility, correct cellular compartment, and E3 availability.
- QCDPred intervals indicate quality-control degron-like composition; they do not identify a specific degron regex or E3 ligase.
- Short regexes with many proteome-wide matches are low specificity without extra evidence.
7. For report integration, pass `protein_degron_annotation.result.json` or `protein_degron_features.tsv` to `protein-annotation-report`.

## DEGRONOPEDIA Web Result Import

If the user runs the web server:

1. Keep the query sequence and parameters together with the downloaded xlsx.
2. Prefer importing a normalized table exported from the xlsx into `protein_degron_features.tsv` shape.
3. Preserve DEGRONOPEDIA-generated context fields in `note` when the exact sheet schema differs from the motif dataset.
4. Report that the full web score/context is service-derived and not identical to local regex-only scanning.

## Evidence Ranking

Suggested ranking for interpretation:

1. Experimentally validated degron instance in the same protein and organism.
2. DEGRONOPEDIA curated degron with UPS-recognizing component and literature support.
3. ELM degron class with validated instances plus matching biological context.
4. QCDPred interval with high max score plus compatible disorder, accessibility, and conservation context.
5. ELM or DEGRONOPEDIA regex-only match.
6. Custom regex-only match.

Always retain lower-ranking evidence rather than deleting it; downstream reports can filter by source/evidence.

## Combining With Other Skills

- Use `protein-idr-disorder-annotation` to determine whether degron candidates sit in IDRs or accessible flexible regions.
- Use `protein-conservation-assessment` to see whether candidate degrons are conserved in an ortholog set.
- Use `protein-localization-signal-annotation` and `protein-tm-topology-annotation` to reject biologically inaccessible motifs, such as cytosolic E3 degrons in extracellular/luminal regions.
- Use `protein-structure-visualize` to map candidates onto PDB/AlphaFold structures and inspect accessibility.
- Use `protein-annotation-report` to merge degron rows with UniProt, InterProScan6, eggNOG, IDR, LLPS, topology, localization, and conservation evidence.
