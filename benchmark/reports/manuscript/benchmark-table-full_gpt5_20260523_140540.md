# Comparative Benchmark Summary

- Cell format is `micro / macro (n=cases)`.
- Strict is the primary manuscript track; lenient is a supplementary fairness track.

## Strict Track

### Main Results

| Participant | routing | groundedness | task_success | overall |
| --- | --- | --- | --- | --- |
| s2f-agent | 100.00% / 100.00% (n=23) | 100.00% / 100.00% (n=8) | 100.00% / 100.00% (n=23) | 100.00% / 100.00% (n=54) |
| gpt-4o | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=8) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=54) |
| o3-mini | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=8) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=54) |
| gpt-5 | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=8) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=54) |
| gpt-5.5 | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=8) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=54) |

### o3-mini Ablation

| Participant | routing | groundedness | task_success | overall |
| --- | --- | --- | --- | --- |
| o3-mini (direct) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=8) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=54) |
| o3-mini (catalog-only) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=8) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=54) |

## Lenient Track

### Main Results

| Participant | routing | groundedness | task_success | overall |
| --- | --- | --- | --- | --- |
| s2f-agent | 100.00% / 100.00% (n=23) | 100.00% / 100.00% (n=8) | 100.00% / 100.00% (n=23) | 100.00% / 100.00% (n=54) |
| gpt-4o | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=8) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=54) |
| o3-mini | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=8) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=54) |
| gpt-5 | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=8) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=54) |
| gpt-5.5 | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=8) | 0.00% / 0.00% (n=23) | 0.00% / 0.00% (n=54) |

## Statistical Comparisons

| Track | Comparison | Suite | Delta micro | 95% CI | McNemar p-value |
| --- | --- | --- | --- | --- | --- |
| strict | s2f-agent vs gpt-4o | overall | +1.000 | [1.000, 1.000] | 1.11022e-16 |
| strict | s2f-agent vs gpt-4o | routing | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| strict | s2f-agent vs gpt-4o | groundedness | +1.000 | [1.000, 1.000] | 0.0078125 |
| strict | s2f-agent vs gpt-4o | task_success | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| strict | s2f-agent vs o3-mini | overall | +1.000 | [1.000, 1.000] | 1.11022e-16 |
| strict | s2f-agent vs o3-mini | routing | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| strict | s2f-agent vs o3-mini | groundedness | +1.000 | [1.000, 1.000] | 0.0078125 |
| strict | s2f-agent vs o3-mini | task_success | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| strict | s2f-agent vs gpt-5 | overall | +1.000 | [1.000, 1.000] | 1.11022e-16 |
| strict | s2f-agent vs gpt-5 | routing | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| strict | s2f-agent vs gpt-5 | groundedness | +1.000 | [1.000, 1.000] | 0.0078125 |
| strict | s2f-agent vs gpt-5 | task_success | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| strict | s2f-agent vs gpt-5.5 | overall | +1.000 | [1.000, 1.000] | 1.11022e-16 |
| strict | s2f-agent vs gpt-5.5 | routing | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| strict | s2f-agent vs gpt-5.5 | groundedness | +1.000 | [1.000, 1.000] | 0.0078125 |
| strict | s2f-agent vs gpt-5.5 | task_success | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| lenient | s2f-agent vs gpt-4o | overall | +1.000 | [1.000, 1.000] | 1.11022e-16 |
| lenient | s2f-agent vs gpt-4o | routing | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| lenient | s2f-agent vs gpt-4o | groundedness | +1.000 | [1.000, 1.000] | 0.0078125 |
| lenient | s2f-agent vs gpt-4o | task_success | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| lenient | s2f-agent vs o3-mini | overall | +1.000 | [1.000, 1.000] | 1.11022e-16 |
| lenient | s2f-agent vs o3-mini | routing | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| lenient | s2f-agent vs o3-mini | groundedness | +1.000 | [1.000, 1.000] | 0.0078125 |
| lenient | s2f-agent vs o3-mini | task_success | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| lenient | s2f-agent vs gpt-5 | overall | +1.000 | [1.000, 1.000] | 1.11022e-16 |
| lenient | s2f-agent vs gpt-5 | routing | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| lenient | s2f-agent vs gpt-5 | groundedness | +1.000 | [1.000, 1.000] | 0.0078125 |
| lenient | s2f-agent vs gpt-5 | task_success | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| lenient | s2f-agent vs gpt-5.5 | overall | +1.000 | [1.000, 1.000] | 1.11022e-16 |
| lenient | s2f-agent vs gpt-5.5 | routing | +1.000 | [1.000, 1.000] | 2.38419e-07 |
| lenient | s2f-agent vs gpt-5.5 | groundedness | +1.000 | [1.000, 1.000] | 0.0078125 |
| lenient | s2f-agent vs gpt-5.5 | task_success | +1.000 | [1.000, 1.000] | 2.38419e-07 |
