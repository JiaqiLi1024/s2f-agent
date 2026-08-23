#!/usr/bin/env python3
"""Dependency-free table normalization and metrics for ProteinGym-style assays."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable


ASSAY_ALIASES = {
    "assay_id": ("assay_id", "DMS_id", "dms_id", "assay", "dataset"),
    "protein_id": ("protein_id", "UniProt_ID", "uniprot_id", "target_id", "protein"),
    "mutation": ("mutation", "mutant", "variant_id", "variant", "mutations"),
    "dms_score": ("DMS_score", "dms_score", "fitness", "experimental_score", "target"),
    "label": ("DMS_score_bin", "dms_score_bin", "label", "class", "clinical_label"),
}

SCORE_ALIASES = {
    "assay_id": ("assay_id", "DMS_id", "dms_id", "assay", "dataset"),
    "protein_id": ("protein_id", "UniProt_ID", "uniprot_id", "target_id", "protein"),
    "mutation": ("mutation", "mutant", "variant_id", "variant", "mutations"),
    "model_id": ("model_id", "model", "model_name", "predictor"),
    "score_name": ("score_name", "metric_name", "output_name"),
    "raw_score": ("raw_score", "score", "prediction", "predicted_score", "model_score"),
    "higher_is": ("higher_is", "direction", "score_direction"),
}

SUBSTITUTION_RE = re.compile(r"^[A-Z*]\d+[A-Z*](?::[A-Z*]\d+[A-Z*])*$")
INDEL_HINT_RE = re.compile(r"(?:del|ins|dup|fs|[+-]\d+)", re.IGNORECASE)


def detect_delimiter(path: Path) -> str:
    if path.suffix.lower() in {".tsv", ".tab"}:
        return "\t"
    if path.suffix.lower() == ".csv":
        return ","
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(8192)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except csv.Error:
        return "\t"


def read_table(path: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    table_path = Path(path)
    if not table_path.is_file():
        raise FileNotFoundError(f"Table not found: {table_path}")
    with table_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=detect_delimiter(table_path))
        if not reader.fieldnames:
            raise ValueError(f"Table has no header: {table_path}")
        fieldnames = [str(value).strip() for value in reader.fieldnames]
        rows = []
        for source in reader:
            rows.append({str(key).strip(): (value or "").strip() for key, value in source.items()})
    return rows, fieldnames


def write_tsv(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: format_cell(row.get(key)) for key in fieldnames})


def format_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        return f"{value:.12g}"
    return str(value)


def write_json(path: str | Path, payload: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_columns(
    headers: list[str], aliases: dict[str, tuple[str, ...]], explicit: dict[str, str | None]
) -> tuple[dict[str, str | None], list[str]]:
    header_lookup = {header.casefold(): header for header in headers}
    mapping: dict[str, str | None] = {}
    warnings: list[str] = []
    for canonical, choices in aliases.items():
        requested = explicit.get(canonical)
        if requested:
            if requested not in headers:
                raise ValueError(f"Requested column '{requested}' for {canonical} is absent")
            mapping[canonical] = requested
            continue
        hits = [header_lookup[item.casefold()] for item in choices if item.casefold() in header_lookup]
        mapping[canonical] = hits[0] if hits else None
        if len(dict.fromkeys(hits)) > 1:
            warnings.append(f"Multiple aliases for {canonical}: {hits}; selected {hits[0]}")
    return mapping, warnings


def normalize_mutation(value: str) -> str:
    return value.strip().replace(" ", "").replace(";", ":").upper()


def mutation_type(value: str) -> str:
    if SUBSTITUTION_RE.fullmatch(value):
        return "substitution"
    if INDEL_HINT_RE.search(value):
        return "indel"
    return "other"


def parse_float(value: str, field: str, row_number: int) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: {field} is not numeric: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"row {row_number}: {field} must be finite: {value!r}")
    return result


def normalize_label(value: str) -> int:
    token = value.strip().casefold()
    positives = {"1", "true", "positive", "pathogenic", "deleterious", "active"}
    negatives = {"0", "false", "negative", "benign", "neutral", "inactive"}
    if token in positives:
        return 1
    if token in negatives:
        return 0
    number = float(value)
    if number in {0.0, 1.0}:
        return int(number)
    raise ValueError(f"label is not binary: {value!r}")


def normalize_higher_is(value: str) -> str:
    token = (value or "higher").strip().casefold().replace("_", "-")
    if token in {
        "higher", "higher-is-better", "beneficial", "positive", "more-tolerated",
        "more-sequence-plausible", "more-evolutionarily-preferred", "more-fit",
        "more-mutant-preferred", "more-stable",
    }:
        return "higher"
    if token in {
        "lower", "lower-is-better", "deleterious", "negative", "more-deleterious",
        "more-pathogenic", "more-destabilizing", "less-stable",
    }:
        return "lower"
    raise ValueError(f"higher_is must be 'higher' or 'lower', got {value!r}")


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda idx: values[idx])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average = (start + 1 + end) / 2.0
        for offset in range(start, end):
            ranks[order[offset]] = average
        start = end
    return ranks


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    denominator = math.sqrt(sum((a - mean_x) ** 2 for a in x) * sum((b - mean_y) ** 2 for b in y))
    return numerator / denominator if denominator else None


def spearman(x: list[float], y: list[float]) -> float | None:
    return pearson(average_ranks(x), average_ranks(y))


def roc_auc(labels: list[int], scores: list[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    ranks = average_ranks(scores)
    positive_rank_sum = sum(rank for rank, label in zip(ranks, labels) if label == 1)
    return (positive_rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def matthews_corrcoef(labels: list[int], predictions: list[int]) -> float | None:
    tp = sum(a == 1 and b == 1 for a, b in zip(labels, predictions))
    tn = sum(a == 0 and b == 0 for a, b in zip(labels, predictions))
    fp = sum(a == 0 and b == 1 for a, b in zip(labels, predictions))
    fn = sum(a == 1 and b == 0 for a, b in zip(labels, predictions))
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return ((tp * tn - fp * fn) / denominator) if denominator else None


def ndcg(labels: list[float], scores: list[float], k: int | None = None, relevance: str = "rank") -> float | None:
    if len(labels) < 2:
        return None
    limit = min(k or len(labels), len(labels))
    if relevance == "rank":
        gains = average_ranks(labels)
    elif relevance == "raw-clipped":
        gains = [max(0.0, value) for value in labels]
    else:
        raise ValueError(f"Unknown NDCG relevance mode: {relevance}")
    if not any(gains):
        return None

    def dcg(order: list[int]) -> float:
        return sum(gains[idx] / math.log2(rank + 2.0) for rank, idx in enumerate(order[:limit]))

    predicted = sorted(range(len(scores)), key=lambda idx: scores[idx], reverse=True)
    ideal = sorted(range(len(gains)), key=lambda idx: gains[idx], reverse=True)
    denominator = dcg(ideal)
    return dcg(predicted) / denominator if denominator else None
