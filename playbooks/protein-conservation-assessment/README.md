# Protein Conservation Assessment Playbook

Use this playbook for sequence-first protein conservation workflows: unknown protein sequence, homolog search/import, MSA, residue conservation scoring, conserved regions, and standardized TSV/JSON reports.

## Inputs

- Amino-acid sequence or protein FASTA.
- Optional homolog FASTA or existing aligned FASTA/Stockholm MSA.
- Optional local search backend: HMMER/jackhmmer or MMseqs2.
- Optional database choice and destination directory.
- Output root and run ID.

## Existing MSA

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --alignment <ALIGNED_FASTA_OR_STOCKHOLM> \
  --query-id <QUERY_ID> \
  --outdir output/protein-conservation-assessment/<RUN_ID>
```

## Homolog FASTA Plus MSA

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --sequence <AA_SEQUENCE> \
  --sequence-name <QUERY_ID> \
  --homolog-fasta <HOMOLOGS_FASTA> \
  --msa-backend auto \
  --outdir output/protein-conservation-assessment/<RUN_ID>
```

## Plan Local Search And Database Download

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --sequence <AA_SEQUENCE> \
  --sequence-name <QUERY_ID> \
  --search-backend local-hmmer \
  --target-db <PROTEIN_DATABASE_FASTA> \
  --db-choice swissprot \
  --db-dir "$HOME/biodata/protein_conservation" \
  --outdir output/protein-conservation-assessment/<RUN_ID>_plan
```

Inspect `commands.sh` and `database_download_plan.sh`. Ask the user before executing downloads, especially UniRef90 or UniRef50.

## Execute Local HMMER

```bash
python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py \
  --sequence <AA_SEQUENCE> \
  --sequence-name <QUERY_ID> \
  --search-backend local-hmmer \
  --target-db <PROTEIN_DATABASE_FASTA> \
  --hmmer-iterations 3 \
  --evalue 1e-4 \
  --cpu 16 \
  --execute \
  --outdir output/protein-conservation-assessment/<RUN_ID>
```

## Inspect Outputs

- `protein_conservation_summary.tsv`: whole-query conservation summary.
- `protein_conservation_sites.tsv`: one row per query residue.
- `protein_conserved_regions.tsv`: conserved and variable contiguous regions.
- `alignment.fasta`: MSA used for scoring.
- `commands.sh`: reproducible local command plan.
- `database_download_plan.sh`: database setup plan requiring user approval.
- `plots/conservation_profile.*`: compact conservation profile when plotting dependencies are available.
- `protein_conservation_assessment.result.json`: parameters, warnings, artifacts, and summary.
