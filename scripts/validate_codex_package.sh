#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_JSON="$REPO_ROOT/.codex-plugin/plugin.json"
REGISTRY_FILE="$REPO_ROOT/registry/skills.yaml"

source "$REPO_ROOT/scripts/lib_registry.sh"

failures=0

fail() {
  echo "fail: $*" >&2
  failures=$((failures + 1))
}

ok() {
  echo "ok: $*"
}

if [[ ! -f "$PLUGIN_JSON" ]]; then
  fail "missing plugin manifest: .codex-plugin/plugin.json"
else
  ok "plugin manifest exists"
fi

if command -v python3 >/dev/null 2>&1; then
  if [[ -f "$PLUGIN_JSON" ]]; then
    python3 - "$PLUGIN_JSON" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text())
required = ["name", "version", "description", "repository", "skills", "interface"]
missing = [key for key in required if key not in data]
if missing:
    raise SystemExit(f"missing required plugin field(s): {', '.join(missing)}")
if data["skills"] != "./skills/":
    raise SystemExit("plugin skills field must be './skills/'")
interface = data["interface"]
for key in ["displayName", "shortDescription", "developerName", "category"]:
    if not interface.get(key):
        raise SystemExit(f"missing interface field: {key}")
prompts = interface.get("defaultPrompt", [])
if len(prompts) > 3:
    raise SystemExit("interface.defaultPrompt must contain at most 3 entries")
for prompt in prompts:
    if len(prompt) > 128:
        raise SystemExit(f"defaultPrompt entry exceeds 128 characters: {prompt!r}")
PY
    ok "plugin manifest JSON is valid"
  fi
else
  fail "python3 is required for package validation"
fi

registry_require_file "$REGISTRY_FILE"

while IFS= read -r skill_id; do
  [[ -z "$skill_id" ]] && continue

  if ! registry_skill_enabled "$REGISTRY_FILE" "$skill_id"; then
    echo "info: $skill_id is disabled; package checks skipped"
    continue
  fi

  skill_path="$(registry_get_path "$REGISTRY_FILE" "$skill_id" || true)"
  if [[ -z "$skill_path" ]]; then
    skill_path="skills/$skill_id"
  fi

  skill_root="$REPO_ROOT/$skill_path"
  skill_md="$skill_root/SKILL.md"
  openai_yaml="$skill_root/agents/openai.yaml"

  if [[ ! -d "$skill_root" ]]; then
    fail "$skill_id missing skill directory: $skill_path"
    continue
  fi

  if [[ "$skill_path" != skills/* ]]; then
    fail "$skill_id enabled package must live under skills/: $skill_path"
  fi

  if [[ ! -f "$skill_md" ]]; then
    fail "$skill_id missing SKILL.md"
  elif ! awk '
    BEGIN { in_fm = 0; seen_name = 0; seen_description = 0; end_count = 0 }
    NR == 1 && $0 == "---" { in_fm = 1; next }
    in_fm && $0 == "---" { end_count = 1; exit }
    in_fm && /^name:[[:space:]]*/ { seen_name = 1 }
    in_fm && /^description:[[:space:]]*/ { seen_description = 1 }
    END { exit !(end_count && seen_name && seen_description) }
  ' "$skill_md"; then
    fail "$skill_id SKILL.md frontmatter must include name and description"
  else
    ok "$skill_id SKILL.md frontmatter"
  fi

  if [[ ! -f "$openai_yaml" ]]; then
    fail "$skill_id missing agents/openai.yaml"
  else
    ok "$skill_id agents/openai.yaml"
  fi
done < <(registry_list_ids "$REGISTRY_FILE")

if [[ "$failures" -ne 0 ]]; then
  echo "Codex package validation failed with $failures issue(s)" >&2
  exit 1
fi

echo "Codex package validation passed"
