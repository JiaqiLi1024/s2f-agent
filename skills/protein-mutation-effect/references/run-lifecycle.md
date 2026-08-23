# Run lifecycle, archiving, cleanup, and retries

## Directory layout

Each run owns one explicit output directory with inputs, raw, intermediate, logs, protein_mutation_scores.tsv, protein_mutation_summary.json, run_manifest.json, and commands.sh. An optional intermediates.tar.gz contains archived intermediates.

run_manifest.json records UTC timestamps, command arguments with secrets redacted, input hashes, model revisions, environment names, package versions when available, execution state, and artifact paths. commands.sh is a reproducibility record and must not embed credentials.

## Archiving

--archive-intermediates creates intermediates.tar.gz from this run's intermediate directory. Confirm that the archive opens before considering it complete. Raw backend outputs remain in raw unless the component skill explicitly documents another retention policy.

## Cleanup

Cleanup is opt-in. --cleanup-intermediates may remove only the resolved intermediate directory directly beneath the resolved run output. It must reject a symlink, workspace root, filesystem root, home directory, or path outside the run. Do not combine cleanup and archive flags in one invocation; inspect or archive first, then run cleanup explicitly.

## Partial failure

A multi-model run is successful-with-warnings when at least one requested backend completes or imports and every other backend has a status row. Retry only the failed backend. Keep prior successful raw outputs immutable and create a new attempt subdirectory or manifest entry.

## Final report

Report requested, completed, planned, unavailable, and failed models; input validation; output paths; archive or cleanup action; verification level; and scientific caveats. Never convert a backend failure into a zero score.
