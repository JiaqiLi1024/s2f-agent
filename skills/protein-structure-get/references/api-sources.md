# API Sources

The script uses public HTTPS endpoints and no API keys.

## UniProt REST

- Base: `https://rest.uniprot.org`
- Search: `/uniprotkb/search`
- Entry: `/uniprotkb/<accession>`
- Used for gene-to-accession resolution, protein metadata, sequence length, gene names, organism, and feature annotations.

## AlphaFold Protein Structure Database

- Base: `https://alphafold.ebi.ac.uk/api`
- Prediction entry: `/prediction/<uniprot_accession>`
- Used for AlphaFold DB entry metadata and structure file URLs.

## RCSB PDB

- Search: `https://search.rcsb.org/rcsbsearch/v2/query`
- Data GraphQL: `https://data.rcsb.org/graphql`
- Used for UniProt-mapped experimental structure IDs and PDB-level metadata.

## Hosted ESMFold

- PDB prediction endpoint: `https://api.esmatlas.com/foldSequence/v1/pdb/`
- Method: POST the raw amino-acid sequence as plain text.
- Response: PDB text (`chemical/x-pdb`) with confidence-like values in the B-factor column.
- Current hosted API limit observed from the service: sequences longer than 400 amino acids return HTTP 413 with `Sequence is longer than 400.`
- The skill enforces a conservative minimum of 15 amino acids before submission.

## Network behavior

- Requests use a bounded timeout controlled by `--timeout-sec`.
- HTTP 404 from AlphaFold DB is converted to a non-fatal unavailable model status.
- HTTP 413 from hosted ESMFold is treated as a fatal input-size error.
- Other HTTP and JSON errors are captured into the result JSON and may fail the run if they prevent UniProt resolution.
