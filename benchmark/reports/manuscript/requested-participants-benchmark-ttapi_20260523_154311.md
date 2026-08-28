# Requested Participants Benchmark Summary

- Source completed benchmark: `benchmark/runs/ttapi_s2f_gpt55_chat_full_20260523_152235`
- ttapi base URL: `https://w.ciykj.cn/v1`
- Unavailable exact slugs are marked `N/A` and are not counted as capability failures.

| Participant | Status | Routing | Groundedness | Task success | Overall | Note |
| --- | --- | --- | --- | --- | --- | --- |
| s2f-agent | completed | 100.00% (23/23) | 100.00% (8/8) | 100.00% (23/23) | 100.00% (54/54) | local agent benchmark completed |
| gpt-5.5 | completed_via_ttapi_chat | 21.74% (5/23) | 0.00% (0/8) | 30.43% (7/23) | 22.22% (12/54) | ttapi Responses long-prompt path returned 502, chat JSON path completed full benchmark |
| gpt-5 | api_unavailable | N/A | N/A | N/A | N/A | exact ttapi model slug returned 503 during probe; not scored as capability failure |
| gpt-4 | api_unavailable | N/A | N/A | N/A | N/A | exact ttapi model slug returned 503 during probe; not scored as capability failure |
| o3-mini | api_unavailable | N/A | N/A | N/A | N/A | exact ttapi model slug returned 503 during probe; not scored as capability failure |

![Requested participants benchmark](/Users/jiaqili/Desktop/s2f-skills/benchmark/runs/ttapi_requested_models_20260523_154311/requested_participants_benchmark.png)
