# Benchmark metrics figure note

`benchmark_metrics_nature` is a two-panel, Nature-style summary of the latest complete paired comparative snapshot currently available in this repository. It is not presented as a Benchmark v2 result because a complete v2 API comparison has not yet been run.

## Figure design

- Panel a reports strict-track micro pass rates and nonparametric bootstrap 95% confidence intervals for routing, groundedness, and task-success cases.
- Panel b reports the paired difference in micro pass rate (`s2f-agent` minus `gpt-5.5 (ttapi chat)`), paired-bootstrap 95% confidence intervals, and two-sided exact McNemar P values.
- Sample sizes refer to aligned cases: routing, n = 23; groundedness, n = 8; task success, n = 23; overall, n = 54.
- The baseline was evaluated through a proxy OpenAI-compatible Chat Completions endpoint. Its result should not be interpreted as an official first-party model evaluation.

## Provenance

- Run: `ttapi_s2f_gpt55_chat_full_20260523_152235`
- Metric source: `manuscript/benchmark-summary-ttapi_s2f_gpt55_chat_full_20260523_152235.csv`
- Statistical source: `manuscript/benchmark-stats-ttapi_s2f_gpt55_chat_full_20260523_152235.json`
- Plot-ready source data: `benchmark_metrics_source_data.csv`
- Reproduction script: `plot_benchmark_metrics_nature.py`

## Export and QA

The script exports editable SVG, vector PDF, 600 dpi PNG, and LZW-compressed 600 dpi TIFF files on a white background at approximately 183 mm x 90 mm. Final QA confirmed:

- PNG and TIFF exports are nonblank, 4320 x 2124 pixels, and carry 600 dpi metadata.
- The PDF is a nonblank, single-page vector export at approximately 183 mm x 90 mm.
- The SVG parses successfully and contains 43 editable text elements.
- Visual inspection at full export resolution found no clipped labels, overlapping annotations, or missing marks.
