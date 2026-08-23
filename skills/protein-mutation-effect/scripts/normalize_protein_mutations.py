#!/usr/bin/env python3
"""Normalize protein sequences and missense substitutions with WT validation."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}
ONE_RE = re.compile(r"^([A-Za-z])([1-9][0-9]*)([A-Za-z])$")
THREE_RE = re.compile(r"^(?:p\.)?([A-Za-z]{3})([1-9][0-9]*)([A-Za-z]{3})$", re.I)


class InputError(ValueError):
    pass


def parse_fasta(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    current: str | None = None
    chunks: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current is not None:
                    records[current] = "".join(chunks).upper()
                current = line[1:].split()[0]
                if not current or current in records:
                    raise InputError(f"invalid_or_duplicate_fasta_id_at_line_{lineno}")
                chunks = []
            elif current is None:
                raise InputError(f"sequence_before_fasta_header_at_line_{lineno}")
            else:
                chunks.append(re.sub(r"\s+", "", line))
    if current is not None:
        records[current] = "".join(chunks).upper()
    if not records:
        raise InputError("empty_fasta")
    return records


def read_sequences(sequence: str | None, fasta: str | None, protein_id: str) -> dict[str, str]:
    if bool(sequence) == bool(fasta):
        raise InputError("provide_exactly_one_of_sequence_or_fasta")
    if sequence:
        records = {protein_id: re.sub(r"\s+", "", sequence).upper()}
    else:
        path = Path(fasta).expanduser().resolve()
        if not path.is_file():
            raise InputError(f"fasta_not_found:{path}")
        records = parse_fasta(path)
    for pid, seq in records.items():
        if not seq:
            raise InputError(f"empty_sequence:{pid}")
        bad = sorted(set(seq) - CANONICAL_AA)
        if bad:
            raise InputError(f"noncanonical_residues:{pid}:{''.join(bad)}")
    return records


def parse_substitution(token: str) -> tuple[str, int, str]:
    token = token.strip()
    match = ONE_RE.fullmatch(token)
    if match:
        wt, pos, mut = match.groups()
        return wt.upper(), int(pos), mut.upper()
    match = THREE_RE.fullmatch(token)
    if match:
        wt3, pos, mut3 = match.groups()
        try:
            return THREE_TO_ONE[wt3.upper()], int(pos), THREE_TO_ONE[mut3.upper()]
        except KeyError as exc:
            raise InputError(f"unknown_three_letter_residue:{token}") from exc
    raise InputError(f"unsupported_protein_substitution:{token}")


def split_protein_prefix(raw: str, records: dict[str, str]) -> tuple[str, str]:
    parts = raw.strip().split(":")
    if len(parts) > 1 and parts[0] in records:
        return parts[0], ":".join(parts[1:])
    if len(records) == 1:
        return next(iter(records)), raw.strip()
    raise InputError(f"protein_id_required_for_multi_fasta:{raw}")


def canonicalize(raw: str, protein_id: str, sequence: str) -> tuple[str, list[int]]:
    tokens = [x.strip() for x in re.split(r"[:,+|/]", raw) if x.strip()]
    if not tokens:
        raise InputError("empty_mutation_group")
    parsed = [parse_substitution(token) for token in tokens]
    positions = [pos for _, pos, _ in parsed]
    if len(set(positions)) != len(positions):
        raise InputError(f"duplicate_position_in_group:{raw}")
    canonical: list[str] = []
    for wt, pos, mut in sorted(parsed, key=lambda x: x[1]):
        if pos > len(sequence):
            raise InputError(f"position_out_of_range:{protein_id}:{pos}:{len(sequence)}")
        actual = sequence[pos - 1]
        if actual != wt:
            raise InputError(f"wild_type_mismatch:{protein_id}:{pos}:expected_{actual}:got_{wt}")
        if wt == mut:
            raise InputError(f"no_op_substitution:{protein_id}:{wt}{pos}{mut}")
        canonical.append(f"{wt}{pos}{mut}")
    return ":".join(canonical), sorted(positions)


def read_mutation_records(
    mutations: list[str], mutations_file: str | None, records: dict[str, str]
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for index, raw in enumerate(mutations, 1):
        pid, group = split_protein_prefix(raw, records)
        output.append({"protein_id": pid, "variant_id": f"variant_{index:04d}", "raw": group})
    if mutations_file:
        path = Path(mutations_file).expanduser().resolve()
        if not path.is_file():
            raise InputError(f"mutations_file_not_found:{path}")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            delimiter = "\t" if "\t" in sample.splitlines()[0] else ","
            reader = csv.DictReader(handle, delimiter=delimiter)
            names = set(reader.fieldnames or [])
            group_col = "mutation_group" if "mutation_group" in names else "mutation" if "mutation" in names else None
            if not group_col:
                raise InputError("mutation_table_requires_mutation_group_or_mutation_column")
            for row_index, row in enumerate(reader, len(output) + 1):
                raw = (row.get(group_col) or "").strip()
                pid = (row.get("protein_id") or "").strip()
                if not pid:
                    if len(records) != 1:
                        raise InputError(f"protein_id_required_at_mutation_row:{row_index}")
                    pid = next(iter(records))
                if pid not in records:
                    raise InputError(f"unknown_protein_id_at_mutation_row:{row_index}:{pid}")
                output.append({
                    "protein_id": pid,
                    "variant_id": (row.get("variant_id") or f"variant_{row_index:04d}").strip(),
                    "raw": raw,
                })
    if not output:
        raise InputError("provide_at_least_one_mutation")
    return output


def normalize(
    sequence: str | None,
    fasta: str | None,
    protein_id: str,
    mutations: list[str],
    mutations_file: str | None,
    output_dir: Path,
) -> dict[str, object]:
    records = read_sequences(sequence, fasta, protein_id)
    source_rows = read_mutation_records(mutations, mutations_file, records)
    normalized: list[dict[str, object]] = []
    seen_variant_ids: set[str] = set()
    for row in source_rows:
        pid = row["protein_id"]
        variant_id = row["variant_id"]
        if not variant_id or variant_id in seen_variant_ids:
            raise InputError(f"empty_or_duplicate_variant_id:{variant_id}")
        seen_variant_ids.add(variant_id)
        canonical, positions = canonicalize(row["raw"], pid, records[pid])
        normalized.append({
            "protein_id": pid,
            "variant_id": variant_id,
            "original_mutation": row["raw"],
            "mutation_group": canonical,
            "mutation_type": "single_substitution" if len(positions) == 1 else "multi_substitution",
            "positions": ",".join(str(x) for x in positions),
            "sequence_length": len(records[pid]),
            "validation_status": "valid",
            "error": "",
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    fasta_out = output_dir / "normalized_sequences.fasta"
    with fasta_out.open("w", encoding="utf-8", newline="\n") as handle:
        for pid, seq in records.items():
            handle.write(f">{pid}\n")
            for start in range(0, len(seq), 80):
                handle.write(seq[start:start + 80] + "\n")
    tsv_out = output_dir / "normalized_mutations.tsv"
    fields = [
        "protein_id", "variant_id", "original_mutation", "mutation_group",
        "mutation_type", "positions", "sequence_length", "validation_status", "error",
    ]
    with tsv_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(normalized)
    result = {
        "status": "valid",
        "protein_count": len(records),
        "variant_count": len(normalized),
        "coordinate_convention": "1-based protein sequence positions",
        "normalized_sequences_fasta": str(fasta_out),
        "normalized_mutations_tsv": str(tsv_out),
    }
    with (output_dir / "validation.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--sequence", help="One raw wild-type amino-acid sequence.")
    source.add_argument("--fasta", help="Wild-type protein FASTA.")
    parser.add_argument("--protein-id", default="protein_1", help="ID used with --sequence.")
    parser.add_argument("--mutation", action="append", default=[], help="Repeat for each variant; group substitutions with colons.")
    parser.add_argument("--mutations-file", help="CSV/TSV with mutation_group or mutation, plus optional protein_id and variant_id.")
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = normalize(
            args.sequence, args.fasta, args.protein_id, args.mutation,
            args.mutations_file, Path(args.output_dir).expanduser().resolve(),
        )
    except (InputError, OSError, csv.Error) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
