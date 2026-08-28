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
