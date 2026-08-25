#!/usr/bin/env python3
"""Emit source-grounded parameter claims for the local agent plan."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--query", required=False, default="")
    args = parser.parse_args()

    catalog = yaml.safe_load(Path(args.catalog).read_text(encoding="utf-8")) or {}
    entry = (catalog.get("skills") or {}).get(args.skill) or {}
    query_lc = str(args.query or "").lower().replace("-", "_")

    # Select the longest catalog parameter whose component words are present
    # in the question. This keeps the runtime contract to one claim while
    # handling natural-language forms such as "default output head" for
    # `output_head_default` and hyphenated CLI spellings.
    candidates: list[str] = []
    for item in entry.get("documented") or []:
        if isinstance(item, dict) and item.get("name"):
            candidates.append(str(item["name"]))
    for item in entry.get("unsupported") or []:
        candidates.append(str(item))
    selected_name = ""
    selected_score = (-1, -1)
    for name in sorted(set(candidates)):
        words = [word for word in re.split(r"[_\s]+", name.lower()) if len(word) > 2]
        matched = sum(1 for word in words if word in query_lc)
        if words and matched == len(words):
            score = (matched, len(name))
            if score > selected_score:
                selected_score = score
                selected_name = name

    claims: list[dict[str, Any]] = []
    for item in entry.get("documented") or []:
        if selected_name and isinstance(item, dict) and item.get("name") and item.get("value") is not None and str(item.get("name")) == selected_name:
            claims.append({
                "name": str(item["name"]),
                "value": str(item["value"]),
                "status": str(item.get("status") or "documented"),
                "evidence": str(item.get("evidence") or "parameter_catalog"),
            })
    for name in entry.get("unsupported") or []:
        if not selected_name or str(name) != selected_name:
            continue
        claims.append({
            "name": str(name),
            "value": "unknown",
            "status": "unknown",
            "evidence": f"not documented as a universal value for {args.skill}; verify the selected version or config",
        })
    print(json.dumps(claims, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
