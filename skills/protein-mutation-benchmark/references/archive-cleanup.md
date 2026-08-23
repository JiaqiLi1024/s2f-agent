# Archiving and Safe Cleanup

## Default Retention

Keep:

- raw input copies and their digests;
- normalized inputs;
- aligned and excluded rows;
- metrics, summary, manifest, command, and logs.

This default makes mapping and metric errors auditable.

## Archive

Use --archive-intermediates only after a successful run. The runner writes intermediate.tar.gz with intermediate/ as the archive root, then removes only output-dir/intermediate.

## Cleanup Without Archive

Use --cleanup-intermediates only if normalized tables are reproducible and storage is constrained. The runner validates that the target:

- is named intermediate;
- is the direct child of the resolved output directory.

It never removes source assay files, source score files, raw/, metrics, summaries, or paths outside the run directory.

## Reruns

Prefer a new output directory for a new release, score orientation, threshold, model checkpoint, or metric definition. The runner refuses a nonempty output directory by default. If intentionally reusing one, inspect manifest.json first and add --allow-existing-output; do not merge artifacts from incompatible runs.
