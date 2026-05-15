#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_REGISTRY_FILE="$REPO_ROOT/registry/skills.yaml"
source "$REPO_ROOT/scripts/lib_registry.sh"

usage() {
  cat <<'EOF'
Usage: validate_registry.sh [options]

Validate that each skill in the registry resolves to a real package path
with required files.

Options:
  --registry FILE    Skill registry file. Default: <repo>/registry/skills.yaml
  --include-disabled Include disabled skills from registry.
  -h, --help         Show this help message.
EOF
}

registry_file="$DEFAULT_REGISTRY_FILE"
include_disabled=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --registry)
      registry_file="$2"
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

failures=0
total=0

while IFS= read -r skill_id; do
  if [[ -z "$skill_id" ]]; then
    continue
  fi
  total=$((total + 1))
  skill_path="$(registry_get_path "$registry_file" "$skill_id" || true)"
  if [[ -z "$skill_path" ]]; then
    skill_path="$skill_id"
  fi
  skill_root="$REPO_ROOT/$skill_path"

  if [[ ! -d "$skill_root" ]]; then
    echo "fail: skill '$skill_id' path missing ($skill_root)" >&2
    failures=$((failures + 1))
    continue
  fi

  if [[ ! -f "$skill_root/SKILL.md" ]]; then
    echo "fail: skill '$skill_id' missing SKILL.md ($skill_root/SKILL.md)" >&2
    failures=$((failures + 1))
  fi

  if [[ ! -f "$skill_root/agents/openai.yaml" ]]; then
    echo "fail: skill '$skill_id' missing agents/openai.yaml ($skill_root/agents/openai.yaml)" >&2
    failures=$((failures + 1))
  fi

  echo "ok: $skill_id -> $skill_path"
done < <(registry_list_ids_filtered "$registry_file" "$include_disabled")

if [[ "$total" -eq 0 ]]; then
  echo "fail: no skills found in registry ($registry_file)" >&2
  exit 1
fi

if [[ "$failures" -ne 0 ]]; then
  echo "registry validation failed with $failures issue(s)" >&2
  exit 1
fi

echo "registry validation passed for $total skill(s)"
