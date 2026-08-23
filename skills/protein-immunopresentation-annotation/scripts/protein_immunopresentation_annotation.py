#!/usr/bin/env python3
"""Annotate MHC-I immunopresentation candidates from protein sequences."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
AMBIGUOUS_AA = set("BXZJUO")
IEDB_MHCI_METADATA_URL = "https://api-nextgen-tools.iedb.org/api/v1/mhci"
IEDB_LEGACY_MHCI_URL = "https://tools-cluster-interface.iedb.org/tools_api/mhci/"
IEDB_LEGACY_PROCESSING_URL = "https://tools-cluster-interface.iedb.org/tools_api/processing/"
IEDB_LEGACY_IMMUNOGENICITY_URL = "https://tools-cluster-interface.iedb.org/tools_api/immunogenicity/"
IEDB_NG_TC1_README_URL = "https://downloads.iedb.org/nextgen-tools/tcell_mhci/LATEST/README"
IEDB_NG_TC1_TARBALL_URL = "https://downloads.iedb.org/nextgen-tools/tcell_mhci/LATEST/IEDB_NG_TC1-0.1.5-beta.tar.gz"
IEDB_NG_TC1_MD5_URL = "https://downloads.iedb.org/nextgen-tools/tcell_mhci/LATEST/MD5SUM"

DEFAULT_ALLELES = [
    "HLA-A*01:01",
    "HLA-A*02:01",
    "HLA-A*02:03",
    "HLA-A*02:06",
    "HLA-A*03:01",
    "HLA-A*11:01",
    "HLA-A*23:01",
    "HLA-A*24:02",
    "HLA-A*26:01",
    "HLA-A*30:01",
    "HLA-A*30:02",
    "HLA-A*31:01",
    "HLA-A*32:01",
    "HLA-A*33:01",
    "HLA-A*68:01",
    "HLA-A*68:02",
    "HLA-B*07:02",
    "HLA-B*08:01",
    "HLA-B*15:01",
    "HLA-B*35:01",
    "HLA-B*40:01",
    "HLA-B*44:02",
    "HLA-B*44:03",
    "HLA-B*51:01",
    "HLA-B*53:01",
    "HLA-B*57:01",
    "HLA-B*58:01",
]

PEPTIDE_COLUMNS = [
    "query_id",
    "protein_length",
    "peptide_start",
    "peptide_end",
    "peptide_length",
    "peptide_sequence",
]

BINDING_COLUMNS = [
    "query_id",
    "peptide_start",
    "peptide_end",
    "peptide_length",
    "peptide_sequence",
    "allele",
    "predictor",
    "rank",
    "score",
    "ic50_nm",
    "binder_level",
    "raw_source",
    "raw_columns_json",
]

PROCESSING_COLUMNS = [
    "query_id",
    "peptide_start",
    "peptide_end",
    "peptide_length",
    "peptide_sequence",
    "allele",
    "predictor",
    "proteasome_score",
    "tap_score",
    "mhc_binding_score",
    "processing_score",
    "total_score",
    "processing_support",
    "raw_source",
    "raw_columns_json",
]

IMMUNOGENICITY_COLUMNS = [
    "query_id",
    "peptide_start",
    "peptide_end",
    "peptide_length",
    "peptide_sequence",
    "immunogenicity_score",
    "raw_source",
    "raw_columns_json",
]

CANDIDATE_COLUMNS = [
    "query_id",
    "protein_length",
    "peptide_start",
    "peptide_end",
    "peptide_length",
    "peptide_sequence",
    "allele_count_tested",
    "strong_binding_alleles",
    "weak_binding_alleles",
    "best_el_rank",
    "best_ba_rank",
    "best_rank",
    "best_score",
    "best_ic50_nm",
    "best_binding_predictor",
    "processing_support",
    "processing_score",
    "proteasome_score",
    "tap_score",
    "mhc_binding_score",
    "total_score",
    "immunogenicity_score",
    "overlaps_signal_peptide",
    "overlaps_tm",
    "overlaps_idr",
    "overlaps_domain",
    "overlaps_conserved_region",
    "context_features",
    "candidate_grade",
    "evidence",
    "note",
]

SUMMARY_COLUMNS = [
    "query_id",
    "input_type",
    "protein_length",
    "sequence_sha256",
    "n_peptides_generated",
    "n_predictions",
    "n_strong_binder_peptides",
    "n_weak_binder_peptides",
    "n_high_confidence_candidates",
    "n_weak_candidates",
    "n_unlikely_candidates",
    "alleles",
    "peptide_lengths",
    "predictors",
    "warnings",
]


@dataclass
class SeqRecord:
    seq_id: str
    sequence: str
    input_type: str
    description: str = ""


@dataclass
class ContextFeature:
    query_id: str
    start: int
    end: int
    source: str
    feature_type: str
    name: str
    category: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Annotate MHC-I immunopresentation candidates.")
    parser.add_argument("--sequence", action="append", default=[], help="Amino-acid sequence; may be repeated.")
    parser.add_argument("--sequence-name", action="append", default=[], help="Name for each --sequence in order.")
    parser.add_argument("--fasta", action="append", default=[], help="Protein FASTA file; may be repeated.")
    parser.add_argument("--allele", action="append", default=[], help="HLA allele; may be repeated or comma-separated.")
    parser.add_argument("--alleles", default=None, help="Comma-separated HLA allele list. Overrides default reference set.")
    parser.add_argument("--peptide-lengths", default="8,9,10,11", help="Comma-separated MHC-I peptide lengths.")
    parser.add_argument("--binding-predictors", default="netmhcpan_el,netmhcpan_ba", help="Comma-separated IEDB MHC-I predictors.")
    parser.add_argument("--processing-predictor", default="netmhcpan_ba", help="IEDB processing binding method with IC50 support.")
    parser.add_argument("--proteasome", default="immuno", choices=["immuno", "constitutive"], help="Proteasome setting for processing.")
    parser.add_argument("--strong-rank-cutoff", type=float, default=0.5, help="Percentile rank cutoff for strong binders.")
    parser.add_argument("--weak-rank-cutoff", type=float, default=2.0, help="Percentile rank cutoff for weak binders.")
    parser.add_argument("--strong-ic50-cutoff", type=float, default=50.0, help="IC50 nM cutoff for strong binders.")
    parser.add_argument("--weak-ic50-cutoff", type=float, default=500.0, help="IC50 nM cutoff for weak binders.")
    parser.add_argument("--immunogenicity-min-score", type=float, default=0.0, help="Minimum immunogenicity score for high confidence if available.")
    parser.add_argument("--api-mode", choices=["legacy", "nextgen"], default="legacy", help="API payload style.")
    parser.add_argument("--api-url", default=IEDB_LEGACY_MHCI_URL, help="MHC-I binding API URL.")
    parser.add_argument("--processing-api-url", default=IEDB_LEGACY_PROCESSING_URL, help="MHC-I processing API URL.")
    parser.add_argument("--immunogenicity-api-url", default=IEDB_LEGACY_IMMUNOGENICITY_URL, help="Immunogenicity API URL.")
    parser.add_argument("--execute-api", action="store_true", help="Submit to IEDB API. Otherwise only write request plans.")
    parser.add_argument("--execute-processing", action="store_true", help="Submit processing API requests when --execute-api is set.")
    parser.add_argument("--execute-immunogenicity", action="store_true", help="Submit immunogenicity API requests when --execute-api is set.")
    parser.add_argument("--iedb-local-tools-dir", default=None, help="Unpacked IEDB Next-Generation TC1 directory containing src/tcell_mhci.py.")
    parser.add_argument("--iedb-wrapper-repo", default=None, help="Optional qinti2023/IEDB wrapper repo containing IEDB_predict.py and fasta_to_json.py for reproducing the original pipeline.")
    parser.add_argument("--local-workdir", default=None, help="Working directory for local IEDB NG TC1 split/predict/aggregate jobs.")
    parser.add_argument("--local-python", default=sys.executable, help="Python executable for local IEDB NG TC1 commands.")
    parser.add_argument("--local-max-workers", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)), help="Maximum parallel workers for local job execution.")
    parser.add_argument("--execute-local", action="store_true", help="Run local IEDB NG TC1 jobs after writing the local input JSON.")
    parser.add_argument("--api-result-tsv", action="append", default=[], help="IEDB MHC-I binding result TSV to import.")
    parser.add_argument("--processing-result-tsv", action="append", default=[], help="IEDB processing result TSV to import.")
    parser.add_argument("--immunogenicity-result-tsv", action="append", default=[], help="IEDB immunogenicity result TSV to import.")
    parser.add_argument("--api-result-json", action="append", default=[], help="IEDB next-gen/local aggregated JSON to import.")
    parser.add_argument("--local-result-json", action="append", default=[], help="Alias for local IEDB NG TC1 aggregate/aggregated_result.json import.")
    parser.add_argument("--context-features-tsv", action="append", default=[], help="Feature TSV for peptide overlap context; may be repeated.")
    parser.add_argument("--localization-features-tsv", action="append", default=[], help="Alias for --context-features-tsv.")
    parser.add_argument("--tm-features-tsv", action="append", default=[], help="Alias for --context-features-tsv.")
    parser.add_argument("--idr-regions-tsv", action="append", default=[], help="Alias for --context-features-tsv.")
    parser.add_argument("--domain-features-tsv", action="append", default=[], help="Alias for --context-features-tsv.")
    parser.add_argument("--conservation-features-tsv", action="append", default=[], help="Alias for --context-features-tsv.")
    parser.add_argument("--outdir", default="output/protein-immunopresentation-annotation", help="Output directory.")
    parser.add_argument("--run-id", default=None, help="Run label; defaults to first query id.")
    parser.add_argument("--allow-ambiguous-aa", action="store_true", help="Allow B/X/Z/J/U/O in input sequences.")
    parser.add_argument("--min-length", type=int, default=8, help="Minimum protein length.")
    parser.add_argument("--timeout-sec", type=int, default=120, help="API timeout.")
    return parser


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text).strip())
    return text.strip("_") or "protein"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_csv_list(value: Optional[str]) -> List[str]:
    if not value:
        return []
    out: List[str] = []
    for part in value.split(","):
        part = part.strip()
        if part:
            out.append(part)
    return out


def unique_preserve(values: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for value in values:
        if value and value not in seen:
            out.append(value)
            seen.add(value)
    return out


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


def load_query_records(args: argparse.Namespace, warnings: List[str]) -> List[SeqRecord]:
    records: List[SeqRecord] = []
    names = list(args.sequence_name or [])
    for idx, sequence in enumerate(args.sequence):
        name = names[idx] if idx < len(names) else f"query_sequence_{idx + 1}"
        sequence = "".join(sequence.split()).upper()
        if sequence.startswith(">"):
            records.extend(read_fasta_text(sequence, "raw_fasta_sequence"))
        else:
            records.append(SeqRecord(safe_name(name), sequence, "raw_sequence"))
    for fasta in args.fasta:
        path = Path(fasta).expanduser()
        if path.exists():
            records.extend(read_fasta(path))
        else:
            warnings.append(f"fasta_missing:{path}")
    deduped: Dict[str, SeqRecord] = {}
    for record in records:
        record.seq_id = safe_name(record.seq_id)
        deduped.setdefault(record.seq_id, record)
    for record in deduped.values():
        warnings.extend(validate_sequence(record, args.allow_ambiguous_aa, args.min_length))
    return list(deduped.values())


def normalized_fasta(records: Sequence[SeqRecord]) -> str:
    chunks: List[str] = []
    for record in records:
        chunks.append(f">{record.seq_id} {record.description}".rstrip())
        for i in range(0, len(record.sequence), 80):
            chunks.append(record.sequence[i : i + 80])
    return "\n".join(chunks) + ("\n" if chunks else "")


def generate_peptides(records: Sequence[SeqRecord], lengths: Sequence[int], warnings: List[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for record in records:
        for length in lengths:
            if length < 8 or length > 15:
                warnings.append(f"unsupported_mhci_length:{length}:expected_8_to_15")
                continue
            if len(record.sequence) < length:
                continue
            for start0 in range(0, len(record.sequence) - length + 1):
                peptide = record.sequence[start0 : start0 + length]
                rows.append(
                    {
                        "query_id": record.seq_id,
                        "protein_length": str(len(record.sequence)),
                        "peptide_start": str(start0 + 1),
                        "peptide_end": str(start0 + length),
                        "peptide_length": str(length),
                        "peptide_sequence": peptide,
                    }
                )
    return rows


def delimiter_for_text(text: str) -> str:
    first = next((line for line in text.splitlines() if line.strip()), "")
    if "\t" in first:
        return "\t"
    if "," in first:
        return ","
    return "\t"


def read_table(path: Path) -> List[Dict[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return []
    delimiter = delimiter_for_text("\n".join(lines[:3]))
    reader = csv.DictReader(lines, delimiter=delimiter)
    if reader.fieldnames and len(reader.fieldnames) > 1:
        return [{str(k): str(v) if v is not None else "" for k, v in row.items()} for row in reader]
    rows: List[Dict[str, str]] = []
    header = re.split(r"\s+", lines[0].strip())
    for line in lines[1:]:
        values = re.split(r"\s+", line.strip())
        rows.append({header[i]: values[i] if i < len(values) else "" for i in range(len(header))})
    return rows


def normalize_key(key: str) -> str:
    key = key.strip().lower()
    key = key.replace("%", "percent_")
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")


def row_get(row: Dict[str, str], *names: str) -> str:
    normalized = {normalize_key(k): v for k, v in row.items()}
    for name in names:
        value = normalized.get(normalize_key(name), "")
        if str(value).strip():
            return str(value).strip()
    return ""


def parse_float(value: Any) -> Optional[float]:
    try:
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "null"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_int(value: Any) -> Optional[int]:
    try:
        text = str(value).strip()
        if not text:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def resolve_query_id(row: Dict[str, str], records: Sequence[SeqRecord]) -> str:
    query_id = row_get(row, "query_id", "sequence_id", "seq_id", "protein_id", "name", "core.sequence_id")
    if query_id:
        return safe_name(query_id)
    seq_num = parse_int(row_get(row, "seq_num", "sequence_number", "seq", "core.sequence_number"))
    if seq_num is not None and 1 <= seq_num <= len(records):
        return records[seq_num - 1].seq_id
    return ""


def locate_peptide(
    query_id: str,
    peptide: str,
    start_value: Optional[int],
    records_by_id: Dict[str, SeqRecord],
) -> Tuple[str, str]:
    if start_value is not None and start_value > 0:
        return str(start_value), str(start_value + len(peptide) - 1)
    record = records_by_id.get(query_id)
    if record and peptide:
        index = record.sequence.find(peptide)
        if index >= 0:
            return str(index + 1), str(index + len(peptide))
    return "", ""


def classify_binder(rank: Optional[float], ic50: Optional[float], args: argparse.Namespace) -> str:
    strong = (rank is not None and rank <= args.strong_rank_cutoff) or (
        ic50 is not None and ic50 <= args.strong_ic50_cutoff
    )
    if strong:
        return "strong"
    weak = (rank is not None and rank <= args.weak_rank_cutoff) or (ic50 is not None and ic50 <= args.weak_ic50_cutoff)
    if weak:
        return "weak"
    return "none"


def normalize_binding_row(
    row: Dict[str, str],
    records: Sequence[SeqRecord],
    records_by_id: Dict[str, SeqRecord],
    source: str,
    args: argparse.Namespace,
) -> Optional[Dict[str, str]]:
    peptide = row_get(row, "peptide", "peptide_sequence", "sequence", "seq", "core.peptide")
    if not peptide:
        return None
    query_id = resolve_query_id(row, records)
    if not query_id:
        for record in records:
            if peptide in record.sequence:
                query_id = record.seq_id
                break
    start = parse_int(row_get(row, "start", "peptide_start", "start_position", "pos", "core.start"))
    start_text, end_text = locate_peptide(query_id, peptide, start, records_by_id)
    allele = row_get(row, "allele", "mhc", "hla", "mhc_allele", "core.allele")
    predictor = row_get(row, "method", "predictor", "prediction_method", "source") or "iedb_mhci"
    rank = parse_float(
        row_get(
            row,
            "rank",
            "percentile_rank",
            "percentile",
            "el_rank",
            "ba_rank",
            "percent_rank",
            "netmhcpan_rank",
            "binding.netmhcpan_el.percentile",
            "binding.netmhcpan_ba.percentile",
            "binding.median_percentile",
        )
    )
    score = parse_float(row_get(row, "score", "el_score", "ba_score", "prediction_score", "binding.netmhcpan_el.score"))
    ic50 = parse_float(row_get(row, "ic50", "ic50_nm", "ann_ic50", "predicted_ic50", "affinity", "binding.netmhcpan_ba.ic50"))
    return {
        "query_id": query_id,
        "peptide_start": start_text,
        "peptide_end": end_text,
        "peptide_length": str(len(peptide)),
        "peptide_sequence": peptide,
        "allele": allele,
        "predictor": predictor,
        "rank": "" if rank is None else f"{rank:g}",
        "score": "" if score is None else f"{score:g}",
        "ic50_nm": "" if ic50 is None else f"{ic50:g}",
        "binder_level": classify_binder(rank, ic50, args),
        "raw_source": source,
        "raw_columns_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
    }


def normalize_processing_row(
    row: Dict[str, str],
    records: Sequence[SeqRecord],
    records_by_id: Dict[str, SeqRecord],
    source: str,
) -> Optional[Dict[str, str]]:
    peptide = row_get(row, "peptide", "peptide_sequence", "sequence", "seq", "core.peptide")
    if not peptide:
        return None
    query_id = resolve_query_id(row, records)
    if not query_id:
        for record in records:
            if peptide in record.sequence:
                query_id = record.seq_id
                break
    start = parse_int(row_get(row, "start", "peptide_start", "start_position", "pos", "core.start"))
    start_text, end_text = locate_peptide(query_id, peptide, start, records_by_id)
    total = row_get(row, "total_score", "total", "combined_score", "score", "processing.basic_processing.total_score")
    processing = row_get(row, "processing_score", "processing", "cleavage_tap_score", "processing.basic_processing.processing_score")
    support = "yes" if total or processing else "unknown"
    return {
        "query_id": query_id,
        "peptide_start": start_text,
        "peptide_end": end_text,
        "peptide_length": str(len(peptide)),
        "peptide_sequence": peptide,
        "allele": row_get(row, "allele", "mhc", "hla", "mhc_allele", "core.allele"),
        "predictor": row_get(row, "method", "predictor", "prediction_method", "source") or "iedb_processing",
        "proteasome_score": row_get(row, "proteasome_score", "cleavage_score", "c_terminal_cleavage_score", "processing.basic_processing.proteasome_score"),
        "tap_score": row_get(row, "tap_score", "tap_transport_score", "processing.basic_processing.tap_score"),
        "mhc_binding_score": row_get(row, "mhc_binding_score", "mhc_score", "binding_score", "processing.basic_processing.mhc_score"),
        "processing_score": processing,
        "total_score": total,
        "processing_support": support,
        "raw_source": source,
        "raw_columns_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
    }


def normalize_immunogenicity_row(
    row: Dict[str, str],
    records: Sequence[SeqRecord],
    records_by_id: Dict[str, SeqRecord],
    source: str,
) -> Optional[Dict[str, str]]:
    peptide = row_get(row, "peptide", "peptide_sequence", "sequence", "seq", "core.peptide")
    if not peptide:
        return None
    query_id = resolve_query_id(row, records)
    if not query_id:
        for record in records:
            if peptide in record.sequence:
                query_id = record.seq_id
                break
    start = parse_int(row_get(row, "start", "peptide_start", "start_position", "pos", "core.start"))
    start_text, end_text = locate_peptide(query_id, peptide, start, records_by_id)
    score = row_get(row, "immunogenicity_score", "score", "prediction_score", "immunogenicity.score")
    return {
        "query_id": query_id,
        "peptide_start": start_text,
        "peptide_end": end_text,
        "peptide_length": str(len(peptide)),
        "peptide_sequence": peptide,
        "immunogenicity_score": score,
        "raw_source": source,
        "raw_columns_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
    }


def rows_from_aggregated_json(path: Path, warnings: List[str]) -> List[Dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        warnings.append(f"json_parse_failed:{path}:{exc}")
        return []
    rows: List[Dict[str, str]] = []
    result_blocks = data.get("results") if isinstance(data, dict) else None
    if isinstance(result_blocks, list):
        for block in result_blocks:
            columns = block.get("table_columns") or block.get("columns") or []
            table_data = block.get("table_data") or block.get("data") or []
            if not columns or not table_data:
                continue
            for values in table_data:
                rows.append({str(columns[i]): str(values[i]) if i < len(values) else "" for i in range(len(columns))})
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rows.append({str(k): str(v) for k, v in item.items()})
    elif isinstance(data, dict):
        flat_rows = data.get("table_data") or data.get("data")
        columns = data.get("table_columns") or data.get("columns")
        if isinstance(flat_rows, list) and isinstance(columns, list):
            for values in flat_rows:
                rows.append({str(columns[i]): str(values[i]) if i < len(values) else "" for i in range(len(columns))})
    return rows


def is_combined_iedb_nextgen_row(row: Dict[str, str]) -> bool:
    normalized = {normalize_key(key) for key in row}
    return "core_peptide" in normalized and any(
        key.startswith(("binding_", "processing_", "immunogenicity_")) for key in normalized
    )


def normalize_combined_iedb_nextgen_row(
    row: Dict[str, str],
    records: Sequence[SeqRecord],
    records_by_id: Dict[str, SeqRecord],
    source: str,
    args: argparse.Namespace,
) -> Tuple[List[Dict[str, str]], Optional[Dict[str, str]], Optional[Dict[str, str]]]:
    binding_rows: List[Dict[str, str]] = []
    base_binding_row = {
        key: value
        for key, value in row.items()
        if normalize_key(key).startswith("core_") or normalize_key(key) in {"query_id", "sequence_id", "seq_id"}
    }
    binding_specs = [
        (
            "netmhcpan_el",
            {
                "method": "netmhcpan_el",
                "percentile": row_get(row, "binding.netmhcpan_el.percentile"),
                "score": row_get(row, "binding.netmhcpan_el.score"),
            },
        ),
        (
            "netmhcpan_ba",
            {
                "method": "netmhcpan_ba",
                "percentile": row_get(row, "binding.netmhcpan_ba.percentile"),
                "ic50": row_get(row, "binding.netmhcpan_ba.ic50"),
            },
        ),
    ]
    for _method, fields in binding_specs:
        if fields.get("percentile") or fields.get("score") or fields.get("ic50"):
            synthetic = dict(base_binding_row)
            synthetic.update(fields)
            normalized = normalize_binding_row(synthetic, records, records_by_id, source, args)
            if normalized:
                binding_rows.append(normalized)

    processing_row = None
    if any(
        row_get(row, name)
        for name in [
            "processing.basic_processing.proteasome_score",
            "processing.basic_processing.tap_score",
            "processing.basic_processing.processing_score",
            "processing.basic_processing.total_score",
        ]
    ):
        synthetic_processing = dict(row)
        synthetic_processing["method"] = "basic_processing"
        processing_row = normalize_processing_row(synthetic_processing, records, records_by_id, source)

    immunogenicity_row = None
    if row_get(row, "immunogenicity.score"):
        synthetic_immunogenicity = dict(row)
        synthetic_immunogenicity["method"] = "immunogenicity"
        immunogenicity_row = normalize_immunogenicity_row(synthetic_immunogenicity, records, records_by_id, source)

    return binding_rows, processing_row, immunogenicity_row


def import_prediction_rows(
    args: argparse.Namespace,
    records: Sequence[SeqRecord],
    warnings: List[str],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    records_by_id = {record.seq_id: record for record in records}
    binding: List[Dict[str, str]] = []
    processing: List[Dict[str, str]] = []
    immunogenicity: List[Dict[str, str]] = []
    for item in args.api_result_tsv:
        path = Path(item).expanduser()
        if not path.exists():
            warnings.append(f"binding_result_tsv_missing:{path}")
            continue
        for row in read_table(path):
            normalized = normalize_binding_row(row, records, records_by_id, str(path), args)
            if normalized:
                binding.append(normalized)
    for item in args.processing_result_tsv:
        path = Path(item).expanduser()
        if not path.exists():
            warnings.append(f"processing_result_tsv_missing:{path}")
            continue
        for row in read_table(path):
            normalized = normalize_processing_row(row, records, records_by_id, str(path))
            if normalized:
                processing.append(normalized)
    for item in args.immunogenicity_result_tsv:
        path = Path(item).expanduser()
        if not path.exists():
            warnings.append(f"immunogenicity_result_tsv_missing:{path}")
            continue
        for row in read_table(path):
            normalized = normalize_immunogenicity_row(row, records, records_by_id, str(path))
            if normalized:
                immunogenicity.append(normalized)
    for item in list(args.api_result_json) + list(args.local_result_json):
        path = Path(item).expanduser()
        if not path.exists():
            warnings.append(f"result_json_missing:{path}")
            continue
        for row in rows_from_aggregated_json(path, warnings):
            if is_combined_iedb_nextgen_row(row):
                b_rows, p_row, i_row = normalize_combined_iedb_nextgen_row(row, records, records_by_id, str(path), args)
                binding.extend(b_rows)
                if p_row:
                    processing.append(p_row)
                if i_row:
                    immunogenicity.append(i_row)
                continue
            row_type = " ".join([row_get(row, "group", "source", "predictor", "method"), json.dumps(row)]).lower()
            if ("processing" in row_type or "tap" in row_type or "proteasome" in row_type) and "binding." not in row_type:
                normalized_processing = normalize_processing_row(row, records, records_by_id, str(path))
                if normalized_processing:
                    processing.append(normalized_processing)
            elif "immunogenicity" in row_type:
                normalized_imm = normalize_immunogenicity_row(row, records, records_by_id, str(path))
                if normalized_imm:
                    immunogenicity.append(normalized_imm)
            else:
                normalized_binding = normalize_binding_row(row, records, records_by_id, str(path), args)
                if normalized_binding:
                    binding.append(normalized_binding)
    return binding, processing, immunogenicity


def context_category(source: str, feature_type: str, name: str) -> str:
    text = " ".join([source, feature_type, name]).lower()
    if "signal" in text or "secretory" in text:
        return "signal_peptide"
    if "transmembrane" in text or "tm helix" in text or "tm_region" in text or re.search(r"\btm\b", text):
        return "tm"
    if "idr" in text or "disorder" in text or "disordered" in text:
        return "idr"
    if "conserved" in text or "conservation" in text:
        return "conserved_region"
    if "domain" in text or "pfam" in text or "interpro" in text or "motif" in text:
        return "domain"
    return "other"


def load_context_features(paths: Sequence[str], warnings: List[str]) -> List[ContextFeature]:
    features: List[ContextFeature] = []
    for item in paths:
        path = Path(item).expanduser()
        if not path.exists():
            warnings.append(f"context_features_missing:{path}")
            continue
        for row in read_table(path):
            query_id = safe_name(row_get(row, "query_id", "protein_id", "seq_id", "id"))
            start = parse_int(row_get(row, "start", "feature_start", "region_start", "peptide_start"))
            end = parse_int(row_get(row, "end", "feature_end", "region_end", "peptide_end"))
            if not query_id or start is None or end is None:
                continue
            source = row_get(row, "source", "database", "tool") or path.stem
            feature_type = row_get(row, "feature_type", "type", "region_type", "annotation")
            name = row_get(row, "name", "description", "feature_name", "accession")
            features.append(
                ContextFeature(
                    query_id=query_id,
                    start=min(start, end),
                    end=max(start, end),
                    source=source,
                    feature_type=feature_type,
                    name=name,
                    category=context_category(source, feature_type, name),
                )
            )
    return features


def overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start <= b_end and b_start <= a_end


def key_for(row: Dict[str, str]) -> Tuple[str, str, str, str]:
    return (row.get("query_id", ""), row.get("peptide_start", ""), row.get("peptide_end", ""), row.get("peptide_sequence", ""))


def best_float(rows: Sequence[Dict[str, str]], column: str, lower_is_better: bool = True) -> str:
    values = [(parse_float(row.get(column)), row.get(column, "")) for row in rows]
    values = [(num, text) for num, text in values if num is not None]
    if not values:
        return ""
    chosen = min(values, key=lambda item: item[0]) if lower_is_better else max(values, key=lambda item: item[0])
    return f"{chosen[0]:g}"


def candidate_grade(
    binding_rows: Sequence[Dict[str, str]],
    processing_support: str,
    immunogenicity_score: str,
    args: argparse.Namespace,
) -> str:
    levels = [row.get("binder_level", "none") for row in binding_rows]
    has_strong = "strong" in levels
    has_weak = has_strong or "weak" in levels
    if not has_weak:
        return "unlikely"
    imm = parse_float(immunogenicity_score)
    immunogenicity_ok = imm is None or imm >= args.immunogenicity_min_score
    if has_strong and processing_support == "yes" and immunogenicity_ok:
        return "high_confidence_candidate"
    return "weak_candidate"


def build_candidates(
    peptide_rows: Sequence[Dict[str, str]],
    binding_rows: Sequence[Dict[str, str]],
    processing_rows: Sequence[Dict[str, str]],
    immunogenicity_rows: Sequence[Dict[str, str]],
    context_features: Sequence[ContextFeature],
    args: argparse.Namespace,
) -> List[Dict[str, str]]:
    binding_by_key: Dict[Tuple[str, str, str, str], List[Dict[str, str]]] = {}
    processing_by_key: Dict[Tuple[str, str, str, str], List[Dict[str, str]]] = {}
    imm_by_key: Dict[Tuple[str, str, str, str], List[Dict[str, str]]] = {}
    for row in binding_rows:
        binding_by_key.setdefault(key_for(row), []).append(row)
    for row in processing_rows:
        processing_by_key.setdefault(key_for(row), []).append(row)
    for row in immunogenicity_rows:
        imm_by_key.setdefault(key_for(row), []).append(row)

    features_by_query: Dict[str, List[ContextFeature]] = {}
    for feature in context_features:
        features_by_query.setdefault(feature.query_id, []).append(feature)

    candidates: List[Dict[str, str]] = []
    for peptide in peptide_rows:
        key = key_for(peptide)
        b_rows = binding_by_key.get(key, [])
        p_rows = processing_by_key.get(key, [])
        i_rows = imm_by_key.get(key, [])
        start = parse_int(peptide.get("peptide_start")) or 0
        end = parse_int(peptide.get("peptide_end")) or 0
        overlaps = [f for f in features_by_query.get(peptide["query_id"], []) if overlap(start, end, f.start, f.end)]
        by_category = {category: [] for category in ["signal_peptide", "tm", "idr", "domain", "conserved_region"]}
        context_text: List[str] = []
        for feature in overlaps:
            if feature.category in by_category:
                by_category[feature.category].append(feature)
            label = f"{feature.category}:{feature.source}:{feature.feature_type}:{feature.name}:{feature.start}-{feature.end}"
            context_text.append(label)

        strong = sorted({row["allele"] for row in b_rows if row.get("binder_level") == "strong" and row.get("allele")})
        weak = sorted({row["allele"] for row in b_rows if row.get("binder_level") == "weak" and row.get("allele")})
        all_alleles = sorted({row["allele"] for row in b_rows if row.get("allele")})
        processing_support = "unknown"
        if p_rows:
            processing_support = "yes" if any(row.get("processing_support") == "yes" for row in p_rows) else "unknown"
        immunogenicity_score = best_float(i_rows, "immunogenicity_score", lower_is_better=False)
        grade = candidate_grade(b_rows, processing_support, immunogenicity_score, args)
        best_predictor = ""
        ranked_rows = [(parse_float(row.get("rank")), row) for row in b_rows]
        ranked_rows = [(rank, row) for rank, row in ranked_rows if rank is not None]
        if ranked_rows:
            best_predictor = min(ranked_rows, key=lambda item: item[0])[1].get("predictor", "")
        elif b_rows:
            best_predictor = b_rows[0].get("predictor", "")
        evidence_parts = []
        if strong:
            evidence_parts.append(f"strong_binder={len(strong)}")
        if weak:
            evidence_parts.append(f"weak_binder={len(weak)}")
        if processing_support == "yes":
            evidence_parts.append("processing_supported")
        if immunogenicity_score:
            evidence_parts.append(f"immunogenicity_score={immunogenicity_score}")
        if context_text:
            evidence_parts.append("context_overlap")
        if not evidence_parts:
            evidence_parts.append("generated_unscored_peptide")
        candidates.append(
            {
                "query_id": peptide["query_id"],
                "protein_length": peptide["protein_length"],
                "peptide_start": peptide["peptide_start"],
                "peptide_end": peptide["peptide_end"],
                "peptide_length": peptide["peptide_length"],
                "peptide_sequence": peptide["peptide_sequence"],
                "allele_count_tested": str(len(all_alleles)),
                "strong_binding_alleles": ";".join(strong),
                "weak_binding_alleles": ";".join(weak),
                "best_el_rank": best_float([row for row in b_rows if "el" in row.get("predictor", "").lower()], "rank"),
                "best_ba_rank": best_float([row for row in b_rows if "ba" in row.get("predictor", "").lower()], "rank"),
                "best_rank": best_float(b_rows, "rank"),
                "best_score": best_float(b_rows, "score", lower_is_better=False),
                "best_ic50_nm": best_float(b_rows, "ic50_nm"),
                "best_binding_predictor": best_predictor,
                "processing_support": processing_support,
                "processing_score": best_float(p_rows, "processing_score", lower_is_better=False),
                "proteasome_score": best_float(p_rows, "proteasome_score", lower_is_better=False),
                "tap_score": best_float(p_rows, "tap_score", lower_is_better=False),
                "mhc_binding_score": best_float(p_rows, "mhc_binding_score", lower_is_better=False),
                "total_score": best_float(p_rows, "total_score", lower_is_better=False),
                "immunogenicity_score": immunogenicity_score,
                "overlaps_signal_peptide": "yes" if by_category["signal_peptide"] else "no",
                "overlaps_tm": "yes" if by_category["tm"] else "no",
                "overlaps_idr": "yes" if by_category["idr"] else "no",
                "overlaps_domain": "yes" if by_category["domain"] else "no",
                "overlaps_conserved_region": "yes" if by_category["conserved_region"] else "no",
                "context_features": ";".join(context_text),
                "candidate_grade": grade,
                "evidence": ";".join(evidence_parts),
                "note": "Candidate immunopresentation annotation; not experimental immunogenicity or ligandome confirmation.",
            }
        )
    return candidates


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


def local_iedb_payload(
    records: Sequence[SeqRecord],
    alleles: Sequence[str],
    lengths: Sequence[int],
    predictors: Sequence[str],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    predictor_blocks: List[Dict[str, Any]] = []
    for predictor in predictors:
        predictor_blocks.append({"type": "binding", "method": predictor})
    predictor_blocks.append(
        {
            "type": "processing",
            "method": "basic_processing",
            "mhc_binding_method": args.processing_predictor,
            "proteasome": args.proteasome,
            "tap_precursor": 1,
            "tap_alpha": 0.2,
        }
    )
    predictor_blocks.append({"type": "immunogenicity", "mask_choice": "default"})
    return {
        "input_sequence_text": normalized_fasta(records),
        "peptide_length_range": list(lengths) if lengths else [8, 9, 10, 11],
        "alleles": ",".join(alleles),
        "predictors": predictor_blocks,
    }


def write_local_iedb_plan(
    args: argparse.Namespace,
    records: Sequence[SeqRecord],
    alleles: Sequence[str],
    lengths: Sequence[int],
    predictors: Sequence[str],
    outdir: Path,
    normalized_fasta_path: Path,
) -> Dict[str, str]:
    local_dir = outdir / "local_iedb"
    safe_mkdir(local_dir)
    input_json = local_dir / "iedb_ng_tc1_input.json"
    manifest_json = local_dir / "local_pipeline_manifest.json"
    plan_sh = local_dir / "local_pipeline_plan.sh"
    workdir = Path(args.local_workdir).expanduser() if args.local_workdir else local_dir / "work"
    tools_dir = Path(args.iedb_local_tools_dir).expanduser() if args.iedb_local_tools_dir else None
    wrapper_repo = Path(args.iedb_wrapper_repo).expanduser() if args.iedb_wrapper_repo else None
    write_json(input_json, local_iedb_payload(records, alleles, lengths, predictors, args))

    tools_default = str(tools_dir) if tools_dir else "/path/to/IEDB_NG_TC1"
    wrapper_default = str(wrapper_repo) if wrapper_repo else "/path/to/qinti2023/IEDB"
    script_path = Path(__file__).resolve()
    imported_report_dir = (outdir / "imported_local_report").resolve()
    executed_report_dir = (outdir / "executed_local_report").resolve()
    plan_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Local route for IEDB Next-Generation Tools T Cell Class I.",
        "# IEDB_TOOLS_DIR must be the unpacked official IEDB_NG_TC1 directory containing src/tcell_mhci.py.",
        "# IEDB_WRAPPER_REPO is optional and only needed to reproduce the qinti2023/IEDB IEDB_predict.py pipeline.",
        f"# Official README: {IEDB_NG_TC1_README_URL}",
        f"# Official tarball: {IEDB_NG_TC1_TARBALL_URL}",
        f"IEDB_TOOLS_DIR=\"${{IEDB_TOOLS_DIR:-{tools_default}}}\"",
        f"IEDB_WRAPPER_REPO=\"${{IEDB_WRAPPER_REPO:-{wrapper_default}}}\"",
        f"WORKDIR=\"${{WORKDIR:-{workdir}}}\"",
        f"S2F_IMMUNO_SCRIPT=\"${{S2F_IMMUNO_SCRIPT:-{script_path}}}\"",
        "",
        "# One-time official package setup, shown for reproducibility.",
        "# The tarball is large; ask before running this on a user's machine.",
        f"# mkdir -p \"$HOME/iedb_tools\"",
        f"# curl -L -O {shell_quote(IEDB_NG_TC1_TARBALL_URL)}",
        f"# curl -L -O {shell_quote(IEDB_NG_TC1_MD5_URL)}",
        "# tar -xvzf IEDB_NG_TC1-0.1.5-beta.tar.gz -C \"$HOME/iedb_tools\"",
        "# cd \"$HOME/iedb_tools/ng_tc1-0.1.5-beta\"",
        "# python3 -m venv \"$HOME/venvs/tc1\"",
        "# source \"$HOME/venvs/tc1/bin/activate\"",
        "# python3 -m pip install --upgrade pip",
        "# pip install -r requirements.txt",
        "# PIP_CONSTRAINTS=pip_constraints.txt pip install -r requirements.txt",
        "# ./configure",
        "",
        "mkdir -p \"$WORKDIR/test\" \"$WORKDIR/results\" \"$WORKDIR/aggregate\"",
        f"cp {shell_quote(str(normalized_fasta_path.resolve()))} \"$WORKDIR/input_sequence.fasta\"",
        f"cp {shell_quote(str(input_json.resolve()))} \"$WORKDIR/output.json\"",
        "",
        "# Recommended: execute split/predict/aggregate through the S2F wrapper job runner.",
        "python \"$S2F_IMMUNO_SCRIPT\" \\",
        "  --fasta \"$WORKDIR/input_sequence.fasta\" \\",
        "  --iedb-local-tools-dir \"$IEDB_TOOLS_DIR\" \\",
        "  --execute-local \\",
        "  --local-workdir \"$WORKDIR\" \\",
        f"  --outdir {shell_quote(str(executed_report_dir))}",
        "",
        "# Optional: reproduce the original qinti2023/IEDB runner if IEDB_WRAPPER_REPO is set.",
        "# cd \"$WORKDIR\"",
        "# python \"$IEDB_TOOLS_DIR/src/tcell_mhci.py\" -j output.json --split --split-dir ./test/",
        "# python \"$IEDB_WRAPPER_REPO/IEDB_predict.py\" job_descriptions.json",
        "",
        "# Import an externally generated aggregate output back into the normalized S2F report.",
        "# python \"$S2F_IMMUNO_SCRIPT\" \\",
        "#   --fasta \"$WORKDIR/input_sequence.fasta\" \\",
        "#   --local-result-json \"$WORKDIR/aggregate/aggregated_result.json\" \\",
        f"#   --outdir {shell_quote(str(imported_report_dir))}",
    ]
    plan_sh.write_text("\n".join(plan_lines) + "\n", encoding="utf-8")
    os.chmod(plan_sh, 0o755)

    manifest = {
        "local_input_json": str(input_json),
        "local_pipeline_plan_sh": str(plan_sh),
        "local_workdir": str(workdir),
        "iedb_local_tools_dir": str(tools_dir) if tools_dir else "",
        "iedb_wrapper_repo": str(wrapper_repo) if wrapper_repo else "",
        "official_readme_url": IEDB_NG_TC1_README_URL,
        "official_tarball_url": IEDB_NG_TC1_TARBALL_URL,
        "official_md5_url": IEDB_NG_TC1_MD5_URL,
        "official_version_observed": "0.1.5-beta",
        "requires_official_iedb_ng_tc1": True,
        "requires_qinti2023_iedb_wrapper": False,
        "expected_aggregate_json": str(workdir / "aggregate" / "aggregated_result.json"),
        "notes": [
            "The official IEDB_NG_TC1 package contains src/tcell_mhci.py.",
            "qinti2023/IEDB contains wrapper scripts and example outputs but does not bundle the official src/tcell_mhci.py tool.",
            "Install or unpack the official IEDB Next-Generation Tools T Cell Class I package before executing local jobs.",
        ],
    }
    write_json(manifest_json, manifest)
    return {
        "local_iedb_dir": str(local_dir),
        "local_iedb_input_json": str(input_json),
        "local_pipeline_manifest_json": str(manifest_json),
        "local_pipeline_plan_sh": str(plan_sh),
    }


def run_logged_command(
    command: Sequence[str],
    cwd: Path,
    log_path: Path,
    warnings: List[str],
    label: str,
) -> bool:
    try:
        result = subprocess.run(command, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        warnings.append(f"{label}_failed_to_start:{exc}")
        return False
    log_path.write_text(
        "$ " + " ".join(shell_quote(str(part)) for part in command) + "\n\n"
        + result.stdout
        + ("\n[stderr]\n" + result.stderr if result.stderr else ""),
        encoding="utf-8",
    )
    if result.returncode != 0:
        warnings.append(f"{label}_failed:returncode={result.returncode}:log={log_path}")
        return False
    return True


def execute_shell_job(job: Dict[str, Any], cwd: Path, logs_dir: Path) -> Tuple[Any, bool]:
    job_id = job.get("job_id", "unknown")
    command = str(job.get("shell_cmd", ""))
    log_path = logs_dir / f"job_{safe_name(str(job_id))}.log"
    result = subprocess.run(command, shell=True, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    log_path.write_text(
        "$ " + command + "\n\n" + result.stdout + ("\n[stderr]\n" + result.stderr if result.stderr else ""),
        encoding="utf-8",
    )
    return job_id, result.returncode == 0


def execute_local_job_descriptions(
    job_json: Path,
    workdir: Path,
    max_workers: int,
    warnings: List[str],
) -> bool:
    try:
        jobs = json.loads(job_json.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"local_job_descriptions_unreadable:{job_json}:{exc}")
        return False
    prediction_jobs = [job for job in jobs if job.get("job_type") == "prediction"]
    aggregate_jobs = [job for job in jobs if job.get("job_type") == "aggregate"]
    logs_dir = workdir / "logs"
    safe_mkdir(logs_dir)
    completed = set()
    failed = set()
    if prediction_jobs:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
            futures = [executor.submit(execute_shell_job, job, workdir, logs_dir) for job in prediction_jobs]
            for future in concurrent.futures.as_completed(futures):
                job_id, ok = future.result()
                if ok:
                    completed.add(job_id)
                else:
                    failed.add(job_id)
        if failed:
            warnings.append(f"local_prediction_jobs_failed:{len(failed)}:logs={logs_dir}")
            return False
    for job in aggregate_jobs:
        deps = set(job.get("depends_on_job_ids", []))
        if deps and not deps.issubset(completed):
            warnings.append(f"local_aggregate_skipped_missing_dependencies:{job.get('job_id')}")
            return False
        job_id, ok = execute_shell_job(job, workdir, logs_dir)
        if not ok:
            warnings.append(f"local_aggregate_job_failed:{job_id}:logs={logs_dir}")
            return False
    return True


def execute_local_iedb(
    args: argparse.Namespace,
    local_input_json: Path,
    normalized_fasta_path: Path,
    outdir: Path,
    warnings: List[str],
) -> Dict[str, str]:
    artifacts: Dict[str, str] = {}
    if not args.iedb_local_tools_dir:
        warnings.append("execute_local_requires_iedb_local_tools_dir")
        return artifacts
    tools_dir = Path(args.iedb_local_tools_dir).expanduser()
    tcell_script = tools_dir / "src" / "tcell_mhci.py"
    if not tcell_script.exists():
        warnings.append(f"local_tcell_mhci_missing:{tcell_script}")
        return artifacts
    workdir = Path(args.local_workdir).expanduser() if args.local_workdir else outdir / "local_iedb" / "work"
    safe_mkdir(workdir)
    safe_mkdir(workdir / "test")
    safe_mkdir(workdir / "results")
    safe_mkdir(workdir / "aggregate")
    logs_dir = workdir / "logs"
    safe_mkdir(logs_dir)
    shutil.copy2(local_input_json, workdir / "output.json")
    shutil.copy2(normalized_fasta_path, workdir / "input_sequence.fasta")
    split_ok = run_logged_command(
        [args.local_python, str(tcell_script), "-j", "output.json", "--split", "--split-dir", "./test/"],
        workdir,
        logs_dir / "split.log",
        warnings,
        "local_iedb_split",
    )
    artifacts["local_workdir"] = str(workdir)
    artifacts["local_split_log"] = str(logs_dir / "split.log")
    job_json = workdir / "job_descriptions.json"
    if not split_ok:
        return artifacts
    if not job_json.exists():
        warnings.append(f"local_job_descriptions_missing:{job_json}")
        return artifacts
    jobs_ok = execute_local_job_descriptions(job_json, workdir, args.local_max_workers, warnings)
    artifacts["local_job_descriptions_json"] = str(job_json)
    artifacts["local_logs_dir"] = str(logs_dir)
    aggregate_json = workdir / "aggregate" / "aggregated_result.json"
    if jobs_ok and aggregate_json.exists():
        artifacts["local_aggregated_result_json"] = str(aggregate_json)
        args.local_result_json.append(str(aggregate_json))
    elif jobs_ok:
        warnings.append(f"local_aggregated_result_missing:{aggregate_json}")
    return artifacts


def post_form(url: str, data: Dict[str, str], timeout_sec: int) -> str:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"User-Agent": "s2f-agent-protein-immunopresentation-annotation/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        return response.read().decode("utf-8", errors="replace")


def write_api_plans(
    args: argparse.Namespace,
    records: Sequence[SeqRecord],
    alleles: Sequence[str],
    lengths: Sequence[int],
    predictors: Sequence[str],
    outdir: Path,
) -> Dict[str, str]:
    requests_dir = outdir / "api_requests"
    safe_mkdir(requests_dir)
    fasta_text = normalized_fasta(records)
    legacy_jsonl = requests_dir / "iedb_legacy_requests.jsonl"
    nextgen_json = requests_dir / "iedb_nextgen_request.json"
    with legacy_jsonl.open("w", encoding="utf-8") as handle:
        for predictor in predictors:
            for length in lengths:
                payload = {
                    "endpoint": args.api_url,
                    "method": predictor,
                    "sequence_text": fasta_text,
                    "allele": ",".join(alleles),
                    "length": str(length),
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        if args.execute_processing:
            for length in lengths:
                payload = {
                    "endpoint": args.processing_api_url,
                    "method": args.processing_predictor,
                    "sequence_text": fasta_text,
                    "allele": ",".join(alleles),
                    "length": str(length),
                    "proteasome": args.proteasome,
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    nextgen_payload = {
        "input_sequence_text": fasta_text,
        "alleles": list(alleles),
        "peptide_length_range": [min(lengths) if lengths else 8, max(lengths) if lengths else 11],
        "predictors": list(predictors),
        "processing": {
            "predictor": "basic_processing",
            "mhc_binding_method": args.processing_predictor,
            "proteasome": args.proteasome,
        },
        "metadata_url": IEDB_MHCI_METADATA_URL,
    }
    write_json(nextgen_json, nextgen_payload)
    commands = outdir / "commands.sh"
    commands.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "",
                "# IEDB legacy Tools-API supports POST for MHC-I binding and processing.",
                "# Review rate limits and privacy before submitting unpublished sequences.",
                f"curl --data {shell_quote('method=netmhcpan_el&sequence_text=<FASTA_OR_SEQUENCE>&allele=' + ','.join(alleles[:2]) + '&length=9')} {shell_quote(args.api_url)}",
                "",
                "# Next-generation metadata for current MHC-I predictors:",
                f"curl -L {shell_quote(IEDB_MHCI_METADATA_URL)}",
                "",
                "# Local next-generation pipeline route based on the official IEDB README and qinti2023/IEDB pipeline notes:",
                f"# Official README: {IEDB_NG_TC1_README_URL}",
                f"# Official tarball: {IEDB_NG_TC1_TARBALL_URL}",
                "# Ask before downloading the tarball; it is about 841 MB in the current LATEST directory.",
                "# mkdir -p \"$HOME/iedb_tools\"",
                f"# curl -L -O {shell_quote(IEDB_NG_TC1_TARBALL_URL)}",
                f"# curl -L -O {shell_quote(IEDB_NG_TC1_MD5_URL)}",
                "# tar -xvzf IEDB_NG_TC1-0.1.5-beta.tar.gz -C \"$HOME/iedb_tools\"",
                "# cd \"$HOME/iedb_tools/ng_tc1-0.1.5-beta\"",
                "# conda create -n IEDB python=3.10 -y",
                "# conda activate IEDB",
                "# python3 -m pip install --upgrade pip",
                "# pip install -r requirements.txt",
                "# PIP_CONSTRAINTS=pip_constraints.txt pip install -r requirements.txt",
                "# ./configure",
                "",
                "# Execute local IEDB NG TC1 through the S2F job runner after installation:",
                "python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \\",
                "  --fasta input_sequence.fasta \\",
                "  --iedb-local-tools-dir \"$HOME/iedb_tools/ng_tc1-0.1.5-beta\" \\",
                "  --execute-local \\",
                "  --local-workdir output/protein-immunopresentation-annotation/<RUN_ID>_iedb_work \\",
                "  --outdir output/protein-immunopresentation-annotation/<RUN_ID>_local",
                "",
                "# Import downloaded/API/local results back into the standardized report:",
                "python skills/protein-immunopresentation-annotation/scripts/protein_immunopresentation_annotation.py \\",
                "  --fasta input_sequence.fasta \\",
                "  --local-result-json <IEDB_WORKDIR>/aggregate/aggregated_result.json \\",
                "  --outdir output/protein-immunopresentation-annotation/<RUN_ID>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(commands, 0o755)
    return {
        "api_requests_dir": str(requests_dir),
        "iedb_legacy_requests_jsonl": str(legacy_jsonl),
        "iedb_nextgen_request_json": str(nextgen_json),
        "commands_sh": str(commands),
    }


def execute_legacy_api(
    args: argparse.Namespace,
    records: Sequence[SeqRecord],
    alleles: Sequence[str],
    lengths: Sequence[int],
    predictors: Sequence[str],
    outdir: Path,
    warnings: List[str],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]], Dict[str, str]]:
    raw_dir = outdir / "raw_api_results"
    safe_mkdir(raw_dir)
    fasta_text = normalized_fasta(records)
    records_by_id = {record.seq_id: record for record in records}
    binding: List[Dict[str, str]] = []
    processing: List[Dict[str, str]] = []
    immunogenicity: List[Dict[str, str]] = []
    artifacts: Dict[str, str] = {"raw_api_results_dir": str(raw_dir)}
    for predictor in predictors:
        for length in lengths:
            payload = {"method": predictor, "sequence_text": fasta_text, "allele": ",".join(alleles), "length": str(length)}
            output = raw_dir / f"mhci_{safe_name(predictor)}_len{length}.tsv"
            try:
                text = post_form(args.api_url, payload, args.timeout_sec)
                output.write_text(text, encoding="utf-8")
                for row in read_table(output):
                    normalized = normalize_binding_row(row, records, records_by_id, str(output), args)
                    if normalized:
                        binding.append(normalized)
            except (urllib.error.URLError, TimeoutError, ValueError, http.client.HTTPException, OSError) as exc:
                warnings.append(f"mhci_api_failed:{predictor}:len{length}:{exc}")
    if args.execute_processing:
        for length in lengths:
            payload = {
                "method": args.processing_predictor,
                "sequence_text": fasta_text,
                "allele": ",".join(alleles),
                "length": str(length),
                "proteasome": args.proteasome,
            }
            output = raw_dir / f"processing_{safe_name(args.processing_predictor)}_len{length}.tsv"
            try:
                text = post_form(args.processing_api_url, payload, args.timeout_sec)
                output.write_text(text, encoding="utf-8")
                for row in read_table(output):
                    normalized = normalize_processing_row(row, records, records_by_id, str(output))
                    if normalized:
                        processing.append(normalized)
            except (urllib.error.URLError, TimeoutError, ValueError, http.client.HTTPException, OSError) as exc:
                warnings.append(f"processing_api_failed:len{length}:{exc}")
    if args.execute_immunogenicity:
        unique_peptides = sorted({row["peptide_sequence"] for row in generate_peptides(records, lengths, warnings)})
        for idx in range(0, len(unique_peptides), 200):
            batch = unique_peptides[idx : idx + 200]
            payload = {"method": "immunogenicity", "sequence_text": "\n".join(batch)}
            output = raw_dir / f"immunogenicity_batch{idx // 200 + 1}.tsv"
            try:
                text = post_form(args.immunogenicity_api_url, payload, args.timeout_sec)
                output.write_text(text, encoding="utf-8")
                for row in read_table(output):
                    normalized = normalize_immunogenicity_row(row, records, records_by_id, str(output))
                    if normalized:
                        immunogenicity.append(normalized)
            except (urllib.error.URLError, TimeoutError, ValueError, http.client.HTTPException, OSError) as exc:
                warnings.append(f"immunogenicity_api_failed:batch{idx // 200 + 1}:{exc}")
    return binding, processing, immunogenicity, artifacts


def summarize_records(
    records: Sequence[SeqRecord],
    peptide_rows: Sequence[Dict[str, str]],
    candidates: Sequence[Dict[str, str]],
    alleles: Sequence[str],
    lengths: Sequence[int],
    predictors: Sequence[str],
    warnings: Sequence[str],
) -> List[Dict[str, str]]:
    peptides_by_query: Dict[str, int] = {}
    candidates_by_query: Dict[str, List[Dict[str, str]]] = {}
    for row in peptide_rows:
        peptides_by_query[row["query_id"]] = peptides_by_query.get(row["query_id"], 0) + 1
    for row in candidates:
        candidates_by_query.setdefault(row["query_id"], []).append(row)
    rows: List[Dict[str, str]] = []
    for record in records:
        cands = candidates_by_query.get(record.seq_id, [])
        rows.append(
            {
                "query_id": record.seq_id,
                "input_type": record.input_type,
                "protein_length": str(len(record.sequence)),
                "sequence_sha256": sha256_text(record.sequence),
                "n_peptides_generated": str(peptides_by_query.get(record.seq_id, 0)),
                "n_predictions": str(sum(1 for cand in cands if cand.get("allele_count_tested") not in {"", "0"})),
                "n_strong_binder_peptides": str(sum(1 for cand in cands if cand.get("strong_binding_alleles"))),
                "n_weak_binder_peptides": str(sum(1 for cand in cands if cand.get("weak_binding_alleles"))),
                "n_high_confidence_candidates": str(
                    sum(1 for cand in cands if cand.get("candidate_grade") == "high_confidence_candidate")
                ),
                "n_weak_candidates": str(sum(1 for cand in cands if cand.get("candidate_grade") == "weak_candidate")),
                "n_unlikely_candidates": str(sum(1 for cand in cands if cand.get("candidate_grade") == "unlikely")),
                "alleles": ",".join(alleles),
                "peptide_lengths": ",".join(str(length) for length in lengths),
                "predictors": ",".join(predictors),
                "warnings": ";".join(w for w in warnings if w.startswith(record.seq_id + ":")),
            }
        )
    return rows


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    outdir = Path(args.outdir).expanduser()
    safe_mkdir(outdir)
    warnings: List[str] = []
    records = load_query_records(args, warnings)
    if not records:
        warnings.append("no_query_sequences_provided")
    allele_values = parse_csv_list(args.alleles) if args.alleles else []
    for item in args.allele:
        allele_values.extend(parse_csv_list(item))
    alleles = unique_preserve(allele_values) or DEFAULT_ALLELES
    lengths = [int(item) for item in parse_csv_list(args.peptide_lengths)]
    predictors = unique_preserve(parse_csv_list(args.binding_predictors)) or ["netmhcpan_el", "netmhcpan_ba"]

    normalized_fasta_path = outdir / "normalized_input.fasta"
    normalized_fasta_path.write_text(normalized_fasta(records), encoding="utf-8")
    peptide_rows = generate_peptides(records, lengths, warnings)
    artifacts = write_api_plans(args, records, alleles, lengths, predictors, outdir)
    local_artifacts = write_local_iedb_plan(args, records, alleles, lengths, predictors, outdir, normalized_fasta_path)
    artifacts.update(local_artifacts)
    artifacts["normalized_input_fasta"] = str(normalized_fasta_path)

    if args.execute_local:
        artifacts.update(
            execute_local_iedb(
                args,
                Path(local_artifacts["local_iedb_input_json"]),
                normalized_fasta_path,
                outdir,
                warnings,
            )
        )

    binding_rows, processing_rows, immunogenicity_rows = import_prediction_rows(args, records, warnings)
    if args.execute_api:
        if args.api_mode != "legacy":
            warnings.append("execute_api_only_implemented_for_legacy_tools_api; wrote nextgen payload for manual use")
        else:
            b2, p2, i2, api_artifacts = execute_legacy_api(args, records, alleles, lengths, predictors, outdir, warnings)
            binding_rows.extend(b2)
            processing_rows.extend(p2)
            immunogenicity_rows.extend(i2)
            artifacts.update(api_artifacts)
    context_paths = []
    for attr in [
        "context_features_tsv",
        "localization_features_tsv",
        "tm_features_tsv",
        "idr_regions_tsv",
        "domain_features_tsv",
        "conservation_features_tsv",
    ]:
        context_paths.extend(getattr(args, attr, []))
    context_features = load_context_features(context_paths, warnings)
    candidates = build_candidates(peptide_rows, binding_rows, processing_rows, immunogenicity_rows, context_features, args)
    summary_rows = summarize_records(records, peptide_rows, candidates, alleles, lengths, predictors, warnings)

    peptide_path = outdir / "mhci_peptides.tsv"
    binding_path = outdir / "mhci_binding_predictions.tsv"
    processing_path = outdir / "mhci_processing_predictions.tsv"
    immunogenicity_path = outdir / "mhci_immunogenicity_predictions.tsv"
    candidates_path = outdir / "immunopresentation_candidates.tsv"
    summary_path = outdir / "protein_immunopresentation_summary.tsv"
    result_path = outdir / "protein_immunopresentation_annotation.result.json"
    write_tsv(peptide_path, peptide_rows, PEPTIDE_COLUMNS)
    write_tsv(binding_path, binding_rows, BINDING_COLUMNS)
    write_tsv(processing_path, processing_rows, PROCESSING_COLUMNS)
    write_tsv(immunogenicity_path, immunogenicity_rows, IMMUNOGENICITY_COLUMNS)
    write_tsv(candidates_path, candidates, CANDIDATE_COLUMNS)
    write_tsv(summary_path, summary_rows, SUMMARY_COLUMNS)
    artifacts.update(
        {
            "mhci_peptides_tsv": str(peptide_path),
            "mhci_binding_predictions_tsv": str(binding_path),
            "mhci_processing_predictions_tsv": str(processing_path),
            "mhci_immunogenicity_predictions_tsv": str(immunogenicity_path),
            "immunopresentation_candidates_tsv": str(candidates_path),
            "summary_tsv": str(summary_path),
            "result_json": str(result_path),
        }
    )
    report = {
        "skill": "protein-immunopresentation-annotation",
        "status": "warning" if warnings else "success",
        "run_id": safe_name(args.run_id or (records[0].seq_id if records else "protein_immunopresentation_annotation")),
        "created_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "parameters": {
            "alleles": alleles,
            "peptide_lengths": lengths,
            "binding_predictors": predictors,
            "processing_predictor": args.processing_predictor,
            "proteasome": args.proteasome,
            "execute_api": args.execute_api,
            "execute_local": args.execute_local,
            "api_mode": args.api_mode,
            "api_url": args.api_url,
            "iedb_local_tools_dir": args.iedb_local_tools_dir or "",
            "iedb_wrapper_repo": args.iedb_wrapper_repo or "",
            "local_workdir": args.local_workdir or "",
            "local_max_workers": args.local_max_workers,
            "strong_rank_cutoff": args.strong_rank_cutoff,
            "weak_rank_cutoff": args.weak_rank_cutoff,
            "strong_ic50_cutoff": args.strong_ic50_cutoff,
            "weak_ic50_cutoff": args.weak_ic50_cutoff,
        },
        "counts": {
            "queries": len(records),
            "peptides_generated": len(peptide_rows),
            "binding_prediction_rows": len(binding_rows),
            "processing_prediction_rows": len(processing_rows),
            "immunogenicity_rows": len(immunogenicity_rows),
            "context_features": len(context_features),
            "candidate_rows": len(candidates),
        },
        "artifacts": artifacts,
        "warnings": warnings,
    }
    write_json(result_path, report)
    print(f"[OK] Protein immunopresentation annotation written to {outdir}")
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
