#!/usr/bin/env python3
"""Sequence-first degron motif annotation from ELM, DEGRONOPEDIA, and QCDPred data."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from zipfile import ZipFile
from xml.etree import ElementTree as ET


CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
AMBIGUOUS_AA = set("BXZJUO")
UNIPROT_FASTA = "https://rest.uniprot.org/uniprotkb/{accession}.fasta"
ELM_CLASSES_URL = "http://elm.eu.org/elms/elms_index.tsv"
ELM_INSTANCES_TSV_URL = "http://elm.eu.org/instances.tsv?q=*&taxon=&instance_logic="
ELM_INSTANCES_FASTA_URL = "http://elm.eu.org/instances.fasta?q=*&taxon=&instance_logic="
ELM_INTDOMAINS_URL = "http://elm.eu.org/interactiondomains.tsv"
DEGRONOPEDIA_XLSX_URL = "https://degronopedia.com/degronopedia/download/data/DEGRONOPEDIA_degron_dataset.xlsx/"

QCDPRED_TILE_LENGTH = 17
QCDPRED_MODEL = {
    "intersect": -0.89102423,
    "C": 0.37721431,
    "D": -0.78986558,
    "E": -0.65124014,
    "K": -0.15518666,
    "R": -0.02030300,
    "H": -0.02110156,
    "N": -0.32782161,
    "Q": -0.17676485,
    "A": 0.10844211,
    "G": -0.37594135,
    "S": -0.09627044,
    "T": -0.08533912,
    "V": 0.43746326,
    "M": 0.31182498,
    "L": 0.53427787,
    "I": 0.61465146,
    "F": 0.52882600,
    "Y": 0.45253658,
    "W": 0.58693535,
    "P": -0.25880796,
}

SUMMARY_COLUMNS = [
    "query_id",
    "input_type",
    "length",
    "sequence_sha256",
    "tools",
    "elm_degron_hits",
    "degronopedia_hits",
    "qcdpred_hits",
    "qcdpred_avg_score",
    "qcdpred_median_score",
    "qcdpred_max_score",
    "custom_degron_hits",
    "n_degron_candidates",
    "n_terminal_degrons",
    "n_internal_degrons",
    "n_phosphodegrons",
    "n_unique_motifs",
    "warnings",
]

FEATURE_COLUMNS = [
    "query_id",
    "source",
    "feature_type",
    "start",
    "end",
    "length",
    "accession",
    "name",
    "description",
    "database",
    "interpro_accession",
    "interpro_description",
    "go_terms",
    "pathways",
    "score",
    "evalue",
    "evidence",
    "note",
    "matched_sequence",
    "degron_location",
    "degron_regex",
    "e3_ligase_or_ups_component",
    "license",
    "free_for_any_use",
    "references",
]

QCDPRED_PROFILE_COLUMNS = [
    "query_id",
    "tile_sequence",
    "score",
    "central_aa",
    "residue",
    "profile_source",
]


@dataclass
class SeqRecord:
    seq_id: str
    sequence: str
    input_type: str
    description: str = ""


@dataclass
class PatternRecord:
    source: str
    database: str
    accession: str
    identifier: str
    name: str
    description: str
    regex: str
    location: str
    score: str = ""
    evidence: str = ""
    e3: str = ""
    license: str = ""
    free_for_any_use: str = ""
    references: str = ""
    note: str = ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Annotate degron motif candidates from protein sequences.")
    parser.add_argument("--sequence", action="append", default=[], help="Amino-acid sequence; may be repeated.")
    parser.add_argument("--sequence-name", action="append", default=[], help="Name for each --sequence in order.")
    parser.add_argument("--fasta", action="append", default=[], help="Protein FASTA file; may be repeated.")
    parser.add_argument("--uniprot", action="append", default=[], help="UniProt accession to fetch as FASTA; may be repeated.")
    parser.add_argument(
        "--tools",
        default="elm,degronopedia",
        help="Comma-separated tools/sources to use: elm,degronopedia,qcdpred,custom. Default: elm,degronopedia.",
    )
    parser.add_argument("--elm-classes-tsv", default=None, help="Local ELM classes TSV, e.g. elms_classes.tsv.")
    parser.add_argument("--degronopedia-xlsx", default=None, help="Local DEGRONOPEDIA degron dataset xlsx.")
    parser.add_argument("--degronopedia-tsv", default=None, help="Local DEGRONOPEDIA degron dataset converted TSV.")
    parser.add_argument("--qcdpred-output", action="append", default=[], help="Precomputed QCDPred raw output table; may be repeated.")
    parser.add_argument("--qcdpred-threshold", type=float, default=0.85, help="QCDPred probability cutoff for candidate intervals.")
    parser.add_argument("--qcdpred-padding", type=int, default=8, help="Residues added to both sides of QCDPred-positive center residues.")
    parser.add_argument("--custom-degron", action="append", default=[], help="Custom degron motif as NAME=REGEX; may be repeated.")
    parser.add_argument("--custom-degron-tsv", action="append", default=[], help="TSV with name/regex/location columns.")
    parser.add_argument("--data-dir", default="$HOME/biodata/protein_degron", help="Directory for data download plan.")
    parser.add_argument("--outdir", default="output/protein-degron-annotation", help="Output directory.")
    parser.add_argument("--run-id", default=None, help="Run label; defaults to first query id.")
    parser.add_argument("--allow-ambiguous-aa", action="store_true", help="Allow B/X/Z/J/U/O in input sequences.")
    parser.add_argument("--min-length", type=int, default=1, help="Minimum protein length for local scanning.")
    parser.add_argument("--timeout-sec", type=int, default=30, help="Timeout for UniProt FASTA fetches.")
    return parser


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text).strip())
    return text.strip("_") or "protein"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_tools(value: str) -> List[str]:
    tools = []
    for item in value.split(","):
        item = item.strip().lower()
        if item:
            tools.append(item)
    return tools or ["elm", "degronopedia"]


def read_fasta_text(text: str, input_type: str = "fasta") -> List[SeqRecord]:
    records: List[SeqRecord] = []
    current_id: Optional[str] = None
    current_desc = ""
    chunks: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_id is not None:
                records.append(SeqRecord(current_id, "".join(chunks).upper(), input_type, current_desc))
            header = line[1:].strip()
            parts = header.split(None, 1)
            current_id = safe_name(parts[0] if parts else f"seq{len(records) + 1}")
            current_desc = parts[1] if len(parts) > 1 else ""
            chunks = []
        else:
            chunks.append("".join(line.split()))
    if current_id is not None:
        records.append(SeqRecord(current_id, "".join(chunks).upper(), input_type, current_desc))
    return records


def read_fasta(path: Path) -> List[SeqRecord]:
    return read_fasta_text(path.read_text(encoding="utf-8", errors="replace"), "fasta")


def validate_sequence(record: SeqRecord, allow_ambiguous: bool, min_length: int) -> List[str]:
    warnings: List[str] = []
    allowed = CANONICAL_AA | (AMBIGUOUS_AA if allow_ambiguous else set())
    invalid = sorted(set(record.sequence) - allowed)
    if invalid:
        warnings.append(f"{record.seq_id}:invalid_amino_acids={''.join(invalid)}")
    if len(record.sequence) < min_length:
        warnings.append(f"{record.seq_id}:sequence_shorter_than_min_length={min_length}")
    if not record.sequence:
        warnings.append(f"{record.seq_id}:empty_sequence")
    return warnings


def fetch_uniprot_fasta(accession: str, timeout_sec: int) -> str:
    url = UNIPROT_FASTA.format(accession=accession)
    request = urllib.request.Request(url, headers={"User-Agent": "s2f-agent-protein-degron-annotation/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        return response.read().decode("utf-8", errors="replace")


def load_query_records(args: argparse.Namespace, warnings: List[str]) -> List[SeqRecord]:
    records: List[SeqRecord] = []
    names = list(args.sequence_name or [])
    for idx, sequence in enumerate(args.sequence):
        name = names[idx] if idx < len(names) else f"query_sequence_{idx + 1}"
        sequence = "".join(sequence.split()).upper()
        if sequence.startswith(">"):
            parsed = read_fasta_text(sequence, "raw_fasta_sequence")
            records.extend(parsed)
        else:
            records.append(SeqRecord(safe_name(name), sequence, "raw_sequence"))
    for fasta in args.fasta:
        path = Path(fasta).expanduser()
        if path.exists():
            records.extend(read_fasta(path))
        else:
            warnings.append(f"fasta_missing:{path}")
    for accession in args.uniprot:
        try:
            fetched = fetch_uniprot_fasta(accession, args.timeout_sec)
            parsed = read_fasta_text(fetched, "uniprot")
            if parsed:
                parsed[0].seq_id = safe_name(accession)
                records.extend(parsed)
            else:
                warnings.append(f"uniprot_empty_fasta:{accession}")
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            warnings.append(f"uniprot_fetch_failed:{accession}:{exc}")
    deduped: Dict[str, SeqRecord] = {}
    for record in records:
        record.seq_id = safe_name(record.seq_id)
        deduped.setdefault(record.seq_id, record)
    for record in deduped.values():
        warnings.extend(validate_sequence(record, args.allow_ambiguous_aa, args.min_length))
    return list(deduped.values())


def read_tsv_rows(path: Path) -> List[Dict[str, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    data = "\n".join(line for line in lines if line.strip() and not line.startswith("#"))
    if not data:
        return []
    return list(csv.DictReader(data.splitlines(), delimiter="\t"))


def is_degron_elm(row: Dict[str, str]) -> bool:
    identifier = row.get("ELMIdentifier", "")
    text = " ".join([row.get("FunctionalSiteName", ""), row.get("Description", "")]).lower()
    return identifier.startswith("DEG_") or "degron" in text or "destruction motif" in text


def load_elm_patterns(path: Optional[str], warnings: List[str]) -> List[PatternRecord]:
    if not path:
        warnings.append("elm_classes_tsv_not_provided")
        return []
    tsv = Path(path).expanduser()
    if not tsv.exists():
        warnings.append(f"elm_classes_tsv_missing:{tsv}")
        return []
    patterns: List[PatternRecord] = []
    for row in read_tsv_rows(tsv):
        if not is_degron_elm(row):
            continue
        identifier = row.get("ELMIdentifier", "")
        patterns.append(
            PatternRecord(
                source="ELM",
                database="ELM",
                accession=row.get("Accession", ""),
                identifier=identifier,
                name=row.get("FunctionalSiteName", "") or identifier,
                description=row.get("Description", ""),
                regex=row.get("Regex", ""),
                location=location_from_text(identifier + " " + row.get("FunctionalSiteName", "") + " " + row.get("Regex", "")),
                score=row.get("Probability", ""),
                evidence=f"ELM degron class; instances={row.get('#Instances', '')}; instances_in_pdb={row.get('#Instances_in_PDB', '')}",
                references="ELM class table",
                note="ELM regex match is a candidate unless supported by context, conservation, or curated instance evidence.",
            )
        )
    return patterns


def col_to_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return idx - 1


def load_xlsx_rows(path: Path, preferred_sheet: str = "Degrons") -> List[Dict[str, str]]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    office_rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    with ZipFile(path) as zf:
        shared: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", ns):
                shared.append("".join(t.text or "" for t in si.findall(".//a:t", ns)))
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("r:Relationship", rel_ns)}
        target = ""
        fallback = ""
        for sheet in workbook.findall(".//a:sheet", ns):
            name = sheet.attrib.get("name", "")
            rid = sheet.attrib.get(office_rel, "")
            candidate = "xl/" + rid_to_target.get(rid, "").lstrip("/")
            if name == preferred_sheet:
                target = candidate
                break
            if name.lower() != "readme" and not fallback:
                fallback = candidate
        target = target or fallback
        if not target:
            return []
        worksheet = ET.fromstring(zf.read(target))
        matrix: List[List[str]] = []
        for row in worksheet.findall(".//a:row", ns):
            values: List[str] = []
            for cell in row.findall("a:c", ns):
                index = col_to_index(cell.attrib.get("r", "A1"))
                while len(values) <= index:
                    values.append("")
                value = ""
                value_node = cell.find("a:v", ns)
                if value_node is not None and value_node.text is not None:
                    value = value_node.text
                    if cell.attrib.get("t") == "s":
                        value = shared[int(value)] if value.isdigit() and int(value) < len(shared) else value
                elif cell.attrib.get("t") == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//a:t", ns))
                values[index] = value
            if any(values):
                matrix.append(values)
        if not matrix:
            return []
        headers = [str(value).strip() for value in matrix[0]]
        rows: List[Dict[str, str]] = []
        for values in matrix[1:]:
            row = {headers[i]: (values[i] if i < len(values) else "") for i in range(len(headers)) if headers[i]}
            if any(str(v).strip() for v in row.values()):
                rows.append(row)
        return rows


def load_degronopedia_patterns(args: argparse.Namespace, warnings: List[str]) -> List[PatternRecord]:
    rows: List[Dict[str, str]] = []
    source_path = ""
    if args.degronopedia_tsv:
        tsv = Path(args.degronopedia_tsv).expanduser()
        if tsv.exists():
            rows = read_tsv_rows(tsv)
            source_path = str(tsv)
        else:
            warnings.append(f"degronopedia_tsv_missing:{tsv}")
    elif args.degronopedia_xlsx:
        xlsx = Path(args.degronopedia_xlsx).expanduser()
        if xlsx.exists():
            try:
                rows = load_xlsx_rows(xlsx)
                source_path = str(xlsx)
            except Exception as exc:
                warnings.append(f"degronopedia_xlsx_parse_failed:{xlsx}:{exc}")
        else:
            warnings.append(f"degronopedia_xlsx_missing:{xlsx}")
    else:
        warnings.append("degronopedia_dataset_not_provided")
    patterns: List[PatternRecord] = []
    for row in rows:
        regex = row.get("Degron_regex") or row.get("regex") or row.get("Regex") or ""
        name = row.get("Degron") or row.get("name") or regex
        if not regex:
            continue
        refs = join_nonempty([row.get("Degron_references_doi", ""), row.get("Degron_references_PMID", "")])
        patterns.append(
            PatternRecord(
                source="DEGRONOPEDIA",
                database="DEGRONOPEDIA",
                accession="",
                identifier=name,
                name=name,
                description=row.get("Degron_additional_info", "") or name,
                regex=regex,
                location=row.get("Degron_location", "") or location_from_text(name + " " + regex),
                evidence="DEGRONOPEDIA curated degron dataset",
                e3=row.get("Known_UPS_components_recognizing_degron", ""),
                license=row.get("Degron_licence", ""),
                free_for_any_use=row.get("Free_for_any_use", ""),
                references=refs,
                note=f"Dataset={source_path}; license varies by degron and must be checked before commercial use.",
            )
        )
    return patterns


def load_custom_patterns(args: argparse.Namespace, warnings: List[str]) -> List[PatternRecord]:
    patterns: List[PatternRecord] = []
    for item in args.custom_degron:
        if "=" not in item:
            warnings.append(f"custom_degron_invalid:{item}")
            continue
        name, regex = item.split("=", 1)
        patterns.append(
            PatternRecord(
                source="custom",
                database="custom",
                accession="",
                identifier=name.strip(),
                name=name.strip(),
                description="User-provided degron motif",
                regex=regex.strip(),
                location=location_from_text(name + " " + regex),
                evidence="user_provided_regex",
                note="Custom degron motif supplied by user.",
            )
        )
    for tsv_path in args.custom_degron_tsv:
        path = Path(tsv_path).expanduser()
        if not path.exists():
            warnings.append(f"custom_degron_tsv_missing:{path}")
            continue
        for row in read_tsv_rows(path):
            name = row.get("name") or row.get("motif") or row.get("Degron") or "custom_degron"
            regex = row.get("regex") or row.get("Degron_regex") or row.get("pattern") or ""
            if not regex:
                continue
            patterns.append(
                PatternRecord(
                    source="custom",
                    database="custom",
                    accession=row.get("accession", ""),
                    identifier=name,
                    name=name,
                    description=row.get("description", "User-provided degron motif"),
                    regex=regex,
                    location=row.get("location", "") or location_from_text(name + " " + regex),
                    evidence=row.get("evidence", "user_provided_regex"),
                    e3=row.get("e3_ligase_or_ups_component", ""),
                    references=row.get("references", ""),
                    note=f"Custom motif imported from {path.name}.",
                )
            )
    return patterns


def location_from_text(text: str) -> str:
    lower = text.lower()
    if "nend" in lower or "n-degron" in lower or "n-terminal" in lower or lower.startswith("^") or "^m" in lower:
        return "N-terminus"
    if "cend" in lower or "c-terminal" in lower or lower.rstrip().endswith("$"):
        return "C-terminus"
    return "Internal"


def join_nonempty(values: Iterable[Any]) -> str:
    return ";".join(str(v).strip() for v in values if str(v).strip())


def is_phosphodegron(pattern: PatternRecord) -> bool:
    text = " ".join([pattern.identifier, pattern.name, pattern.description]).lower()
    return "phosphodegron" in text or "phospho" in text


def scan_patterns(record: SeqRecord, patterns: Sequence[PatternRecord], warnings: List[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    seen_warnings: set[str] = set()
    for pattern in patterns:
        regex = pattern.regex.strip()
        if not regex:
            continue
        try:
            compiled = re.compile(f"(?=({regex}))")
        except re.error as exc:
            key = f"invalid_regex:{pattern.source}:{pattern.identifier}:{exc}"
            if key not in seen_warnings:
                warnings.append(key)
                seen_warnings.add(key)
            continue
        for match in compiled.finditer(record.sequence):
            matched = match.group(1)
            if not matched:
                continue
            start = match.start(1) + 1
            end = match.end(1)
            location = pattern.location or location_from_text(pattern.name + " " + regex)
            feature_type = "phosphodegron_candidate" if is_phosphodegron(pattern) else "degron_candidate"
            if location.lower().startswith(("n-", "c-")):
                feature_type = "terminal_" + feature_type
            note_parts = [pattern.note, f"regex={regex}"]
            if is_phosphodegron(pattern):
                note_parts.append("candidate may require phosphorylation or other context for activity")
            rows.append(
                {
                    "query_id": record.seq_id,
                    "source": pattern.source,
                    "feature_type": feature_type,
                    "start": str(start),
                    "end": str(end),
                    "length": str(end - start + 1),
                    "accession": pattern.accession,
                    "name": pattern.name or pattern.identifier,
                    "description": pattern.description,
                    "database": pattern.database,
                    "interpro_accession": "",
                    "interpro_description": "",
                    "go_terms": "",
                    "pathways": "",
                    "score": pattern.score,
                    "evalue": "",
                    "evidence": pattern.evidence,
                    "note": "; ".join(part for part in note_parts if part),
                    "matched_sequence": matched,
                    "degron_location": location,
                    "degron_regex": regex,
                    "e3_ligase_or_ups_component": pattern.e3,
                    "license": pattern.license,
                    "free_for_any_use": pattern.free_for_any_use,
                    "references": pattern.references,
                }
            )
    return rows


def qcdpred_probability(tile: str) -> float:
    linear = QCDPRED_MODEL["intersect"] + sum(QCDPRED_MODEL[aa] for aa in tile)
    return 1.0 / (1.0 + math.exp(-linear))


def qcdpred_profile(record: SeqRecord, warnings: List[str]) -> List[Dict[str, str]]:
    if len(record.sequence) < QCDPRED_TILE_LENGTH:
        warnings.append(f"{record.seq_id}:qcdpred_requires_sequence_length_at_least_{QCDPRED_TILE_LENGTH}")
        return []
    rows: List[Dict[str, str]] = []
    skipped = 0
    for start in range(0, len(record.sequence) - QCDPRED_TILE_LENGTH + 1):
        tile = record.sequence[start : start + QCDPRED_TILE_LENGTH]
        if set(tile) - CANONICAL_AA:
            skipped += 1
            continue
        score = qcdpred_probability(tile)
        rows.append(
            {
                "query_id": record.seq_id,
                "tile_sequence": tile,
                "score": f"{score:.5f}",
                "central_aa": tile[8],
                "residue": str(start + 9),
                "profile_source": "native_python_qcdpred_model",
            }
        )
    if skipped:
        warnings.append(f"{record.seq_id}:qcdpred_skipped_noncanonical_windows={skipped}")
    return rows


def parse_float(value: Any) -> Optional[float]:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> Optional[int]:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def normalize_qcdpred_row(row: Dict[str, str], source_name: str, warnings: List[str]) -> Optional[Dict[str, str]]:
    query_id = row.get("query_id") or row.get("name") or row.get("protein") or row.get("id") or ""
    tile = row.get("tile_sequence") or row.get("seq") or row.get("sequence") or row.get("tile") or ""
    score = parse_float(row.get("score") or row.get("probability") or row.get("qcdpred") or row.get("QCDpred"))
    residue = parse_int(row.get("residue") or row.get("resi") or row.get("position") or row.get("pos"))
    central_aa = row.get("central_aa") or row.get("aa") or (tile[8] if len(tile) >= 9 else "")
    if not query_id or score is None or residue is None:
        warnings.append(f"qcdpred_output_row_skipped:{source_name}")
        return None
    return {
        "query_id": safe_name(query_id),
        "tile_sequence": tile,
        "score": f"{score:.5f}",
        "central_aa": central_aa,
        "residue": str(residue),
        "profile_source": source_name,
    }


def read_qcdpred_output(path: Path, warnings: List[str]) -> List[Dict[str, str]]:
    if not path.exists():
        warnings.append(f"qcdpred_output_missing:{path}")
        return []
    rows: List[Dict[str, str]] = []
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    if not lines:
        return rows
    first = lines[0].split()
    has_header = any(token.lower() in {"query_id", "name", "score", "resi", "residue"} for token in first)
    if has_header:
        header = first
        data_lines = lines[1:]
        for line in data_lines:
            values = line.split()
            row = {header[i]: values[i] if i < len(values) else "" for i in range(len(header))}
            normalized = normalize_qcdpred_row(row, path.name, warnings)
            if normalized:
                rows.append(normalized)
    else:
        for line in lines:
            values = line.split()
            if len(values) < 5:
                warnings.append(f"qcdpred_output_short_row:{path.name}:{line[:80]}")
                continue
            row = {"name": values[0], "seq": values[1], "score": values[2], "aa": values[3], "resi": values[4]}
            normalized = normalize_qcdpred_row(row, path.name, warnings)
            if normalized:
                rows.append(normalized)
    return rows


def merge_ranges(ranges: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    merged: List[Tuple[int, int]] = []
    for start, end in sorted(ranges):
        if not merged or start > merged[-1][1] + 1:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def qcdpred_features_for_record(
    record: SeqRecord,
    profile_rows: Sequence[Dict[str, str]],
    threshold: float,
    padding: int,
) -> List[Dict[str, str]]:
    usable: List[Tuple[int, float, Dict[str, str]]] = []
    for row in profile_rows:
        if row.get("query_id") != record.seq_id:
            continue
        residue = parse_int(row.get("residue"))
        score = parse_float(row.get("score"))
        if residue is None or score is None:
            continue
        usable.append((residue, score, row))
    positive = [(residue, score) for residue, score, _ in usable if score >= threshold]
    intervals = merge_ranges(
        (max(1, residue - padding), min(len(record.sequence), residue + padding)) for residue, _ in positive
    )
    features: List[Dict[str, str]] = []
    for start, end in intervals:
        interval_scores = [score for residue, score, _ in usable if start <= residue <= end]
        positive_residues = [str(residue) for residue, score in positive if start <= residue <= end]
        if not interval_scores:
            continue
        max_score = max(interval_scores)
        mean_score = sum(interval_scores) / len(interval_scores)
        median_score = median(interval_scores)
        if start == 1:
            location = "N-terminus"
        elif end == len(record.sequence):
            location = "C-terminus"
        else:
            location = "Internal"
        note = (
            f"threshold={threshold:g}; padding={padding}; tile_length={QCDPRED_TILE_LENGTH}; "
            f"positive_center_residues={','.join(positive_residues)}; "
            f"qcdpred_mean_score={mean_score:.5f}; qcdpred_median_score={median_score:.5f}; "
            "model=Johansson_et_al_QCDPred_17aa_logistic_regression"
        )
        features.append(
            {
                "query_id": record.seq_id,
                "source": "QCDPred",
                "feature_type": "quality_control_degron_candidate",
                "start": str(start),
                "end": str(end),
                "length": str(end - start + 1),
                "accession": "",
                "name": "QCDPred high-scoring QCD interval",
                "description": "Quality-control degron candidate interval from QCDPred 17-aa composition model.",
                "database": "QCDPred",
                "interpro_accession": "",
                "interpro_description": "",
                "go_terms": "",
                "pathways": "",
                "score": f"{max_score:.5f}",
                "evalue": "",
                "evidence": "QCDPred probability score from 17-aa peptide logistic regression model.",
                "note": note,
                "matched_sequence": record.sequence[start - 1 : end],
                "degron_location": location,
                "degron_regex": "",
                "e3_ligase_or_ups_component": "quality-control-associated proteolysis context; E3 not specified",
                "license": "",
                "free_for_any_use": "",
                "references": "Johansson et al. QCDPred; KULL-Centre papers 2022 degron-predict repository",
            }
        )
    return features


def qcdpred_score_summary(profile_rows: Sequence[Dict[str, str]], query_id: str) -> Tuple[str, str, str]:
    scores = [
        score
        for row in profile_rows
        if row.get("query_id") == query_id
        for score in [parse_float(row.get("score"))]
        if score is not None
    ]
    if not scores:
        return "", "", ""
    return f"{sum(scores) / len(scores):.5f}", f"{median(scores):.5f}", f"{max(scores):.5f}"


def summarize_record(
    record: SeqRecord,
    rows: Sequence[Dict[str, str]],
    tools: Sequence[str],
    warnings: Sequence[str],
    qcdpred_rows: Sequence[Dict[str, str]] = (),
) -> Dict[str, str]:
    by_source = {"ELM": 0, "DEGRONOPEDIA": 0, "QCDPred": 0, "custom": 0}
    terminal = 0
    internal = 0
    phospho = 0
    motifs: set[str] = set()
    for row in rows:
        source = row.get("source", "")
        by_source[source] = by_source.get(source, 0) + 1
        location = row.get("degron_location", "").lower()
        if location.startswith(("n-", "c-")):
            terminal += 1
        else:
            internal += 1
        if "phospho" in row.get("feature_type", "").lower() or "phospho" in row.get("name", "").lower():
            phospho += 1
        if row.get("name"):
            motifs.add(row["name"])
    qcd_avg, qcd_median, qcd_max = qcdpred_score_summary(qcdpred_rows, record.seq_id)
    return {
        "query_id": record.seq_id,
        "input_type": record.input_type,
        "length": str(len(record.sequence)),
        "sequence_sha256": sha256_text(record.sequence),
        "tools": ",".join(tools),
        "elm_degron_hits": str(by_source.get("ELM", 0)),
        "degronopedia_hits": str(by_source.get("DEGRONOPEDIA", 0)),
        "qcdpred_hits": str(by_source.get("QCDPred", 0)),
        "qcdpred_avg_score": qcd_avg,
        "qcdpred_median_score": qcd_median,
        "qcdpred_max_score": qcd_max,
        "custom_degron_hits": str(by_source.get("custom", 0)),
        "n_degron_candidates": str(len(rows)),
        "n_terminal_degrons": str(terminal),
        "n_internal_degrons": str(internal),
        "n_phosphodegrons": str(phospho),
        "n_unique_motifs": str(len(motifs)),
        "warnings": ";".join(w for w in warnings if w.startswith(record.seq_id + ":")),
    }


def write_tsv(path: Path, rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def shell_path_assignment(value: str) -> str:
    if value.startswith("$HOME/"):
        return '"${HOME}/' + value[len("$HOME/") :].replace('"', '\\"') + '"'
    if value.startswith("~/"):
        return '"${HOME}/' + value[len("~/") :].replace('"', '\\"') + '"'
    return shell_quote(value)


def write_plans(args: argparse.Namespace, outdir: Path) -> Dict[str, str]:
    commands_path = outdir / "commands.sh"
    download_path = outdir / "database_download_plan.sh"
    script = "skills/protein-degron-annotation/scripts/protein_degron_annotation.py"
    commands = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Example local scan after reviewing/downloading ELM and DEGRONOPEDIA data:",
        (
            f"python {script} --fasta <PROTEINS_FASTA> "
            "--elm-classes-tsv \"$DB_DIR/elms_classes.tsv\" "
            "--degronopedia-xlsx \"$DB_DIR/DEGRONOPEDIA_degron_dataset.xlsx\" "
            "--tools elm,degronopedia,qcdpred "
            "--outdir output/protein-degron-annotation/<RUN_ID>"
        ),
        "",
        "# QCDPred is built into this wrapper from the published 17-aa logistic model; no database is required.",
        f"python {script} --sequence <AA_SEQUENCE> --sequence-name <QUERY_ID> --tools qcdpred --outdir output/protein-degron-annotation/<RUN_ID>_qcdpred",
        "",
        "# To reuse output generated by the original QCDpred.py, provide the raw five-column table:",
        f"python {script} --fasta <PROTEINS_FASTA> --tools qcdpred --qcdpred-output <QCDPRED_OUTPUT_TXT> --outdir output/protein-degron-annotation/<RUN_ID>_qcdpred_import",
        "",
        "# ELM hosted API exists but must be rate-limited: UniProt <= 1 query per 3 minutes; raw sequence <= 1 query per minute.",
        "# Prefer local ELM TSV scans for batch annotation and reproducibility.",
        "# DEGRONOPEDIA is an online service with one-protein-at-a-time submissions; import its downloaded xlsx output when manual web analysis is needed.",
    ]
    commands_path.write_text("\n".join(commands) + "\n", encoding="utf-8")
    os.chmod(commands_path, 0o755)

    db_dir = args.data_dir or "$HOME/biodata/protein_degron"
    downloads = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Review licenses and obtain user approval before running this script.",
        "# ELM data are distributed under the ELM academic/non-commercial license.",
        "# DEGRONOPEDIA degron licenses vary by source; inspect the license columns before commercial use.",
        f"DB_DIR={shell_path_assignment(db_dir)}",
        "mkdir -p \"$DB_DIR\"",
        "",
        f"curl -L --fail --retry 3 --retry-delay 5 --max-time 180 -o \"$DB_DIR/elms_classes.tsv\" {ELM_CLASSES_URL}",
        f"curl -L --fail --retry 3 --retry-delay 5 --max-time 180 -o \"$DB_DIR/elm_instances.tsv\" {shell_quote(ELM_INSTANCES_TSV_URL)}",
        f"curl -L --fail --retry 3 --retry-delay 5 --max-time 180 -o \"$DB_DIR/elm_instances.fasta\" {shell_quote(ELM_INSTANCES_FASTA_URL)}",
        f"curl -L --fail --retry 3 --retry-delay 5 --max-time 180 -o \"$DB_DIR/elm_interaction_domains.tsv\" {ELM_INTDOMAINS_URL}",
        f"curl -L --fail --retry 3 --retry-delay 5 --max-time 180 -o \"$DB_DIR/DEGRONOPEDIA_degron_dataset.xlsx\" {DEGRONOPEDIA_XLSX_URL}",
    ]
    download_path.write_text("\n".join(downloads) + "\n", encoding="utf-8")
    os.chmod(download_path, 0o755)
    return {"commands_sh": str(commands_path), "database_download_plan_sh": str(download_path)}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    outdir = Path(args.outdir).expanduser()
    safe_mkdir(outdir)
    warnings: List[str] = []
    tools = parse_tools(args.tools)
    if args.qcdpred_output and "qcdpred" not in tools:
        tools.append("qcdpred")
    records = load_query_records(args, warnings)
    artifacts = write_plans(args, outdir)

    patterns: List[PatternRecord] = []
    if "elm" in tools:
        patterns.extend(load_elm_patterns(args.elm_classes_tsv, warnings))
    if "degronopedia" in tools:
        patterns.extend(load_degronopedia_patterns(args, warnings))
    if "custom" in tools or args.custom_degron or args.custom_degron_tsv:
        patterns.extend(load_custom_patterns(args, warnings))

    imported_qcdpred_rows: Dict[str, List[Dict[str, str]]] = {}
    for qcdpred_output in args.qcdpred_output:
        path = Path(qcdpred_output).expanduser()
        for row in read_qcdpred_output(path, warnings):
            imported_qcdpred_rows.setdefault(row["query_id"], []).append(row)

    qcdpred_rows_by_record: Dict[str, List[Dict[str, str]]] = {}
    qcdpred_profile_rows: List[Dict[str, str]] = []
    if "qcdpred" in tools:
        for record in records:
            rows_for_record = imported_qcdpred_rows.get(record.seq_id)
            if rows_for_record is None:
                rows_for_record = qcdpred_profile(record, warnings)
            qcdpred_rows_by_record[record.seq_id] = rows_for_record
            qcdpred_profile_rows.extend(rows_for_record)

    normalized_fasta = outdir / "normalized_input.fasta"
    with normalized_fasta.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(f">{record.seq_id} {record.description}\n")
            for i in range(0, len(record.sequence), 80):
                handle.write(record.sequence[i : i + 80] + "\n")
    artifacts["normalized_input_fasta"] = str(normalized_fasta)

    all_features: List[Dict[str, str]] = []
    summary_rows: List[Dict[str, str]] = []
    for record in records:
        record_rows = scan_patterns(record, patterns, warnings)
        if "qcdpred" in tools:
            record_rows.extend(
                qcdpred_features_for_record(
                    record,
                    qcdpred_rows_by_record.get(record.seq_id, []),
                    args.qcdpred_threshold,
                    args.qcdpred_padding,
                )
            )
        all_features.extend(record_rows)
        summary_rows.append(
            summarize_record(record, record_rows, tools, warnings, qcdpred_rows_by_record.get(record.seq_id, []))
        )
    if not records:
        warnings.append("no_query_sequences_provided")
    if not patterns and any(tool in {"elm", "degronopedia", "custom"} for tool in tools):
        warnings.append("no_degron_patterns_loaded")

    summary_path = outdir / "protein_degron_summary.tsv"
    features_path = outdir / "protein_degron_features.tsv"
    qcdpred_profile_path = outdir / "qcdpred_profile.tsv"
    result_path = outdir / "protein_degron_annotation.result.json"
    write_tsv(summary_path, summary_rows, SUMMARY_COLUMNS)
    write_tsv(features_path, all_features, FEATURE_COLUMNS)
    write_tsv(qcdpred_profile_path, qcdpred_profile_rows, QCDPRED_PROFILE_COLUMNS)
    artifacts.update(
        {
            "summary_tsv": str(summary_path),
            "features_tsv": str(features_path),
            "qcdpred_profile_tsv": str(qcdpred_profile_path),
            "result_json": str(result_path),
        }
    )
    report = {
        "skill": "protein-degron-annotation",
        "status": "warning" if warnings else "success",
        "run_id": safe_name(args.run_id or (records[0].seq_id if records else "protein_degron_annotation")),
        "created_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "parameters": {
            "tools": tools,
            "elm_classes_tsv": args.elm_classes_tsv,
            "degronopedia_xlsx": args.degronopedia_xlsx,
            "degronopedia_tsv": args.degronopedia_tsv,
            "qcdpred_output": args.qcdpred_output,
            "qcdpred_threshold": args.qcdpred_threshold,
            "qcdpred_padding": args.qcdpred_padding,
            "data_dir": args.data_dir,
            "allow_ambiguous_aa": args.allow_ambiguous_aa,
        },
        "counts": {
            "queries": len(records),
            "patterns_loaded": len(patterns),
            "qcdpred_profile_rows": len(qcdpred_profile_rows),
            "feature_rows": len(all_features),
        },
        "artifacts": artifacts,
        "warnings": warnings,
    }
    write_json(result_path, report)
    print(f"[OK] Degron annotation written to {outdir}")
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
