# Constraints

- This skill retrieves public database records and can submit amino-acid sequences to the hosted ESMFold API. It does not perform local AlphaFold inference, structural alignment, docking, or molecular dynamics.
- Default organism is human. If the gene symbol is ambiguous, ask for organism or UniProt accession.
- UniProt resolution prefers reviewed Swiss-Prot records, then relaxes to any UniProtKB record for the organism.
- RCSB PDB results are based on UniProt cross-reference mappings. Structures without a mapped UniProt accession may be missed.
- AlphaFold DB absence is not a failed scientific result. Record `alphafold_available=false` when the API returns 404 or an empty list.
- ESMFold sequence input must be 15-400 amino acids by default. The hosted API currently rejects sequences longer than 400 aa with HTTP 413.
- ESMFold sequence input accepts canonical one-letter amino-acid codes by default. Ambiguous codes require explicit `--allow-ambiguous-aa`.
- PyMOL is optional. `--pymol` only writes a `.pml` script; `--run-pymol` requires a local PyMOL executable and may fail independently of database retrieval.
- Runtime requires `matplotlib>=3.7.0`, `numpy>=1.24.0`, `pandas>=2.0.0`, and `requests>=2.28.0`; install from `requirements.txt` before real runs.
- Do not interpret AlphaFold confidence, domain overlap, or PDB coverage as clinical evidence without a separate validated interpretation workflow.
