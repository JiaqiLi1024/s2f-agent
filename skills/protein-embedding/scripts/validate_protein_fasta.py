#!/usr/bin/env python3
"""Validate protein FASTA inputs for protein embedding workflows."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
AMBIGUOUS_AA = set("BXZJ")
RARE_AA = set("UO")
UNKNOWN_AA = set("X")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate protein FASTA for PLM embeddings.")
    parser.add_argument("--fasta", required=True)
    parser.add_argument("--allow-ambiguous-aa", action="store_true")
    parser.add_argument("--allow-rare-aa", action="store_true")
    parser.add_argument("--allow-saprot-tokens", action="store_true")
    parser.add_argument("--max-length", type=int, default=None)
    parser.add_argument("--output-json", default=None)
    return parser.parse_args()


def parse_fasta(path: Path) -> list[tuple[str, str, str]]:
    records: list[tuple[str, str, str]] = []
    current_id: str | None = None
    current_desc = ""
    chunks: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_id is not None:
                records.append((current_id, current_desc, "".join(chunks)))
            header = line[1:].strip()
            if not header:
                raise ValueError("empty FASTA header")
            parts = header.split(None, 1)
            current_id = parts[0]
            current_desc = parts[1] if len(parts) > 1 else ""
            chunks = []
        else:
            if current_id is None:
                raise ValueError("sequence line appears before first FASTA header")
            chunks.append(line)
    if current_id is not None:
        records.append((current_id, current_desc, "".join(chunks)))
    if not records:
        raise ValueError("no FASTA records found")
    return records


def validate(args: argparse.Namespace) -> dict:
    path = Path(args.fasta)
    records = parse_fasta(path)
    seen: set[str] = set()
    errors: list[str] = []
    warnings: list[str] = []
    summaries: list[dict] = []

    saprot_allowed = set("ACDEFGHIKLMNPQRSTVWYUOXBZJ#abcdefghijklmnopqrstuvwxyz")
    for protein_id, desc, raw_seq in records:
        seq = raw_seq if args.allow_saprot_tokens else re.sub(r"\s+", "", raw_seq).upper()
        if protein_id in seen:
            errors.append(f"{protein_id}: duplicate FASTA ID")
        seen.add(protein_id)
        if not seq:
            errors.append(f"{protein_id}: empty sequence")
        if args.max_length is not None and len(seq) > args.max_length:
            warnings.append(f"{protein_id}: length {len(seq)} exceeds max_length {args.max_length}")
        if args.allow_saprot_tokens:
            invalid = sorted(set(seq) - saprot_allowed)
            if invalid:
                errors.append(f"{protein_id}: invalid SaProt token characters: {''.join(invalid)}")
        else:
            invalid = sorted(set(seq) - CANONICAL_AA - AMBIGUOUS_AA - RARE_AA - UNKNOWN_AA)
            if invalid:
                errors.append(f"{protein_id}: invalid amino-acid characters: {''.join(invalid)}")
            ambiguous = sorted((set(seq) & AMBIGUOUS_AA) - UNKNOWN_AA)
            rare = sorted(set(seq) & RARE_AA)
            if ambiguous and not args.allow_ambiguous_aa:
                errors.append(f"{protein_id}: ambiguous residues require --allow-ambiguous-aa: {''.join(ambiguous)}")
            if rare and not args.allow_rare_aa:
                errors.append(f"{protein_id}: rare residues require --allow-rare-aa: {''.join(rare)}")
            if "X" in seq:
                warnings.append(f"{protein_id}: contains X unknown residues")
        summaries.append(
            {
                "protein_id": protein_id,
                "description": desc,
                "length": len(seq),
            }
        )

    return {
        "status": "ok" if not errors else "error",
        "fasta": str(path),
        "record_count": len(records),
        "records": summaries,
        "warnings": warnings,
        "errors": errors,
    }


def main() -> int:
    args = parse_args()
    try:
        result = validate(args)
    except Exception as exc:
        result = {"status": "error", "errors": [str(exc)], "warnings": []}

    text = json.dumps(result, indent=2)
    if args.output_json:
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
