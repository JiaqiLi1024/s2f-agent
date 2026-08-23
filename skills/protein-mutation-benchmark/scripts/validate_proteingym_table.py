#!/usr/bin/env python3
"""Validate and normalize ProteinGym-like assay or project score tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from proteingym_utils import (
    ASSAY_ALIASES,
    SCORE_ALIASES,
    mutation_type,
    normalize_higher_is,
    normalize_label,
    normalize_mutation,
    parse_float,
    read_table,
    resolve_columns,
    write_json,
    write_tsv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV/TSV table")
    parser.add_argument("--kind", required=True, choices=("assay", "scores"))
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--assay-id", help="Fallback assay ID when no assay column exists")
    parser.add_argument("--mutation-column")
    parser.add_argument("--assay-column")
    parser.add_argument("--protein-column")
    parser.add_argument("--score-column", help="DMS score for assay; raw model score for scores")
    parser.add_argument("--label-column")
    parser.add_argument("--model-column")
    parser.add_argument("--score-name-column")
    parser.add_argument("--higher-is-column")
    parser.add_argument("--allow-invalid", action="store_true", help="Write valid rows and exit zero despite exclusions")
    return parser


def normalize_table(args: argparse.Namespace) -> tuple[list[dict], dict]:
    rows, headers = read_table(args.input)
    aliases = ASSAY_ALIASES if args.kind == "assay" else SCORE_ALIASES
    explicit = {
        "assay_id": args.assay_column,
        "protein_id": args.protein_column,
        "mutation": args.mutation_column,
        "dms_score": args.score_column if args.kind == "assay" else None,
        "label": args.label_column,
        "raw_score": args.score_column if args.kind == "scores" else None,
        "model_id": args.model_column,
        "score_name": args.score_name_column,
        "higher_is": args.higher_is_column,
    }
    mapping, warnings = resolve_columns(headers, aliases, explicit)
    required = ["mutation"] if args.kind == "assay" else ["mutation", "model_id", "raw_score"]
    missing = [name for name in required if not mapping.get(name)]
    if missing:
        raise ValueError(f"Missing required canonical columns: {', '.join(missing)}")
    if args.kind == "assay" and not mapping.get("dms_score") and not mapping.get("label"):
        raise ValueError("Assay input requires a DMS_score-like numeric column, a binary label column, or both")

    normalized: list[dict] = []
    exclusions: list[dict] = []
    seen: set[tuple[str, ...]] = set()
    for row_number, row in enumerate(rows, start=2):
        try:
            mutation = normalize_mutation(row[mapping["mutation"]])
            if not mutation:
                raise ValueError(f"row {row_number}: empty mutation")
            assay_id = row.get(mapping.get("assay_id") or "", "") or args.assay_id or Path(args.input).stem
            protein_id = row.get(mapping.get("protein_id") or "", "")
            base = {
                "assay_id": assay_id,
                "protein_id": protein_id,
                "mutation": mutation,
                "mutation_type": mutation_type(mutation),
                "source_row": row_number,
            }
            if args.kind == "assay":
                score_column = mapping.get("dms_score")
                base["dms_score"] = (
                    parse_float(row[score_column], "dms_score", row_number)
                    if score_column and row.get(score_column, "")
                    else ""
                )
                label_column = mapping.get("label")
                base["label"] = normalize_label(row[label_column]) if label_column and row.get(label_column, "") else ""
                key = (assay_id, protein_id, mutation)
            else:
                model_id = row[mapping["model_id"]].strip()
                if not model_id:
                    raise ValueError(f"row {row_number}: empty model_id")
                base["model_id"] = model_id
                base["score_name"] = row.get(mapping.get("score_name") or "", "") or "raw_score"
                base["raw_score"] = parse_float(row[mapping["raw_score"]], "raw_score", row_number)
                base["higher_is"] = normalize_higher_is(row.get(mapping.get("higher_is") or "", "higher"))
                key = (assay_id, protein_id, mutation, model_id, str(base["score_name"]))
            if key in seen:
                raise ValueError(f"row {row_number}: duplicate normalized key {key}")
            seen.add(key)
            normalized.append(base)
        except (KeyError, ValueError) as exc:
            exclusions.append({"source_row": row_number, "reason": str(exc)})

    fields = (
        ["assay_id", "protein_id", "mutation", "mutation_type", "dms_score", "label", "source_row"]
        if args.kind == "assay"
        else [
            "assay_id",
            "protein_id",
            "mutation",
            "mutation_type",
            "model_id",
            "score_name",
            "raw_score",
            "higher_is",
            "source_row",
        ]
    )
    report = {
        "status": "valid" if not exclusions else "valid_with_exclusions" if normalized else "invalid",
        "kind": args.kind,
        "input": str(Path(args.input).resolve()),
        "column_mapping": mapping,
        "warnings": warnings,
        "input_rows": len(rows),
        "valid_rows": len(normalized),
        "excluded_rows": len(exclusions),
        "exclusions": exclusions,
    }
    write_tsv(args.output_tsv, normalized, fields)
    write_json(args.report_json, report)
    return normalized, report


def main() -> int:
    args = build_parser().parse_args()
    try:
        rows, report = normalize_table(args)
    except (FileNotFoundError, ValueError) as exc:
        write_json(args.report_json, {"status": "invalid", "error": str(exc)})
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"{report['status']}: {len(rows)} normalized rows -> {args.output_tsv}")
    if report["excluded_rows"] and not args.allow_invalid:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
