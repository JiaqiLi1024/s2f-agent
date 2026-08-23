#!/usr/bin/env python3
"""Validate FASTA-linked protein mutation requests before model execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mutation_io import load_mutation_requests, read_fasta, write_tsv

FIELDS = ["protein_id", "variant_id", "mutation_group", "mutation_count", "positions", "mutated_sequence", "status", "error"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasta", required=True, help="WT protein FASTA; identifiers must be unique")
    parser.add_argument("--mutations-file", help="TSV/CSV with protein_id, variant_id, mutation_group")
    parser.add_argument("--mutation", action="append", default=[], help="A42V, p.Ala42Val, or A42V:G55D; repeatable")
    parser.add_argument("--mutations", help="Semicolon-delimited mutation groups for a single FASTA record")
    parser.add_argument("--protein-id", help="Default protein ID for command-line mutations")
    parser.add_argument("--output", help="Normalized TSV (default: stdout)")
    parser.add_argument("--summary-json", help="Optional validation summary JSON")
    parser.add_argument("--allow-invalid", action="store_true", help="Return zero even when rows are invalid")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cli_mutations = list(args.mutation)
    if args.mutations:
        cli_mutations.extend(item for item in args.mutations.split(";") if item.strip())
    try:
        fasta = read_fasta(args.fasta)
        rows = load_mutation_requests(fasta, args.mutations_file, cli_mutations, args.protein_id)
    except Exception as exc:
        build_parser().error(str(exc))
    if args.output:
        write_tsv(args.output, rows, FIELDS)
    else:
        import csv, sys
        writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, delimiter="\t", extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    invalid = sum(row["status"] != "valid" for row in rows)
    summary = {
        "schema_version": 1,
        "records": len(rows),
        "valid": len(rows) - invalid,
        "invalid": invalid,
        "protein_count": len(fasta),
        "coordinate_system": "one-based-protein",
    }
    if args.summary_json:
        Path(args.summary_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_json).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if invalid == 0 or args.allow_invalid else 1


if __name__ == "__main__":
    raise SystemExit(main())
