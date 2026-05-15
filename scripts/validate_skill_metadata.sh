#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_REGISTRY_FILE="$REPO_ROOT/registry/skills.yaml"
DEFAULT_TAGS_FILE="$REPO_ROOT/registry/tags.yaml"
source "$REPO_ROOT/scripts/lib_registry.sh"

usage() {
  cat <<'EOF'
Usage: validate_skill_metadata.sh [options]

Validate skill-level metadata completeness and consistency with registry entries.

Options:
  --registry FILE    Skill registry file. Default: <repo>/registry/skills.yaml
  --tags FILE        Task tag registry file. Default: <repo>/registry/tags.yaml
  --include-disabled Include disabled skills from registry.
  -h, --help         Show this help message.
EOF
}

registry_file="$DEFAULT_REGISTRY_FILE"
tags_file="$DEFAULT_TAGS_FILE"
include_disabled=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry)
      registry_file="$2"
      shift 2
      ;;
    --tags)
      tags_file="$2"
      shift 2
      ;;
    --include-disabled)
      include_disabled=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unexpected argument '$1'" >&2
      usage >&2
      exit 1
      ;;
  esac
done

registry_require_file "$registry_file"
registry_require_file "$tags_file"

failures=0
warnings=0
total=0

all_tasks_csv=""
while IFS= read -r t; do
  [[ -z "$t" ]] && continue
  if [[ -z "$all_tasks_csv" ]]; then
    all_tasks_csv="$t"
  else
    all_tasks_csv="$all_tasks_csv,$t"
  fi
done < <(tag_registry_list_tasks "$tags_file")

in_csv_list() {
  local value="${1:-}"
  local csv="${2:-}"
  if [[ -z "$value" || -z "$csv" ]]; then
    return 1
  fi
  local -a arr=()
  IFS=',' read -r -a arr <<<"$csv"
  if [[ ${#arr[@]} -eq 0 ]]; then
    return 1
  fi
  for item in "${arr[@]}"; do
    if [[ "$item" == "$value" ]]; then
      return 0
    fi
  done
  return 1
}

count_list_items() {
  local file="$1"
  local key="$2"
  local c=0
  while IFS= read -r _v; do
    [[ -n "$_v" ]] && c=$((c + 1))
  done < <(yaml_get_list_field "$file" "$key")
  printf '%s\n' "$c"
}

required_scalar_fields=(
  "schema_version"
  "id"
  "title"
  "path"
  "status"
  "family"
)

required_list_fields=(
  "tasks"
  "triggers"
  "required_inputs"
  "constraints"
  "priority_rules"
)

for skill_id in $(registry_list_ids_filtered "$registry_file" "$include_disabled"); do
  [[ -z "$skill_id" ]] && continue
  total=$((total + 1))

  skill_path="$(registry_get_path "$registry_file" "$skill_id" || true)"
  if [[ -z "$skill_path" ]]; then
    skill_path="$skill_id"
  fi
  skill_root="$REPO_ROOT/$skill_path"
  skill_meta="$skill_root/skill.yaml"

  if [[ ! -f "$skill_meta" ]]; then
    echo "fail: $skill_id missing skill metadata ($skill_meta)" >&2
    failures=$((failures + 1))
    continue
  fi

  ok=1

  for key in "${required_scalar_fields[@]}"; do
    value="$(yaml_get_scalar_field "$skill_meta" "$key" || true)"
    if [[ -z "$value" ]]; then
      echo "fail: $skill_id missing scalar field '$key' in $skill_meta" >&2
      failures=$((failures + 1))
      ok=0
    fi
  done

  for key in "${required_list_fields[@]}"; do
    count="$(count_list_items "$skill_meta" "$key")"
    if [[ "$count" -le 0 ]]; then
      echo "fail: $skill_id requires non-empty list '$key' in $skill_meta" >&2
      failures=$((failures + 1))
      ok=0
    fi
  done

  if ! grep -q '^tool_contracts:' "$skill_meta"; then
    echo "fail: $skill_id missing 'tool_contracts' field in $skill_meta" >&2
    failures=$((failures + 1))
    ok=0
  fi

  tools_count="$(count_list_items "$skill_meta" "tools")"
  tool_contracts_count="$(count_list_items "$skill_meta" "tool_contracts")"
  if [[ "$tools_count" -gt 0 && "$tool_contracts_count" -le 0 ]]; then
    echo "fail: $skill_id has tools but no tool_contracts entries in $skill_meta" >&2
    failures=$((failures + 1))
    ok=0
  fi

  meta_id="$(yaml_get_scalar_field "$skill_meta" "id" || true)"
  meta_path="$(yaml_get_scalar_field "$skill_meta" "path" || true)"
  meta_status="$(yaml_get_scalar_field "$skill_meta" "status" || true)"

  if [[ -n "$meta_id" && "$meta_id" != "$skill_id" ]]; then
    echo "fail: $skill_id skill.yaml id mismatch (got '$meta_id')" >&2
    failures=$((failures + 1))
    ok=0
  fi

  if [[ -n "$meta_path" && "$meta_path" != "$skill_path" ]]; then
    echo "fail: $skill_id skill.yaml path mismatch (got '$meta_path', expected '$skill_path')" >&2
    failures=$((failures + 1))
    ok=0
  fi

  if [[ -n "$meta_status" && "$meta_status" != "active" && "$meta_status" != "inactive" ]]; then
    echo "fail: $skill_id has invalid status '$meta_status' (expected active|inactive)" >&2
    failures=$((failures + 1))
    ok=0
  fi

  while IFS= read -r t; do
    [[ -z "$t" ]] && continue
    if ! in_csv_list "$t" "$all_tasks_csv"; then
      echo "warn: $skill_id task '$t' is not registered in registry/tags.yaml" >&2
      warnings=$((warnings + 1))
    fi
  done < <(yaml_get_list_field "$skill_meta" "tasks")

  if [[ "$ok" -eq 1 ]]; then
    echo "ok: $skill_id metadata"
  fi
done

if [[ "$total" -eq 0 ]]; then
  echo "fail: no skills discovered from registry ($registry_file)" >&2
  exit 1
fi

if [[ "$failures" -ne 0 ]]; then
  echo "skill metadata validation failed with $failures issue(s) and $warnings warning(s)" >&2
  exit 1
fi

echo "skill metadata validation passed for $total skill(s) with $warnings warning(s)"
