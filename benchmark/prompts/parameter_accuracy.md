You are participating in a parameter-groundedness benchmark for computational-genomics workflows.

Return exactly one JSON object and no surrounding prose. Use only the retrieved context bundle and the response fields listed below. Do not infer a numeric value from a model name, a common convention, or a neighboring tool. If the requested value is not explicitly documented as a universal value, mark that claim as `status: "unknown"` and explain the verification boundary in `evidence`.

User query:
{{QUERY}}

Retrieved context bundle:
{{CONTEXT_BUNDLE}}

Target response schema:
{{JSON_SCHEMA}}

For this track, populate `parameter_claims` with one claim for the requested parameter. A documented claim must preserve the exact value or relationship and cite its repository evidence path. An unknown claim must use `value: "unknown"`, `status: "unknown"`, and evidence containing `not documented` or an equivalent verification warning. A claim is not a place to guess a default.
