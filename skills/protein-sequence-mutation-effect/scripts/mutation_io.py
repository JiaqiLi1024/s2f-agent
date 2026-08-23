#!/usr/bin/env python3
"""Dependency-free FASTA and protein-substitution normalization helpers."""
from __future__ import annotations

import csv
import gzip
import hashlib
import re
from pathlib import Path
from typing import Iterable

AA20 = set("ACDEFGHIKLMNPQRSTVWY")
AA3 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}
ONE_RE = re.compile(r"^(?:p\.)?([A-Za-z*])([1-9][0-9]*)([A-Za-z*])$")
THREE_RE = re.compile(r"^(?:p\.)?([A-Za-z]{3})([1-9][0-9]*)([A-Za-z]{3})$")


def open_text(path: str | Path):
    path = Path(path)
    return gzip.open(path, "rt", encoding="utf-8-sig", newline="") if path.suffix == ".gz" else path.open("r", encoding="utf-8-sig", newline="")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_fasta(path: str | Path, aligned: bool = False) -> dict[str, str]:
    records: dict[str, list[str]] = {}
    current = None
    with open_text(path) as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                current = line[1:].split()[0]
                if not current or current in records:
                    raise ValueError(f"empty or duplicate FASTA identifier: {current!r}")
                records[current] = []
            elif current is None:
                raise ValueError("FASTA sequence appears before the first header")
            else:
                # A3M lowercase characters are insertions relative to the query.
                seq = line if aligned else line.upper()
                if aligned:
                    seq = "".join(ch for ch in seq if not ch.islower()).upper()
                records[current].append(seq)
    if not records:
        raise ValueError("FASTA has no records")
    out = {key: "".join(parts).replace(" ", "") for key, parts in records.items()}
    for key, seq in out.items():
        if not seq:
            raise ValueError(f"empty sequence for {key}")
        allowed = AA20 | ({"-", ".", "X", "B", "Z", "J", "U", "O"} if aligned else set())
        bad = sorted(set(seq) - allowed)
        if bad:
            raise ValueError(f"invalid residues for {key}: {''.join(bad)}")
    return out


def parse_substitution(text: str) -> tuple[str, int, str]:
    token = text.strip().replace(" ", "")
    match = ONE_RE.fullmatch(token)
    if match:
        ref, pos, alt = match.groups()
        ref, alt = ref.upper(), alt.upper()
    else:
        match = THREE_RE.fullmatch(token)
        if not match:
            raise ValueError(f"unsupported substitution syntax: {text!r}")
        ref3, pos, alt3 = match.groups()
        ref = AA3.get(ref3.upper(), "")
        alt = AA3.get(alt3.upper(), "")
    if ref not in AA20 or alt not in AA20:
        raise ValueError(f"only canonical amino-acid substitutions are supported: {text!r}")
    if ref == alt:
        raise ValueError(f"reference and alternate residues are identical: {text!r}")
    return ref, int(pos), alt


def parse_mutation_group(text: str) -> list[tuple[str, int, str]]:
    parts = [part for part in re.split(r"[:;,]", text.strip()) if part.strip()]
    if not parts:
        raise ValueError("empty mutation group")
    substitutions = [parse_substitution(part) for part in parts]
    seen: set[int] = set()
    for _, pos, _ in substitutions:
        if pos in seen:
            raise ValueError(f"duplicate position {pos} within mutation group")
        seen.add(pos)
    return substitutions


def canonical_group(substitutions: Iterable[tuple[str, int, str]]) -> str:
    return ":".join(f"{ref}{pos}{alt}" for ref, pos, alt in substitutions)


def apply_group(sequence: str, substitutions: list[tuple[str, int, str]]) -> str:
    chars = list(sequence)
    for ref, pos, alt in substitutions:
        if pos > len(chars):
            raise ValueError(f"position {pos} exceeds sequence length {len(chars)}")
        observed = chars[pos - 1]
        if observed != ref:
            raise ValueError(f"WT mismatch at {pos}: mutation says {ref}, FASTA has {observed}")
        chars[pos - 1] = alt
    return "".join(chars)


def _delimiter(path: str | Path, sample: str) -> str:
    name = str(path).lower()
    if name.endswith((".tsv", ".tsv.gz", ".txt", ".txt.gz")):
        return "\t"
    if name.endswith((".csv", ".csv.gz")):
        return ","
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t,").delimiter
    except csv.Error:
        return "\t"


def read_table(path: str | Path) -> list[dict[str, str]]:
    with open_text(path) as handle:
        lines = [line for line in handle if line.strip() and not line.startswith("##")]
    if not lines:
        raise ValueError(f"empty table: {path}")
    # AlphaMissense genomic releases use a single leading '#' on the header.
    lines[0] = lines[0].lstrip("#")
    delimiter = _delimiter(path, "".join(lines[:5]))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(lines, delimiter=delimiter)]


def first_value(row: dict[str, str], names: Iterable[str]) -> str:
    lower = {key.lower(): value for key, value in row.items()}
    for name in names:
        value = lower.get(name.lower(), "")
        if value:
            return value
    return ""


def load_mutation_requests(
    fasta: dict[str, str], mutations_file: str | None, mutations: list[str], default_protein_id: str | None = None
) -> list[dict[str, str]]:
    raw_rows: list[dict[str, str]] = []
    if mutations_file:
        raw_rows.extend(read_table(mutations_file))
    for item in mutations:
        raw_rows.append({"protein_id": default_protein_id or "", "mutation_group": item})
    if not raw_rows:
        raise ValueError("provide --mutations-file, --mutation, or --mutations")
    only_id = next(iter(fasta)) if len(fasta) == 1 else ""
    normalized: list[dict[str, str]] = []
    for index, row in enumerate(raw_rows, 1):
        protein_id = first_value(row, ("protein_id", "sequence_id", "uniprot_id", "uniprot", "protein")) or default_protein_id or only_id
        variant_id = first_value(row, ("variant_id", "id", "mutation_id"))
        group_text = first_value(row, ("mutation_group", "mutation", "mutant", "protein_variant", "variant"))
        result = {
            "protein_id": protein_id,
            "variant_id": variant_id,
            "mutation_group": group_text,
            "mutation_count": "",
            "positions": "",
            "mutated_sequence": "",
            "status": "valid",
            "error": "",
        }
        try:
            if not protein_id:
                raise ValueError("protein_id is required when FASTA contains multiple records")
            if protein_id not in fasta:
                # Permit common UniProt pipe identifiers by exact suffix match only.
                matches = [key for key in fasta if protein_id in key.split("|") or key in protein_id.split("|")]
                if len(matches) != 1:
                    raise ValueError(f"protein_id {protein_id!r} is not in FASTA")
                protein_id = matches[0]
                result["protein_id"] = protein_id
            substitutions = parse_mutation_group(group_text)
            canonical = canonical_group(substitutions)
            mutated = apply_group(fasta[protein_id], substitutions)
            provided_mutated = first_value(row, ("mutated_sequence", "variant_sequence"))
            if provided_mutated and provided_mutated.upper() != mutated:
                raise ValueError("provided mutated_sequence disagrees with FASTA plus mutation_group")
            result.update({
                "variant_id": variant_id or f"{protein_id}:{canonical}",
                "mutation_group": canonical,
                "mutation_count": str(len(substitutions)),
                "positions": ",".join(str(pos) for _, pos, _ in substitutions),
                "mutated_sequence": mutated,
            })
        except Exception as exc:  # validation errors must remain row-addressable
            result["status"] = "invalid"
            result["error"] = str(exc)
            result["variant_id"] = variant_id or f"row-{index}"
        normalized.append(result)
    return normalized


def write_tsv(path: str | Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
