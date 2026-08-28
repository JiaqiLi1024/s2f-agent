# Methods: Comparative S2F Benchmark

## Manuscript-ready methods paragraph

We constructed a 54-case comparative benchmark to evaluate repository-aware orchestration for computational-genomics workflows. Cases were defined in three ground-truth suites: routing to the appropriate skill or clarification behavior (23 cases), groundedness to repository task and output contracts without fabricated identifiers or commands (8 cases), and task-success planning with required skills, runnable steps, expected outputs, missing-input handling, and retry policies (23 cases). The local `s2f-agent` was evaluated through the repository runtime entrypoints (`scripts/route_query.sh` and `scripts/run_agent.sh`), while the baseline `gpt-5.5-ttapi-chat` received the same canonical task definitions, enabled skill catalog, and output contracts through a structured JSON-only prompt. All outputs were normalized to a common JSON schema and scored automatically under a strict primary track and a lenient supplementary track. We report micro pass rates across cases and macro pass rates averaged across task labels; 95% confidence intervals were estimated with 2,000 nonparametric bootstrap iterations, and paired differences between `s2f-agent` and the baseline were assessed with paired bootstrap confidence intervals and exact McNemar tests on aligned case outcomes.

## Benchmark objective

We evaluated whether a repository-aware genomics orchestration agent (`s2f-agent`) could select the correct skill, preserve task-specific constraints, and produce executable planning artifacts for common computational-genomics workflows. The benchmark was designed as a structured, automatically scored comparison between `s2f-agent` and general-purpose model participants that received the same curated task, skill, and output-contract information.

The current manuscript snapshot corresponds to run `ttapi_s2f_gpt55_chat_full_20260523_152235`, generated at `2026-05-23T07:37:36Z`. The primary comparison used two participants: `s2f-agent` and `gpt-5.5-ttapi-chat`.

## Benchmark suites and cases

Benchmark cases were stored as YAML ground-truth suites under `evals/` and loaded by `benchmark/tools/eval_benchmark.py`.

- `routing`: 23 cases testing whether the system should route to a canonical skill or ask a clarification question.
- `groundedness`: 8 cases testing whether the response stays grounded in repository contracts and avoids forbidden fabricated identifiers, paths, flags, or APIs.
- `task_success`: 23 cases testing whether the response contains a valid task plan with the required selected skill, runnable steps, expected outputs, missing-input handling, and retry policy.

The full run therefore contained 54 unique cases per participant. Cases covered variant-effect prediction, track prediction, embeddings, fine-tuning, environment setup, framework selection, segmentation, and skill scaffolding. The benchmark used only enabled skills from `registry/skills.yaml` unless the run was explicitly configured to include disabled skills.

## Shared knowledge supplied to participants

For OpenAI-compatible model participants, the benchmark rendered a prompt from `benchmark/prompts/catalog_contracts.md`. This prompt supplied:

- the benchmark suite name and task hint;
- the user query from the case file;
- canonical task definitions from `registry/task_contracts.yaml`;
- enabled skill IDs and task families from `registry/skills.yaml`;
- output and retry contracts from `registry/output_contracts.yaml`;
- a target JSON response shape.

The prompt instructed participants to return exactly one JSON object, use only repository concepts listed in the prompt, and prefer `clarify`, `null`, or empty arrays when the correct action was uncertain.

The local `s2f-agent` participant was evaluated through repository runtime entrypoints rather than the rendered OpenAI prompt. For routing cases, the benchmark called `scripts/route_query.sh --format json`; for groundedness and task-success cases, it called `scripts/run_agent.sh --format json`, passing the task hint when present.

## Participants and run configuration

Participants were defined in `benchmark/config/participants.yaml`.

- `s2f-agent`: local repository-aware agent, `kind=local_agent`, `prompt_variant=runtime`.
- `gpt-5.5-ttapi-chat`: OpenAI-compatible Chat Completions participant, `model=gpt-5.5`, `prompt_variant=catalog+contracts`, `reasoning_effort=medium`.

The latest manuscript run used seed `7`, `2000` bootstrap iterations, OpenAI-compatible base URL `https://w.ciykj.cn/v1`, request timeout `240` seconds, and `2` retries for retriable 429 or 5xx responses. Chat-completion payloads used `temperature=0` and `response_format={"type": "json_object"}`.

A reproducible invocation matching the latest manuscript run is:

```bash
OPENAI_API_KEY=<key> python3 benchmark/tools/eval_benchmark.py \
  --participants s2f-agent,gpt-5.5-ttapi-chat \
  --output-dir benchmark/runs/ttapi_s2f_gpt55_chat_full_20260523_152235 \
  --seed 7 \
  --openai-base-url https://w.ciykj.cn/v1 \
  --openai-timeout 240 \
  --openai-max-retries 2
```

## Response normalization

Every raw response was normalized to a common JSON representation before scoring. The normalizer extracted:

- `decision`;
- `primary_skill`;
- `secondary_skills`;
- `clarify_question`;
- constraints, assumptions, and missing inputs;
- selected required-input group;
- plan-level fields, including selected skill, runnable steps, expected outputs, fallbacks, and retry policy.

Responses that failed to parse as JSON, selected unknown skill IDs, or used unknown plan-selected skills received validation errors. These validation errors were incorporated into suite-level scoring.

## Scoring

Each case was scored automatically under two tracks. The strict track is the primary manuscript track. The lenient track is a supplementary fairness track that accepts a small number of equivalent field placements, such as reading selected skill from plan-level fields when top-level fields are missing.

For routing cases, a response passed if it matched the expected decision. Route cases additionally required the expected primary skill and all expected secondary skills. Clarification cases required the clarification question to contain the expected diagnostic phrase.

For groundedness cases, a response passed if it routed to the expected primary skill, included the required constraint fragment, omitted the forbidden fabricated substring, and had no normalization validation errors.

For task-success cases, a response passed if it routed, supplied a non-null plan, matched the task hint when specified, selected a valid skill, provided a retry policy, included all required plan array fields, met minimum runnable-step and expected-output counts, and satisfied any case-specific required or forbidden fragments for steps, outputs, selected skill, selected required-input group, missing inputs, or assumptions.

## Metrics and statistical analysis

For each participant and suite, the benchmark reported micro and macro pass rates.

- Micro pass rate was the fraction of scored cases that passed.
- Macro pass rate first averaged pass rates within task labels and then averaged across task labels, reducing the influence of tasks represented by more cases.

Suite-level 95% confidence intervals for micro and macro rates were estimated with nonparametric bootstrap resampling using `2000` iterations. Pairwise comparisons used aligned case outcomes between `s2f-agent` and each baseline. The reported delta was the difference in micro pass rate. Delta confidence intervals were estimated by paired bootstrap resampling. McNemar's exact test was computed from discordant paired outcomes, with `n10` counting cases passed by `s2f-agent` and failed by the baseline, and `n01` counting the converse.

## Output artifacts and quality control

Each benchmark run wrote raw outputs, normalized case records, summary tables, statistics, and selected examples under `benchmark/runs/<run_id>/`. A successful non-dry-run with no run errors was synchronized into `benchmark/reports/manuscript/`.

The manuscript snapshot includes:

- `benchmark-results-latest.md`: current manuscript summary and quality-control note;
- `benchmark-summary-ttapi_s2f_gpt55_chat_full_20260523_152235.csv`: per-suite metric table;
- `benchmark-stats-ttapi_s2f_gpt55_chat_full_20260523_152235.json`: bootstrap and McNemar statistics;
- `benchmark-table-ttapi_s2f_gpt55_chat_full_20260523_152235.md`: manuscript-ready results table;
- `benchmark-examples-ttapi_s2f_gpt55_chat_full_20260523_152235.md`: selected qualitative examples.

The latest requested-participant probe also tracked unavailable model requests. Exact ttapi slugs for `gpt-5`, `gpt-4`, and `o3-mini` returned service-unavailable responses during probing and were marked unavailable rather than scored as model capability failures.
