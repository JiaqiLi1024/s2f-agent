# Archive, cleanup, and troubleshooting

## Retention policy

Keep `normalized_mutations.tsv`, `scores.tsv`, `run_summary.json`, `manifest.json`, `commands.sh`, logs, environment locks, license notices, and model/data checksums. For publishable runs, also keep raw native outputs. Large reusable model caches and source datasets belong outside the run directory and are referenced by ID/hash rather than copied.

`--archive-intermediates` creates `intermediates.tar.gz` from only `<output-dir>/raw` and `<output-dir>/intermediate`. `--cleanup-intermediates` is rejected unless archive is also requested. Cleanup resolves each path and proves it is a direct child named `raw` or `intermediate`; it never touches FASTA, MSA, AlphaMissense tables, PoET repositories, conda environments, or Hugging Face/PyTorch caches.

Verify an archive before manual deletion:

```bash
tar -tzf <output-dir>/intermediates.tar.gz
sha256sum <output-dir>/intermediates.tar.gz
```

## Common failures

- **WT mismatch**: confirm isoform and whether numbering includes signal peptides/transit peptides. Do not override; supply the correct FASTA or map coordinates explicitly upstream.
- **MSA query not unique**: remove duplicate query rows or use an alignment specific to one target. The profile adapter refuses ambiguous mapping.
- **ESM-1v import resolves to the wrong `esm`**: use the isolated `s2f-esm1v` environment. Biohub ESMC and FAIR ESM share an import name.
- **ESMC class/tokenizer error**: install the official Biohub package at the recorded commit; authenticate if the model revision requires it; then retry with `--local-files-only` after download.
- **CUDA out of memory**: shorten batches/runs, use one ESM-1v member for diagnosis, lower PoET `--poet-batch-size`, or move to a suitable GPU. Never silently substitute another checkpoint.
- **PoET unavailable**: verify `nvidia-smi`, upstream `poet` environment, `data/poet.ckpt`, A3M path, and `scripts/score.py --help`. Read `raw/poet.stderr.log` after a failed native run.
- **AlphaMissense not found**: verify human protein/isoform ID, single substitution, v2023 table type, and one-based protein variant. Missing rows remain `not_found`; do not infer a value.
- **Compressed AlphaMissense memory concerns**: lookup streams `.gz` rows and does not load the full release into RAM. For repeated large batches, create a separately versioned indexed database and preserve its build command/checksum.

## Recovery

Rerun only `unavailable`, `failed`, or `not_found` rows after correcting prerequisites. Keep the original run directory immutable; write retries to a new directory and record the parent manifest hash. An `ok` row is reusable only when inputs, model revision, scoring semantics, and preprocessing hashes match.
