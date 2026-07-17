#!/usr/bin/env python3
"""Normalize DeepLoc 2.1 and SignalP 6.0 localization/signal predictions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shlex
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")
AMBIGUOUS_AA = set("XBZUO")
ALLOWED_AA = STANDARD_AA | AMBIGUOUS_AA

LOCALIZATION_LABELS = [
    "Nucleus",
    "Cytoplasm",
    "Extracellular",
    "Mitochondrion",
    "Cell membrane",
    "Endoplasmic reticulum",
    "Chloroplast",
    "Golgi apparatus",
    "Lysosome/Vacuole",
    "Peroxisome",
]
MEMBRANE_LABELS = ["Peripheral", "Transmembrane", "Lipid anchor", "Soluble"]
TARGETP_LABELS = ["SP", "mTP", "cTP", "lTP", "Other", "MT", "CH", "TH"]

SUMMARY_COLUMNS = [
    "query_id",
    "length",
    "sources",
    "deeploc_top_localization",
    "deeploc_localizations",
    "deeploc_membrane_association",
    "deeploc_signals",
    "signalp_prediction",
    "signalp_signal_peptide",
    "signalp_cleavage_site",
    "signalp_probability",
    "targetp_prediction",
    "targetp_presequence",
    "targetp_cleavage_site",
    "targetp_probability",
    "integrated_localization",
    "secretory_pathway_evidence",
    "warnings",
]

FEATURE_COLUMNS = [
    "query_id",
    "source",
    "feature_type",
    "start",
    "end",
    "length",
    "label",
    "score",
    "evidence",
    "note",
]

SCORE_COLUMNS = [
    "query_id",
    "source",
    "score_type",
    "label",
    "score",
    "threshold",
    "above_threshold",
]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create standardized localization and signal peptide tables from DeepLoc 2.1 and SignalP 6.0."
    )
    parser.add_argument("--sequence", action="append", default=[], help="Raw amino-acid sequence. Can be repeated.")
    parser.add_argument("--sequence-name", action="append", default=[], help="Label for --sequence. Can be repeated.")
    parser.add_argument("--fasta", action="append", default=[], help="Protein FASTA file. Can be repeated.")
    parser.add_argument("--tools", default="deeploc,signalp,targetp", help="Comma- or plus-separated tools: deeploc,signalp,targetp.")
    parser.add_argument("--outdir", default="output/protein-localization-signal-annotation/run")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--execute", action="store_true", help="Run command templates.")
    parser.add_argument("--allow-ambiguous-aa", action="store_true", help="Allow X/B/Z/U/O residues.")
    parser.add_argument("--sanitize-invalid-to-x", action="store_true", help="Convert invalid alphabetic residues to X.")
    parser.add_argument("--min-length", type=int, default=10)
    parser.add_argument("--max-length", type=int, default=10000)
    parser.add_argument("--no-plots", action="store_true", help="Disable summary SVG/HTML plots.")

    parser.add_argument("--deeploc-command-template", default="", help="Shell command with {input} and {outdir}.")
    parser.add_argument("--deeploc-output", action="append", default=[], help="DeepLoc result table to import.")
    parser.add_argument("--deeploc-model", choices=["fast", "slow"], default="fast")
    parser.add_argument("--deeploc-format", choices=["short", "long"], default="short")
    parser.add_argument("--deeploc-threshold", type=float, default=0.5)
    parser.add_argument("--deeploc-web-url", default="https://services.healthtech.dtu.dk/services/DeepLoc-2.1/")

    parser.add_argument("--signalp-command-template", default="", help="Shell command with {input} and {outdir}.")
    parser.add_argument("--signalp-output", action="append", default=[], help="SignalP summary/result table to import.")
    parser.add_argument("--signalp-gff3", action="append", default=[], help="SignalP GFF3 output to import.")
    parser.add_argument("--signalp-mode", choices=["fast", "slow"], default="fast")
    parser.add_argument("--signalp-organism", choices=["eukarya", "other"], default="eukarya")
    parser.add_argument("--signalp-web-url", default="https://services.healthtech.dtu.dk/services/SignalP-6.0/")
    parser.add_argument("--targetp-command-template", default="", help="Shell command with {input} and {outdir}.")
    parser.add_argument("--targetp-output", action="append", default=[], help="TargetP summary/result table to import.")
    parser.add_argument("--targetp-organism", choices=["plant", "non-plant"], default="non-plant")
    parser.add_argument("--targetp-format", choices=["short", "long"], default="short")
    parser.add_argument("--targetp-web-url", default="https://services.healthtech.dtu.dk/services/TargetP-2.0/")
    parser.add_argument("--native-plot", action="append", default=[], help="Record SOURCE:PATH native plot artifact.")
    return parser.parse_args(argv)


def selected_tools(value: str) -> List[str]:
    parts = [part.strip().lower() for part in re.split(r"[,+]", value) if part.strip()]
    if not parts or "all" in parts:
        parts = ["deeploc", "signalp", "targetp"]
    valid = {"deeploc", "signalp", "targetp"}
    unknown = [part for part in parts if part not in valid]
    if unknown:
        raise SystemExit(f"Unknown tool(s): {', '.join(unknown)}")
    return list(dict.fromkeys(parts))


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("._") or "query"


def read_fasta(path: Path) -> List[Tuple[str, str]]:
    records: List[Tuple[str, str]] = []
    name = ""
    chunks: List[str] = []
    with path.open() as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name:
                    records.append((name, "".join(chunks)))
                name = safe_name(line[1:].split()[0])
                chunks = []
            else:
                chunks.append(line)
    if name:
        records.append((name, "".join(chunks)))
    return records


def normalize_sequence(seq: str, args: argparse.Namespace) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    letters = re.sub(r"[^A-Za-z*.-]", "", seq).upper()
    cleaned: List[str] = []
    invalid: List[str] = []
    ambiguous: List[str] = []
    allowed = ALLOWED_AA if args.allow_ambiguous_aa else STANDARD_AA
    for char in letters:
        if char in allowed:
            cleaned.append(char)
            if char in AMBIGUOUS_AA:
                ambiguous.append(char)
        elif char in ALLOWED_AA and not args.allow_ambiguous_aa:
            invalid.append(char)
            if args.sanitize_invalid_to_x:
                cleaned.append("X")
        else:
            invalid.append(char)
            if args.sanitize_invalid_to_x:
                cleaned.append("X")
    if invalid and not args.sanitize_invalid_to_x:
        raise ValueError(f"invalid amino-acid symbols: {''.join(sorted(set(invalid)))}")
    if invalid and args.sanitize_invalid_to_x:
        warnings.append(f"invalid_symbols_converted_to_X:{''.join(sorted(set(invalid)))}")
    if ambiguous:
        warnings.append(f"ambiguous_residues_present:{''.join(sorted(set(ambiguous)))}")
    sequence = "".join(cleaned)
    if len(sequence) < args.min_length:
        raise ValueError(f"sequence length {len(sequence)} is shorter than minimum {args.min_length}")
    if len(sequence) > args.max_length:
        raise ValueError(f"sequence length {len(sequence)} exceeds maximum {args.max_length}")
    if len(sequence) > 1022 and args.deeploc_model == "fast":
        warnings.append("deeploc_fast_model_truncates_or_limits_sequences_above_1022_residues")
    if len(sequence) > 4000 and args.deeploc_model == "slow":
        warnings.append("deeploc_slow_model_represents_sequences_above_4000_by_terminal_segments")
    return sequence, warnings


def collect_records(args: argparse.Namespace) -> Tuple[List[Tuple[str, str]], Dict[str, List[str]]]:
    records: List[Tuple[str, str]] = []
    warnings: Dict[str, List[str]] = defaultdict(list)
    for path_text in args.fasta:
        path = Path(path_text).expanduser()
        if not path.exists():
            raise FileNotFoundError(path)
        for name, seq in read_fasta(path):
            normalized, row_warnings = normalize_sequence(seq, args)
            records.append((safe_name(name), normalized))
            warnings[safe_name(name)].extend(row_warnings)
    for idx, seq in enumerate(args.sequence):
        name = args.sequence_name[idx] if idx < len(args.sequence_name) else f"query{idx + 1}"
        normalized, row_warnings = normalize_sequence(seq, args)
        records.append((safe_name(name), normalized))
        warnings[safe_name(name)].extend(row_warnings)
    deduped: List[Tuple[str, str]] = []
    seen: Dict[str, int] = defaultdict(int)
    for name, seq in records:
        seen[name] += 1
        final_name = name if seen[name] == 1 else f"{name}_{seen[name]}"
        deduped.append((final_name, seq))
    return deduped, warnings


def write_fasta(path: Path, records: Sequence[Tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for name, seq in records:
            handle.write(f">{name}\n")
            for idx in range(0, len(seq), 60):
                handle.write(seq[idx : idx + 60] + "\n")


def write_tsv(path: Path, rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "NA", "None", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        match = re.search(r"Pr:\s*([0-9.]+)", text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def fmt_float(value: Any) -> str:
    number = as_float(value)
    return "" if number is None else f"{number:.4f}"


def join_values(values: Iterable[Any]) -> str:
    seen = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)
    return ";".join(seen)


def read_table(path: Path) -> List[Dict[str, str]]:
    lines = [line.rstrip("\n") for line in path.read_text(errors="replace").splitlines() if line.strip()]
    if not lines:
        return []
    header_idx = 0
    for idx, line in enumerate(lines):
        if line.startswith("#") and ("\t" in line or "," in line):
            header_idx = idx
            break
        if not line.startswith("#"):
            header_idx = idx
            break
    header_line = lines[header_idx].lstrip("#").strip()
    delimiter = "\t" if header_line.count("\t") >= header_line.count(",") else ","
    reader = csv.DictReader(lines[header_idx:], delimiter=delimiter)
    rows: List[Dict[str, str]] = []
    for row in reader:
        cleaned = {clean_key(key): (value or "").strip() for key, value in row.items() if key is not None}
        if cleaned:
            rows.append(cleaned)
    return rows


def clean_key(key: str) -> str:
    return re.sub(r"\s+", " ", key.lstrip("#").strip())


def get_first(row: Dict[str, str], keys: Sequence[str]) -> str:
    lowered = {key.lower(): key for key in row}
    for key in keys:
        real = lowered.get(key.lower())
        if real is not None and str(row.get(real, "")).strip():
            return str(row[real]).strip()
    return ""


def find_numeric_label(row: Dict[str, str], labels: Sequence[str]) -> Tuple[str, Optional[float]]:
    best_label = ""
    best_score: Optional[float] = None
    lowered = {key.lower(): key for key in row}
    for label in labels:
        real = lowered.get(label.lower())
        if real is None:
            real = lowered.get(label.replace(" ", "_").lower())
        if real is None:
            continue
        score = as_float(row.get(real))
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_label = label
            best_score = score
    return best_label, best_score


def split_labels(value: str) -> List[str]:
    return [part.strip() for part in re.split(r"[;,|]", value or "") if part.strip()]


def feature_row(
    query_id: str,
    source: str,
    feature_type: str,
    label: str,
    score: Any = "",
    start: Any = "",
    end: Any = "",
    evidence: str = "",
    note: str = "",
) -> Dict[str, Any]:
    length = ""
    try:
        if start != "" and end != "":
            length = int(end) - int(start) + 1
    except (TypeError, ValueError):
        length = ""
    return {
        "query_id": query_id,
        "source": source,
        "feature_type": feature_type,
        "start": start,
        "end": end,
        "length": length,
        "label": label,
        "score": fmt_float(score),
        "evidence": evidence,
        "note": note,
    }


def score_row(query_id: str, source: str, score_type: str, label: str, score: Any, threshold: Any = "") -> Dict[str, Any]:
    numeric = as_float(score)
    threshold_number = as_float(threshold)
    above = ""
    if numeric is not None and threshold_number is not None:
        above = "true" if numeric >= threshold_number else "false"
    return {
        "query_id": query_id,
        "source": source,
        "score_type": score_type,
        "label": label,
        "score": fmt_float(score),
        "threshold": fmt_float(threshold),
        "above_threshold": above,
    }


def parse_deeploc_table(path: Path, threshold: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    features: List[Dict[str, Any]] = []
    scores: List[Dict[str, Any]] = []
    meta: Dict[str, Dict[str, Any]] = {}
    for row in read_table(path):
        query_id = safe_name(
            get_first(row, ["Protein_ID", "Protein Id", "Sequence_ID", "Entry", "ID", "Name", "query_id"])
            or next(iter(row.values()), "query")
        )
        localizations = split_labels(
            get_first(row, ["Localizations", "Localization", "Predicted localizations", "Predicted localization(s)"])
        )
        membranes = split_labels(get_first(row, ["Membrane types", "Membrane type", "Membrane association", "Membrane"]))
        signals = split_labels(get_first(row, ["Signals", "Sorting signals", "Predicted signals", "Signal"]))
        top_loc, top_score = find_numeric_label(row, LOCALIZATION_LABELS)
        top_mem, _ = find_numeric_label(row, MEMBRANE_LABELS)
        if not localizations and top_loc:
            localizations = [top_loc]
        if not membranes and top_mem:
            membranes = [top_mem]
        meta.setdefault(query_id, {})
        meta[query_id].update(
            {
                "deeploc_top_localization": localizations[0] if localizations else top_loc,
                "deeploc_localizations": join_values(localizations),
                "deeploc_membrane_association": join_values(membranes),
                "deeploc_signals": join_values(signals),
            }
        )
        for label in localizations:
            score = row.get(label, top_score if label == top_loc else "")
            features.append(feature_row(query_id, "DeepLoc-2.1", "subcellular_location", label, score, evidence="deeploc_prediction"))
        for label in membranes:
            features.append(feature_row(query_id, "DeepLoc-2.1", "membrane_association", label, row.get(label, ""), evidence="deeploc_prediction"))
        for label in signals:
            features.append(feature_row(query_id, "DeepLoc-2.1", "sorting_signal", label, "", evidence="deeploc_prediction"))
        lowered = {key.lower(): key for key in row}
        for label in LOCALIZATION_LABELS:
            real = lowered.get(label.lower()) or lowered.get(label.replace(" ", "_").lower())
            if real and as_float(row.get(real)) is not None:
                scores.append(score_row(query_id, "DeepLoc-2.1", "localization_probability", label, row[real], threshold))
        for label in MEMBRANE_LABELS:
            real = lowered.get(label.lower()) or lowered.get(label.replace(" ", "_").lower())
            if real and as_float(row.get(real)) is not None:
                scores.append(score_row(query_id, "DeepLoc-2.1", "membrane_probability", label, row[real], threshold))
    return features, scores, meta


def parse_cleavage_site(value: str) -> Tuple[str, str, str, str]:
    text = value or ""
    before_prob = re.split(r"\bPr\b|prob", text, maxsplit=1, flags=re.IGNORECASE)[0]
    numbers = re.findall(r"\d+", before_prob)
    if not numbers:
        return "", "", "", ""
    if len(numbers) >= 2:
        site = f"{numbers[0]}-{numbers[1]}"
    else:
        site = numbers[0]
    end = numbers[0]
    return site, "1", end, "signal_peptide_end_inferred_from_cleavage_site"


def is_signalp_positive(prediction: str) -> bool:
    text = prediction.strip().lower()
    if not text:
        return False
    negative = {"other", "no", "none", "no_sp", "no signal peptide", "non-sp", "no-sp"}
    return text not in negative and "other" not in text


def parse_signalp_table(path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    features: List[Dict[str, Any]] = []
    scores: List[Dict[str, Any]] = []
    meta: Dict[str, Dict[str, Any]] = {}
    for row in read_table(path):
        query_id = safe_name(get_first(row, ["ID", "Protein_ID", "Sequence_ID", "Name", "query_id"]) or next(iter(row.values()), "query"))
        prediction = get_first(row, ["Prediction", "pred", "signal peptide", "signalp_prediction"])
        cleavage_text = get_first(row, ["CS Position", "CS position", "Cleavage site", "cleavage_site", "CS"])
        if not cleavage_text:
            for key, value in row.items():
                if "cs" in key.lower() and "pos" in key.lower():
                    cleavage_text = value
                    break
        site, start, end, note = parse_cleavage_site(cleavage_text)
        probability = ""
        if cleavage_text:
            probability = fmt_float(cleavage_text)
        for key, value in row.items():
            key_low = key.lower()
            if "cs" in key_low or "cleavage" in key_low:
                continue
            if as_float(value) is not None and key_low not in {"id", "position", "start", "end"}:
                scores.append(score_row(query_id, "SignalP-6.0", "signalp_probability", key, value))
                if key.lower() in {"sp(seci/spi)", "sp", prediction.lower(), prediction.replace(" ", "_").lower()}:
                    probability = fmt_float(value)
        positive = is_signalp_positive(prediction)
        meta.setdefault(query_id, {})
        meta[query_id].update(
            {
                "signalp_prediction": prediction,
                "signalp_signal_peptide": "yes" if positive else "no",
                "signalp_cleavage_site": site,
                "signalp_probability": probability,
            }
        )
        if positive:
            features.append(
                feature_row(
                    query_id,
                    "SignalP-6.0",
                    "signal_peptide",
                    prediction,
                    probability,
                    start,
                    end,
                    evidence="signalp_prediction",
                    note=note,
                )
            )
    return features, scores, meta


def normalize_targetp_label(value: str) -> str:
    text = (value or "").strip()
    low = text.lower()
    aliases = {
        "mt": "mTP",
        "mtp": "mTP",
        "ch": "cTP",
        "ctp": "cTP",
        "th": "lTP",
        "ltp": "lTP",
        "sp": "SP",
        "signal peptide": "SP",
        "other": "Other",
        "no_tp": "Other",
    }
    return aliases.get(low, text)


def targetp_feature_type(label: str) -> str:
    normalized = normalize_targetp_label(label)
    return {
        "SP": "signal_peptide",
        "mTP": "mitochondrial_transit_peptide",
        "cTP": "chloroplast_transit_peptide",
        "lTP": "thylakoid_luminal_transit_peptide",
    }.get(normalized, "targeting_peptide")


def targetp_localization_hint(label: str) -> str:
    normalized = normalize_targetp_label(label)
    return {
        "SP": "secretory_pathway_candidate",
        "mTP": "Mitochondrion",
        "cTP": "Chloroplast",
        "lTP": "Thylakoid lumen",
        "Other": "",
    }.get(normalized, "")


def parse_targetp_table(path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    features: List[Dict[str, Any]] = []
    scores: List[Dict[str, Any]] = []
    meta: Dict[str, Dict[str, Any]] = {}
    for row in read_table(path):
        query_id = safe_name(get_first(row, ["ID", "Protein_ID", "Sequence_ID", "Name", "query_id"]) or next(iter(row.values()), "query"))
        prediction = normalize_targetp_label(
            get_first(row, ["Prediction", "pred", "targetp_prediction", "Predicted presequence", "Type"])
        )
        top_label, top_score = find_numeric_label(row, TARGETP_LABELS)
        top_label = normalize_targetp_label(top_label)
        if not prediction:
            prediction = top_label
        cleavage_text = get_first(row, ["CS Position", "CS position", "Cleavage site", "cleavage_site", "CS", "TP length", "Length"])
        site, start, end, note = parse_cleavage_site(cleavage_text)
        probability = fmt_float(top_score)
        lowered = {key.lower(): key for key in row}
        seen_score_labels = set()
        for label in TARGETP_LABELS:
            real = lowered.get(label.lower())
            if real is None:
                real = lowered.get(normalize_targetp_label(label).lower())
            if real and as_float(row.get(real)) is not None:
                display = normalize_targetp_label(label)
                if display in seen_score_labels:
                    continue
                seen_score_labels.add(display)
                scores.append(score_row(query_id, "TargetP-2.0", "targetp_probability", display, row[real]))
                if display == prediction:
                    probability = fmt_float(row[real])
        positive = bool(prediction and normalize_targetp_label(prediction) != "Other")
        meta.setdefault(query_id, {})
        meta[query_id].update(
            {
                "targetp_prediction": prediction,
                "targetp_presequence": "yes" if positive else "no",
                "targetp_cleavage_site": site,
                "targetp_probability": probability,
            }
        )
        if positive:
            features.append(
                feature_row(
                    query_id,
                    "TargetP-2.0",
                    targetp_feature_type(prediction),
                    prediction,
                    probability,
                    start,
                    end,
                    evidence="targetp_prediction",
                    note=note,
                )
            )
    return features, scores, meta


def parse_gff3_attributes(value: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for part in value.split(";"):
        if not part:
            continue
        if "=" in part:
            key, val = part.split("=", 1)
        elif " " in part:
            key, val = part.split(" ", 1)
        else:
            key, val = part, ""
        attrs[key.strip()] = val.strip()
    return attrs


def parse_signalp_gff3(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    features: List[Dict[str, Any]] = []
    meta: Dict[str, Dict[str, Any]] = {}
    with path.open() as handle:
        for raw in handle:
            if not raw.strip() or raw.startswith("#"):
                continue
            parts = raw.rstrip("\n").split("\t")
            if len(parts) < 9:
                continue
            query_id, source, feature_type, start, end, score, _, _, attrs_text = parts[:9]
            normalized_type = "signal_peptide" if "signal" in feature_type.lower() else feature_type
            attrs = parse_gff3_attributes(attrs_text)
            label = attrs.get("Name") or attrs.get("prediction") or normalized_type
            features.append(
                feature_row(
                    safe_name(query_id),
                    source or "SignalP-6.0",
                    normalized_type,
                    label,
                    score if score != "." else "",
                    start,
                    end,
                    evidence=feature_type,
                    note=attrs_text,
                )
            )
            if normalized_type == "signal_peptide":
                meta.setdefault(safe_name(query_id), {})
                meta[safe_name(query_id)].update(
                    {
                        "signalp_prediction": label,
                        "signalp_signal_peptide": "yes",
                        "signalp_cleavage_site": str(int(end) + 1) if str(end).isdigit() else "",
                        "signalp_probability": fmt_float(score),
                    }
                )
    return features, meta


def format_command(template: str, input_fasta: Path, outdir: Path, args: argparse.Namespace) -> str:
    mapping = {
        "input": str(input_fasta),
        "fasta": str(input_fasta),
        "outdir": str(outdir),
        "deeploc_model": args.deeploc_model,
        "deeploc_format": args.deeploc_format,
        "signalp_mode": args.signalp_mode,
        "signalp_organism": args.signalp_organism,
        "targetp_organism": args.targetp_organism,
        "targetp_format": args.targetp_format,
    }
    return template.format(**mapping)


def write_commands(
    path: Path,
    input_fasta: Path,
    tools: Sequence[str],
    args: argparse.Namespace,
    web_inputs: Dict[str, str],
) -> Dict[str, Dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    plans: Dict[str, Dict[str, Any]] = {}
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    if "deeploc" in tools:
        tool_outdir = path.parent / "deeploc"
        if args.deeploc_command_template:
            cmd = format_command(args.deeploc_command_template, input_fasta, tool_outdir, args)
            lines.extend([f"mkdir -p {shlex.quote(str(tool_outdir))}", cmd, ""])
            plans["deeploc"] = {"mode": "command_template", "command": cmd, "outdir": str(tool_outdir)}
        else:
            lines.append(f"# DeepLoc 2.1 web submission: {args.deeploc_web_url}")
            lines.append(f"# Upload FASTA: {web_inputs['deeploc']}")
            lines.append("# Import downloaded result table with --deeploc-output <FILE>.")
            lines.append("")
            plans["deeploc"] = {"mode": "web_or_import", "url": args.deeploc_web_url, "input": web_inputs["deeploc"]}
    if "signalp" in tools:
        tool_outdir = path.parent / "signalp"
        if args.signalp_command_template:
            cmd = format_command(args.signalp_command_template, input_fasta, tool_outdir, args)
            lines.extend([f"mkdir -p {shlex.quote(str(tool_outdir))}", cmd, ""])
            plans["signalp"] = {"mode": "command_template", "command": cmd, "outdir": str(tool_outdir)}
        else:
            lines.append(f"# SignalP 6.0 web submission: {args.signalp_web_url}")
            lines.append(f"# Upload FASTA: {web_inputs['signalp']}")
            lines.append("# Import downloaded result table with --signalp-output <FILE> or GFF3 with --signalp-gff3 <FILE>.")
            lines.append("")
            plans["signalp"] = {"mode": "web_or_import", "url": args.signalp_web_url, "input": web_inputs["signalp"]}
    if "targetp" in tools:
        tool_outdir = path.parent / "targetp"
        if args.targetp_command_template:
            cmd = format_command(args.targetp_command_template, input_fasta, tool_outdir, args)
            lines.extend([f"mkdir -p {shlex.quote(str(tool_outdir))}", cmd, ""])
            plans["targetp"] = {"mode": "command_template", "command": cmd, "outdir": str(tool_outdir)}
        else:
            lines.append(f"# TargetP 2.0 web submission: {args.targetp_web_url}")
            lines.append(f"# Upload FASTA: {web_inputs['targetp']}")
            lines.append("# Import downloaded result table with --targetp-output <FILE>.")
            lines.append("")
            plans["targetp"] = {"mode": "web_or_import", "url": args.targetp_web_url, "input": web_inputs["targetp"]}
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o755)
    return plans


def run_templates(plans: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    execution: Dict[str, Any] = {}
    for tool, plan in plans.items():
        if plan.get("mode") != "command_template":
            continue
        command = plan["command"]
        proc = subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        execution[tool] = {"returncode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]}
        if proc.returncode != 0:
            raise RuntimeError(f"{tool} command failed with exit code {proc.returncode}: {proc.stderr[-500:]}")
    return execution


def discover_tables(outdir: Path) -> List[Path]:
    if not outdir.exists():
        return []
    suffixes = {".tsv", ".csv", ".txt"}
    return sorted(path for path in outdir.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)


def discover_gff3(outdir: Path) -> List[Path]:
    if not outdir.exists():
        return []
    return sorted(path for path in outdir.rglob("*") if path.is_file() and path.suffix.lower() in {".gff", ".gff3"})


def summarize(
    records: Sequence[Tuple[str, str]],
    features: Sequence[Dict[str, Any]],
    scores: Sequence[Dict[str, Any]],
    deeploc_meta: Dict[str, Dict[str, Any]],
    signalp_meta: Dict[str, Dict[str, Any]],
    targetp_meta: Dict[str, Dict[str, Any]],
    warnings: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    lengths = {name: len(seq) for name, seq in records}
    query_ids = sorted(set(lengths) | set(deeploc_meta) | set(signalp_meta) | set(targetp_meta) | {str(row["query_id"]) for row in features})
    rows: List[Dict[str, Any]] = []
    for query_id in query_ids:
        q_features = [row for row in features if row["query_id"] == query_id]
        sources = join_values(row["source"] for row in q_features) or join_values(row["source"] for row in scores if row["query_id"] == query_id)
        dmeta = deeploc_meta.get(query_id, {})
        smeta = signalp_meta.get(query_id, {})
        tmeta = targetp_meta.get(query_id, {})
        top = dmeta.get("deeploc_top_localization", "")
        signalp_positive = smeta.get("signalp_signal_peptide") == "yes"
        targetp_hint = targetp_localization_hint(tmeta.get("targetp_prediction", ""))
        if top:
            integrated = top
        elif targetp_hint:
            integrated = targetp_hint
        elif signalp_positive:
            integrated = "secretory_pathway_candidate"
        else:
            integrated = "no_localization_prediction"
        secretory_bits = []
        if dmeta.get("deeploc_signals"):
            secretory_bits.append(f"DeepLoc signals={dmeta['deeploc_signals']}")
        if smeta.get("signalp_prediction"):
            secretory_bits.append(f"SignalP={smeta.get('signalp_prediction')}")
        if tmeta.get("targetp_prediction"):
            secretory_bits.append(f"TargetP={tmeta.get('targetp_prediction')}")
        rows.append(
            {
                "query_id": query_id,
                "length": lengths.get(query_id, ""),
                "sources": sources,
                "deeploc_top_localization": top,
                "deeploc_localizations": dmeta.get("deeploc_localizations", ""),
                "deeploc_membrane_association": dmeta.get("deeploc_membrane_association", ""),
                "deeploc_signals": dmeta.get("deeploc_signals", ""),
                "signalp_prediction": smeta.get("signalp_prediction", ""),
                "signalp_signal_peptide": smeta.get("signalp_signal_peptide", ""),
                "signalp_cleavage_site": smeta.get("signalp_cleavage_site", ""),
                "signalp_probability": smeta.get("signalp_probability", ""),
                "targetp_prediction": tmeta.get("targetp_prediction", ""),
                "targetp_presequence": tmeta.get("targetp_presequence", ""),
                "targetp_cleavage_site": tmeta.get("targetp_cleavage_site", ""),
                "targetp_probability": tmeta.get("targetp_probability", ""),
                "integrated_localization": integrated,
                "secretory_pathway_evidence": join_values(secretory_bits),
                "warnings": join_values(warnings.get(query_id, [])),
            }
        )
    return rows


def write_summary_plot(root: Path, summary_rows: Sequence[Dict[str, Any]]) -> List[str]:
    if not summary_rows:
        return []
    plots_dir = root / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, row in enumerate(summary_rows):
        label = row.get("integrated_localization") or "no_prediction"
        signal = row.get("signalp_signal_peptide") or ""
        y = 34 + idx * 28
        rows.append(
            f'<text x="18" y="{y}" font-size="13">{escape_xml(row.get("query_id", ""))}</text>'
            f'<text x="230" y="{y}" font-size="13">{escape_xml(label)}</text>'
            f'<text x="520" y="{y}" font-size="13">{escape_xml("SP=" + signal if signal else "")}</text>'
        )
    height = max(90, 45 + len(summary_rows) * 28)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="{height}" viewBox="0 0 760 {height}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        '<text x="18" y="20" font-size="14" font-weight="700">Protein localization summary</text>'
        + "".join(rows)
        + "</svg>\n"
    )
    svg_path = plots_dir / "protein_localization_summary.svg"
    html_path = plots_dir / "protein_localization_summary.html"
    svg_path.write_text(svg)
    html_path.write_text(f"<!doctype html><html><body>{svg}</body></html>\n")
    return [str(svg_path), str(html_path)]


def escape_xml(value: Any) -> str:
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def parse_native_plot(value: str) -> Dict[str, str]:
    if ":" in value:
        source, path = value.split(":", 1)
    else:
        source, path = "native", value
    return {"source": source, "path": str(Path(path).expanduser())}


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    tools = selected_tools(args.tools)
    root = Path(args.outdir).expanduser()
    root.mkdir(parents=True, exist_ok=True)

    records, row_warnings = collect_records(args)
    if not records:
        row_warnings["run"].append("no_sequence_input_provided; import-only mode")
    input_fasta = root / "normalized_input.fasta"
    if records:
        write_fasta(input_fasta, records)

    web_dir = root / "web_submission"
    web_inputs = {
        "deeploc": str(web_dir / "deeploc_2_1_input.fasta"),
        "signalp": str(web_dir / "signalp_6_0_input.fasta"),
        "targetp": str(web_dir / "targetp_2_0_input.fasta"),
    }
    if records:
        write_fasta(Path(web_inputs["deeploc"]), records)
        write_fasta(Path(web_inputs["signalp"]), records)
        write_fasta(Path(web_inputs["targetp"]), records)

    plans = write_commands(root / "commands.sh", input_fasta, tools, args, web_inputs)
    execution: Dict[str, Any] = {}
    errors: List[str] = []
    if args.execute:
        try:
            execution = run_templates(plans)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    features: List[Dict[str, Any]] = []
    scores: List[Dict[str, Any]] = []
    deeploc_meta: Dict[str, Dict[str, Any]] = {}
    signalp_meta: Dict[str, Dict[str, Any]] = {}
    targetp_meta: Dict[str, Dict[str, Any]] = {}
    source_files: Dict[str, List[str]] = defaultdict(list)

    deeploc_paths = [Path(path).expanduser() for path in args.deeploc_output]
    if args.execute and "deeploc" in plans:
        deeploc_paths.extend(discover_tables(Path(plans["deeploc"].get("outdir", ""))))
    for path in deeploc_paths:
        if not path.exists():
            row_warnings["run"].append(f"deeploc_output_missing:{path}")
            continue
        try:
            new_features, new_scores, new_meta = parse_deeploc_table(path, args.deeploc_threshold)
            features.extend(new_features)
            scores.extend(new_scores)
            for key, value in new_meta.items():
                deeploc_meta.setdefault(key, {}).update(value)
            source_files["deeploc"].append(str(path))
        except Exception as exc:  # noqa: BLE001
            row_warnings["run"].append(f"deeploc_parse_failed:{path}:{exc}")

    signalp_paths = [Path(path).expanduser() for path in args.signalp_output]
    signalp_gff3_paths = [Path(path).expanduser() for path in args.signalp_gff3]
    if args.execute and "signalp" in plans:
        outdir = Path(plans["signalp"].get("outdir", ""))
        signalp_paths.extend(discover_tables(outdir))
        signalp_gff3_paths.extend(discover_gff3(outdir))
    for path in signalp_paths:
        if not path.exists():
            row_warnings["run"].append(f"signalp_output_missing:{path}")
            continue
        try:
            new_features, new_scores, new_meta = parse_signalp_table(path)
            features.extend(new_features)
            scores.extend(new_scores)
            for key, value in new_meta.items():
                signalp_meta.setdefault(key, {}).update(value)
            source_files["signalp"].append(str(path))
        except Exception as exc:  # noqa: BLE001
            row_warnings["run"].append(f"signalp_parse_failed:{path}:{exc}")
    for path in signalp_gff3_paths:
        if not path.exists():
            row_warnings["run"].append(f"signalp_gff3_missing:{path}")
            continue
        try:
            new_features, new_meta = parse_signalp_gff3(path)
            features.extend(new_features)
            for key, value in new_meta.items():
                signalp_meta.setdefault(key, {}).update(value)
            source_files["signalp_gff3"].append(str(path))
        except Exception as exc:  # noqa: BLE001
            row_warnings["run"].append(f"signalp_gff3_parse_failed:{path}:{exc}")

    targetp_paths = [Path(path).expanduser() for path in args.targetp_output]
    if args.execute and "targetp" in plans:
        targetp_paths.extend(discover_tables(Path(plans["targetp"].get("outdir", ""))))
    for path in targetp_paths:
        if not path.exists():
            row_warnings["run"].append(f"targetp_output_missing:{path}")
            continue
        try:
            new_features, new_scores, new_meta = parse_targetp_table(path)
            features.extend(new_features)
            scores.extend(new_scores)
            for key, value in new_meta.items():
                targetp_meta.setdefault(key, {}).update(value)
            source_files["targetp"].append(str(path))
        except Exception as exc:  # noqa: BLE001
            row_warnings["run"].append(f"targetp_parse_failed:{path}:{exc}")

    if "deeploc" in tools and not args.deeploc_output and not args.deeploc_command_template:
        row_warnings["run"].append("deeploc_requires_web_submission_import_or_command_template_for_predictions")
    if "signalp" in tools and not args.signalp_output and not args.signalp_gff3 and not args.signalp_command_template:
        row_warnings["run"].append("signalp_requires_web_submission_import_or_command_template_for_predictions")
    if "targetp" in tools and not args.targetp_output and not args.targetp_command_template:
        row_warnings["run"].append("targetp_requires_web_submission_import_or_command_template_for_predictions")

    summary_rows = summarize(records, features, scores, deeploc_meta, signalp_meta, targetp_meta, row_warnings)
    summary_path = root / "protein_localization_summary.tsv"
    features_path = root / "protein_localization_features.tsv"
    scores_path = root / "protein_localization_scores.tsv"
    write_tsv(summary_path, summary_rows, SUMMARY_COLUMNS)
    write_tsv(features_path, features, FEATURE_COLUMNS)
    write_tsv(scores_path, scores, SCORE_COLUMNS)

    plots: List[str] = []
    if not args.no_plots:
        plots = write_summary_plot(root, summary_rows)

    result = {
        "skill": "protein-localization-signal-annotation",
        "run_id": args.run_id or root.name,
        "tools": tools,
        "outputs": {
            "summary_tsv": str(summary_path),
            "features_tsv": str(features_path),
            "scores_tsv": str(scores_path),
            "result_json": str(root / "protein_localization_signal_annotation.result.json"),
            "commands_sh": str(root / "commands.sh"),
            "normalized_input_fasta": str(input_fasta) if records else "",
            "web_submission_inputs": web_inputs,
            "plots": plots,
        },
        "counts": {"records": len(records), "summary_rows": len(summary_rows), "features": len(features), "scores": len(scores)},
        "plans": plans,
        "execution": execution,
        "source_files": source_files,
        "native_plots": [parse_native_plot(value) for value in args.native_plot],
        "warnings": dict(row_warnings),
        "errors": errors,
    }
    result_path = root / "protein_localization_signal_annotation.result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"saved summary: {summary_path}")
    print(f"saved features: {features_path}")
    print(f"saved scores: {scores_path}")
    print(f"saved result: {result_path}")
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
