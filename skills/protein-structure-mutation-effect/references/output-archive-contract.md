# Adapter, output, archive, and cleanup contract

## Adapter states

- `plan`: validate, normalize, create directories, emit `commands.sh`, and write `planned` rows. Do not download or execute a model.
- `execute`: run only explicit `--adapter-command model=...` commands. Supported placeholders are `{fasta}`, `{structure}`, `{chain}`, `{mutations}`, `{output}`, `{raw_dir}`, and `{intermediate_dir}`. Commands are tokenized and run without a shell. Each adapter must write a tabular output.
- `import`: read explicit `--import-file model=path` files. Preserve the source file in `raw/<model>/` and normalize supported column aliases.

Each imported/executed table needs `mutation` plus one score column. Preferred columns are `variant_id`, `mutation_group`, `mutation`, `score_name`, `effect_axis`, `raw_score`, `higher_is`, `status`, and `error`. Recognized score aliases include `score`, `mut_value`, `ddG`, `ddg`, `log_odds`, and `llr`. The wrapper will not infer missing mutation identities from row order.

## Long score TSV

`structure_mutation_scores.tsv` contains at least:

`protein_id, variant_id, mutation_group, mutation, chain, canonical_position, wt, alt, model_id, model_version, score_name, effect_axis, raw_score, score_unit, higher_is, status, error, source_path`

Allowed status values are `completed`, `planned`, `imported`, `unavailable`, `failed`, and `invalid_input`. Empty scores must carry a non-completed status and an explanatory `error`.

## Run layout

```text
output-dir/
  normalized_mutations.tsv
  residue_mapping.tsv
  structure_mutation_scores.tsv
  run_summary.json
  manifest.json
  commands.sh
  logs/
  raw/<model>/
  intermediate/<model>/
  archive/intermediates.tar.gz
```

The manifest records input paths and hashes, mode, requested models, structure availability, adapter commands/imports, timestamps, source/checkpoint metadata when supplied, and archive/cleanup actions. `commands.sh` is an audit artifact and is not executed by the wrapper.

## Archive and cleanup

Default to retaining intermediates. `--archive-intermediates` creates a gzip tar archive from `raw/`, `intermediate/`, and `logs/`. `--cleanup-intermediates` is honored only after a nonempty archive exists. Cleanup resolves each known child path, verifies it is inside the output directory, refuses symlinks, and removes only those exact children. It never deletes inputs, model caches, source repositories, the output root, or arbitrary glob matches.
