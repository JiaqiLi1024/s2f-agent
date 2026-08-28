# Benchmark Results (Latest)

## Run Metadata

- Run ID: `ttapi_s2f_gpt55_chat_full_20260523_152235`
- Generated at (UTC): `2026-05-23T07:37:36Z`
- Suites: `routing, groundedness, task_success`
- Participants: `s2f-agent, gpt-5.5-ttapi-chat`
- Seed: `7`
- OpenAI base URL: `https://w.ciykj.cn/v1`
- OpenAI timeout/retries: `240s / 2`

## Case Counts

- routing: 23
- groundedness: 8
- task_success: 23
- overall: 54

# Comparative Benchmark Summary

- Cell format is `micro / macro (n=cases)`.
- Strict is the primary manuscript track; lenient is a supplementary fairness track.

## Strict Track

### Main Results

| Participant | routing | groundedness | task_success | overall |
| --- | --- | --- | --- | --- |
| s2f-agent | 100.00% / 100.00% (n=23) | 100.00% / 100.00% (n=8) | 100.00% / 100.00% (n=23) | 100.00% / 100.00% (n=54) |
| gpt-5.5 (ttapi chat) | 21.74% / 41.11% (n=23) | 0.00% / 0.00% (n=8) | 30.43% / 38.54% (n=23) | 22.22% / 26.55% (n=54) |

## Lenient Track

### Main Results

| Participant | routing | groundedness | task_success | overall |
| --- | --- | --- | --- | --- |
| s2f-agent | 100.00% / 100.00% (n=23) | 100.00% / 100.00% (n=8) | 100.00% / 100.00% (n=23) | 100.00% / 100.00% (n=54) |
| gpt-5.5 (ttapi chat) | 21.74% / 41.11% (n=23) | 0.00% / 0.00% (n=8) | 30.43% / 38.54% (n=23) | 22.22% / 26.55% (n=54) |

## Statistical Comparisons

| Track | Comparison | Suite | Delta micro | 95% CI | McNemar p-value |
| --- | --- | --- | --- | --- | --- |
| strict | s2f-agent vs gpt-5.5-ttapi-chat | overall | +0.778 | [0.667, 0.889] | 4.54747e-13 |
| strict | s2f-agent vs gpt-5.5-ttapi-chat | routing | +0.783 | [0.609, 0.913] | 7.62939e-06 |
| strict | s2f-agent vs gpt-5.5-ttapi-chat | groundedness | +1.000 | [1.000, 1.000] | 0.0078125 |
| strict | s2f-agent vs gpt-5.5-ttapi-chat | task_success | +0.696 | [0.522, 0.870] | 3.05176e-05 |
| lenient | s2f-agent vs gpt-5.5-ttapi-chat | overall | +0.778 | [0.667, 0.889] | 4.54747e-13 |
| lenient | s2f-agent vs gpt-5.5-ttapi-chat | routing | +0.783 | [0.609, 0.913] | 7.62939e-06 |
| lenient | s2f-agent vs gpt-5.5-ttapi-chat | groundedness | +1.000 | [1.000, 1.000] | 0.0078125 |
| lenient | s2f-agent vs gpt-5.5-ttapi-chat | task_success | +0.696 | [0.522, 0.870] | 3.05176e-05 |

## Quality-Control Note

- Strict is the primary manuscript track; lenient is a supplementary fairness track.
- Report numbers must come from the current run folder, not older manuscript snapshots.

## Artifacts

- Run folder: `/Users/jiaqili/Desktop/s2f-skills/benchmark/runs/ttapi_s2f_gpt55_chat_full_20260523_152235/`
- Summary CSV: `/Users/jiaqili/Desktop/s2f-skills/benchmark/runs/ttapi_s2f_gpt55_chat_full_20260523_152235/summary.csv`
- Stats JSON: `/Users/jiaqili/Desktop/s2f-skills/benchmark/runs/ttapi_s2f_gpt55_chat_full_20260523_152235/stats.json`
- Table snapshot: `/Users/jiaqili/Desktop/s2f-skills/benchmark/runs/ttapi_s2f_gpt55_chat_full_20260523_152235/table.md`
- Example snapshot: `/Users/jiaqili/Desktop/s2f-skills/benchmark/runs/ttapi_s2f_gpt55_chat_full_20260523_152235/examples.md`

## Requested Participant Coverage

Requested participants: `s2f-agent`, `gpt-5.5`, `gpt-5`, `gpt-4`, `o3-mini`.

- `s2f-agent`: completed full 54-case benchmark.
- `gpt-5.5`: completed full 54-case benchmark through ttapi Chat Completions JSON mode as `gpt-5.5-ttapi-chat`.
- `gpt-5`, `gpt-4`, `o3-mini`: exact ttapi slugs returned `503 Service temporarily unavailable` during probe; these are marked unavailable rather than scored as model capability failures.

![Requested participants benchmark](/Users/jiaqili/Desktop/s2f-skills/benchmark/reports/manuscript/requested-participants-benchmark-ttapi_20260523_154311.png)

- Requested participant summary: `/Users/jiaqili/Desktop/s2f-skills/benchmark/reports/manuscript/requested-participants-summary-ttapi_20260523_154311.csv`
- Requested participant figure SVG: `/Users/jiaqili/Desktop/s2f-skills/benchmark/reports/manuscript/requested-participants-benchmark-ttapi_20260523_154311.svg`

