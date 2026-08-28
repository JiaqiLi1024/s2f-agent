# Benchmark Examples

## groundedness / grounded_001

Query:

> Help me run AlphaGenome predict_variant on hg38 with REF ALT.

Participants:

- gpt-5.5-ttapi-chat: status=scored pass=False
  - raw_preview: {   "clarify_question": "Please provide the hg38 variant coordinate or interval and the exact REF and ALT alleles, with the coordinate convention made explicit.",   "constraints": [     "Use only AlphaGenome Cloud API-based variant effect prediction.",     "Assembly is hg38.",     "Coordinate convention must be explicit.",     "REF/ALT interpretation is limited to the selected model."   ],   "deci

## routing / route_001

Query:

> Use $dnabert2 to validate my train/dev/test CSV and suggest model_max_length.

Participants:

- gpt-5.5-ttapi-chat: status=scored pass=False
  - raw_preview: {"clarify_question":"Please provide the task objective, the train/dev/test CSV dataset schema, and compute constraints so DNABERT-2 can validate the CSVs and suggest model_max_length.","constraints":["Use only the dnabert2 skill for DNABERT-2 CSV validation and fine-tuning preparation.","Do not start training until dataset schema and compute constraints are provided."],"decision":"clarify","plan":

## task_success / task_success_001

Query:

> Need variant-effect guidance for hg38 chr12 REF ALT with output summary.

Participants:

- gpt-5.5-ttapi-chat: status=scored pass=False
  - raw_preview: {"clarify_question":"Please provide the chr12 coordinate or interval and the explicit REF and ALT alleles for hg38, e.g. chr12:<position> REF>ALT.","constraints":["coordinate-convention-must-be-explicit","ref-alt-interpretation-limited-to-selected-model","unified-output-defaults-to-wide-table-plus-per-skill-standardized-records"],"decision":"clarify","plan":{"assumptions":["coordinate-convention-m

