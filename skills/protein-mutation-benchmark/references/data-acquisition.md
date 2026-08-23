# Data Acquisition and Verification

## Plan Before Downloading

Run:

    python scripts/fetch_proteingym_data.py --list

Then generate a command without network activity:

    python scripts/fetch_proteingym_data.py \
      --asset dms-substitutions \
      --version v1.3 \
      --output-dir downloads/proteingym-v1.3

The official v1.3 table reports uncompressed sizes ranging from a few MB to many GB. Notable assets include DMS substitutions (1.0 GB), DMS indels (200 MB), zero-shot substitution scores (4.4 GB), DMS MSAs (5.2 GB), and clinical MSAs (17.8 GB). Confirm free space for both the ZIP and extracted content.

## Execute Deliberately

Add --execute only after confirming the URL and storage. Add --extract only when extraction is required:

    python scripts/fetch_proteingym_data.py \
      --asset dms-substitutions \
      --version v1.3 \
      --output-dir downloads/proteingym-v1.3 \
      --execute \
      --extract

The downloader accepts only a release asset whitelist, rejects unsafe ZIP paths, retains the archive, and records the observed SHA-256 and byte count.

## Checksum Policy

The main official resource table does not publish per-file checksums. Therefore:

1. Prefer a trusted digest from an archival record when available and pass --sha256.
2. Otherwise, record the observed digest in download_manifest.json.
3. Reuse a cached archive only when its recorded digest matches.
4. Do not describe an observed digest as upstream-authenticated.

## Subset Policy

Do not download all assets by default. For development:

- use references/fixtures/toy_dms.csv and toy_scores.tsv;
- select one assay and one relevant score file;
- record exactly how the subset was chosen;
- never select a test subset based on favorable model performance.

Official source: https://github.com/OATML-Markslab/ProteinGym#resources
