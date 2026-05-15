#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_SCRIPT="$REPO_ROOT/scripts/run_agent.sh"

if [[ ! -f "$AGENT_SCRIPT" ]]; then
  echo "error: missing run_agent script at $AGENT_SCRIPT" >&2
  exit 1
fi

echo "s2f agent console"
echo "type 'exit' to quit"
echo

while true; do
  printf '> '
  if ! IFS= read -r line; then
    echo
    break
  fi

  trimmed="$(printf '%s' "$line" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')"
  if [[ -z "$trimmed" ]]; then
    continue
  fi
  if [[ "$trimmed" == "exit" || "$trimmed" == "quit" ]]; then
    break
  fi

  bash "$AGENT_SCRIPT" --query "$trimmed"
  echo
done
