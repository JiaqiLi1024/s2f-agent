#!/usr/bin/env python3
"""Validate protein mutations and map PDB/mmCIF author residues to FASTA positions."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shlex
from collections import OrderedDict
from pathlib import Path
from typing import Iterable

AA3 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "MSE": "M", "SEC": "U", "PYL": "O",
}
CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
MUTATION_RE = re.compile(r"^([A-Z])(\d+)([A-Z])$")
MAPPING_FIELDS = [
    "protein_id", "canonical_position", "fasta_aa", "chain", "auth_seq_id",
    "insertion_code", "pdb_aa", "mean_bfactor", "mapping_status",
]
MUTATION_FIELDS = [
    "protein_id", "variant_id", "mutation_group", "mutation", "chain",
    "numbering", "canonical_position", "auth_seq_id", "insertion_code",
    "wt", "alt", "pdb_aa", "mean_bfactor", "validation_status", "error",
]


def parse_fasta(path: Path) -> tuple[str, str]:
    records: list[tuple[str, str]] = []
    name: str | None = None
    chunks: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if name is not None:
                records.append((name, "".join(chunks).upper()))
            name = line[1:].split()[0]
            chunks = []
        else:
            if name is None:
                raise ValueError("FASTA sequence encountered before a header")
            chunks.append("".join(line.split()))
    if name is not None:
        records.append((name, "".join(chunks).upper()))
    if len(records) != 1:
        raise ValueError(f"expected exactly one FASTA record, found {len(records)}")
    protein_id, sequence = records[0]
    if not sequence:
        raise ValueError("FASTA sequence is empty")
    invalid = sorted(set(sequence) - CANONICAL_AA)
    if invalid:
        raise ValueError(f"FASTA contains unsupported residues: {','.join(invalid)}")
    return protein_id, sequence


def _new_residue(chain: str, auth_seq_id: str, icode: str, resname: str) -> dict:
    return {
        "chain": chain, "auth_seq_id": auth_seq_id, "insertion_code": icode,
        "resname": resname, "aa": AA3.get(resname.upper(), "X"),
        "bfactors": [], "atoms": set(),
    }


def parse_pdb(path: Path) -> list[dict]:
    residues: OrderedDict[tuple[str, str, str], dict] = OrderedDict()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.startswith("ATOM"):
            continue
        altloc = raw[16:17].strip()
        if altloc not in {"", "A"}:
            continue
        chain = raw[21:22].strip() or "_"
        auth_seq_id = raw[22:26].strip()
        icode = raw[26:27].strip()
        resname = raw[17:20].strip().upper()
        atom = raw[12:16].strip()
        key = (chain, auth_seq_id, icode)
        residue = residues.setdefault(key, _new_residue(chain, auth_seq_id, icode, resname))
        residue["atoms"].add(atom)
        try:
            residue["bfactors"].append(float(raw[60:66]))
        except ValueError:
            pass
    return list(residues.values())


def _clean_cif(value: str) -> str:
    return "" if value in {".", "?"} else value


def parse_mmcif(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    residues: OrderedDict[tuple[str, str, str], dict] = OrderedDict()
    index = 0
    while index < len(lines):
        if lines[index].strip() != "loop_":
            index += 1
            continue
        index += 1
        headers: list[str] = []
        while index < len(lines) and lines[index].strip().startswith("_"):
            headers.append(lines[index].strip().split()[0])
            index += 1
        if not headers or not any(h.startswith("_atom_site.") for h in headers):
            while index < len(lines) and not lines[index].strip().startswith(("#", "loop_", "data_", "_")):
                index += 1
            continue
        positions = {header: i for i, header in enumerate(headers)}
        tokens: list[str] = []
        rows: list[list[str]] = []
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped or stripped.startswith("#"):
                index += 1
                break
            if stripped == "loop_" or stripped.startswith(("data_", "_")):
                break
            tokens.extend(shlex.split(stripped, posix=True))
            while len(tokens) >= len(headers):
                rows.append(tokens[:len(headers)])
                tokens = tokens[len(headers):]
            index += 1
        def value(row: list[str], *keys: str, default: str = "") -> str:
            for key in keys:
                if key in positions:
                    return _clean_cif(row[positions[key]])
            return default
        for row in rows:
            if value(row, "_atom_site.group_PDB").upper() != "ATOM":
                continue
            altloc = value(row, "_atom_site.label_alt_id", "_atom_site.auth_alt_id")
            if altloc not in {"", "A"}:
                continue
            chain = value(row, "_atom_site.auth_asym_id", "_atom_site.label_asym_id", default="_") or "_"
            auth_seq_id = value(row, "_atom_site.auth_seq_id", "_atom_site.label_seq_id")
            icode = value(row, "_atom_site.pdbx_PDB_ins_code")
            resname = value(row, "_atom_site.auth_comp_id", "_atom_site.label_comp_id").upper()
            atom = value(row, "_atom_site.auth_atom_id", "_atom_site.label_atom_id")
            key = (chain, auth_seq_id, icode)
            residue = residues.setdefault(key, _new_residue(chain, auth_seq_id, icode, resname))
            residue["atoms"].add(atom)
            bfactor = value(row, "_atom_site.B_iso_or_equiv")
            try:
                residue["bfactors"].append(float(bfactor))
            except ValueError:
                pass
    return list(residues.values())


def parse_structure(path: Path) -> list[dict]:
    suffix = path.suffix.lower()
    if suffix in {".cif", ".mmcif"}:
        residues = parse_mmcif(path)
    else:
        residues = parse_pdb(path)
    if not residues:
        raise ValueError(f"no ATOM residues parsed from {path}")
    for residue in residues:
        values = residue.pop("bfactors")
        residue["mean_bfactor"] = sum(values) / len(values) if values else None
        residue["atoms"] = sorted(residue["atoms"])
    return residues


def global_alignment(left: str, right: str) -> tuple[str, str]:
    match, mismatch, gap = 2, -1, -2
    rows, cols = len(left) + 1, len(right) + 1
    score = [[0] * cols for _ in range(rows)]
    trace = [[""] * cols for _ in range(rows)]
    for i in range(1, rows):
        score[i][0] = i * gap
        trace[i][0] = "U"
    for j in range(1, cols):
        score[0][j] = j * gap
        trace[0][j] = "L"
    for i in range(1, rows):
        for j in range(1, cols):
            choices = [
                (score[i - 1][j - 1] + (match if left[i - 1] == right[j - 1] else mismatch), "D"),
                (score[i - 1][j] + gap, "U"),
                (score[i][j - 1] + gap, "L"),
            ]
            score[i][j], trace[i][j] = max(choices, key=lambda item: (item[0], {"D": 2, "U": 1, "L": 0}[item[1]]))
    aligned_left: list[str] = []
    aligned_right: list[str] = []
    i, j = len(left), len(right)
    while i or j:
        direction = trace[i][j]
        if direction == "D":
            aligned_left.append(left[i - 1]); aligned_right.append(right[j - 1]); i -= 1; j -= 1
        elif direction == "U":
            aligned_left.append(left[i - 1]); aligned_right.append("-"); i -= 1
        else:
            aligned_left.append("-"); aligned_right.append(right[j - 1]); j -= 1
    return "".join(reversed(aligned_left)), "".join(reversed(aligned_right))


def build_mapping(protein_id: str, sequence: str, residues: list[dict], chain: str) -> tuple[list[dict], dict[int, dict], dict]:
    chain_residues = [item for item in residues if item["chain"] == chain]
    if not chain_residues:
        chains = sorted({item["chain"] for item in residues})
        raise ValueError(f"chain {chain!r} not found; available chains: {','.join(chains)}")
    structure_sequence = "".join(item["aa"] for item in chain_residues)
    aligned_fasta, aligned_structure = global_alignment(sequence, structure_sequence)
    canonical_index = structure_index = 0
    by_position: dict[int, dict] = {}
    matches = mapped = 0
    for fasta_aa, pdb_aa in zip(aligned_fasta, aligned_structure):
        if fasta_aa != "-":
            canonical_index += 1
        if pdb_aa != "-":
            structure_index += 1
        if fasta_aa != "-" and pdb_aa != "-":
            residue = chain_residues[structure_index - 1]
            by_position[canonical_index] = residue
            mapped += 1
            if fasta_aa == pdb_aa:
                matches += 1
    rows: list[dict] = []
    for position, fasta_aa in enumerate(sequence, start=1):
        residue = by_position.get(position)
        if residue is None:
            rows.append({
                "protein_id": protein_id, "canonical_position": position, "fasta_aa": fasta_aa,
                "chain": chain, "auth_seq_id": "", "insertion_code": "", "pdb_aa": "",
                "mean_bfactor": "", "mapping_status": "missing_structure_residue",
            })
        else:
            rows.append({
                "protein_id": protein_id, "canonical_position": position, "fasta_aa": fasta_aa,
                "chain": chain, "auth_seq_id": residue["auth_seq_id"],
                "insertion_code": residue["insertion_code"], "pdb_aa": residue["aa"],
                "mean_bfactor": "" if residue["mean_bfactor"] is None else f"{residue['mean_bfactor']:.3f}",
                "mapping_status": "mapped" if residue["aa"] == fasta_aa else "structure_wt_mismatch",
            })
    stats = {
        "chain": chain, "canonical_length": len(sequence), "structure_chain_length": len(chain_residues),
        "mapped_positions": mapped, "matching_positions": matches,
        "mapped_identity": (matches / mapped) if mapped else 0.0,
        "aligned_fasta": aligned_fasta, "aligned_structure": aligned_structure,
    }
    return rows, by_position, stats


def _read_table(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    first = text.splitlines()[0] if text.splitlines() else ""
    delimiter = "\t" if "\t" in first else ","
    return [dict(row) for row in csv.DictReader(text.splitlines(), delimiter=delimiter)]


def read_mutations(path: Path | None, mutations: str | None, protein_id: str, chain: str, numbering: str) -> list[dict]:
    if path:
        rows = _read_table(path)
        if not rows:
            raise ValueError("mutation table contains no rows")
        return rows
    if not mutations:
        raise ValueError("provide --mutations-file or --mutations")
    rows = []
    for index, item in enumerate(filter(None, (part.strip() for part in mutations.split(","))), start=1):
        item_chain = chain
        if ":" in item:
            item_chain, item = item.split(":", 1)
        rows.append({
            "protein_id": protein_id, "variant_id": f"variant_{index}",
            "mutation_group": f"variant_{index}", "mutation": item,
            "chain": item_chain, "numbering": numbering,
        })
    return rows


def normalize_mutations(rows: Iterable[dict], protein_id: str, sequence: str, chain: str,
                        numbering: str, by_position: dict[int, dict]) -> list[dict]:
    auth_lookup = {
        (item["chain"], str(item["auth_seq_id"]), str(item["insertion_code"])): position
        for position, item in by_position.items()
    }
    output: list[dict] = []
    for index, source in enumerate(rows, start=1):
        errors: list[str] = []
        source_protein_id = (source.get("protein_id") or protein_id).strip()
        if source_protein_id != protein_id:
            errors.append("protein_id_mismatch")
        mutation = (source.get("mutation") or "").strip().upper()
        match = MUTATION_RE.fullmatch(mutation)
        wt = match.group(1) if match else ""
        encoded_position = int(match.group(2)) if match else 0
        alt = match.group(3) if match else ""
        if not match or wt not in CANONICAL_AA or alt not in CANONICAL_AA or wt == alt:
            errors.append("invalid_substitution_syntax")
        row_chain = (source.get("chain") or chain).strip()
        if row_chain != chain:
            errors.append("chain_mismatch")
        row_numbering = (source.get("numbering") or numbering).strip().lower()
        auth_seq_id = (source.get("auth_seq_id") or "").strip()
        insertion_code = (source.get("insertion_code") or "").strip()
        canonical_position = encoded_position
        if row_numbering == "pdb-auth":
            auth_seq_id = auth_seq_id or str(encoded_position)
            canonical_position = auth_lookup.get((chain, auth_seq_id, insertion_code), 0)
            if not canonical_position:
                errors.append("pdb_auth_residue_not_mapped")
        elif row_numbering != "sequence":
            errors.append("unsupported_numbering")
        residue = by_position.get(canonical_position)
        fasta_aa = sequence[canonical_position - 1] if 1 <= canonical_position <= len(sequence) else ""
        if not fasta_aa:
            errors.append("canonical_position_out_of_range")
        elif wt and fasta_aa != wt:
            errors.append("fasta_wt_mismatch")
        if residue is None:
            errors.append("missing_structure_residue")
        elif residue["aa"] != wt:
            errors.append("structure_wt_mismatch")
        if residue:
            auth_seq_id = str(residue["auth_seq_id"])
            insertion_code = str(residue["insertion_code"])
        variant_id = (source.get("variant_id") or f"variant_{index}").strip()
        mutation_group = (source.get("mutation_group") or variant_id).strip()
        output.append({
            "protein_id": protein_id, "variant_id": variant_id, "mutation_group": mutation_group,
            "mutation": mutation, "chain": chain, "numbering": row_numbering,
            "canonical_position": canonical_position or "", "auth_seq_id": auth_seq_id,
            "insertion_code": insertion_code, "wt": wt, "alt": alt,
            "pdb_aa": residue["aa"] if residue else "",
            "mean_bfactor": "" if not residue or residue["mean_bfactor"] is None else f"{residue['mean_bfactor']:.3f}",
            "validation_status": "valid" if not errors else "invalid",
            "error": ";".join(dict.fromkeys(errors)),
        })
    return output


def write_tsv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate_inputs(fasta: Path, structure: Path, chain: str, mutations_file: Path | None,
                    mutations: str | None, numbering: str, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    protein_id, sequence = parse_fasta(fasta)
    residues = parse_structure(structure)
    mapping_rows, by_position, alignment = build_mapping(protein_id, sequence, residues, chain)
    mutation_rows = read_mutations(mutations_file, mutations, protein_id, chain, numbering)
    normalized = normalize_mutations(mutation_rows, protein_id, sequence, chain, numbering, by_position)
    mapping_path = output_dir / "residue_mapping.tsv"
    mutations_path = output_dir / "normalized_mutations.tsv"
    write_tsv(mapping_path, mapping_rows, MAPPING_FIELDS)
    write_tsv(mutations_path, normalized, MUTATION_FIELDS)
    summary = {
        "status": "valid" if all(row["validation_status"] == "valid" for row in normalized) else "invalid",
        "protein_id": protein_id, "sequence_length": len(sequence), "structure": str(structure.resolve()),
        "structure_format": "mmcif" if structure.suffix.lower() in {".cif", ".mmcif"} else "pdb",
        "alignment": alignment, "mutation_count": len(normalized),
        "valid_mutation_count": sum(row["validation_status"] == "valid" for row in normalized),
        "artifacts": {"residue_mapping_tsv": str(mapping_path.resolve()), "normalized_mutations_tsv": str(mutations_path.resolve())},
    }
    summary_path = output_dir / "validation.json"
    summary["artifacts"]["validation_json"] = str(summary_path.resolve())
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasta", required=True, type=Path)
    parser.add_argument("--structure", required=True, type=Path, help="PDB, CIF, or mmCIF file")
    parser.add_argument("--chain", default="A")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--mutations-file", type=Path)
    group.add_argument("--mutations", help="Comma-separated substitutions, e.g. A2V,D3N")
    parser.add_argument("--numbering", choices=("sequence", "pdb-auth"), default="sequence")
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        summary = validate_inputs(args.fasta, args.structure, args.chain, args.mutations_file,
                                  args.mutations, args.numbering, args.output_dir)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
