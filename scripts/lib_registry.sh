#!/usr/bin/env bash
set -euo pipefail

registry_require_file() {
  local registry_file="$1"
  if [[ ! -f "$registry_file" ]]; then
    echo "error: registry file not found: $registry_file" >&2
    return 1
  fi
}

yaml_get_scalar_field() {
  local yaml_file="$1"
  local field_name="$2"
  registry_require_file "$yaml_file"
  awk -v field="$field_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    $0 ~ ("^[[:space:]]*" field ":[[:space:]]*") {
      v = $0
      sub("^[[:space:]]*" field ":[[:space:]]*", "", v)
      v = cleaned(v)
      print v
      exit
    }
  ' "$yaml_file"
}

yaml_get_list_field() {
  local yaml_file="$1"
  local field_name="$2"
  registry_require_file "$yaml_file"
  awk -v field="$field_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    $0 ~ ("^[[:space:]]*" field ":[[:space:]]*$") {
      in_list = 1
      next
    }
    in_list && /^[[:space:]]*-[[:space:]]*/ {
      item = $0
      sub(/^[[:space:]]*-[[:space:]]*/, "", item)
      item = cleaned(item)
      if (item != "") {
        print item
      }
      next
    }
    in_list && /^[[:space:]]*[a-zA-Z0-9_-]+:[[:space:]]*/ {
      in_list = 0
      next
    }
  ' "$yaml_file"
}

registry_list_ids() {
  local registry_file="$1"
  registry_require_file "$registry_file"
  awk '
    /^[[:space:]]*-[[:space:]]id:[[:space:]]*/ {
      id = $0
      sub(/^[[:space:]]*-[[:space:]]id:[[:space:]]*/, "", id)
      gsub(/"/, "", id)
      print id
    }
  ' "$registry_file"
}

registry_get_path() {
  local registry_file="$1"
  local target_id="$2"
  registry_require_file "$registry_file"
  awk -v target="$target_id" '
    /^[[:space:]]*-[[:space:]]id:[[:space:]]*/ {
      current = $0
      sub(/^[[:space:]]*-[[:space:]]id:[[:space:]]*/, "", current)
      gsub(/"/, "", current)
      in_block = (current == target)
      next
    }
    in_block && /^[[:space:]]*path:[[:space:]]*/ {
      p = $0
      sub(/^[[:space:]]*path:[[:space:]]*/, "", p)
      gsub(/"/, "", p)
      print p
      exit
    }
  ' "$registry_file"
}

registry_get_scalar_field() {
  local registry_file="$1"
  local target_id="$2"
  local field_name="$3"
  registry_require_file "$registry_file"
  awk -v target="$target_id" -v field="$field_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*-[[:space:]]id:[[:space:]]*/ {
      current = $0
      sub(/^[[:space:]]*-[[:space:]]id:[[:space:]]*/, "", current)
      current = cleaned(current)
      in_block = (current == target)
      next
    }
    in_block && $0 ~ ("^[[:space:]]*" field ":[[:space:]]*") {
      v = $0
      sub("^[[:space:]]*" field ":[[:space:]]*", "", v)
      v = cleaned(v)
      print v
      exit
    }
  ' "$registry_file"
}

registry_skill_enabled() {
  local registry_file="$1"
  local target_id="$2"
  local enabled
  enabled="$(registry_get_scalar_field "$registry_file" "$target_id" "enabled" || true)"
  if [[ -z "$enabled" || "$enabled" == "true" ]]; then
    return 0
  fi
  return 1
}

registry_list_ids_filtered() {
  local registry_file="$1"
  local include_disabled="${2:-0}"
  local skill_id
  while IFS= read -r skill_id; do
    [[ -z "$skill_id" ]] && continue
    if [[ "$include_disabled" == "1" ]]; then
      echo "$skill_id"
      continue
    fi
    if registry_skill_enabled "$registry_file" "$skill_id"; then
      echo "$skill_id"
    fi
  done < <(registry_list_ids "$registry_file")
}

registry_get_list_field() {
  local registry_file="$1"
  local target_id="$2"
  local field_name="$3"
  registry_require_file "$registry_file"
  awk -v target="$target_id" -v field="$field_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*-[[:space:]]id:[[:space:]]*/ {
      current = $0
      sub(/^[[:space:]]*-[[:space:]]id:[[:space:]]*/, "", current)
      current = cleaned(current)
      in_block = (current == target)
      in_list = 0
      next
    }
    in_block && $0 ~ ("^[[:space:]]*" field ":[[:space:]]*$") {
      in_list = 1
      next
    }
    in_block && in_list && /^[[:space:]]*-[[:space:]]*/ {
      item = $0
      sub(/^[[:space:]]*-[[:space:]]*/, "", item)
      item = cleaned(item)
      if (item != "") {
        print item
      }
      next
    }
    in_block && in_list && /^[[:space:]]*[a-zA-Z0-9_-]+:[[:space:]]*/ {
      in_list = 0
      next
    }
    in_block && in_list && /^[[:space:]]*#[^[:alnum:]]*/ {
      next
    }
  ' "$registry_file"
}

tag_registry_list_for_task() {
  local tags_file="$1"
  local task_name="$2"
  registry_require_file "$tags_file"
  awk -v target="$task_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*[a-zA-Z0-9_-]+:[[:space:]]*$/ {
      key = $0
      sub(/^[[:space:]]*/, "", key)
      sub(/:[[:space:]]*$/, "", key)
      in_task = (key == target)
      next
    }
    in_task && /^[[:space:]]*-[[:space:]]*/ {
      item = $0
      sub(/^[[:space:]]*-[[:space:]]*/, "", item)
      item = cleaned(item)
      if (item != "") {
        print item
      }
      next
    }
    in_task && /^[[:space:]]*[a-zA-Z0-9_-]+:[[:space:]]*$/ {
      in_task = 0
      next
    }
  ' "$tags_file"
}

tag_registry_list_tasks() {
  local tags_file="$1"
  registry_require_file "$tags_file"
  awk '
    /^[[:space:]]*tags:[[:space:]]*$/ {
      in_tags = 1
      next
    }
    in_tags && /^[[:space:]]{2}[a-zA-Z0-9_-]+:[[:space:]]*$/ {
      key = $0
      sub(/^[[:space:]]*/, "", key)
      sub(/:[[:space:]]*$/, "", key)
      print key
      next
    }
    in_tags && /^[^[:space:]]/ {
      in_tags = 0
      next
    }
  ' "$tags_file"
}

task_contract_list_required_inputs() {
  local contracts_file="$1"
  local task_name="$2"
  registry_require_file "$contracts_file"
  awk -v target="$task_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*contracts:[[:space:]]*$/ {
      in_contracts = 1
      next
    }
    in_contracts && $0 ~ ("^[[:space:]]{2}" target ":[[:space:]]*$") {
      in_task = 1
      in_required = 0
      next
    }
    in_contracts && in_task && /^[[:space:]]{2}[a-zA-Z0-9_-]+:[[:space:]]*$/ {
      in_task = 0
      in_required = 0
      next
    }
    in_task && /^[[:space:]]{4}required_inputs:[[:space:]]*$/ {
      in_required = 1
      next
    }
    in_task && in_required && /^[[:space:]]{6}-[[:space:]]*/ {
      item = $0
      sub(/^[[:space:]]{6}-[[:space:]]*/, "", item)
      item = cleaned(item)
      if (item != "") {
        print item
      }
      next
    }
    in_task && in_required && /^[[:space:]]{4}[a-zA-Z0-9_-]+:[[:space:]]*/ {
      in_required = 0
      next
    }
  ' "$contracts_file"
}

task_contract_list_canonical_required_inputs() {
  local contracts_file="$1"
  local task_name="$2"
  registry_require_file "$contracts_file"
  awk -v target="$task_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*contracts:[[:space:]]*$/ {
      in_contracts = 1
      next
    }
    in_contracts && $0 ~ ("^[[:space:]]{2}" target ":[[:space:]]*$") {
      in_task = 1
      in_required = 0
      next
    }
    in_contracts && in_task && /^[[:space:]]{2}[a-zA-Z0-9_-]+:[[:space:]]*$/ {
      in_task = 0
      in_required = 0
      next
    }
    in_task && /^[[:space:]]{4}canonical_required_inputs:[[:space:]]*$/ {
      in_required = 1
      next
    }
    in_task && in_required && /^[[:space:]]{6}-[[:space:]]*/ {
      item = $0
      sub(/^[[:space:]]{6}-[[:space:]]*/, "", item)
      item = cleaned(item)
      if (item != "") {
        print item
      }
      next
    }
    in_task && in_required && /^[[:space:]]{4}[a-zA-Z0-9_-]+:[[:space:]]*/ {
      in_required = 0
      next
    }
  ' "$contracts_file"
}

task_contract_list_any_of_groups() {
  local contracts_file="$1"
  local task_name="$2"
  registry_require_file "$contracts_file"
  awk -v target="$task_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    function emit() {
      if (group_id != "") {
        print group_id "|" description "|" required "|" canonical
        group_id = ""
        description = ""
        required = ""
        canonical = ""
      }
    }
    /^[[:space:]]*contracts:[[:space:]]*$/ {
      in_contracts = 1
      next
    }
    in_contracts && $0 ~ ("^[[:space:]]{2}" target ":[[:space:]]*$") {
      in_task = 1
      in_any = 0
      in_required = 0
      in_canonical = 0
      group_id = ""
      description = ""
      required = ""
      canonical = ""
      next
    }
    in_contracts && in_task && /^[[:space:]]{2}[a-zA-Z0-9_-]+:[[:space:]]*$/ {
      emit()
      in_task = 0
      in_any = 0
      in_required = 0
      in_canonical = 0
      next
    }
    in_task && /^[[:space:]]{4}any_of_required_inputs:[[:space:]]*$/ {
      in_any = 1
      in_required = 0
      in_canonical = 0
      group_id = ""
      description = ""
      required = ""
      canonical = ""
      next
    }
    in_task && in_any && /^[[:space:]]{6}-[[:space:]]id:[[:space:]]*/ {
      emit()
      group_id = $0
      sub(/^[[:space:]]{6}-[[:space:]]id:[[:space:]]*/, "", group_id)
      group_id = cleaned(group_id)
      description = ""
      required = ""
      canonical = ""
      in_required = 0
      in_canonical = 0
      next
    }
    in_task && in_any && /^[[:space:]]{8}description:[[:space:]]*/ {
      description = $0
      sub(/^[[:space:]]{8}description:[[:space:]]*/, "", description)
      description = cleaned(description)
      next
    }
    in_task && in_any && /^[[:space:]]{8}required_inputs:[[:space:]]*$/ {
      in_required = 1
      in_canonical = 0
      next
    }
    in_task && in_any && /^[[:space:]]{8}canonical_required_inputs:[[:space:]]*$/ {
      in_required = 0
      in_canonical = 1
      next
    }
    in_task && in_any && in_required && /^[[:space:]]{10}-[[:space:]]*/ {
      item = $0
      sub(/^[[:space:]]{10}-[[:space:]]*/, "", item)
      item = cleaned(item)
      if (item != "") {
        required = (required == "" ? item : required "," item)
      }
      next
    }
    in_task && in_any && in_canonical && /^[[:space:]]{10}-[[:space:]]*/ {
      item = $0
      sub(/^[[:space:]]{10}-[[:space:]]*/, "", item)
      item = cleaned(item)
      if (item != "") {
        canonical = (canonical == "" ? item : canonical "," item)
      }
      next
    }
    in_task && in_any && /^[[:space:]]{4}[a-zA-Z0-9_-]+:[[:space:]]*/ {
      emit()
      in_any = 0
      in_required = 0
      in_canonical = 0
      group_id = ""
      description = ""
      required = ""
      canonical = ""
      next
    }
    END {
      emit()
    }
  ' "$contracts_file"
}

input_schema_list_keys() {
  local schema_file="$1"
  registry_require_file "$schema_file"
  awk '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*inputs:[[:space:]]*$/ {
      in_inputs = 1
      next
    }
    in_inputs && /^[[:space:]]*-[[:space:]]*key:[[:space:]]*/ {
      v = $0
      sub(/^[[:space:]]*-[[:space:]]*key:[[:space:]]*/, "", v)
      v = cleaned(v)
      if (v != "") {
        print v
      }
      next
    }
    in_inputs && /^[^[:space:]]/ {
      in_inputs = 0
      next
    }
  ' "$schema_file"
}

input_schema_resolve_key() {
  local schema_file="$1"
  local raw_key="$2"
  registry_require_file "$schema_file"

  if [[ -z "$raw_key" ]]; then
    printf '\n'
    return 0
  fi

  while IFS= read -r k; do
    if [[ "$k" == "$raw_key" ]]; then
      printf '%s\n' "$raw_key"
      return 0
    fi
  done < <(input_schema_list_keys "$schema_file")

  awk -v target="$raw_key" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*legacy_key_map:[[:space:]]*$/ {
      in_map = 1
      next
    }
    in_map && /^[[:space:]]{2}[a-zA-Z0-9_.-]+:[[:space:]]*/ {
      line = $0
      sub(/^[[:space:]]{2}/, "", line)
      key = line
      sub(/:[[:space:]]*.*/, "", key)
      val = line
      sub(/^[^:]+:[[:space:]]*/, "", val)
      key = cleaned(key)
      val = cleaned(val)
      if (key == target) {
        print val
        exit
      }
      next
    }
    in_map && /^[^[:space:]]/ {
      in_map = 0
      next
    }
  ' "$schema_file"
}

input_schema_list_query_tokens() {
  local schema_file="$1"
  local key_name="$2"
  registry_require_file "$schema_file"
  awk -v target="$key_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*inputs:[[:space:]]*$/ {
      in_inputs = 1
      next
    }
    in_inputs && /^[[:space:]]*-[[:space:]]*key:[[:space:]]*/ {
      key = $0
      sub(/^[[:space:]]*-[[:space:]]*key:[[:space:]]*/, "", key)
      key = cleaned(key)
      in_target = (key == target)
      in_tokens = 0
      next
    }
    in_target && /^[[:space:]]*query_tokens:[[:space:]]*$/ {
      in_tokens = 1
      next
    }
    in_target && in_tokens && /^[[:space:]]*-[[:space:]]*/ {
      item = $0
      sub(/^[[:space:]]*-[[:space:]]*/, "", item)
      item = cleaned(item)
      if (item != "") {
        print item
      }
      next
    }
    in_target && in_tokens && /^[[:space:]]*[a-zA-Z0-9_-]+:[[:space:]]*/ {
      in_tokens = 0
      next
    }
    in_inputs && /^[^[:space:]]/ {
      in_inputs = 0
      in_target = 0
      in_tokens = 0
      next
    }
  ' "$schema_file"
}

skill_meta_list_query_tokens() {
  local skill_meta="$1"
  local key_name="$2"
  registry_require_file "$skill_meta"

  local mapping=""
  local head=""
  local segment=""
  local payload=""
  local token=""

  while IFS= read -r mapping; do
    [[ -z "$mapping" ]] && continue
    head="${mapping%%|*}"
    if [[ "$head" != "$key_name" ]]; then
      continue
    fi
    while IFS='|' read -r segment; do
      if [[ "$segment" == query_tokens=* ]]; then
        payload="${segment#query_tokens=}"
        while IFS=',' read -r token; do
          token="$(printf '%s' "$token" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')"
          [[ -n "$token" ]] && printf '%s\n' "$token"
        done <<<"$payload"
      fi
    done <<<"$(printf '%s' "$mapping" | tr '|' '\n')"
  done < <(yaml_get_list_field "$skill_meta" "input_mappings")
}

task_contract_get_task_alias() {
  local contracts_file="$1"
  local alias_name="$2"
  registry_require_file "$contracts_file"
  awk -v target="$alias_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*task_aliases:[[:space:]]*$/ {
      in_aliases = 1
      next
    }
    in_aliases && $0 ~ ("^[[:space:]]{2}" target ":[[:space:]]*") {
      v = $0
      sub("^[[:space:]]{2}" target ":[[:space:]]*", "", v)
      v = cleaned(v)
      print v
      exit
    }
    in_aliases && /^[[:space:]]{2}[a-zA-Z0-9_-]+:[[:space:]]*/ {
      next
    }
    in_aliases && /^[^[:space:]]/ {
      in_aliases = 0
      next
    }
  ' "$contracts_file"
}

output_contract_list_field() {
  local contracts_file="$1"
  local task_name="$2"
  local field_name="$3"
  registry_require_file "$contracts_file"
  awk -v target="$task_name" -v field="$field_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*contracts:[[:space:]]*$/ {
      in_contracts = 1
      next
    }
    in_contracts && $0 ~ ("^[[:space:]]{2}" target ":[[:space:]]*$") {
      in_task = 1
      in_field = 0
      next
    }
    in_contracts && in_task && /^[[:space:]]{2}[a-zA-Z0-9_-]+:[[:space:]]*$/ {
      in_task = 0
      in_field = 0
      next
    }
    in_task && $0 ~ ("^[[:space:]]{4}" field ":[[:space:]]*$") {
      in_field = 1
      next
    }
    in_task && in_field && /^[[:space:]]{6}-[[:space:]]*/ {
      item = $0
      sub(/^[[:space:]]{6}-[[:space:]]*/, "", item)
      item = cleaned(item)
      if (item != "") {
        print item
      }
      next
    }
    in_task && in_field && /^[[:space:]]{4}[a-zA-Z0-9_-]+:[[:space:]]*/ {
      in_field = 0
      next
    }
  ' "$contracts_file"
}

output_contract_get_scalar() {
  local contracts_file="$1"
  local task_name="$2"
  local field_name="$3"
  registry_require_file "$contracts_file"
  awk -v target="$task_name" -v field="$field_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*contracts:[[:space:]]*$/ {
      in_contracts = 1
      next
    }
    in_contracts && $0 ~ ("^[[:space:]]{2}" target ":[[:space:]]*$") {
      in_task = 1
      next
    }
    in_contracts && in_task && /^[[:space:]]{2}[a-zA-Z0-9_-]+:[[:space:]]*$/ {
      in_task = 0
      next
    }
    in_task && $0 ~ ("^[[:space:]]{4}" field ":[[:space:]]*") {
      v = $0
      sub("^[[:space:]]{4}" field ":[[:space:]]*", "", v)
      v = cleaned(v)
      print v
      exit
    }
  ' "$contracts_file"
}

recovery_policy_get_retry_policy() {
  local policy_file="$1"
  local task_name="$2"
  registry_require_file "$policy_file"
  awk -v target="$task_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*policies:[[:space:]]*$/ {
      in_policies = 1
      next
    }
    in_policies && $0 ~ ("^[[:space:]]{2}" target ":[[:space:]]*$") {
      in_task = 1
      next
    }
    in_policies && in_task && /^[[:space:]]{2}[a-zA-Z0-9_-]+:[[:space:]]*$/ {
      in_task = 0
      next
    }
    in_task && /^[[:space:]]{4}retry_policy:[[:space:]]*/ {
      v = $0
      sub(/^[[:space:]]{4}retry_policy:[[:space:]]*/, "", v)
      print cleaned(v)
      exit
    }
  ' "$policy_file"
}

recovery_policy_list_fallback_skills() {
  local policy_file="$1"
  local task_name="$2"
  registry_require_file "$policy_file"
  awk -v target="$task_name" '
    function cleaned(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      gsub(/"/, "", s)
      return s
    }
    /^[[:space:]]*policies:[[:space:]]*$/ {
      in_policies = 1
      next
    }
    in_policies && $0 ~ ("^[[:space:]]{2}" target ":[[:space:]]*$") {
      in_task = 1
      in_fallback = 0
      next
    }
    in_policies && in_task && /^[[:space:]]{2}[a-zA-Z0-9_-]+:[[:space:]]*$/ {
      in_task = 0
      in_fallback = 0
      next
    }
    in_task && /^[[:space:]]{4}fallback_skills:[[:space:]]*$/ {
      in_fallback = 1
      next
    }
    in_task && in_fallback && /^[[:space:]]{6}-[[:space:]]*/ {
      item = $0
      sub(/^[[:space:]]{6}-[[:space:]]*/, "", item)
      item = cleaned(item)
      if (item != "") {
        print item
      }
      next
    }
    in_task && in_fallback && /^[[:space:]]{4}[a-zA-Z0-9_-]+:[[:space:]]*/ {
      in_fallback = 0
      next
    }
  ' "$policy_file"
}
