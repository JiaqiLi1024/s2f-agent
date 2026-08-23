#!/usr/bin/env python3
"""Normalize TMHMM/DeepTMHMM topology outputs into residue states and plots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shlex
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SUMMARY_COLUMNS = [
    "query_id",
    "length",
    "sources",
    "topology_class",
    "n_tm_helices",
    "n_beta_strands",
    "n_signal_peptides",
    "n_inside_regions",
    "n_outside_regions",
    "n_periplasmic_regions",
    "n_other_regions",
    "topology_string",
    "warnings",
]

REGION_COLUMNS = [
    "query_id",
    "source",
    "feature_type",
    "start",
    "end",
    "length",
    "score",
    "strand",
    "phase",
    "evidence",
    "attributes",
    "note",
]

RESIDUE_COLUMNS = [
    "query_id",
    "source",
    "position",
    "residue",
    "state",
    "state_detail",
    "feature_type",
    "feature_id",
    "score",
    "attributes",
]

SOURCE_COLORS = {
    "TMhelix": "#2563eb",
    "Beta_strand": "#7c3aed",
    "inside": "#16a34a",
    "outside": "#dc2626",
    "periplasmic": "#f59e0b",
    "signal_peptide": "#0891b2",
    "other": "#6b7280",
    "unknown": "#d1d5db",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create standardized TM topology tables and plots from TMHMM/DeepTMHMM outputs."
    )
    parser.add_argument("--sequence", action="append", default=[], help="Raw amino-acid sequence.")
    parser.add_argument("--sequence-name", default="query")
    parser.add_argument("--fasta", action="append", default=[], help="Protein FASTA input.")
    parser.add_argument(
        "--tools",
        default="tmhmm,deeptmhmm",
        help="Comma- or plus-separated tools: tmhmm,deeptmhmm.",
    )
    parser.add_argument("--outdir", default="output/protein-tm-topology-annotation/run")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-ambiguous-aa", action="store_true")
    parser.add_argument("--no-plots", action="store_true")

    parser.add_argument("--gff3", action="append", default=[], help="Generic GFF3 input as SOURCE:PATH or PATH.")
    parser.add_argument("--tmhmm-gff3", action="append", default=[], help="TMHMM GFF3 output.")
    parser.add_argument("--deeptmhmm-gff3", action="append", default=[], help="DeepTMHMM GFF3 output.")
    parser.add_argument("--tmhmm-output", action="append", default=[], help="TMHMM long output text.")
    parser.add_argument("--native-plot", action="append", default=[], help="Native plot artifact as SOURCE:PATH or PATH.")

    parser.add_argument("--tmhmm-bin", default="tmhmm")
    parser.add_argument("--tmhmm-extra-args", default="")
    parser.add_argument(
        "--deeptmhmm-command-template",
        default="",
        help="Command template with {input} and {outdir}, for example: biolib run DTU/DeepTMHMM --fasta {input}.",
    )
    parser.add_argument("--timeout-sec", type=int, default=0, help="Per-command timeout; 0 disables timeout.")
    return parser.parse_args()


def selected_tools(value: str) -> List[str]:
    tools = [token.strip().lower() for token in re.split(r"[,+]", value or "") if token.strip()]
    if not tools or "all" in tools:
        tools = ["tmhmm", "deeptmhmm"]
    aliases = {"deep": "deeptmhmm", "deep-tmhmm": "deeptmhmm", "depp": "deeptmhmm", "deppTMHMM".lower(): "deeptmhmm"}
    normalized = [aliases.get(tool, tool) for tool in tools]
    valid = {"tmhmm", "deeptmhmm"}
    invalid = sorted(set(normalized) - valid)
    if invalid:
        raise SystemExit(f"Unsupported tool(s): {', '.join(invalid)}")
    return list(dict.fromkeys(normalized))


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "query"


def parse_fasta(path: Path, allow_ambiguous: bool = False) -> List[Tuple[str, str]]:
    records: List[Tuple[str, str]] = []
    name: Optional[str] = None
    chunks: List[str] = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    records.append((safe_name(name), clean_sequence("".join(chunks), allow_ambiguous)))
                name = line[1:].split()[0] or f"sequence_{len(records) + 1}"
                chunks = []
            else:
                chunks.append(line)
    if name is not None:
        records.append((safe_name(name), clean_sequence("".join(chunks), allow_ambiguous)))
    return records


def clean_sequence(sequence: str, allow_ambiguous: bool = False) -> str:
    seq = re.sub(r"\s+", "", sequence).upper()
    allowed = set("ACDEFGHIKLMNPQRSTVWY")
    if allow_ambiguous:
        allowed |= set("BXZJUO")
    invalid = sorted(set(seq) - allowed)
    if invalid:
        raise SystemExit(f"Invalid amino-acid character(s): {''.join(invalid)}")
    return seq


def collect_records(args: argparse.Namespace) -> List[Tuple[str, str]]:
    records: List[Tuple[str, str]] = []
    for fasta in args.fasta:
        records.extend(parse_fasta(Path(fasta).expanduser(), args.allow_ambiguous_aa))
    for index, sequence in enumerate(args.sequence, start=1):
        name = args.sequence_name if len(args.sequence) == 1 else f"{args.sequence_name}_{index}"
        records.append((safe_name(name), clean_sequence(sequence, args.allow_ambiguous_aa)))
    seen: Dict[str, int] = {}
    unique: List[Tuple[str, str]] = []
    for name, seq in records:
        base = safe_name(name)
        count = seen.get(base, 0)
        seen[base] = count + 1
        unique_name = base if count == 0 else f"{base}_{count + 1}"
        unique.append((unique_name, seq))
    return unique


def write_fasta(path: Path, records: Sequence[Tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for name, seq in records:
            handle.write(f">{name}\n")
            for i in range(0, len(seq), 60):
                handle.write(seq[i : i + 60] + "\n")


def write_tsv(path: Path, rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def parse_attributes(value: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for part in value.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, raw = part.split("=", 1)
        elif " " in part:
            key, raw = part.split(" ", 1)
        else:
            key, raw = part, ""
        attrs[key.strip()] = raw.strip().strip('"')
    return attrs


def format_attributes(attrs: Dict[str, str]) -> str:
    return ";".join(f"{key}={value}" if value else key for key, value in sorted(attrs.items()))


def normalize_feature_type(raw_type: str, attrs: Optional[Dict[str, str]] = None) -> str:
    attrs = attrs or {}
    text = " ".join([raw_type] + [attrs.get(k, "") for k in ("Name", "Note", "prediction", "Prediction", "type")])
    low = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if "signal" in low:
        return "signal_peptide"
    if "tmhelix" in low or "tm_helix" in low or "transmembrane_helix" in low or low == "tm":
        return "TMhelix"
    if "beta" in low and ("strand" in low or "barrel" in low):
        return "Beta_strand"
    if "periplasm" in low:
        return "periplasmic"
    if "outside" in low or "extracellular" in low or "non_cytoplasmic" in low or low in {"o", "out"}:
        return "outside"
    if "inside" in low or "cytoplasm" in low or "cytoplasmic" in low or low in {"i", "in"}:
        return "inside"
    if "membrane" in low or "transmembrane" in low:
        return "TMhelix"
    return raw_type.strip() or "other"


def parse_score(value: str) -> str:
    if value == ".":
        return ""
    return value


def region_length(start: Any, end: Any) -> int:
    try:
        return int(end) - int(start) + 1
    except (TypeError, ValueError):
        return 0


def parse_gff3(path: Path, source_label: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open() as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 9:
                continue
            seqid, source, feature_type, start, end, score, strand, phase, attr_text = fields[:9]
            attrs = parse_attributes(attr_text)
            normalized = normalize_feature_type(feature_type, attrs)
            rows.append(
                {
                    "query_id": safe_name(seqid),
                    "source": source_label or source or "GFF3",
                    "feature_type": normalized,
                    "start": int(start),
                    "end": int(end),
                    "length": int(end) - int(start) + 1,
                    "score": parse_score(score),
                    "strand": "" if strand == "." else strand,
                    "phase": "" if phase == "." else phase,
                    "evidence": feature_type,
                    "attributes": format_attributes(attrs),
                    "note": str(path),
                }
            )
    return rows


TMHMM_REGION_RE = re.compile(r"^(\S+)\s+TMHMM\S*\s+(\S+)\s+(\d+)\s+(\d+)\s*$")


def parse_tmhmm_output(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    rows: List[Dict[str, Any]] = []
    meta: Dict[str, Dict[str, str]] = defaultdict(dict)
    with path.open() as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                parse_tmhmm_meta(stripped, meta)
                continue
            match = TMHMM_REGION_RE.match(stripped)
            if not match:
                continue
            query_id, raw_type, start, end = match.groups()
            feature_type = normalize_feature_type(raw_type)
            rows.append(
                {
                    "query_id": safe_name(query_id),
                    "source": "TMHMM",
                    "feature_type": feature_type,
                    "start": int(start),
                    "end": int(end),
                    "length": int(end) - int(start) + 1,
                    "score": "",
                    "strand": "",
                    "phase": "",
                    "evidence": raw_type,
                    "attributes": "",
                    "note": str(path),
                }
            )
    return rows, meta


def parse_tmhmm_meta(line: str, meta: Dict[str, Dict[str, str]]) -> None:
    line = line.lstrip("#").strip()
    if " " not in line:
        return
    query_id, rest = line.split(None, 1)
    query_id = safe_name(query_id)
    patterns = [
        ("length", r"Length:\s*(\S+)"),
        ("predicted_tmhs", r"Number of predicted TMHs:\s*(\S+)"),
        ("expected_tm_aas", r"Exp number of AAs in TMHs:\s*(\S+)"),
        ("expected_tm_aas_first60", r"Exp number, first 60 AAs:\s*(\S+)"),
        ("n_in_probability", r"Total prob of N-in:\s*(\S+)"),
    ]
    for key, pattern in patterns:
        match = re.search(pattern, rest)
        if match:
            meta[query_id][key] = match.group(1)
    if "POSSIBLE N-term signal sequence" in rest:
        meta[query_id]["possible_n_term_signal_sequence"] = "true"


def expand_residue_rows(
    records: Sequence[Tuple[str, str]],
    regions: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    sequence_by_id = {name: seq for name, seq in records}
    max_end_by_key: Dict[Tuple[str, str], int] = defaultdict(int)
    regions_by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in regions:
        key = (str(row["query_id"]), str(row["source"]))
        max_end_by_key[key] = max(max_end_by_key[key], int(row["end"]))
        regions_by_key[key].append(row)

    residue_rows: List[Dict[str, Any]] = []
    for key, q_regions in sorted(regions_by_key.items()):
        query_id, source = key
        sequence = sequence_by_id.get(query_id, "")
        length = max(len(sequence), max_end_by_key[key])
        state_rows = [empty_state_row(query_id, source, pos, sequence) for pos in range(1, length + 1)]
        for region in sorted(q_regions, key=lambda r: (priority(str(r["feature_type"])), int(r["start"]), int(r["end"]))):
            feature_id = feature_identifier(region)
            for pos in range(max(1, int(region["start"])), min(length, int(region["end"])) + 1):
                idx = pos - 1
                state_rows[idx].update(
                    {
                        "state": state_label(str(region["feature_type"])),
                        "state_detail": region["feature_type"],
                        "feature_type": region["feature_type"],
                        "feature_id": feature_id,
                        "score": region.get("score", ""),
                        "attributes": region.get("attributes", ""),
                    }
                )
        residue_rows.extend(state_rows)
    return residue_rows


def empty_state_row(query_id: str, source: str, pos: int, sequence: str) -> Dict[str, Any]:
    residue = sequence[pos - 1] if 0 <= pos - 1 < len(sequence) else ""
    return {
        "query_id": query_id,
        "source": source,
        "position": pos,
        "residue": residue,
        "state": "unknown",
        "state_detail": "",
        "feature_type": "",
        "feature_id": "",
        "score": "",
        "attributes": "",
    }


def priority(feature_type: str) -> int:
    order = {
        "TMhelix": 0,
        "Beta_strand": 0,
        "signal_peptide": 1,
        "inside": 2,
        "outside": 2,
        "periplasmic": 2,
    }
    return order.get(feature_type, 3)


def state_label(feature_type: str) -> str:
    if feature_type in {"TMhelix", "Beta_strand", "inside", "outside", "periplasmic", "signal_peptide"}:
        return feature_type
    return "other"


def feature_identifier(region: Dict[str, Any]) -> str:
    attrs = parse_attributes(str(region.get("attributes", "")))
    for key in ("ID", "Name", "Parent"):
        if attrs.get(key):
            return attrs[key]
    return f"{region.get('feature_type')}:{region.get('start')}-{region.get('end')}"


def summarize(records: Sequence[Tuple[str, str]], regions: Sequence[Dict[str, Any]], warnings: Sequence[str]) -> List[Dict[str, Any]]:
    sequence_by_id = {name: seq for name, seq in records}
    regions_by_query: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    max_end: Dict[str, int] = defaultdict(int)
    for row in regions:
        q = str(row["query_id"])
        regions_by_query[q].append(row)
        max_end[q] = max(max_end[q], int(row["end"]))
    all_queries = sorted(set(sequence_by_id) | set(regions_by_query))
    summary_rows: List[Dict[str, Any]] = []
    for query_id in all_queries:
        q_regions = sorted(regions_by_query.get(query_id, []), key=lambda r: (str(r["source"]), int(r["start"]), int(r["end"])))
        sequence_length = len(sequence_by_id.get(query_id, ""))
        length = max(sequence_length, max_end.get(query_id, 0)) or ""
        feature_counts = defaultdict(int)
        for row in q_regions:
            feature_counts[str(row["feature_type"])] += 1
        summary_rows.append(
            {
                "query_id": query_id,
                "length": length,
                "sources": ";".join(sorted({str(row["source"]) for row in q_regions})),
                "topology_class": topology_class(q_regions),
                "n_tm_helices": feature_counts["TMhelix"],
                "n_beta_strands": feature_counts["Beta_strand"],
                "n_signal_peptides": feature_counts["signal_peptide"],
                "n_inside_regions": feature_counts["inside"],
                "n_outside_regions": feature_counts["outside"],
                "n_periplasmic_regions": feature_counts["periplasmic"],
                "n_other_regions": sum(count for feature, count in feature_counts.items() if feature not in {"TMhelix", "Beta_strand", "signal_peptide", "inside", "outside", "periplasmic"}),
                "topology_string": topology_string(q_regions),
                "warnings": ";".join(warnings_for_query(query_id, warnings)),
            }
        )
    return summary_rows


def topology_class(regions: Sequence[Dict[str, Any]]) -> str:
    features = {str(row["feature_type"]) for row in regions}
    if "Beta_strand" in features:
        return "beta_barrel_tm"
    if "TMhelix" in features:
        return "alpha_helical_tm"
    if "signal_peptide" in features:
        return "signal_peptide_only"
    if regions:
        return "no_tm_detected"
    return "no_prediction"


def topology_string(regions: Sequence[Dict[str, Any]]) -> str:
    parts = []
    for row in sorted(regions, key=lambda r: (str(r["source"]), int(r["start"]), int(r["end"]))):
        parts.append(f"{row['source']}:{row['feature_type']}:{row['start']}-{row['end']}")
    return "|".join(parts)


def warnings_for_query(query_id: str, warnings: Sequence[str]) -> List[str]:
    return [warning for warning in warnings if warning.startswith(f"{query_id}:") or ":" not in warning]


def build_command_plan(
    args: argparse.Namespace,
    input_fasta: Optional[Path],
    root: Path,
    tools: Sequence[str],
) -> Dict[str, Dict[str, Any]]:
    plans: Dict[str, Dict[str, Any]] = {}
    if not input_fasta:
        return plans
    if "tmhmm" in tools and not args.tmhmm_output and not args.tmhmm_gff3:
        outdir = root / "tmhmm"
        output = outdir / "tmhmm.long.txt"
        cmd = [args.tmhmm_bin]
        cmd.extend(shlex.split(args.tmhmm_extra_args))
        cmd.append(str(input_fasta))
        plans["tmhmm"] = {
            "commands": [cmd],
            "stdout_files": [str(output)],
            "expected_files": [str(output)],
        }
    if "deeptmhmm" in tools and not args.deeptmhmm_gff3 and args.deeptmhmm_command_template:
        outdir = root / "deeptmhmm"
        formatted = args.deeptmhmm_command_template.format(input=str(input_fasta), outdir=str(outdir))
        cmd = shlex.split(formatted)
        plans["deeptmhmm"] = {
            "commands": [cmd],
            "stdout_files": [str(outdir / "deeptmhmm.log")],
            "expected_files": [],
        }
    return plans


def run_plan(plans: Dict[str, Dict[str, Any]], timeout_sec: int) -> Dict[str, Any]:
    execution: Dict[str, Any] = {}
    for name, plan in plans.items():
        runs = []
        for command, stdout_file in zip(plan.get("commands", []), plan.get("stdout_files", [])):
            stdout_path = Path(stdout_file)
            stdout_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with stdout_path.open("w") as stdout:
                    completed = subprocess.run(
                        command,
                        stdout=stdout,
                        stderr=subprocess.STDOUT,
                        text=True,
                        check=False,
                        timeout=timeout_sec or None,
                    )
                runs.append({"command": command, "returncode": completed.returncode, "stdout": str(stdout_path)})
            except Exception as exc:  # noqa: BLE001
                runs.append({"command": command, "error": str(exc), "stdout": str(stdout_path)})
        execution[name] = runs
    return execution


def discover_gff3_files(path: Path) -> List[Path]:
    if path.is_file() and path.suffix.lower() in {".gff", ".gff3"}:
        return [path]
    if not path.exists():
        return []
    return sorted([p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in {".gff", ".gff3"}])


def parse_source_path(value: str, default_source: str) -> Tuple[str, Path]:
    if ":" in value and not re.match(r"^[A-Za-z]:[\\/]", value):
        left, right = value.split(":", 1)
        if right:
            return left or default_source, Path(right).expanduser()
    return default_source, Path(value).expanduser()


def write_plots(root: Path, residue_rows: Sequence[Dict[str, Any]], regions: Sequence[Dict[str, Any]]) -> List[str]:
    plots_dir = root / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    rows_by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    regions_by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in residue_rows:
        rows_by_key[(str(row["query_id"]), str(row["source"]))].append(row)
    for row in regions:
        regions_by_key[(str(row["query_id"]), str(row["source"]))].append(row)
    outputs: List[str] = []
    for key, rows in sorted(rows_by_key.items()):
        query_id, source = key
        svg = render_topology_svg(query_id, source, rows, regions_by_key.get(key, []))
        stem = safe_name(f"{query_id}.{source}.tm_topology")
        svg_path = plots_dir / f"{stem}.svg"
        html_path = plots_dir / f"{stem}.html"
        svg_path.write_text(svg, encoding="utf-8")
        html_path.write_text(
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(query_id)} {html.escape(source)} TM topology</title></head>"
            f"<body>{svg}</body></html>\n",
            encoding="utf-8",
        )
        outputs.extend([str(svg_path), str(html_path)])
    return outputs


def render_topology_svg(
    query_id: str,
    source: str,
    residue_rows: Sequence[Dict[str, Any]],
    regions: Sequence[Dict[str, Any]],
) -> str:
    length = len(residue_rows)
    width = max(760, min(1800, length * 4 + 180))
    height = 210
    left = 80
    right = 40
    track_y = 82
    track_h = 28
    scale_w = width - left - right

    def xpos(pos: int) -> float:
        if length <= 1:
            return float(left)
        return left + ((pos - 1) / max(1, length - 1)) * scale_w

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="28" font-family="Arial" font-size="16" font-weight="700">{html.escape(query_id)} TM topology</text>',
        f'<text x="{left}" y="50" font-family="Arial" font-size="12" fill="#4b5563">source: {html.escape(source)}; length: {length}</text>',
        f'<rect x="{left}" y="{track_y}" width="{scale_w}" height="{track_h}" fill="#f3f4f6" stroke="#9ca3af"/>',
    ]
    segments = residue_segments(residue_rows)
    for start, end, state in segments:
        color = SOURCE_COLORS.get(state, SOURCE_COLORS["other"])
        x1 = xpos(start)
        x2 = xpos(end + 1) if end < length else left + scale_w
        parts.append(
            f'<rect x="{x1:.2f}" y="{track_y}" width="{max(1.0, x2 - x1):.2f}" height="{track_h}" fill="{color}" opacity="0.88"/>'
        )
        if (x2 - x1) > 38:
            parts.append(
                f'<text x="{(x1 + x2) / 2:.2f}" y="{track_y + 18}" text-anchor="middle" font-family="Arial" font-size="10" fill="#ffffff">{html.escape(short_state(state))}</text>'
            )
    parts.append(f'<line x1="{left}" y1="{track_y + track_h + 18}" x2="{left + scale_w}" y2="{track_y + track_h + 18}" stroke="#111827"/>')
    for tick in axis_ticks(length):
        x = xpos(tick)
        parts.append(f'<line x1="{x:.2f}" y1="{track_y + track_h + 14}" x2="{x:.2f}" y2="{track_y + track_h + 22}" stroke="#111827"/>')
        parts.append(f'<text x="{x:.2f}" y="{track_y + track_h + 38}" text-anchor="middle" font-family="Arial" font-size="10">{tick}</text>')
    parts.append(f'<text x="{left}" y="{track_y + track_h + 58}" font-family="Arial" font-size="11" fill="#4b5563">GFF3/TMHMM regions are rendered as a state track. Native posterior probability curves require native probability data.</text>')

    legend_x = left
    legend_y = height - 28
    for state in ["TMhelix", "Beta_strand", "inside", "outside", "periplasmic", "signal_peptide", "unknown"]:
        parts.append(f'<rect x="{legend_x}" y="{legend_y - 11}" width="13" height="13" fill="{SOURCE_COLORS[state]}"/>')
        parts.append(f'<text x="{legend_x + 18}" y="{legend_y}" font-family="Arial" font-size="11">{html.escape(short_state(state))}</text>')
        legend_x += max(76, len(short_state(state)) * 7 + 28)

    for region in regions:
        if region["feature_type"] not in {"TMhelix", "Beta_strand", "signal_peptide"}:
            continue
        x1 = xpos(int(region["start"]))
        x2 = xpos(int(region["end"]) + 1) if int(region["end"]) < length else left + scale_w
        parts.append(
            f'<rect x="{x1:.2f}" y="{track_y - 14}" width="{max(1.0, x2 - x1):.2f}" height="8" fill="{SOURCE_COLORS.get(region["feature_type"], SOURCE_COLORS["other"])}" opacity="0.95"/>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def residue_segments(rows: Sequence[Dict[str, Any]]) -> List[Tuple[int, int, str]]:
    segments: List[Tuple[int, int, str]] = []
    active_state = ""
    active_start = 1
    for row in rows:
        pos = int(row["position"])
        state = str(row.get("state") or "unknown")
        if not active_state:
            active_state = state
            active_start = pos
        elif state != active_state:
            segments.append((active_start, pos - 1, active_state))
            active_state = state
            active_start = pos
    if active_state:
        segments.append((active_start, int(rows[-1]["position"]), active_state))
    return segments


def short_state(state: str) -> str:
    return {
        "TMhelix": "TM helix",
        "Beta_strand": "beta strand",
        "signal_peptide": "signal",
        "periplasmic": "periplasm",
    }.get(state, state)


def axis_ticks(length: int) -> List[int]:
    if length <= 0:
        return []
    if length <= 120:
        step = 20
    elif length <= 600:
        step = 100
    else:
        step = 250
    ticks = [1]
    ticks.extend(range(step, length + 1, step))
    if ticks[-1] != length:
        ticks.append(length)
    return sorted(set(ticks))


def sequence_hash(records: Sequence[Tuple[str, str]]) -> str:
    digest = hashlib.sha256()
    for name, seq in records:
        digest.update(f">{name}\n{seq}\n".encode())
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    tools = selected_tools(args.tools)
    root = Path(args.outdir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    records = collect_records(args)
    warnings: List[str] = []
    normalized_fasta: Optional[Path] = None
    if records:
        normalized_fasta = root / "normalized_input.fasta"
        write_fasta(normalized_fasta, records)
    elif not (args.gff3 or args.tmhmm_gff3 or args.deeptmhmm_gff3 or args.tmhmm_output):
        raise SystemExit("Provide --sequence, --fasta, --gff3, --tmhmm-gff3, --deeptmhmm-gff3, or --tmhmm-output.")

    plans = build_command_plan(args, normalized_fasta, root, tools)
    commands_path = root / "commands.sh"
    with commands_path.open("w") as handle:
        handle.write("#!/usr/bin/env bash\nset -euo pipefail\n")
        for plan in plans.values():
            for command in plan.get("commands", []):
                handle.write(" ".join(shlex.quote(str(part)) for part in command) + "\n")

    execution: Dict[str, Any] = {}
    if args.execute:
        execution = run_plan(plans, args.timeout_sec)
    else:
        for tool in tools:
            if tool == "tmhmm" and not (args.tmhmm_output or args.tmhmm_gff3):
                warnings.append("tmhmm_not_executed_run_with_execute_or_import_tmhmm_output")
            if tool == "deeptmhmm" and not (args.deeptmhmm_gff3 or args.deeptmhmm_command_template):
                warnings.append("deeptmhmm_requires_imported_gff3_or_command_template")

    regions: List[Dict[str, Any]] = []
    tmhmm_meta: Dict[str, Dict[str, str]] = {}
    gff3_inputs: List[Tuple[str, Path]] = []
    gff3_inputs.extend([("TMHMM", Path(p).expanduser()) for p in args.tmhmm_gff3])
    gff3_inputs.extend([("DeepTMHMM", Path(p).expanduser()) for p in args.deeptmhmm_gff3])
    gff3_inputs.extend([parse_source_path(value, "GFF3") for value in args.gff3])
    if args.execute and "deeptmhmm" in plans:
        for path in discover_gff3_files(root / "deeptmhmm"):
            gff3_inputs.append(("DeepTMHMM", path))
    if args.execute and "tmhmm" in plans:
        for expected in plans["tmhmm"].get("expected_files", []):
            path = Path(expected)
            if path.exists():
                parsed, meta = parse_tmhmm_output(path)
                regions.extend(parsed)
                tmhmm_meta.update(meta)

    for source, path in gff3_inputs:
        if not path.exists():
            warnings.append(f"gff3_missing:{path}")
            continue
        regions.extend(parse_gff3(path, source))

    for path_text in args.tmhmm_output:
        path = Path(path_text).expanduser()
        if not path.exists():
            warnings.append(f"tmhmm_output_missing:{path}")
            continue
        parsed, meta = parse_tmhmm_output(path)
        regions.extend(parsed)
        tmhmm_meta.update(meta)

    if not regions:
        warnings.append("no_topology_regions_parsed")

    residue_rows = expand_residue_rows(records, regions)
    summary_rows = summarize(records, regions, warnings)

    summary_path = root / "protein_tm_topology_summary.tsv"
    regions_path = root / "protein_tm_topology_regions.tsv"
    residues_path = root / "protein_tm_topology_residue_states.tsv"
    write_tsv(summary_path, summary_rows, SUMMARY_COLUMNS)
    write_tsv(regions_path, regions, REGION_COLUMNS)
    write_tsv(residues_path, residue_rows, RESIDUE_COLUMNS)

    plot_paths: List[str] = []
    if not args.no_plots and residue_rows:
        plot_paths = write_plots(root, residue_rows, regions)

    native_plots = [parse_source_path(value, "native_plot") for value in args.native_plot]
    result = {
        "skill": "protein-tm-topology-annotation",
        "run_id": args.run_id or root.name,
        "tools": tools,
        "inputs": {
            "fasta": args.fasta,
            "sequence_count": len(args.sequence),
            "normalized_fasta": str(normalized_fasta) if normalized_fasta else "",
            "sequence_sha256": sequence_hash(records) if records else "",
            "gff3": [str(path) for _, path in gff3_inputs],
            "tmhmm_output": args.tmhmm_output,
        },
        "outputs": {
            "summary_tsv": str(summary_path),
            "regions_tsv": str(regions_path),
            "residue_states_tsv": str(residues_path),
            "plots": plot_paths,
            "native_plots": [{"source": source, "path": str(path)} for source, path in native_plots],
            "commands": str(commands_path),
            "result_json": str(root / "protein_tm_topology_annotation.result.json"),
        },
        "counts": {
            "summary_rows": len(summary_rows),
            "regions": len(regions),
            "residue_states": len(residue_rows),
            "plots": len(plot_paths),
        },
        "execution": execution,
        "tmhmm_metadata": tmhmm_meta,
        "warnings": warnings,
    }
    result_path = root / "protein_tm_topology_annotation.result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"saved summary: {summary_path}")
    print(f"saved regions: {regions_path}")
    print(f"saved residue states: {residues_path}")
    if plot_paths:
        print(f"saved plots: {root / 'plots'}")
    print(f"saved result: {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
