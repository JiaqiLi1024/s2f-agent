# Benchmark v2

This directory is the management root for regression and comparative benchmark work. Benchmark v2 separates the case-study-free comparative protocol from the full legacy regression corpus and makes publication an explicit, gated action.

## Layout

- `protocols/v2-main.yaml` freezes tracks, participants, model settings, repeats, retry policy, and statistical defaults.
- `protocols/v2-main-gpt56.yaml` is an additive protocol version that includes the `gpt-5.6` Responses API participant; it does not replace `v2-main.yaml`.
- `protocols/v2-main-gpt56-ttapi.yaml` is a diagnostic paired protocol for the ttapi Chat Completions compatibility endpoint.
- `manifests/v2-main.yaml` selects the 40-case, case-study-free, normalized-query-deduplicated test split by case ID.
- `manifests/v2-regression.yaml` retains all 54 legacy cases, including case-study-coupled and duplicate cases, for regression diagnostics only.
- `prompts/task_blind.md` omits gold task, output contracts, scorer fields, and expected answers.
- `prompts/equal_context.md` supplies the same deterministic registry-derived context bundle to every API participant.
- `prompts/task_conditioned.md` is supplementary and explicitly exposes the canonical task.
- `tools/eval_benchmark.py` is the compatible CLI entry point.
- `tools/eval_benchmark_v2.py` implements v2 execution, coverage, resume, statistics, sanitization, and publication gates.
- `manifests/skills-parameter.yaml` covers all registry skills for routing and the paired parameter-accuracy corpus.
- `protocols/skills-parameter.yaml` enables disabled-skill visibility and the structured `parameter-accuracy` track.
- `evals/parameter_accuracy/cases.yaml` is the source corpus for exact parameter claims and abstention from undocumented defaults.

The source case files remain under `evals/`. The v2 manifests select cases by ID and do not duplicate their gold scoring fields.

## Main Run

```bash
python3 benchmark/tools/eval_benchmark.py \
  --protocol benchmark/protocols/v2-main.yaml \
  --manifest benchmark/manifests/v2-main.yaml \
  --track task-blind-routing,equal-information-orchestration \
  --replicates 3 \
  --seed 7
```

Use `--participants` or `--suites` for development diagnostics. Such partial runs still produce complete artifacts but cannot pass the publication gate. `--dry-run` renders and validates every prompt without invoking participants; all records are marked `skipped`.

Resume an interrupted run by naming its existing output directory. A record is reused only when its fingerprint still matches:

```bash
python3 benchmark/tools/eval_benchmark.py \
  --protocol benchmark/protocols/v2-main.yaml \
  --manifest benchmark/manifests/v2-main.yaml \
  --output-dir benchmark/runs/<run_id> \
  --resume
```

The primary paired comparison always uses `repeat_index=0`. Later successful repeats never replace an infrastructure failure in repeat 0. Additional repeats report stability only.

## GPT-5.6 Extension

The checked-in extension protocol adds `gpt-5.6` with the same prompt, track, case, and repeat settings as the existing main participants. Run a prompt and coverage validation without making API calls with:

```bash
python3 benchmark/tools/eval_benchmark.py \
  --protocol benchmark/protocols/v2-main-gpt56.yaml \
  --manifest benchmark/manifests/v2-main.yaml \
  --participants gpt-5.6,s2f-agent \
  --dry-run
```

For a real run, remove `--dry-run` and provide `OPENAI_API_KEY`. The protocol intentionally keeps `model_snapshot: unresolved` until an availability probe verifies the provider-returned model identity; no result from this extension is publication-eligible before that snapshot is frozen.

For the ttapi compatibility endpoint, use the dedicated proxy participant and protocol:

```bash
set -a
. ./.env
set +a
python3 benchmark/tools/eval_benchmark.py \
  --protocol benchmark/protocols/v2-main-gpt56-ttapi.yaml \
  --manifest benchmark/manifests/v2-main.yaml \
  --track task-blind-routing,equal-information-orchestration \
  --replicates 3 \
  --seed 7
```

The ttapi run remains a proxy/system compatibility result and must not be labeled as a first-party OpenAI evaluation. Connection failures and unavailable model slugs are infrastructure errors, never zero scores.

The runner accepts a relay base URL with or without a scheme or `/v1` suffix. For example, `OPENAI_BASE_URL=www.a8pi.com` is normalized to `https://www.a8pi.com/v1` for OpenAI-compatible requests.

## Tracks

- `task-blind-routing`: routing cases; no canonical task is passed to any participant, and local `route_query.sh` is called without `--task`.
- `equal-information-orchestration`: groundedness and task-success cases; API participants receive a deterministic query-derived registry context bundle whose IDs and content hash are recorded.
- `task-conditioned`: supplementary groundedness/task-success analysis in which the canonical task is explicitly supplied.

The local agent consumes its native registry and runtime, so comparisons against API participants are system-level comparisons, not isolated foundation-model comparisons.

## Skill Coverage And Parameters

`protocols/skills-parameter.yaml` is the focused diagnostic protocol for the
current registry. Its manifest contains 34 case-study-free routing cases and
37 parameter cases, and declares all 20 registry skill IDs in
`required_skill_coverage`. The runner rejects the manifest if any registry
skill is absent from the selected routing cases. The five disabled-only cases
are scored with `include_disabled_skills: true`; the default
`scripts/validate_routing.sh` reports them as skipped, while
`--include-disabled` evaluates them.

Routing uses two complementary secondary-candidate rules. An expected
secondary list is a required containment set when alternatives are known; an
empty expected list is an explicit negative in the strict track. Candidate
precision, recall, and F1 are always reported as diagnostics, so broad
rankings cannot be mistaken for exact routing.

The parameter track tests 17 documented values, 17 unsupported universal
defaults, and 3 disabled-skill refusal cases. Claims are structured as
`name`, `value`, `status`, and `evidence`; undocumented values must be
reported as `value: "unknown"` with a `not documented` verification boundary.
The local runtime emits only the claim selected by the query, and the scorer
requires the requested name, value, and evidence to occur in that same claim.

Run the focused suite locally with:

```bash
python3 benchmark/tools/eval_benchmark.py \
  --protocol benchmark/protocols/skills-parameter.yaml \
  --manifest benchmark/manifests/skills-parameter.yaml \
  --participants s2f-agent \
  --output-dir benchmark/runs/skills_parameter_<run_id>
```

To compare an API model against the local runtime, keep the same protocol and
manifest and change only `--participants` (for example,
`s2f-agent,gpt-5.5,gpt-5.6`), supplying the provider key and compatible base
URL. API responses are scored against the same structured claims; unavailable
model slugs or transport failures are recorded as infrastructure errors, not
as hallucination failures.

The validated local runs scored all records with no infrastructure errors:
`benchmark/runs/skills_parameter_routing_final` reports routing at 44.12%
strict and 88.24% lenient, while
`benchmark/runs/skills_parameter_parameter_final2` reports parameter accuracy
at 100% (37/37) in both tracks. The strict/lenient routing gap is intentional:
it exposes extra secondary routes and malformed/partial routing claims rather
than hiding them in a prose-normalized score.

## Status And Coverage

Every expected participant/track/suite/case/repeat record has exactly one status:

- `scored`: a response was returned and is included in pass/fail metrics. HTTP 200 malformed JSON or schema-invalid model output is a scored failure.
- `infrastructure_error`: authentication, exhausted rate limits, network/provider errors, HTTP 4xx/5xx, local nonzero exits, or runner failures. These records never enter the model pass-rate denominator.
- `skipped`: dry-run or a protocol/fixture exclusion. These records never enter the denominator.

`coverage.json` reports expected, scored, pass, fail, infrastructure-error, and skipped counts overall and by participant/track/suite. A paired comparison is `invalid` when either participant lacks a scored primary-repeat record; the runner never silently shrinks to the successful intersection.

## Outputs

Each run writes an isolated directory under `benchmark/runs/` unless `--output-dir` is supplied:

```text
run_manifest.json
coverage.json
summary.json
summary.csv
table.md
stats.json
examples.md
prompts/<participant>/<track>/<suite>/<case>/<repeat>.txt
raw_outputs/<participant>/<track>/<suite>/<case>/<repeat>.txt
case_records/<participant>/<track>/<suite>/<case>/<repeat>.json
```

`run_manifest.json` records source and prompt hashes, git state, runtime, case order, protocol settings, requested models, response metadata, and publication-gate reasons. Stored prompts, responses, records, errors, credentials, and local home paths are sanitized before writing. `--resume` reuses a record only when its execution fingerprint matches the current case, prompt, participant, protocol, manifest, and scorer code.

## Publication

Normal runs never update `benchmark/reports/manuscript/benchmark-results-latest.md`. Only `--publish` can create an immutable `benchmark/releases/<run_id>/` package and update the latest pointer.

Publication requires the exact protocol participant/track/suite/repeat matrix, 100% scored coverage, no infrastructure errors or skips, a clean worktree, a case-study-free benchmark manifest, prompt and secret scans passing, and exact provider model identity matching the frozen snapshot.

The checked-in protocol deliberately uses `model_snapshot: unresolved` for API participants because the repository does not yet contain verified snapshot IDs. This prevents accidental publication. Freeze each supported provider snapshot in a new protocol version after an availability probe; do not replace these values with unverified aliases.

## Regression And Tests

Legacy commands remain available for diagnostic compatibility, but they do not publish results automatically:

```bash
make eval-benchmark
python3 benchmark/tools/eval_benchmark.py --participants s2f-agent --dry-run
```

Run fixture and v2 contract tests with:

```bash
make test-eval-benchmark-mock
# or
python3 -m unittest benchmark.tools.test_eval_benchmark_mock -v
```
