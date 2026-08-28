# Benchmark Examples

## routing / route_001

Query:

> Use $dnabert2 to validate my train/dev/test CSV and suggest model_max_length.

Participants:

- gpt-5.5-ttapi-chat: status=scored pass=False
  - raw_preview: {"clarify_question":"Please provide the task-objective, dataset-schema for the train/dev/test CSV files, and compute-constraints so DNABERT-2 can validate the CSVs and suggest model_max_length.","constraints":["Use dnabert2.","Validate train/dev/test CSV.","Suggest model_max_length."],"decision":"clarify","plan":{"assumptions":["dataset-schema-must-be-validated-before-training","evaluation-artifac

