# Benchmark Examples

## groundedness / grounded_001

Query:

> Help me run AlphaGenome predict_variant on hg38 with REF ALT.

Participants:

- s2f-agent: status=scored pass=True
  - raw_preview: {"query":"Help me run AlphaGenome predict_variant on hg38 with REF ALT.","task":"variant-effect","task_source":"provided","decision":"route","confidence":{"level":"high","score":0.86},"clarify_question":null,"primary_skill":"alphagenome-api","primary_skill_path":"skills/alphagenome-api","skill_doc":"/Users/jiaqili/Desktop/s2f-skills/skills/alphagenome-api/SKILL.md","skill_metadata":"/Users/jiaqili

## routing / route_001

Query:

> Use $dnabert2 to validate my train/dev/test CSV and suggest model_max_length.

Participants:

- s2f-agent: status=scored pass=True
  - raw_preview: {"query":"Use $dnabert2 to validate my train/dev/test CSV and suggest model_max_length.","task":"fine-tuning","task_source":"provided","decision":"route","confidence":{"level":"high","score":0.92},"clarify_question":null,"primary":{"skill":"dnabert2","score":245,"reasons":["explicit skill mention: $dnabert2","query mentions skill id","matched triggers: dnabert2","task alignment: fine-tuning"]},"se

## task_success / task_success_001

Query:

> Need variant-effect guidance for hg38 chr12 REF ALT with output summary.

Participants:

- s2f-agent: status=scored pass=True
  - raw_preview: {"query":"Need variant-effect guidance for hg38 chr12 REF ALT with output summary.","task":"variant-effect","task_source":"provided","decision":"route","confidence":{"level":"low","score":0.34},"clarify_question":null,"primary_skill":"alphagenome-api","primary_skill_path":"skills/alphagenome-api","skill_doc":"/Users/jiaqili/Desktop/s2f-skills/skills/alphagenome-api/SKILL.md","skill_metadata":"/Use

