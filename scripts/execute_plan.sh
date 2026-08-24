#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_RUN_AGENT_SCRIPT="$REPO_ROOT/scripts/run_agent.sh"
DEFAULT_REGISTRY_FILE="$REPO_ROOT/registry/skills.yaml"
source "$REPO_ROOT/scripts/lib_registry.sh"

usage() {
  cat <<'EOF_USAGE'
Usage: execute_plan.sh [options]

Build and execute an s2f agent plan.

By default this command runs in dry-run mode and only prints what would execute.

Options:
  --query TEXT          Query to plan/execute. If omitted, read from stdin.
  --task TASK           Optional task hint.
  --run                 Execute runnable steps.
  --dry-run             Dry-run mode (default).
  --format FMT          Output format: text or json. Default: text
  --agent FILE          Path to run_agent.sh. Default: <repo>/scripts/run_agent.sh
  --include-disabled    Include disabled skills in upstream routing.
  -h, --help            Show this help message.
EOF_USAGE
}

json_escape() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

trim_text() {
  printf '%s' "$1" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//'
}

normalize_text() {
  printf '%s' "$1" | tr '\n' ' ' | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//'
}

in_csv_list() {
  local value="${1:-}"
  local csv="${2:-}"
  local -a arr=()
  local item
  if [[ -z "$value" || -z "$csv" ]]; then
    return 1
  fi
  IFS=',' read -r -a arr <<<"$csv"
  for item in "${arr[@]}"; do
    if [[ "$item" == "$value" ]]; then
      return 0
    fi
  done
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

extract_decision() {
  local json="$1"
  printf '%s\n' "$json" | sed -n 's/.*"decision":"\([^"]*\)".*/\1/p'
}

extract_clarify_question() {
  local json="$1"
  if printf '%s\n' "$json" | grep -q '"clarify_question":null'; then
    printf '\n'
    return 0
  fi
  printf '%s\n' "$json" | sed -n 's/.*"clarify_question":"\([^"]*\)".*/\1/p' | sed 's/\\"/"/g'
}

extract_primary_skill() {
  local json="$1"
  if printf '%s\n' "$json" | grep -q '"primary_skill":null'; then
    printf '\n'
    return 0
  fi
  printf '%s\n' "$json" | sed -n 's/.*"primary_skill":"\([^"]*\)".*/\1/p' | sed 's/\\"/"/g'
}

extract_skill_metadata_path() {
  local json="$1"
  if printf '%s\n' "$json" | grep -q '"skill_metadata":null'; then
    printf '\n'
    return 0
  fi
  printf '%s\n' "$json" | sed -n 's/.*"skill_metadata":"\([^"]*\)".*/\1/p' | sed 's/\\"/"/g'
}

extract_plan_scalar() {
  local json="$1"
  local field="$2"
  printf '%s\n' "$json" | sed -n "s/.*\"plan\":{.*\"$field\":\"\([^\"]*\)\".*/\1/p" | sed 's/\\"/"/g'
}

extract_plan_array_csv() {
  local json="$1"
  local field="$2"
  local raw
  raw="$(printf '%s\n' "$json" | sed -n "s/.*\"plan\":{.*\"$field\":\[\([^]]*\)\].*/\1/p")"
  if [[ -z "$raw" ]]; then
    printf '\n'
    return 0
  fi
  printf '%s\n' "$raw" | sed 's/^"//; s/"$//' | sed 's/","/\n/g' | sed 's/\\"/"/g' | paste -sd ',' -
}

csv_to_lines() {
  local csv="${1:-}"
  if [[ -z "$csv" ]]; then
    return 0
  fi
  printf '%s\n' "$csv" | tr ',' '\n'
}

emit_json_array_from_csv() {
  local csv="${1:-}"
  local first=1
  local item
  printf '['
  while IFS= read -r item; do
    [[ -z "$item" ]] && continue
    if [[ "$first" -eq 0 ]]; then
      printf ','
    fi
    printf '"%s"' "$(json_escape "$item")"
    first=0
  done < <(csv_to_lines "$csv")
  printf ']'
}

resolve_skill_metadata_path() {
  local path_from_agent="${1:-}"
  local primary_skill="${2:-}"
  local registry_file="$DEFAULT_REGISTRY_FILE"
  local resolved=""
  local skill_rel=""

  if [[ -n "$path_from_agent" ]]; then
    resolved="$path_from_agent"
    if [[ "$resolved" != /* ]]; then
      resolved="$REPO_ROOT/$resolved"
    fi
    if [[ -f "$resolved" ]]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  fi

  if [[ -n "$primary_skill" && -f "$registry_file" ]]; then
    skill_rel="$(registry_get_path "$registry_file" "$primary_skill" || true)"
    if [[ -n "$skill_rel" ]]; then
      resolved="$REPO_ROOT/$skill_rel/skill.yaml"
      if [[ -f "$resolved" ]]; then
        printf '%s\n' "$resolved"
        return 0
      fi
    fi
  fi

  printf '\n'
}

dotenv_var_has_value() {
  local dotenv_file="$1"
  local var_name="$2"
  local line=""
  local value=""

  [[ -f "$dotenv_file" ]] || return 1
  line="$(grep -E "^[[:space:]]*${var_name}[[:space:]]*=" "$dotenv_file" | head -n 1 || true)"
  [[ -n "$line" ]] || return 1

  value="${line#*=}"
  value="$(trim_text "$value")"

  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value#\"}"
    value="${value%\"}"
  elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
    value="${value#\'}"
    value="${value%\'}"
  fi

  [[ -n "$value" ]]
}

env_var_visible() {
  local var_name="$1"
  local dotenv_file="$2"
  local v=""
  v="${!var_name-}"
  if [[ -n "$v" ]]; then
    return 0
  fi
  if dotenv_var_has_value "$dotenv_file" "$var_name"; then
    return 0
  fi
  return 1
}

emit_text_env_precheck() {
  local skill_name="$1"
  local status="$2"
  local missing_required_csv="$3"
  local missing_any_csv="$4"
  local source_summary="$5"
  local item

  echo "env_precheck:"
  echo "  skill: ${skill_name:-unknown}"
  echo "  status: ${status:-unknown}"
  echo "  source_summary: ${source_summary:-process_env_only}"
  echo "  missing_required:"
  if [[ -n "$missing_required_csv" ]]; then
    while IFS= read -r item; do
      [[ -z "$item" ]] && continue
      echo "    - $item"
    done < <(csv_to_lines "$missing_required_csv")
  else
    echo "    - none"
  fi
  echo "  missing_any_groups:"
  if [[ -n "$missing_any_csv" ]]; then
    while IFS= read -r item; do
      [[ -z "$item" ]] && continue
      echo "    - $item"
    done < <(csv_to_lines "$missing_any_csv")
  else
    echo "    - none"
  fi
}

is_command_fallback() {
  local item="${1:-}"
  [[ -z "$item" ]] && return 1
  [[ "$item" == *";"* ]] && return 0
  [[ "$item" == *"|"* ]] && return 0
  [[ "$item" == *" conda run "* ]] && return 0
  [[ "$item" == conda\ run* ]] && return 0
  [[ "$item" == bash\ * ]] && return 0
  [[ "$item" == python\ * ]] && return 0
  [[ "$item" == set\ * ]] && return 0
  return 1
}

path_matches_hint() {
  local hint="${1:-}"
  local check_a="${2:-}"
  local check_b="${3:-}"
  if [[ -z "$hint" ]]; then
    return 1
  fi

  # If glob chars are present, use shell glob matching against all three candidates.
  if [[ "$hint" == *"*"* || "$hint" == *"?"* || "$hint" == *"["* ]]; then
    if compgen -G "$hint" >/dev/null 2>&1; then
      return 0
    fi
    if compgen -G "$check_a" >/dev/null 2>&1; then
      return 0
    fi
    if compgen -G "$check_b" >/dev/null 2>&1; then
      return 0
    fi
    return 1
  fi

  [[ -e "$hint" || -e "$check_a" || -e "$check_b" ]]
}

query=""
task=""
dry_run=1
format="text"
agent_script="$DEFAULT_RUN_AGENT_SCRIPT"
include_disabled=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --query)
      query="$2"
      shift 2
      ;;
    --task)
      task="$2"
      shift 2
      ;;
    --run)
      dry_run=0
      shift
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --format)
      format="$2"
      shift 2
      ;;
    --agent)
      agent_script="$2"
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

if [[ -z "$query" && ! -t 0 ]]; then
  query="$(cat)"
fi
query="$(normalize_text "$query")"

if [[ -z "$query" ]]; then
  echo "error: query is required (use --query or stdin)." >&2
  exit 1
fi

if [[ "$format" != "text" && "$format" != "json" ]]; then
  echo "error: --format must be 'text' or 'json'." >&2
  exit 1
fi

if [[ ! -f "$agent_script" ]]; then
  echo "error: run_agent script not found: $agent_script" >&2
  exit 1
fi

agent_cmd=(bash "$agent_script" --query "$query" --format json)
if [[ -n "$task" ]]; then
  agent_cmd+=(--task "$task")
fi
if [[ "$include_disabled" -eq 1 ]]; then
  agent_cmd+=(--include-disabled)
fi

agent_json=""
if ! agent_json="$("${agent_cmd[@]}" 2>&1)"; then
  echo "error: run_agent failed: $agent_json" >&2
  exit 1
fi

decision="$(extract_decision "$agent_json")"
if [[ "$decision" == "clarify" ]]; then
  question="$(extract_clarify_question "$agent_json")"
  if [[ "$format" == "text" ]]; then
    echo "decision: clarify"
    echo "clarify_question: ${question:-Please clarify task and inputs.}"
  else
    printf '{"decision":"clarify","clarify_question":"%s","env_precheck":null}\n' "$(json_escape "${question:-Please clarify task and inputs.}")"
  fi
  exit 2
fi

plan_task="$(extract_plan_scalar "$agent_json" "task")"
selected_skill="$(extract_plan_scalar "$agent_json" "selected_skill")"
primary_skill="$(extract_primary_skill "$agent_json")"
skill_meta_from_agent="$(extract_skill_metadata_path "$agent_json")"
if [[ -z "$primary_skill" ]]; then
  primary_skill="$selected_skill"
fi
retry_policy="$(extract_plan_scalar "$agent_json" "retry_policy")"
steps_csv="$(extract_plan_array_csv "$agent_json" "runnable_steps")"
outputs_csv="$(extract_plan_array_csv "$agent_json" "expected_outputs")"
fallbacks_csv="$(extract_plan_array_csv "$agent_json" "fallbacks")"
skill_meta_path="$(resolve_skill_metadata_path "$skill_meta_from_agent" "$primary_skill")"
dotenv_file="$REPO_ROOT/.env"
required_env_csv=""
optional_env_csv=""
required_env_any_csv=""
missing_required_env_csv=""
missing_required_any_csv=""
env_precheck_status="not_configured"
env_precheck_skill="${primary_skill:-${selected_skill:-unknown}}"
env_precheck_source_summary="process_env_only"

if [[ -f "$dotenv_file" ]]; then
  env_precheck_source_summary="process_env_plus_repo_dotenv_fallback"
fi

if [[ -n "$skill_meta_path" && -f "$skill_meta_path" ]]; then
  while IFS= read -r v; do
    [[ -n "$v" ]] && required_env_csv="$(append_csv "$required_env_csv" "$v")"
  done < <(yaml_get_list_field "$skill_meta_path" "required_env")
  while IFS= read -r v; do
    [[ -n "$v" ]] && optional_env_csv="$(append_csv "$optional_env_csv" "$v")"
  done < <(yaml_get_list_field "$skill_meta_path" "optional_env")
  while IFS= read -r v; do
    [[ -n "$v" ]] && required_env_any_csv="$(append_csv "$required_env_any_csv" "$v")"
  done < <(yaml_get_list_field "$skill_meta_path" "required_env_any")
fi

if [[ -n "$required_env_csv" || -n "$required_env_any_csv" || -n "$optional_env_csv" ]]; then
  env_precheck_status="pass"

  while IFS= read -r var_name; do
    [[ -z "$var_name" ]] && continue
    if ! env_var_visible "$var_name" "$dotenv_file"; then
      missing_required_env_csv="$(append_csv "$missing_required_env_csv" "$var_name")"
    fi
  done < <(csv_to_lines "$required_env_csv")

  while IFS= read -r group; do
    [[ -z "$group" ]] && continue
    group_ok=0
    IFS='|' read -r -a group_vars <<<"$group"
    for var_name in "${group_vars[@]}"; do
      var_name="$(trim_text "$var_name")"
      [[ -z "$var_name" ]] && continue
      if env_var_visible "$var_name" "$dotenv_file"; then
        group_ok=1
        break
      fi
    done
    if [[ "$group_ok" -eq 0 ]]; then
      missing_required_any_csv="$(append_csv "$missing_required_any_csv" "$group")"
    fi
  done < <(csv_to_lines "$required_env_any_csv")

  if [[ -n "$missing_required_env_csv" || -n "$missing_required_any_csv" ]]; then
    env_precheck_status="fail"
  fi
fi

if [[ -z "$steps_csv" ]]; then
  echo "error: plan has no runnable steps" >&2
  exit 1
fi

executed=0
failed=0
verified=0
verify_failed=0
fallback_attempted=0
fallback_succeeded=0

if [[ "$format" == "text" ]]; then
  echo "task: ${plan_task:-unknown}"
  echo "selected_skill: ${selected_skill:-unknown}"
  echo "retry_policy: ${retry_policy:-none}"
  emit_text_env_precheck \
    "$env_precheck_skill" \
    "$env_precheck_status" \
    "$missing_required_env_csv" \
    "$missing_required_any_csv" \
    "$env_precheck_source_summary"
fi

if [[ "$dry_run" -eq 0 && "$env_precheck_status" == "fail" ]]; then
  echo "error: env precheck failed for skill '$env_precheck_skill'" >&2
  if [[ "$format" == "text" ]]; then
    if [[ -n "$missing_required_env_csv" ]]; then
      echo "error: missing required env vars: $missing_required_env_csv" >&2
    fi
    if [[ -n "$missing_required_any_csv" ]]; then
      echo "error: missing required any-of env groups: $missing_required_any_csv" >&2
    fi
  fi
  exit 1
fi

while IFS= read -r step; do
  [[ -z "$step" ]] && continue
  if [[ "$dry_run" -eq 1 ]]; then
    if [[ "$format" == "text" ]]; then
      echo "dry-run step: $step"
    fi
    continue
  fi

  if [[ "$format" == "text" ]]; then
    echo "run step: $step"
  fi
  if bash -o pipefail -lc "$step"; then
    executed=$((executed + 1))
  else
    step_recovered=0
    if [[ "$dry_run" -eq 0 && -n "$fallbacks_csv" ]]; then
      while IFS= read -r fallback; do
        [[ -z "$fallback" ]] && continue
        if ! is_command_fallback "$fallback"; then
          continue
        fi
        fallback_attempted=$((fallback_attempted + 1))
        if [[ "$format" == "text" ]]; then
          echo "run fallback: $fallback"
        fi
        if bash -o pipefail -lc "$fallback"; then
          fallback_succeeded=$((fallback_succeeded + 1))
          executed=$((executed + 1))
          step_recovered=1
          break
        fi
      done < <(csv_to_lines "$fallbacks_csv")
    fi

    if [[ "$step_recovered" -eq 0 ]]; then
      failed=$((failed + 1))
      if [[ "$format" == "text" ]]; then
        echo "step failed: $step" >&2
      fi
    fi
  fi
done < <(csv_to_lines "$steps_csv")

while IFS= read -r item; do
  [[ -z "$item" ]] && continue
  case "$item" in
    expected-file:*|expected-plot:*)
      path_hint="${item#*:}"
      check_a="$REPO_ROOT/$path_hint"
      check_b="$REPO_ROOT/output/$path_hint"
      if [[ "$dry_run" -eq 1 ]]; then
        if [[ "$format" == "text" ]]; then
          echo "dry-run verify: $item"
        fi
        continue
      fi
      if [[ "$failed" -ne 0 ]]; then
        verify_failed=$((verify_failed + 1))
        if [[ "$format" == "text" ]]; then
          echo "verify skipped after execution failure: $item" >&2
        fi
        continue
      fi
      if path_matches_hint "$path_hint" "$check_a" "$check_b"; then
        verified=$((verified + 1))
      else
        verify_failed=$((verify_failed + 1))
        if [[ "$format" == "text" ]]; then
          echo "verify failed: $item" >&2
        fi
      fi
      ;;
    *)
      if [[ "$format" == "text" ]]; then
        echo "note output contract: $item"
      fi
      ;;
  esac
done < <(csv_to_lines "$outputs_csv")

if [[ "$format" == "text" ]]; then
  echo "fallbacks: ${fallbacks_csv:-none}"
  echo "summary: dry_run=$dry_run executed=$executed failed=$failed verified=$verified verify_failed=$verify_failed fallback_attempted=$fallback_attempted fallback_succeeded=$fallback_succeeded"
else
  printf '{'
  printf '"decision":"route",'
  printf '"dry_run":%s,' "$([[ "$dry_run" -eq 1 ]] && echo true || echo false)"
  printf '"task":"%s",' "$(json_escape "${plan_task:-unknown}")"
  printf '"selected_skill":"%s",' "$(json_escape "${selected_skill:-unknown}")"
  printf '"retry_policy":"%s",' "$(json_escape "${retry_policy:-none}")"
  printf '"runnable_steps":"%s",' "$(json_escape "$steps_csv")"
  printf '"expected_outputs":"%s",' "$(json_escape "$outputs_csv")"
  printf '"fallbacks":"%s",' "$(json_escape "${fallbacks_csv:-}")"
  printf '"executed":%s,' "$executed"
  printf '"failed":%s,' "$failed"
  printf '"verified":%s,' "$verified"
  printf '"verify_failed":%s,' "$verify_failed"
  printf '"fallback_attempted":%s,' "$fallback_attempted"
  printf '"fallback_succeeded":%s,' "$fallback_succeeded"
  printf '"env_precheck":{'
  printf '"skill":"%s",' "$(json_escape "${env_precheck_skill:-unknown}")"
  printf '"status":"%s",' "$(json_escape "${env_precheck_status:-unknown}")"
  printf '"missing_required":'
  emit_json_array_from_csv "$missing_required_env_csv"
  printf ','
  printf '"missing_any_groups":'
  emit_json_array_from_csv "$missing_required_any_csv"
  printf ','
  printf '"source_summary":"%s"' "$(json_escape "${env_precheck_source_summary:-process_env_only}")"
  printf '}'
  printf '}\n'
fi

if [[ "$failed" -ne 0 || "$verify_failed" -ne 0 ]]; then
  exit 1
fi
