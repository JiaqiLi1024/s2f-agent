#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_REGISTRY_FILE="$REPO_ROOT/registry/skills.yaml"
DEFAULT_CONTRACTS_FILE="$REPO_ROOT/registry/task_contracts.yaml"
DEFAULT_INPUT_SCHEMA_FILE="$REPO_ROOT/registry/input_schema.yaml"
source "$REPO_ROOT/scripts/lib_registry.sh"

usage() {
  cat <<'EOF_USAGE'
Usage: validate_input_contracts.sh [options]

Validate canonical input contracts across task contracts, skill metadata, and input schema.

Options:
  --registry FILE      Skill registry file. Default: <repo>/registry/skills.yaml
  --contracts FILE     Task contracts file. Default: <repo>/registry/task_contracts.yaml
  --input-schema FILE  Canonical input schema file. Default: <repo>/registry/input_schema.yaml
  --include-disabled   Include disabled skills in registry scan.
  -h, --help           Show this help message.
EOF_USAGE
}

registry_file="$DEFAULT_REGISTRY_FILE"
contracts_file="$DEFAULT_CONTRACTS_FILE"
input_schema_file="$DEFAULT_INPUT_SCHEMA_FILE"
include_disabled=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry)
      registry_file="$2"
      shift 2
      ;;
    --contracts)
      contracts_file="$2"
      shift 2
      ;;
    --input-schema)
      input_schema_file="$2"
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
registry_require_file "$contracts_file"
registry_require_file "$input_schema_file"

failures=0
warnings=0

in_csv_list() {
  local value="${1:-}"
  local csv="${2:-}"
  local item=""
  if [[ -z "$value" || -z "$csv" ]]; then
    return 1
  fi
  while IFS= read -r item; do
    [[ -z "$item" ]] && continue
    if [[ "$item" == "$value" ]]; then
      return 0
    fi
  done < <(printf '%s\n' "$csv" | tr ',' '\n')
  return 1
}

append_csv() {
  local csv="${1:-}"
  local value="${2:-}"
  if [[ -z "$value" ]]; then
    printf '%s\n' "$csv"
    return 0
  fi
  if in_csv_list "$value" "$csv"; then
    printf '%s\n' "$csv"
    return 0
  fi
  if [[ -z "$csv" ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$csv,$value"
  fi
}

schema_keys_csv=""
while IFS= read -r k; do
  [[ -z "$k" ]] && continue
  schema_keys_csv="$(append_csv "$schema_keys_csv" "$k")"
done < <(input_schema_list_keys "$input_schema_file")

if [[ -z "$schema_keys_csv" ]]; then
  echo "fail: input schema has no declared keys ($input_schema_file)" >&2
  exit 1
fi

echo "[check] task contracts vs canonical schema"
while IFS= read -r task_name; do
  [[ -z "$task_name" ]] && continue

  required_csv=""
  canonical_csv=""
  while IFS= read -r v; do
    [[ -n "$v" ]] && required_csv="$(append_csv "$required_csv" "$v")"
  done < <(task_contract_list_required_inputs "$contracts_file" "$task_name")

  while IFS= read -r v; do
    [[ -n "$v" ]] && canonical_csv="$(append_csv "$canonical_csv" "$v")"
  done < <(task_contract_list_canonical_required_inputs "$contracts_file" "$task_name")

  if [[ -z "$required_csv" ]]; then
    echo "fail: task '$task_name' missing required_inputs" >&2
    failures=$((failures + 1))
    continue
  fi

  if [[ -z "$canonical_csv" ]]; then
    echo "fail: task '$task_name' missing canonical_required_inputs" >&2
    failures=$((failures + 1))
    continue
  fi

  while IFS= read -r req; do
    [[ -z "$req" ]] && continue
    resolved="$(input_schema_resolve_key "$input_schema_file" "$req" || true)"
    if [[ -z "$resolved" ]]; then
      echo "fail: task '$task_name' required input '$req' not resolvable in input schema" >&2
      failures=$((failures + 1))
    fi
  done < <(printf '%s\n' "$required_csv" | tr ',' '\n')

  while IFS= read -r req; do
    [[ -z "$req" ]] && continue
    if ! in_csv_list "$req" "$schema_keys_csv"; then
      echo "fail: task '$task_name' canonical input '$req' missing from input schema keys" >&2
      failures=$((failures + 1))
    fi
  done < <(printf '%s\n' "$canonical_csv" | tr ',' '\n')

done < <(
  awk '
    /^[[:space:]]*contracts:[[:space:]]*$/ {in_contracts=1; next}
    in_contracts && /^[[:space:]][[:space:]][a-zA-Z0-9_-]+:[[:space:]]*$/ {
      t=$0
      sub(/^[[:space:]][[:space:]]/, "", t)
      sub(/:[[:space:]]*$/, "", t)
      print t
      next
    }
    in_contracts && /^[^[:space:]]/ {in_contracts=0; next}
  ' "$contracts_file"
)

echo "[check] stable skills vs canonical schema"
total_skills=0
while IFS= read -r skill_id; do
  [[ -z "$skill_id" ]] && continue

  skill_path="$(registry_get_path "$registry_file" "$skill_id" || true)"
  [[ -z "$skill_path" ]] && skill_path="$skill_id"

  if [[ "$skill_path" != skills/* ]]; then
    continue
  fi

  total_skills=$((total_skills + 1))
  skill_meta="$REPO_ROOT/$skill_path/skill.yaml"

  if [[ ! -f "$skill_meta" ]]; then
    echo "fail: stable skill '$skill_id' missing skill.yaml" >&2
    failures=$((failures + 1))
    continue
  fi

  if ! grep -q '^input_mappings:' "$skill_meta"; then
    echo "fail: stable skill '$skill_id' missing input_mappings field" >&2
    failures=$((failures + 1))
    continue
  fi

  required_csv=""
  optional_csv=""
  while IFS= read -r v; do
    [[ -n "$v" ]] && required_csv="$(append_csv "$required_csv" "$v")"
  done < <(yaml_get_list_field "$skill_meta" "required_inputs")
  while IFS= read -r v; do
    [[ -n "$v" ]] && optional_csv="$(append_csv "$optional_csv" "$v")"
  done < <(yaml_get_list_field "$skill_meta" "optional_inputs")

  while IFS= read -r key_name; do
    [[ -z "$key_name" ]] && continue
    resolved="$(input_schema_resolve_key "$input_schema_file" "$key_name" || true)"
    if [[ -z "$resolved" ]]; then
      echo "fail: stable skill '$skill_id' input key '$key_name' not resolvable in input schema" >&2
      failures=$((failures + 1))
    fi
  done < <(printf '%s\n%s\n' "$required_csv" "$optional_csv" | tr ',' '\n')

  mappings_csv=""
  while IFS= read -r mapping; do
    [[ -z "$mapping" ]] && continue
    map_key="${mapping%%|*}"
    mappings_csv="$(append_csv "$mappings_csv" "$map_key")"

    if [[ "$mapping" != *"query_tokens="* ]]; then
      echo "fail: stable skill '$skill_id' mapping '$mapping' missing query_tokens= segment" >&2
      failures=$((failures + 1))
    fi
    if [[ "$mapping" != *"script_flags="* ]]; then
      echo "fail: stable skill '$skill_id' mapping '$mapping' missing script_flags= segment" >&2
      failures=$((failures + 1))
    fi

    resolved="$(input_schema_resolve_key "$input_schema_file" "$map_key" || true)"
    if [[ -z "$resolved" ]]; then
      echo "fail: stable skill '$skill_id' mapping key '$map_key' not resolvable in input schema" >&2
      failures=$((failures + 1))
    fi
  done < <(yaml_get_list_field "$skill_meta" "input_mappings")

  # P1: warn if coordinate/interval mappings lack coordinate system annotation
  coord_constraints_raw=""
  while IFS= read -r c; do
    [[ -n "$c" ]] && coord_constraints_raw="$coord_constraints_raw $c"
  done < <(yaml_get_list_field "$skill_meta" "constraints")

  while IFS= read -r mapping; do
    [[ -z "$mapping" ]] && continue
    map_key="${mapping%%|*}"
    if [[ "$map_key" == "coordinate-or-interval" || "$map_key" == "sequence-or-interval" ]]; then
      if [[ "$mapping" != *"coord_system="* ]]; then
        if ! printf '%s' "$coord_constraints_raw" | grep -qi "based"; then
          echo "warn: stable skill '$skill_id' mapping '$map_key' missing coordinate system annotation (add coord_system= to mapping or a 'based' constraint)" >&2
          warnings=$((warnings + 1))
        fi
      fi
    fi
  done < <(yaml_get_list_field "$skill_meta" "input_mappings")

  tools_count=0
  while IFS= read -r _tool; do
    [[ -n "$_tool" ]] && tools_count=$((tools_count + 1))
  done < <(yaml_get_list_field "$skill_meta" "tools")

  if [[ "$tools_count" -gt 0 ]]; then
    while IFS= read -r key_name; do
      [[ -z "$key_name" ]] && continue
      if ! in_csv_list "$key_name" "$mappings_csv"; then
        echo "warn: stable skill '$skill_id' required input '$key_name' has no explicit mapping entry" >&2
        warnings=$((warnings + 1))
      fi
    done < <(printf '%s\n' "$required_csv" | tr ',' '\n')
  fi

done < <(registry_list_ids_filtered "$registry_file" "$include_disabled")

if [[ "$total_skills" -eq 0 ]]; then
  echo "fail: no stable skills discovered from registry" >&2
  exit 1
fi

if [[ "$failures" -ne 0 ]]; then
  echo "input contract validation failed with $failures issue(s) and $warnings warning(s)" >&2
  exit 1
fi

echo "input contract validation passed for $total_skills stable skill(s) with $warnings warning(s)"
