# Benchmark: Repository-aware orchestration for sequence-to-function workflows

> **Draft status (21 August 2026).** This manuscript revision reports the
> completed 54-case legacy comparative snapshot
> `ttapi_s2f_gpt55_chat_full_20260523_152235`. It does not report Benchmark v2
> performance. Benchmark v2 introduces a stricter task-blind,
> information-equivalent protocol, but no completed non-dry-run v2 result is
> available for inclusion here. The external comparator was accessed through a
> third-party OpenAI-compatible proxy; its results therefore characterize the
> evaluated system configuration and endpoint, not an official first-party
> model evaluation.

**One-sentence argument.** In a 54-case, repository-aware comparative
snapshot, `s2f-agent` achieved higher automatically scored orchestration pass
rates than a `gpt-5.5` participant accessed through a ttapi Chat Completions
proxy, with the strongest separation observed in groundedness and adherence to
task-success contracts.

## Results

<!-- Figure mapping for manuscript assembly:
Fig. 1: ../benchmark_metrics_nature
Panel a: strict micro pass rates and bootstrap confidence intervals
Panel b: paired micro-rate differences, paired-bootstrap confidence intervals
         and exact McNemar P values
The figure is a legacy comparative snapshot and not a Benchmark v2 result.
-->

### A contract-based benchmark separated routing, groundedness and task-success behavior

We evaluated repository-aware orchestration using 54 curated cases divided
among routing (23 cases), groundedness (8 cases) and task-success planning (23
cases). Routing cases tested selection of a canonical repository skill or an
appropriate clarification action. Groundedness cases tested whether outputs
preserved required repository constraints while avoiding fabricated
identifiers, paths, flags or application programming interfaces. Task-success
cases tested whether the system produced a non-null, contract-compliant plan
with a valid selected skill, explicit input handling, runnable steps, expected
outputs and a retry policy. The primary analysis used the strict scoring track;
the supplementary lenient track accepted a limited set of equivalent field
placements. Both tracks produced identical case-level outcomes in this
snapshot.

The comparison included the local `s2f-agent` runtime and an external
`gpt-5.5-ttapi-chat` participant. The external participant was requested as
model slug `gpt-5.5` through the OpenAI-compatible ttapi Chat Completions
endpoint and received the repository catalog and contracts in its prompt. The
local participant instead used its native repository runtime and registry
files. This design tested two deployable orchestration configurations under the
legacy protocol; it was not a model-weight-matched comparison and did not yet
implement the task-blind information-equivalence controls subsequently added
to Benchmark v2.

### The local agent passed all cases in the completed snapshot

Under strict scoring, `s2f-agent` passed 54 of 54 cases (100.00% micro pass
rate). It passed all routing cases (23 of 23), all groundedness cases (8 of 8)
and all task-success cases (23 of 23; Fig. 1a). The suite-level nonparametric
bootstrap confidence intervals were 100.00-100.00% because every resampled
case passed. Macro pass rates, calculated by first averaging within task labels,
were also 100.00% for each suite and overall. These values describe complete
coverage of this curated corpus under its automated contracts; they do not
imply error-free behavior on unseen genomics requests.

The `gpt-5.5-ttapi-chat` configuration passed 12 of 54 cases (22.22% micro;
26.55% macro). Its strict routing pass rate was 21.74% (5 of 23; bootstrap 95%
confidence interval, 4.35-39.13%), and its task-success pass rate was 30.43% (7
of 23; 13.04-47.83%). It passed none of the eight groundedness cases (0.00%;
0.00-0.00%). Macro pass rates were 41.11% for routing, 0.00% for groundedness
and 38.54% for task success. The difference between micro and macro summaries
indicates that successes and failures were unevenly distributed across task
labels, but the direction of the comparison was unchanged under either
aggregation.

| Participant | Routing, passed/total (micro) | Groundedness, passed/total (micro) | Task success, passed/total (micro) | Overall, passed/total (micro) | Overall macro |
| --- | ---: | ---: | ---: | ---: | ---: |
| `s2f-agent` | 23/23 (100.00%) | 8/8 (100.00%) | 23/23 (100.00%) | 54/54 (100.00%) | 100.00% |
| `gpt-5.5-ttapi-chat` | 5/23 (21.74%) | 0/8 (0.00%) | 7/23 (30.43%) | 12/54 (22.22%) | 26.55% |

### Paired outcomes showed separation across all three suites

Because both participants completed the same 54 cases, we compared aligned
binary outcomes. The overall strict micro-rate difference for `s2f-agent`
minus `gpt-5.5-ttapi-chat` was 77.78 percentage points (paired-bootstrap 95%
confidence interval, 66.67-88.89; exact McNemar `P = 4.55 x 10^-13`; Fig. 1b).
There were 42 discordant cases passed only by `s2f-agent` and no cases passed
only by the comparator.

The paired difference was 78.26 percentage points for routing (95% confidence
interval, 60.87-91.30; `P = 7.63 x 10^-6`), 100.00 points for groundedness
(100.00-100.00; `P = 0.0078125`) and 69.57 points for task success
(52.17-86.96; `P = 3.05 x 10^-5`). The corresponding discordant counts in
favor of `s2f-agent` were 18, 8 and 16, respectively, with zero discordant
cases in the converse direction in every suite. The confidence interval for
the eight-case groundedness suite is degenerate because all aligned outcomes
had the same direction; its small sample size remains an important limitation.
No multiplicity correction was applied, so suite-level tests are interpreted
as supporting descriptions of this benchmark snapshot rather than independent
confirmatory claims.

### Endpoint availability bounded the historical participant comparison

The requested historical participant set also included exact ttapi model slugs
`gpt-5`, `gpt-4` and `o3-mini`. Each returned `503 Service temporarily
unavailable` during the recorded probe and was therefore marked unavailable.
These participants were not assigned failed cases or zero performance scores.
The `gpt-5.5` slug completed all 54 cases only through the Chat Completions JSON
path; an attempted Responses-style long-prompt path returned an endpoint error.
Consequently, the completed comparison supports a system-level statement about
the tested local agent and proxy configuration, but it does not establish the
relative performance of the unavailable models or the intrinsic capability of
an official `gpt-5.5` deployment.

### The snapshot evaluates orchestration contracts rather than biological prediction accuracy

The benchmark measured whether a system selected repository skills and emitted
grounded, executable planning structures. It did not execute the planned
sequence-to-function analyses, compare predicted molecular effects with
experimental measurements, or assess downstream disease prediction. The
observed separation therefore supports the narrower conclusion that repository
integration and explicit task contracts were associated with more reliable
orchestration within these cases. It does not demonstrate superior general
biological reasoning, clinical utility or foundation-model capability.

## Methods

### Study design and scope

We constructed a comparative benchmark for orchestration of
computational-genomics and sequence-to-function workflows. The evaluation unit
was a curated user request paired with an automatically checkable contract.
The benchmark asked whether a participant could route the request to a
repository-supported skill, preserve case-specific constraints and construct a
plan that exposed required inputs, executable actions, outputs and recovery
behavior. It did not score free-form answer quality or run the downstream
scientific workflow.

This manuscript reports run
`ttapi_s2f_gpt55_chat_full_20260523_152235`, generated on 23 May 2026 at
07:37:36 UTC. The run contained 54 unique cases for each of two participants.
The stored summary contains strict and lenient records for each participant and
suite, but these are two scoring views of the same responses rather than
independent cases. Thus, 108 summary records correspond to 54 evaluated
requests per participant, not 108 distinct benchmark cases.

### Benchmark suites and case contracts

Cases were defined in YAML ground-truth suites and evaluated by
`benchmark/tools/eval_benchmark.py`. The routing suite contained 23 cases. Each
specified an expected decision to route or clarify. Route cases could require a
primary skill and one or more secondary skills; clarification cases required a
diagnostic phrase in the clarification question.

The groundedness suite contained eight cases. Each defined an expected primary
skill, a constraint fragment that had to be retained and a forbidden substring
representing a fabricated identifier, path, command-line flag or API concept. A
case passed only if the expected skill and required constraint were present,
the forbidden content was absent and response normalization produced no
validation error.

The task-success suite contained 23 cases. A passing response required a
non-null plan, a valid repository skill, agreement with the case task hint when
one was specified, a retry policy, all required plan arrays, and the minimum
numbers of runnable steps and expected outputs. Individual cases could also
require or forbid fragments in steps, outputs, assumptions and missing-input
fields, or require a particular selected skill or acceptable required-input
group. These contracts evaluated structural and repository-level task
readiness, not whether executing a plan would produce a scientifically correct
result.

### Participants and runtime paths

Participants were configured in `benchmark/config/participants.yaml`. The
`s2f-agent` participant was the repository-aware local system and was evaluated
through its native runtime entrypoints. Routing cases invoked
`scripts/route_query.sh --format json`; groundedness and task-success cases
invoked `scripts/run_agent.sh --format json`, with the task hint supplied when
available. The runtime read repository registries and generated structured
outputs for normalization and scoring.

The external participant, `gpt-5.5-ttapi-chat`, used the requested model slug
`gpt-5.5` through an OpenAI-compatible Chat Completions proxy at
`https://w.ciykj.cn/v1`. It used the `catalog+contracts` prompt variant,
`reasoning_effort=medium`, `temperature=0` and
`response_format={"type": "json_object"}`. Because the endpoint was operated
through a third-party relay, both model identity and serving configuration are
treated as properties reported by that endpoint. The comparison should not be
presented as an official first-party OpenAI benchmark.

### Repository information supplied to the external participant

The external prompt was rendered from
`benchmark/prompts/catalog_contracts.md`. For each case, it included the suite
name, task hint, user query, canonical task definitions from
`registry/task_contracts.yaml`, enabled skill identifiers and task families
from `registry/skills.yaml`, output and retry contracts from
`registry/output_contracts.yaml`, and the requested JSON response shape. The
prompt instructed the participant to return one JSON object, restrict its
choices to listed repository concepts and use clarification, `null` values or
empty arrays when information was insufficient.

The local system did not receive this rendered prompt; it operated through the
repository runtime and its native access to registry information. The legacy
comparison therefore sought to expose the external participant to the relevant
catalog and contracts, but it did not enforce identical context packaging or a
task-blind interface. The later Benchmark v2 protocol separates hidden scoring
contracts from participant-visible context and defines stricter
information-equivalence controls. Those changes address a design limitation of
the legacy run and are not retroactively attributed to the results reported
here.

### Response normalization and validation

Raw participant outputs were normalized to a common JSON representation before
scoring. The representation included the top-level decision, primary and
secondary skills, clarification question, constraints, assumptions, missing
inputs and selected required-input group. Plan-level normalization extracted
the selected skill, runnable steps, expected outputs, fallbacks and retry
policy.

Malformed JSON, unknown top-level skills and unknown plan-selected skills
generated validation errors. Validation errors contributed to case failure
under the relevant suite contract. The normalization layer permitted a common
scorer to operate on native local-agent responses and proxy model responses
without treating arbitrary prose as equivalent to the required structured
fields.

### Strict and lenient scoring

The strict track was defined as the primary manuscript analysis. It required
the normalized values to appear in their canonical fields and to satisfy all
suite-specific checks. The lenient track was a supplementary fairness analysis
that accepted a limited set of semantically equivalent field placements, such
as reading a selected skill from a valid plan-level field when the corresponding
top-level field was absent. Strict and lenient results were computed from the
same raw responses. They were identical for both participants in the reported
run, indicating that the observed difference was not caused by the lenient
field-placement allowances.

### Metrics and statistical analysis

For participant `i` and suite `s`, the micro pass rate was the number of cases
passing every applicable contract check divided by the number of scored cases.
The macro pass rate was calculated by averaging pass rates within task labels
and then averaging across those labels, limiting the influence of task labels
represented by more cases. Overall micro rates pooled all 54 cases; overall
macro rates aggregated the task-level summaries.

Suite-level 95% confidence intervals for micro and macro rates were estimated
by 2,000 nonparametric bootstrap resamples using seed 7. Pairwise comparisons
were restricted to aligned case identifiers completed by both participants.
The reported effect was the difference in micro pass rate, calculated as
`s2f-agent` minus `gpt-5.5-ttapi-chat`; its 95% confidence interval was estimated
by paired bootstrap resampling. Exact two-sided McNemar tests used the
discordant binary outcomes, with `n10` denoting a pass by `s2f-agent` and a
failure by the comparator and `n01` denoting the converse. No correction for
the suite-level multiple comparisons was applied.

### Run configuration, endpoint errors and coverage

The evaluation used seed 7, a 240-s request timeout and up to two retries for
retriable rate-limit or server errors. It was a non-dry-run evaluation. Each
completed participant produced outcomes for all 23 routing, 8 groundedness and
23 task-success cases, enabling complete paired analysis. Endpoint failures
during model-availability probing were tracked separately from benchmark case
failures. In particular, requested model slugs that returned `503` during the
probe were classified as unavailable and excluded from performance summaries.

A command corresponding to the completed comparison is:

```bash
OPENAI_API_KEY=<relay-key> python3 benchmark/tools/eval_benchmark.py \
  --participants s2f-agent,gpt-5.5-ttapi-chat \
  --output-dir benchmark/runs/ttapi_s2f_gpt55_chat_full_20260523_152235 \
  --seed 7 \
  --openai-base-url https://w.ciykj.cn/v1 \
  --openai-timeout 240 \
  --openai-max-retries 2
```

The relay key is not stored in manuscript artifacts. Re-execution depends on
the continuing availability and behavior of the third-party endpoint and may
therefore not reproduce the external response stream even when the local code,
cases and seed are held constant.

### Result provenance and reproducibility artifacts

The frozen run directory is
`benchmark/runs/ttapi_s2f_gpt55_chat_full_20260523_152235/`. The principal
manuscript inputs are
`benchmark-summary-ttapi_s2f_gpt55_chat_full_20260523_152235.csv` for pass-rate
summaries and confidence intervals,
`benchmark-stats-ttapi_s2f_gpt55_chat_full_20260523_152235.json` for paired
differences and exact McNemar tests, and
`requested-participants-summary-ttapi_20260523_154311.csv` for endpoint
availability. The corresponding Nature-style visualization is
`benchmark/reports/benchmark_metrics_nature.png`. Raw and normalized case
records, table snapshots and examples remain in the frozen run directory for
audit.

## Current evidence boundary

- The numerical claims apply to one curated 54-case legacy snapshot with two
  completed participants. They are not Benchmark v2 results.
- The comparison is between a repository-native agent runtime and a proxy-hosted
  Chat Completions configuration. It does not isolate architecture, model
  weights, prompt, tool access or serving infrastructure as causal factors.
- The external endpoint was a third-party relay. The recorded model slug is not
  independently verified here, and the result must not be presented as an
  official `gpt-5.5` evaluation.
- The local 100% pass rate indicates complete success on the observed cases, not
  perfect generalization. The eight-case groundedness suite is particularly
  small.
- Automated contract checks assess routing, repository grounding and plan
  structure. They do not establish scientific correctness after workflow
  execution, biological validity, clinical utility or downstream prediction
  accuracy.
- The same benchmark cases and repository contracts were used to develop and
  evaluate the local system. Without a frozen, independently held-out set,
  development-set familiarity remains a plausible source of optimistic
  performance.
- Strict and lenient tracks are alternative scorings of the same outputs, not
  independent replications. Suite-level McNemar tests were not adjusted for
  multiple comparisons.
- Exact ttapi slugs that returned endpoint errors were treated as unavailable,
  not as zero-scoring model participants. No claim is made about their
  capability.

## Assumptions or missing inputs

- A completed non-dry-run Benchmark v2 artifact is unavailable. The manuscript
  should be updated when the task-blind, information-equivalent v2 evaluation
  has been frozen and audited.
- No independent endpoint attestation verifies the external model identity,
  model revision, hidden system prompt, sampling implementation or serving
  stack used by the relay.
- The current corpus does not provide an external blinded test set, repeated
  stochastic runs, rater-based quality assessment, execution-based validation
  or perturbation tests for prompt sensitivity.
- Formal figure numbering and placement have not been frozen. The provisional
  reference `Fig. 1` maps to `benchmark_metrics_nature.png`.
- Public archival identifiers, software-environment hashes and a submission
  repository DOI remain to be added before publication.

## Terminology ledger

| Term | Definition used here | Explicit exclusion |
| --- | --- | --- |
| repository-aware orchestration | Routing and structured planning constrained by the local skill and contract registries | Not general biological reasoning |
| pass | A response satisfied every automated check applicable to a case and score track | Not proof that a downstream analysis is scientifically correct |
| groundedness | Retention of required repository constraints without specified fabricated identifiers, paths, flags or APIs | Not factuality over unrestricted scientific knowledge |
| task success | Contract-compliant planning with valid skills, input handling, runnable steps, outputs and retry behavior | Not successful execution of the downstream workflow |
| strict track | Primary scoring using canonical normalized fields | Not a separate benchmark run |
| lenient track | Supplementary scoring accepting limited equivalent field placements | Not relaxed scientific correctness |
| `gpt-5.5-ttapi-chat` | The system configuration reached through the ttapi Chat Completions proxy with requested slug `gpt-5.5` | Not an independently verified or official first-party evaluation |
| legacy snapshot | The completed 54-case run reported in this document | Not Benchmark v2 |
| Benchmark v2 | A later protocol with stronger task-blind and information-equivalence controls | No completed v2 performance is reported here |

## Claim-evidence map

| Manuscript claim | Direct evidence | Boundary retained |
| --- | --- | --- |
| `s2f-agent` passed all 54 legacy cases | Strict summary CSV: 54/54 overall; 23/23 routing; 8/8 groundedness; 23/23 task success | Curated observed corpus only |
| The proxy comparator passed 12 of 54 cases | Strict summary CSV: 12/54 overall; 5/23 routing; 0/8 groundedness; 7/23 task success | System-level proxy result, not intrinsic or official model capability |
| The overall paired difference was 77.78 percentage points | Statistics JSON: paired delta 0.7778, 95% confidence interval 0.6667-0.8889, exact McNemar `P = 4.55 x 10^-13` | Complete paired legacy cases; no causal attribution |
| Groundedness showed the largest suite-level separation | Statistics JSON: delta 1.0000 across 8 aligned cases | Small suite with a degenerate bootstrap interval |
| Strict and lenient results were identical | Summary CSV contains identical case counts and rates under both tracks | Alternative scoring views of the same responses |
| Other requested model slugs were unavailable | Requested-participant summary: `503` for `gpt-5`, `gpt-4` and `o3-mini` | Endpoint status is not a capability score |
| The result is not Benchmark v2 | Frozen run used the legacy evaluator and catalog-plus-contracts prompt; v2 artifacts currently comprise protocol and dry-run checks rather than a completed scored run | Await completed, audited v2 evaluation |
