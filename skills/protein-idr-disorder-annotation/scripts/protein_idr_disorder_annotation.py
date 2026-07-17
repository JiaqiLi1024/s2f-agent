#!/usr/bin/env python3
"""Plan, run, and normalize protein IDR/disorder annotation workflows."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
AMBIGUOUS_AA = set("BXZJUO")
USER_AGENT = "s2f-agent-protein-idr-disorder-annotation/0.1"

SCORE_COLUMNS = [
    "query_id",
    "source",
    "score_type",
    "position",
    "residue",
    "score",
    "threshold",
    "above_threshold",
]

REGION_COLUMNS = [
    "query_id",
    "source",
    "region_type",
    "start",
    "end",
    "length",
    "mean_score",
    "max_score",
    "threshold",
    "evidence",
]

SUMMARY_COLUMNS = [
    "query_id",
    "length",
    "sources",
    "mean_disorder_score",
    "fraction_disordered",
    "n_disordered_residues",
    "n_idr_regions",
    "longest_idr",
    "n_binding_regions",
    "n_linker_regions",
    "warnings",
]

LLPS_SUMMARY_COLUMNS = [
    "query_id",
    "length",
    "sources",
    "pLLPS",
    "mean_aggregation_score",
    "fraction_aggregation_prone",
    "n_aggregation_prone_residues",
    "n_aggregation_regions",
    "n_dpr_regions",
    "n_hotspot_regions",
    "n_dor_regions",
    "n_ddr_regions",
    "n_cdr_regions",
    "warnings",
]

LLPS_FEATURE_COLUMNS = [
    "query_id",
    "source",
    "feature_type",
    "start",
    "end",
    "length",
    "score",
    "threshold",
    "evidence",
    "note",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Protein IDR/disorder annotation wrapper.")
    parser.add_argument("--sequence", help="Single amino-acid sequence.")
    parser.add_argument("--sequence-name", default="query_sequence")
    parser.add_argument("--fasta", action="append", default=[], help="Protein FASTA input; may be repeated.")
    parser.add_argument("--uniprot", action="append", default=[], help="UniProt accession for IUPred3 REST.")
    parser.add_argument(
        "--tools",
        default="metapredict,aiupred,iupred3",
        help="Comma- or plus-separated tools: metapredict,aiupred,iupred3,fuzdrop,aggrescanai.",
    )
    parser.add_argument("--outdir", default="output/protein-idr-disorder-annotation")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-ambiguous-aa", action="store_true")
    parser.add_argument("--disorder-threshold", type=float, default=0.5)
    parser.add_argument("--binding-threshold", type=float, default=0.5)
    parser.add_argument("--linker-threshold", type=float, default=0.5)
    parser.add_argument("--min-region-length", type=int, default=5)
    parser.add_argument("--merge-gap", type=int, default=2)

    parser.add_argument("--metapredict-bin", default="metapredict-predict-disorder")
    parser.add_argument("--metapredict-idrs-bin", default="metapredict-predict-idrs")
    parser.add_argument("--metapredict-graph-bin", default="metapredict-graph-disorder")
    parser.add_argument("--metapredict-plot", action="store_true")
    parser.add_argument("--metapredict-extra-args", default="")

    parser.add_argument("--aiupred-mode", choices=["cli", "nextflow"], default="cli")
    parser.add_argument("--aiupred-bin", default="aiupred")
    parser.add_argument("--aiupred-binding", action="store_true")
    parser.add_argument("--aiupred-linker", action="store_true")
    parser.add_argument("--aiupred-redox", action="store_true")
    parser.add_argument("--aiupred-force-cpu", action="store_true")
    parser.add_argument("--aiupred-nextflow-bin", default="nextflow")
    parser.add_argument("--aiupred-release", default="master")
    parser.add_argument("--aiupred-profile", default="conda,cpu")
    parser.add_argument("--aiupred-extra-args", default="")

    parser.add_argument("--iupred3-type", choices=["long", "short", "glob"], default="long")
    parser.add_argument("--iupred3-json", action="append", default=[], help="Existing IUPred3 JSON file.")
    parser.add_argument("--iupred3-timeout-sec", type=int, default=30)
    parser.add_argument("--no-iupred3-rest", action="store_true")
    parser.add_argument("--iupred3-local-bin", default=None)
    parser.add_argument("--iupred3-local-input-format", choices=["fasta", "table"], default="fasta")
    parser.add_argument("--iupred3-local-extra-args", default="")
    parser.add_argument("--fuzdrop-json", action="append", default=[], help="Existing FuzDrop JSON result file.")
    parser.add_argument("--fuzdrop-api-url", default="https://fuzpred.bio.unipd.it/api/submit_protein")
    parser.add_argument("--fuzdrop-captcha-token", default="", help="reCAPTCHA token for manual FuzDrop API submission.")
    parser.add_argument("--aggrescanai-csv", action="append", default=[], help="AggrescanAI CSV output with residue scores.")
    parser.add_argument("--aggrescanai-threshold", type=float, default=0.3)
    parser.add_argument("--aggrescanai-script", default="", help="Optional local AggrescanAI runner script.")
    parser.add_argument("--aggrescanai-extra-args", default="")
    parser.add_argument("--llps-threshold", type=float, default=0.5)
    parser.add_argument("--no-plots", action="store_true", help="Disable built-in SVG/HTML profile plots.")
    return parser.parse_args()


def shell_join(cmd: Iterable[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in cmd)


def split_extra_args(raw: str) -> List[str]:
    return shlex.split(raw) if raw.strip() else []


def safe_name(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return clean.strip("._-") or "protein_idr"


def normalize_sequence(raw: str) -> str:
    parts = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(">"):
            parts.append(stripped)
    return "".join(parts).replace(" ", "").replace("\t", "").upper()


def read_fasta(path: Path) -> List[Tuple[str, str]]:
    records: List[Tuple[str, str]] = []
    header: Optional[str] = None
    seq_parts: List[str] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(">"):
                if header is not None:
                    records.append((header.split()[0], normalize_sequence("\n".join(seq_parts))))
                header = stripped[1:].strip() or f"record_{len(records) + 1}"
                seq_parts = []
            else:
                seq_parts.append(stripped)
    if header is not None:
        records.append((header.split()[0], normalize_sequence("\n".join(seq_parts))))
    return records


def write_fasta(path: Path, records: Sequence[Tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for name, sequence in records:
            handle.write(f">{name}\n")
            for i in range(0, len(sequence), 80):
                handle.write(sequence[i : i + 80] + "\n")


def write_iupred3_table_input(path: Path, records: Sequence[Tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        for name, sequence in records:
            if sequence:
                writer.writerow([name, sequence])


def validate_records(records: Sequence[Tuple[str, str]], allow_ambiguous: bool) -> List[str]:
    warnings: List[str] = []
    allowed = CANONICAL_AA | (AMBIGUOUS_AA if allow_ambiguous else set())
    for name, sequence in records:
        if not sequence:
            warnings.append(f"empty_sequence:{name}")
            continue
        invalid = sorted({aa for aa in sequence if aa not in allowed})
        if invalid:
            warnings.append(f"invalid_amino_acid_codes:{name}:{','.join(invalid)}")
    return warnings


def selected_tools(raw: str) -> List[str]:
    tools = [item.strip().lower() for item in re.split(r"[,+]", raw) if item.strip()]
    if "all" in tools:
        tools = ["metapredict", "aiupred", "iupred3", "fuzdrop", "aggrescanai"]
    valid = {"metapredict", "aiupred", "iupred3", "fuzdrop", "aggrescanai"}
    invalid = sorted(set(tools) - valid)
    if invalid:
        raise ValueError(f"Unsupported tool(s): {','.join(invalid)}")
    return tools


def build_commands(
    args: argparse.Namespace,
    input_fasta: Path,
    root: Path,
    tools: Sequence[str],
    iupred3_table_input: Optional[Path] = None,
    sequence_records: Sequence[Tuple[str, str]] = (),
) -> Dict[str, Dict[str, Any]]:
    plans: Dict[str, Dict[str, Any]] = {}
    if "metapredict" in tools:
        outdir = root / "metapredict"
        disorder_out = outdir / "metapredict_disorder.tsv"
        idr_out = outdir / "metapredict_idrs.tsv"
        cmd = [args.metapredict_bin, str(input_fasta), "-o", str(disorder_out)]
        cmd.extend(split_extra_args(args.metapredict_extra_args))
        idr_cmd = [args.metapredict_idrs_bin, str(input_fasta), "-o", str(idr_out)]
        graph_cmd: List[str] = []
        if args.metapredict_plot:
            graph_cmd = [args.metapredict_graph_bin, str(input_fasta), "-o", str(outdir / "plots")]
        plans["metapredict"] = {
            "commands": [cmd, idr_cmd] + ([graph_cmd] if graph_cmd else []),
            "expected_files": [str(disorder_out), str(idr_out)],
            "outdir": str(outdir),
        }

    if "aiupred" in tools:
        outdir = root / "aiupred"
        if args.aiupred_mode == "cli":
            output = outdir / "aiupred.tsv"
            cmd = [args.aiupred_bin, "-i", str(input_fasta), "-o", str(output)]
            if args.aiupred_binding:
                cmd.append("-b")
            if args.aiupred_linker:
                cmd.append("-l")
            if args.aiupred_redox:
                cmd.append("-r")
            if args.aiupred_force_cpu:
                cmd.append("--force-cpu")
            cmd.extend(split_extra_args(args.aiupred_extra_args))
            plans["aiupred"] = {
                "commands": [cmd],
                "expected_files": [str(output)],
                "outdir": str(outdir),
            }
        else:
            cmd = [
                args.aiupred_nextflow_bin,
                "run",
                "doszilab/AIUPred",
                "-r",
                args.aiupred_release,
                "-profile",
                args.aiupred_profile,
                "--input",
                str(input_fasta),
                "--outdir",
                str(outdir),
            ]
            if args.aiupred_binding:
                cmd.extend(["--aiupred.predict_binding", "true"])
            if args.aiupred_linker:
                cmd.extend(["--aiupred.predict_linker", "true"])
            if args.aiupred_redox:
                cmd.extend(["--aiupred.redox", "true"])
            cmd.extend(split_extra_args(args.aiupred_extra_args))
            plans["aiupred"] = {
                "commands": [cmd],
                "expected_files": [str(outdir)],
                "outdir": str(outdir),
            }

    if "iupred3" in tools and args.iupred3_local_bin:
        outdir = root / "iupred3"
        if args.iupred3_local_input_format == "table":
            output = outdir / "iupred3_local.txt"
            local_input = iupred3_table_input if iupred3_table_input else input_fasta
            cmd = [args.iupred3_local_bin, str(local_input), args.iupred3_type]
            cmd.extend(split_extra_args(args.iupred3_local_extra_args))
            plans["iupred3_local"] = {
                "commands": [cmd],
                "stdout_files": [str(output)],
                "expected_files": [str(output)],
                "input_format": args.iupred3_local_input_format,
                "outdir": str(outdir),
            }
        else:
            commands: List[List[str]] = []
            stdout_files: List[str] = []
            input_files: List[str] = []
            input_root = outdir / "single_fasta_inputs"
            for name, sequence in sequence_records:
                if not sequence:
                    continue
                one_fasta = input_root / f"{safe_name(name)}.fasta"
                write_fasta(one_fasta, [(name, sequence)])
                output = outdir / f"{safe_name(name)}.iupred3_local.txt"
                cmd = [args.iupred3_local_bin, str(one_fasta), args.iupred3_type]
                cmd.extend(split_extra_args(args.iupred3_local_extra_args))
                commands.append(cmd)
                stdout_files.append(str(output))
                input_files.append(str(one_fasta))
            plans["iupred3_local"] = {
                "commands": commands,
                "stdout_files": stdout_files,
                "expected_files": stdout_files,
                "input_files": input_files,
                "input_format": args.iupred3_local_input_format,
                "outdir": str(outdir),
            }

    if "fuzdrop" in tools and args.fuzdrop_captcha_token and sequence_records:
        outdir = root / "fuzdrop"
        plans["fuzdrop"] = {
            "commands": [],
            "api_url": args.fuzdrop_api_url,
            "expected_files": [str(outdir / "fuzdrop_api_results.jsonl")],
            "outdir": str(outdir),
            "note": "FuzDrop API submission requires an externally obtained reCAPTCHA token.",
        }

    if "aggrescanai" in tools and args.aggrescanai_script:
        outdir = root / "aggrescanai"
        output = outdir / "aggrescanai_results.csv"
        cmd = [args.aggrescanai_script, "--fasta", str(input_fasta), "--out", str(output)]
        cmd.extend(split_extra_args(args.aggrescanai_extra_args))
        plans["aggrescanai"] = {
            "commands": [cmd],
            "expected_files": [str(output)],
            "outdir": str(outdir),
        }
    return plans


def run_command(cmd: List[str], log_path: Path, stdout_path: Optional[Path] = None) -> Dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_handle = None
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"$ {shell_join(cmd)}\n\n")
        log.flush()
        try:
            if stdout_path:
                stdout_path.parent.mkdir(parents=True, exist_ok=True)
                stdout_handle = stdout_path.open("w", encoding="utf-8")
                process = subprocess.run(cmd, stdout=stdout_handle, stderr=log, check=False)
            else:
                process = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=False)
            return {"ok": process.returncode == 0, "returncode": process.returncode, "log": str(log_path)}
        finally:
            if stdout_handle:
                stdout_handle.close()


def fetch_iupred3_json(accession: str, iupred_type: str, timeout: int) -> Dict[str, Any]:
    urls = [
        f"https://iupred3.elte.hu/iupred3/{iupred_type}/{accession}.json",
        f"http://iupred3.elte.hu/iupred3/{iupred_type}/{accession}.json",
    ]
    last_error: Optional[Exception] = None
    for url in urls:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(f"IUPred3 REST request failed for {accession}: {last_error}")


def submit_fuzdrop_sequence(api_url: str, name: str, sequence: str, captcha_token: str, timeout: int) -> Dict[str, Any]:
    payload = json.dumps({"protein": f">{name}\n{sequence}\n", "captcha": captcha_token}).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
        raise RuntimeError(f"FuzDrop API request failed for {name}: {exc}") from exc


def as_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def infer_score_type(name: str) -> str:
    lower = name.lower()
    if "anchor" in lower or "binding" in lower:
        return "binding"
    if "linker" in lower:
        return "linker"
    if "redoxplus" in lower or "redox_plus" in lower:
        return "redox_plus_disorder"
    if "redoxminus" in lower or "redox_minus" in lower:
        return "redox_minus_disorder"
    if lower in {"exp_dis", "experimental_disorder"} or "experimental" in lower:
        return "experimental_disorder"
    if "aggrescan" in lower or "aggregation" in lower or lower in {"apr", "agg"}:
        return "aggregation"
    if "llps" in lower or "fuzdrop" in lower:
        return "llps_propensity"
    if "plddt" in lower:
        return "plddt"
    return "disorder"


def threshold_for(score_type: str, args: argparse.Namespace) -> float:
    if score_type == "binding":
        return args.binding_threshold
    if score_type == "linker":
        return args.linker_threshold
    if score_type == "aggregation":
        return args.aggrescanai_threshold
    if score_type == "llps_propensity":
        return args.llps_threshold
    return args.disorder_threshold


def extract_iupred_scores(data: Any, query_id: str, source: str, args: argparse.Namespace) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    if isinstance(data, dict):
        sequence = str(data.get("sequence") or data.get("seq") or "")
        score_fields = {
            key: value
            for key, value in data.items()
            if isinstance(value, list)
            and value
            and all(isinstance(item, (int, float)) or as_float(item) is not None for item in value[:10])
        }
        if not score_fields:
            for key in ("iupred2", "iupred", "anchor2", "scores", "result"):
                value = data.get(key)
                if isinstance(value, dict):
                    nested = extract_iupred_scores(value, query_id, f"{source}:{key}", args)
                    rows.extend(nested)
            if rows:
                return rows
        for field, values in score_fields.items():
            score_type = infer_score_type(field)
            threshold = threshold_for(score_type, args)
            for idx, value in enumerate(values, start=1):
                score = as_float(value)
                if score is None:
                    continue
                residue = sequence[idx - 1] if sequence and idx <= len(sequence) else ""
                rows.append(score_row(query_id, source, score_type, idx, residue, score, threshold))
        return rows

    if isinstance(data, list):
        for idx, item in enumerate(data, start=1):
            if isinstance(item, dict):
                position = int(item.get("position") or item.get("pos") or idx)
                residue = str(item.get("residue") or item.get("aa") or "")
                for key, value in item.items():
                    score = as_float(value)
                    if score is None or key.lower() in {"position", "pos"}:
                        continue
                    score_type = infer_score_type(key)
                    rows.append(score_row(query_id, source, score_type, position, residue, score, threshold_for(score_type, args)))
    return rows


def score_row(
    query_id: str,
    source: str,
    score_type: str,
    position: int,
    residue: str,
    score: float,
    threshold: float,
) -> Dict[str, Any]:
    return {
        "query_id": query_id,
        "source": source,
        "score_type": score_type,
        "position": position,
        "residue": residue,
        "score": f"{score:.4f}",
        "threshold": f"{threshold:.4f}",
        "above_threshold": "true" if score >= threshold else "false",
    }


def parse_aiupred_table(path: Path, args: argparse.Namespace) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    query_id = path.stem
    header: List[str] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                clean = stripped.lstrip("#").strip()
                if clean.lower().startswith("position"):
                    header = re.split(r"\s+|\t+", clean)
                elif clean and not clean.lower().startswith(("position", "residue")):
                    query_id = clean.split()[0]
                continue
            parts = re.split(r"\s+|\t+", stripped)
            if len(parts) < 3:
                continue
            if header and len(header) == len(parts):
                record = dict(zip(header, parts))
            else:
                record = {"Position": parts[0], "Residue": parts[1], "Disorder": parts[2]}
                if len(parts) > 3:
                    record["Region"] = parts[-1]
            try:
                position = int(record.get("Position") or record.get("position") or parts[0])
            except ValueError:
                continue
            residue = str(record.get("Residue") or record.get("residue") or parts[1])
            for key, value in record.items():
                if key.lower() in {"position", "residue", "region"}:
                    continue
                score = as_float(value)
                if score is None:
                    continue
                score_type = infer_score_type(key)
                rows.append(score_row(query_id, "AIUPred", score_type, position, residue, score, threshold_for(score_type, args)))
    return rows


def parse_generic_score_table(path: Path, source: str, args: argparse.Namespace) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header: Optional[List[str]] = None
        for parts in reader:
            if not parts:
                continue
            if parts[0].startswith("#"):
                continue
            lower = [part.lower() for part in parts]
            if any(item in lower for item in ("position", "pos")) and any(item in lower for item in ("score", "disorder")):
                header = parts
                continue
            if header and len(parts) == len(header):
                record = dict(zip(header, parts))
                query_id = record.get("query_id") or record.get("id") or path.stem
                position = record.get("position") or record.get("pos")
                residue = record.get("residue") or record.get("aa") or ""
                score = record.get("score") or record.get("disorder")
            elif len(parts) >= 3:
                query_id = path.stem
                position, residue, score = parts[0], parts[1], parts[2]
            else:
                continue
            score_f = as_float(score)
            if score_f is None:
                continue
            try:
                position_i = int(str(position))
            except ValueError:
                continue
            rows.append(score_row(str(query_id), source, "disorder", position_i, str(residue), score_f, args.disorder_threshold))
    return rows


def parse_iupred3_local_table(path: Path, args: argparse.Namespace) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for parts in reader:
            if len(parts) < 3 or not parts[0] or parts[0].startswith("#"):
                continue
            if parts[0].lower() in {"identifier", "query_id", "id"}:
                continue
            query_id = safe_name(parts[0])
            sequence = parts[1].strip().upper()
            score_columns = [("disorder", parts[2])]
            if len(parts) >= 5:
                score_columns.append(("binding", parts[4]))
            for score_type, raw_scores in score_columns:
                threshold = threshold_for(score_type, args)
                for idx, raw_score in enumerate(raw_scores.split(","), start=1):
                    score = as_float(raw_score.strip())
                    if score is None:
                        continue
                    residue = sequence[idx - 1] if idx <= len(sequence) else ""
                    rows.append(score_row(query_id, "IUPred3-local", score_type, idx, residue, score, threshold))
    return rows


def parse_iupred3_plain_output(path: Path, query_id: str, args: argparse.Namespace) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = re.split(r"\s+", stripped)
            if len(parts) < 3:
                continue
            try:
                position = int(parts[0])
            except ValueError:
                continue
            residue = parts[1]
            disorder_score = as_float(parts[2])
            if disorder_score is not None:
                rows.append(
                    score_row(
                        query_id,
                        "IUPred3-local",
                        "disorder",
                        position,
                        residue,
                        disorder_score,
                        args.disorder_threshold,
                    )
                )
            if len(parts) >= 4:
                binding_score = as_float(parts[3])
                if binding_score is not None:
                    rows.append(
                        score_row(
                            query_id,
                            "IUPred3-local",
                            "binding",
                            position,
                            residue,
                            binding_score,
                            args.binding_threshold,
                        )
                    )
    return rows


def parse_aggrescanai_csv(path: Path, args: argparse.Namespace) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;") if sample.strip() else csv.excel
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        for row in reader:
            query_id = (
                row.get("query_id")
                or row.get("protein_id")
                or row.get("uniprot_id")
                or row.get("id")
                or safe_name(path.stem)
            )
            position = row.get("position") or row.get("pos") or row.get("residue_index")
            residue = row.get("residue") or row.get("aa") or ""
            score = (
                as_float(row.get("aggrescanai_score"))
                or as_float(row.get("aggregation_score"))
                or as_float(row.get("score"))
                or as_float(row.get("probability"))
            )
            if score is None:
                continue
            try:
                position_i = int(str(position))
            except (TypeError, ValueError):
                continue
            rows.append(
                score_row(
                    safe_name(str(query_id)),
                    "AggrescanAI",
                    "aggregation",
                    position_i,
                    str(residue),
                    score,
                    args.aggrescanai_threshold,
                )
            )
    return rows


def int_or_blank(value: Any) -> Any:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return ""


def parse_region_bounds(item: Any) -> Tuple[Any, Any, str, str]:
    if isinstance(item, dict):
        start = (
            item.get("start")
            or item.get("begin")
            or item.get("from")
            or item.get("start_position")
            or item.get("start_residue")
        )
        end = item.get("end") or item.get("to") or item.get("stop") or item.get("end_position") or item.get("end_residue")
        score = item.get("score") or item.get("probability") or item.get("p") or item.get("mean_score") or ""
        note = item.get("name") or item.get("label") or item.get("type") or ""
        return int_or_blank(start), int_or_blank(end), stringify_simple(score), stringify_simple(note)
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        score = item[2] if len(item) >= 3 else ""
        return int_or_blank(item[0]), int_or_blank(item[1]), stringify_simple(score), ""
    text = str(item)
    match = re.search(r"(\d+)\D+(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2)), "", text
    return "", "", "", text


def stringify_simple(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def parse_fuzdrop_json(path: Path, fallback_query: str = "") -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    query_id = safe_name(
        str(
            data.get("query_id")
            or data.get("uniprot_acc")
            or data.get("uniprot_id")
            or data.get("id")
            or fallback_query
            or path.stem
        )
    )
    sequence = str(data.get("sequence") or "")
    pllps = data.get("pLLPS")
    if pllps is None:
        pllps = data.get("pllps")
    if pllps is None:
        pllps = data.get("p_llps")
    meta = {
        query_id: {
            "pLLPS": stringify_simple(pllps),
            "length": len(sequence) if sequence else "",
            "source": "FuzDrop",
        }
    }
    region_map = {
        "detected_regions_DPR": "droplet_promoting_region",
        "detected_regions_hotspots": "fuzdrop_hotspot",
        "detected_regions_DOR": "droplet_organizing_region",
        "detected_regions_DDR": "droplet_destabilizing_region",
        "detected_regions_CDR": "context_dependent_region",
    }
    features: List[Dict[str, Any]] = []
    for key, feature_type in region_map.items():
        values = data.get(key) or data.get(key.lower()) or []
        if isinstance(values, dict):
            values = values.get("regions") or values.get("data") or list(values.values())
        if not isinstance(values, list):
            values = [values]
        for item in values:
            start, end, score, note = parse_region_bounds(item)
            if start == "" or end == "":
                continue
            features.append(
                {
                    "query_id": query_id,
                    "source": "FuzDrop",
                    "feature_type": feature_type,
                    "start": start,
                    "end": end,
                    "length": interval_length(start, end),
                    "score": score,
                    "threshold": "",
                    "evidence": key,
                    "note": note,
                }
            )
    return features, meta


def interval_length(start: Any, end: Any) -> str:
    try:
        return str(int(str(end)) - int(str(start)) + 1)
    except (TypeError, ValueError):
        return ""


def make_llps_features(score_rows: Sequence[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for row in score_rows:
        score_type = str(row["score_type"])
        if score_type not in {"aggregation", "llps_propensity"}:
            continue
        key = (str(row["query_id"]), str(row["source"]), score_type)
        groups.setdefault(key, []).append(row)

    features: List[Dict[str, Any]] = []
    for (query_id, source, score_type), rows in groups.items():
        threshold = threshold_for(score_type, args)
        sorted_rows = sorted(rows, key=lambda item: int(item["position"]))
        active: List[Dict[str, Any]] = []
        last_pos: Optional[int] = None
        for row in sorted_rows:
            pos = int(row["position"])
            if float(row["score"]) >= threshold:
                if active and last_pos is not None and pos - last_pos > args.merge_gap + 1:
                    append_llps_feature(features, query_id, source, score_type, active, threshold, args)
                    active = []
                active.append(row)
                last_pos = pos
        if active:
            append_llps_feature(features, query_id, source, score_type, active, threshold, args)
    return features


def append_llps_feature(
    features: List[Dict[str, Any]],
    query_id: str,
    source: str,
    score_type: str,
    active: Sequence[Dict[str, Any]],
    threshold: float,
    args: argparse.Namespace,
) -> None:
    start = int(active[0]["position"])
    end = int(active[-1]["position"])
    length = end - start + 1
    if length < args.min_region_length:
        return
    values = [float(row["score"]) for row in active]
    feature_type = "aggregation_prone_region" if score_type == "aggregation" else "llps_prone_region"
    features.append(
        {
            "query_id": query_id,
            "source": source,
            "feature_type": feature_type,
            "start": start,
            "end": end,
            "length": length,
            "score": f"{sum(values) / len(values):.4f}",
            "threshold": f"{threshold:.4f}",
            "evidence": score_type,
            "note": f"Threshold-derived {feature_type}; max_score={max(values):.4f}.",
        }
    )


def summarize_llps(
    records: Sequence[Tuple[str, str]],
    score_rows: Sequence[Dict[str, Any]],
    llps_features: Sequence[Dict[str, Any]],
    fuzdrop_meta: Dict[str, Dict[str, Any]],
    warnings: Sequence[str],
) -> List[Dict[str, Any]]:
    record_lengths = {name: len(seq) for name, seq in records if seq}
    aggregation_by_query: Dict[str, List[Dict[str, Any]]] = {}
    for row in score_rows:
        if str(row["score_type"]) == "aggregation":
            aggregation_by_query.setdefault(str(row["query_id"]), []).append(row)
    query_ids = sorted(set(record_lengths) | set(aggregation_by_query) | set(fuzdrop_meta) | {str(row["query_id"]) for row in llps_features})
    rows: List[Dict[str, Any]] = []
    for query_id in query_ids:
        agg_scores = aggregation_by_query.get(query_id, [])
        agg_values = [float(row["score"]) for row in agg_scores]
        agg_above = [row for row in agg_scores if row["above_threshold"] == "true"]
        q_features = [row for row in llps_features if row["query_id"] == query_id]
        q_warnings = [warning for warning in warnings if f":{query_id}" in warning or warning.endswith(f":{query_id}")]
        length = record_lengths.get(query_id) or fuzdrop_meta.get(query_id, {}).get("length")
        if not length and agg_scores:
            length = max([int(row["position"]) for row in agg_scores], default=0) or ""
        sources = sorted({str(row["source"]) for row in q_features} | {str(row["source"]) for row in agg_scores})
        rows.append(
            {
                "query_id": query_id,
                "length": length,
                "sources": ";".join([source for source in sources if source]),
                "pLLPS": fuzdrop_meta.get(query_id, {}).get("pLLPS", ""),
                "mean_aggregation_score": fmt_float(sum(agg_values) / len(agg_values)) if agg_values else "",
                "fraction_aggregation_prone": fmt_float(len(agg_above) / len(agg_scores)) if agg_scores else "",
                "n_aggregation_prone_residues": len(agg_above),
                "n_aggregation_regions": sum(1 for row in q_features if row["feature_type"] == "aggregation_prone_region"),
                "n_dpr_regions": sum(1 for row in q_features if row["feature_type"] == "droplet_promoting_region"),
                "n_hotspot_regions": sum(1 for row in q_features if row["feature_type"] == "fuzdrop_hotspot"),
                "n_dor_regions": sum(1 for row in q_features if row["feature_type"] == "droplet_organizing_region"),
                "n_ddr_regions": sum(1 for row in q_features if row["feature_type"] == "droplet_destabilizing_region"),
                "n_cdr_regions": sum(1 for row in q_features if row["feature_type"] == "context_dependent_region"),
                "warnings": ";".join(q_warnings),
            }
        )
    return rows


def make_regions(score_rows: Sequence[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for row in score_rows:
        score_type = str(row["score_type"])
        if score_type in {"plddt", "experimental_disorder", "aggregation", "llps_propensity"}:
            continue
        key = (str(row["query_id"]), str(row["source"]), score_type)
        groups.setdefault(key, []).append(row)

    regions: List[Dict[str, Any]] = []
    for (query_id, source, score_type), rows in groups.items():
        sorted_rows = sorted(rows, key=lambda item: int(item["position"]))
        threshold = threshold_for(score_type, args)
        active: List[Dict[str, Any]] = []
        last_pos: Optional[int] = None
        for row in sorted_rows:
            pos = int(row["position"])
            score = float(row["score"])
            if score >= threshold:
                if active and last_pos is not None and pos - last_pos > args.merge_gap + 1:
                    append_region(regions, query_id, source, score_type, active, threshold, args)
                    active = []
                active.append(row)
                last_pos = pos
        if active:
            append_region(regions, query_id, source, score_type, active, threshold, args)
    return regions


def append_region(
    regions: List[Dict[str, Any]],
    query_id: str,
    source: str,
    score_type: str,
    active: Sequence[Dict[str, Any]],
    threshold: float,
    args: argparse.Namespace,
) -> None:
    start = int(active[0]["position"])
    end = int(active[-1]["position"])
    length = end - start + 1
    if length < args.min_region_length:
        return
    values = [float(row["score"]) for row in active]
    region_type = {
        "binding": "disordered_binding_region",
        "linker": "flexible_linker",
        "redox_plus_disorder": "redox_plus_idr",
        "redox_minus_disorder": "redox_minus_idr",
    }.get(score_type, "idr")
    regions.append(
        {
            "query_id": query_id,
            "source": source,
            "region_type": region_type,
            "start": start,
            "end": end,
            "length": length,
            "mean_score": f"{sum(values) / len(values):.4f}",
            "max_score": f"{max(values):.4f}",
            "threshold": f"{threshold:.4f}",
            "evidence": score_type,
        }
    )


def summarize(records: Sequence[Tuple[str, str]], score_rows: Sequence[Dict[str, Any]], regions: Sequence[Dict[str, Any]], warnings: Sequence[str]) -> List[Dict[str, Any]]:
    record_lengths = {name: len(seq) for name, seq in records if seq}
    by_query: Dict[str, List[Dict[str, Any]]] = {}
    for row in score_rows:
        if str(row["score_type"]) in {"disorder", "redox_plus_disorder", "redox_minus_disorder"}:
            by_query.setdefault(str(row["query_id"]), []).append(row)
    query_ids = sorted(set(record_lengths) | set(by_query) | {str(region["query_id"]) for region in regions})
    rows: List[Dict[str, Any]] = []
    for query_id in query_ids:
        scores = by_query.get(query_id, [])
        disorder_scores = [float(row["score"]) for row in scores]
        above = [row for row in scores if row["above_threshold"] == "true"]
        q_regions = [region for region in regions if region["query_id"] == query_id and region["region_type"] == "idr"]
        binding_regions = [region for region in regions if region["query_id"] == query_id and region["region_type"] == "disordered_binding_region"]
        linker_regions = [region for region in regions if region["query_id"] == query_id and region["region_type"] == "flexible_linker"]
        sources = sorted({str(row["source"]) for row in score_rows if row["query_id"] == query_id})
        q_warnings = [warning for warning in warnings if f":{query_id}" in warning or warning.endswith(f":{query_id}")]
        inferred_length = record_lengths.get(query_id)
        if inferred_length is None:
            inferred_length = max([int(row["position"]) for row in scores], default=0) or ""
        rows.append(
            {
                "query_id": query_id,
                "length": inferred_length,
                "sources": ";".join(sources),
                "mean_disorder_score": fmt_float(sum(disorder_scores) / len(disorder_scores)) if disorder_scores else "",
                "fraction_disordered": fmt_float(len(above) / len(scores)) if scores else "",
                "n_disordered_residues": len(above),
                "n_idr_regions": len(q_regions),
                "longest_idr": max([int(region["length"]) for region in q_regions], default=0),
                "n_binding_regions": len(binding_regions),
                "n_linker_regions": len(linker_regions),
                "warnings": ";".join(q_warnings),
            }
        )
    return rows


def fmt_float(value: float) -> str:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    return f"{value:.4f}"


def html_escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def svg_polyline(points: Sequence[Tuple[float, float]]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def write_profile_plots(
    root: Path,
    score_rows: Sequence[Dict[str, Any]],
    regions: Sequence[Dict[str, Any]],
    llps_features: Sequence[Dict[str, Any]],
) -> List[str]:
    plot_paths: List[str] = []
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for row in score_rows:
        score_type = str(row["score_type"])
        if score_type in {"experimental_disorder", "plddt"}:
            continue
        groups.setdefault((str(row["query_id"]), str(row["source"]), score_type), []).append(row)

    plots_dir = root / "plots"
    for (query_id, source, score_type), rows in groups.items():
        if not rows:
            continue
        sorted_rows = sorted(rows, key=lambda row: int(row["position"]))
        threshold = float(sorted_rows[0].get("threshold") or 0.5)
        title = f"{query_id} {source} {score_type} profile"
        feature_rows: List[Dict[str, Any]]
        if score_type in {"aggregation", "llps_propensity"}:
            feature_rows = [row for row in llps_features if row["query_id"] == query_id and row["source"] == source]
        else:
            feature_rows = [row for row in regions if row["query_id"] == query_id and row["source"] == source]
        svg = render_profile_svg(title, sorted_rows, feature_rows, threshold)
        stem = safe_name(f"{query_id}.{source}.{score_type}")
        svg_path = plots_dir / f"{stem}.svg"
        html_path = plots_dir / f"{stem}.html"
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(svg, encoding="utf-8")
        html_path.write_text(
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{html_escape(title)}</title></head><body>{svg}</body></html>\n",
            encoding="utf-8",
        )
        plot_paths.extend([str(svg_path), str(html_path)])

    feature_only_queries = sorted({str(row["query_id"]) for row in llps_features})
    for query_id in feature_only_queries:
        if any(key[0] == query_id and key[2] in {"aggregation", "llps_propensity"} for key in groups):
            continue
        q_features = [row for row in llps_features if row["query_id"] == query_id]
        if not q_features:
            continue
        svg = render_feature_map_svg(f"{query_id} LLPS feature map", q_features)
        stem = safe_name(f"{query_id}.llps_features")
        svg_path = plots_dir / f"{stem}.svg"
        html_path = plots_dir / f"{stem}.html"
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(svg, encoding="utf-8")
        html_path.write_text(
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{html_escape(query_id)} LLPS features</title></head><body>{svg}</body></html>\n",
            encoding="utf-8",
        )
        plot_paths.extend([str(svg_path), str(html_path)])
    return plot_paths


def render_profile_svg(
    title: str,
    rows: Sequence[Dict[str, Any]],
    feature_rows: Sequence[Dict[str, Any]],
    threshold: float,
) -> str:
    width, height = 980, 360
    left, right, top, bottom = 64, 24, 42, 48
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_pos = max([int(row["position"]) for row in rows], default=1)

    def x_for(pos: int) -> float:
        return left + (pos - 1) / max(max_pos - 1, 1) * plot_w

    def y_for(score: float) -> float:
        return top + (1.0 - max(0.0, min(score, 1.0))) * plot_h

    points = [(x_for(int(row["position"])), y_for(float(row["score"]))) for row in rows]
    threshold_y = y_for(threshold)
    rects = []
    colors = {
        "idr": "#9ecae1",
        "disordered_binding_region": "#fdd0a2",
        "flexible_linker": "#c7e9c0",
        "aggregation_prone_region": "#f4a3a8",
        "llps_prone_region": "#d7b5d8",
        "droplet_promoting_region": "#bcbddc",
        "fuzdrop_hotspot": "#fdae6b",
    }
    for feature in feature_rows:
        start = int_or_blank(feature.get("start"))
        end = int_or_blank(feature.get("end"))
        if start == "" or end == "":
            continue
        color = colors.get(str(feature.get("region_type") or feature.get("feature_type") or ""), "#d9d9d9")
        x = x_for(int(start))
        w = max(1.0, x_for(int(end)) - x)
        label = html_escape(feature.get("region_type") or feature.get("feature_type") or "")
        rects.append(f'<rect x="{x:.2f}" y="{top}" width="{w:.2f}" height="{plot_h}" fill="{color}" opacity="0.35"><title>{label} {start}-{end}</title></rect>')

    path = svg_polyline(points)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<style>text{font-family:Arial,sans-serif;font-size:13px}.title{font-size:18px;font-weight:700}.axis{stroke:#222;stroke-width:1}.grid{stroke:#ddd;stroke-dasharray:4 4}.line{fill:none;stroke:#1f77b4;stroke-width:2}</style>'
        f'<text class="title" x="{left}" y="24">{html_escape(title)}</text>'
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#fff" stroke="#ddd"/>'
        + "".join(rects)
        + f'<line class="grid" x1="{left}" x2="{left + plot_w}" y1="{threshold_y:.2f}" y2="{threshold_y:.2f}"/>'
        + f'<text x="{left + 6}" y="{threshold_y - 6:.2f}">threshold {threshold:.2f}</text>'
        + f'<polyline class="line" points="{path}"/>'
        + f'<line class="axis" x1="{left}" x2="{left + plot_w}" y1="{top + plot_h}" y2="{top + plot_h}"/>'
        + f'<line class="axis" x1="{left}" x2="{left}" y1="{top}" y2="{top + plot_h}"/>'
        + f'<text x="{left + plot_w / 2 - 36}" y="{height - 12}">Residue</text>'
        + f'<text x="10" y="{top + plot_h / 2}" transform="rotate(-90 10 {top + plot_h / 2})">Score</text>'
        + f'<text x="{left}" y="{top + plot_h + 18}">1</text>'
        + f'<text x="{left + plot_w - 36}" y="{top + plot_h + 18}">{max_pos}</text>'
        + '</svg>'
    )


def render_feature_map_svg(title: str, features: Sequence[Dict[str, Any]]) -> str:
    width, height = 980, 150
    left, right, top = 64, 24, 52
    max_pos = max([int(row["end"]) for row in features if int_or_blank(row.get("end")) != ""], default=1)
    plot_w = width - left - right

    def x_for(pos: int) -> float:
        return left + (pos - 1) / max(max_pos - 1, 1) * plot_w

    lanes = sorted({str(row.get("feature_type") or "feature") for row in features})
    lane_y = {name: top + idx * 20 for idx, name in enumerate(lanes)}
    colors = ["#9ecae1", "#fdd0a2", "#c7e9c0", "#bcbddc", "#f4a3a8", "#d9d9d9"]
    rects = []
    for feature in features:
        start = int_or_blank(feature.get("start"))
        end = int_or_blank(feature.get("end"))
        if start == "" or end == "":
            continue
        feature_type = str(feature.get("feature_type") or "feature")
        color = colors[lanes.index(feature_type) % len(colors)]
        x = x_for(int(start))
        w = max(2.0, x_for(int(end)) - x)
        y = lane_y[feature_type]
        rects.append(f'<rect x="{x:.2f}" y="{y}" width="{w:.2f}" height="12" fill="{color}"><title>{html_escape(feature_type)} {start}-{end}</title></rect>')
    labels = "".join(f'<text x="6" y="{y + 10}">{html_escape(name[:18])}</text>' for name, y in lane_y.items())
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height + max(0, len(lanes) - 1) * 20}" viewBox="0 0 {width} {height + max(0, len(lanes) - 1) * 20}">'
        '<style>text{font-family:Arial,sans-serif;font-size:12px}.title{font-size:18px;font-weight:700}.axis{stroke:#222;stroke-width:1}</style>'
        f'<text class="title" x="{left}" y="24">{html_escape(title)}</text>'
        f'<line class="axis" x1="{left}" x2="{left + plot_w}" y1="{top - 8}" y2="{top - 8}"/>'
        + labels
        + "".join(rects)
        + f'<text x="{left}" y="{top - 14}">1</text><text x="{left + plot_w - 36}" y="{top - 14}">{max_pos}</text>'
        + '</svg>'
    )


def write_tsv(path: Path, rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.outdir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    run_id = safe_name(args.run_id or args.sequence_name or "protein_idr")
    warnings: List[str] = []
    errors: List[str] = []
    tools = selected_tools(args.tools)

    records: List[Tuple[str, str]] = []
    if args.sequence:
        records.append((safe_name(args.sequence_name), normalize_sequence(args.sequence)))
    for fasta in args.fasta:
        path = Path(fasta).expanduser()
        if not path.exists():
            errors.append(f"FASTA not found: {path}")
            continue
        records.extend(read_fasta(path))
    records.extend([(safe_name(acc), "") for acc in args.uniprot if not records])
    warnings.extend(validate_records([(n, s) for n, s in records if s], args.allow_ambiguous_aa))

    input_fasta = root / "normalized_input.fasta"
    sequence_records = [(name, seq) for name, seq in records if seq]
    if sequence_records:
        write_fasta(input_fasta, sequence_records)
    else:
        input_fasta.write_text("", encoding="utf-8")
    iupred3_table_input: Optional[Path] = None
    if args.iupred3_local_bin and args.iupred3_local_input_format == "table":
        iupred3_table_input = root / "iupred3" / "iupred3_local_input.tsv"
        write_iupred3_table_input(iupred3_table_input, sequence_records)

    plans = build_commands(args, input_fasta, root, tools, iupred3_table_input, sequence_records)
    commands_path = root / "commands.sh"
    with commands_path.open("w", encoding="utf-8") as handle:
        handle.write("#!/usr/bin/env bash\nset -euo pipefail\n\n")
        for tool_name, plan in plans.items():
            handle.write(f"# {tool_name}\n")
            for cmd in plan["commands"]:
                handle.write(shell_join(cmd) + "\n")
            handle.write("\n")
        if "iupred3" in tools and args.uniprot and not args.no_iupred3_rest:
            for accession in args.uniprot:
                handle.write(f"# IUPred3 REST: https://iupred3.elte.hu/iupred3/{args.iupred3_type}/{accession}.json\n")
    commands_path.chmod(0o755)

    if args.execute:
        if "metapredict" in tools:
            if shutil.which(args.metapredict_bin) is None:
                errors.append(f"metapredict binary not found: {args.metapredict_bin}")
            if shutil.which(args.metapredict_idrs_bin) is None:
                errors.append(f"metapredict IDR binary not found: {args.metapredict_idrs_bin}")
        if "aiupred" in tools and args.aiupred_mode == "cli" and shutil.which(args.aiupred_bin) is None:
            errors.append(f"AIUPred CLI binary not found: {args.aiupred_bin}")
        if "aiupred" in tools and args.aiupred_mode == "nextflow" and shutil.which(args.aiupred_nextflow_bin) is None:
            errors.append(f"Nextflow binary not found: {args.aiupred_nextflow_bin}")
        if "iupred3" in tools and not args.uniprot and not args.iupred3_local_bin and not args.iupred3_json:
            warnings.append("iupred3_requires_uniprot_for_rest_or_iupred3_local_bin_for_sequence_input")
        if "fuzdrop" in tools and not args.fuzdrop_json and not args.fuzdrop_captcha_token:
            warnings.append("fuzdrop_api_requires_manual_recaptcha_token_or_imported_fuzdrop_json")
        if "aggrescanai" in tools and not args.aggrescanai_csv and not args.aggrescanai_script:
            warnings.append("aggrescanai_requires_imported_csv_or_local_runner_script")

    execution: Dict[str, Any] = {}
    score_rows: List[Dict[str, Any]] = []
    llps_features: List[Dict[str, Any]] = []
    fuzdrop_meta: Dict[str, Dict[str, Any]] = {}

    for json_path in args.iupred3_json:
        path = Path(json_path).expanduser()
        if not path.exists():
            warnings.append(f"iupred3_json_missing:{path}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        query_id = safe_name(path.stem)
        score_rows.extend(extract_iupred_scores(data, query_id, "IUPred3", args))

    for csv_path in args.aggrescanai_csv:
        path = Path(csv_path).expanduser()
        if not path.exists():
            warnings.append(f"aggrescanai_csv_missing:{path}")
            continue
        score_rows.extend(parse_aggrescanai_csv(path, args))

    for json_path in args.fuzdrop_json:
        path = Path(json_path).expanduser()
        if not path.exists():
            warnings.append(f"fuzdrop_json_missing:{path}")
            continue
        features, meta = parse_fuzdrop_json(path)
        llps_features.extend(features)
        fuzdrop_meta.update(meta)

    if args.execute and not errors:
        for tool_name, plan in plans.items():
            Path(plan["outdir"]).mkdir(parents=True, exist_ok=True)
            tool_results = []
            stdout_files = plan.get("stdout_files") or ([plan["stdout_file"]] if plan.get("stdout_file") else [])
            for idx, cmd in enumerate(plan["commands"], start=1):
                stdout_path = Path(stdout_files[idx - 1]) if idx - 1 < len(stdout_files) else None
                result = run_command(cmd, root / "logs" / f"{run_id}.{tool_name}.{idx}.log", stdout_path=stdout_path)
                tool_results.append(result)
                if not result["ok"]:
                    errors.append(f"{tool_name} command {idx} failed with exit code {result['returncode']}")
            execution[tool_name] = tool_results
        if "aiupred" in plans and args.aiupred_mode == "cli":
            for expected in plans["aiupred"].get("expected_files", []):
                path = Path(expected)
                if path.exists():
                    score_rows.extend(parse_aiupred_table(path, args))
        if "metapredict" in plans:
            for expected in plans["metapredict"].get("expected_files", []):
                path = Path(expected)
                if path.exists():
                    score_rows.extend(parse_generic_score_table(path, "metapredict", args))
        if "iupred3_local" in plans:
            for expected in plans["iupred3_local"].get("expected_files", []):
                path = Path(expected)
                if path.exists():
                    if plans["iupred3_local"].get("input_format") == "table":
                        score_rows.extend(parse_iupred3_local_table(path, args))
                    else:
                        query_id = safe_name(path.name.replace(".iupred3_local.txt", "").replace(".txt", ""))
                        score_rows.extend(parse_iupred3_plain_output(path, query_id, args))
        if "aggrescanai" in plans:
            for expected in plans["aggrescanai"].get("expected_files", []):
                path = Path(expected)
                if path.exists():
                    score_rows.extend(parse_aggrescanai_csv(path, args))
        if "fuzdrop" in tools and args.fuzdrop_captcha_token and sequence_records:
            fuzdrop_dir = root / "fuzdrop"
            fuzdrop_dir.mkdir(parents=True, exist_ok=True)
            fuzdrop_results = []
            for name, sequence in sequence_records:
                try:
                    data = submit_fuzdrop_sequence(
                        args.fuzdrop_api_url,
                        name,
                        sequence,
                        args.fuzdrop_captcha_token,
                        args.iupred3_timeout_sec,
                    )
                    raw_path = fuzdrop_dir / f"{safe_name(name)}.fuzdrop.json"
                    write_json(raw_path, data)
                    features, meta = parse_fuzdrop_json(raw_path, name)
                    llps_features.extend(features)
                    fuzdrop_meta.update(meta)
                    fuzdrop_results.append({"ok": True, "query_id": name, "json": str(raw_path)})
                except RuntimeError as exc:
                    errors.append(str(exc))
                    fuzdrop_results.append({"ok": False, "query_id": name, "error": str(exc)})
            execution["fuzdrop_api"] = fuzdrop_results
        if "iupred3" in tools and args.uniprot and not args.no_iupred3_rest:
            for accession in args.uniprot:
                try:
                    data = fetch_iupred3_json(accession, args.iupred3_type, args.iupred3_timeout_sec)
                    raw_path = root / "iupred3" / f"{safe_name(accession)}.{args.iupred3_type}.json"
                    write_json(raw_path, data)
                    score_rows.extend(extract_iupred_scores(data, safe_name(accession), "IUPred3", args))
                except RuntimeError as exc:
                    errors.append(str(exc))

    regions = make_regions(score_rows, args)
    llps_features.extend(make_llps_features(score_rows, args))
    summary_rows = summarize(records, score_rows, regions, warnings)
    llps_summary_rows = summarize_llps(records, score_rows, llps_features, fuzdrop_meta, warnings)
    scores_path = root / "protein_idr_residue_scores.tsv"
    regions_path = root / "protein_idr_regions.tsv"
    summary_path = root / "protein_idr_summary.tsv"
    llps_summary_path = root / "protein_llps_summary.tsv"
    llps_features_path = root / "protein_llps_features.tsv"
    result_path = root / "protein_idr_disorder_annotation.result.json"
    plot_paths: List[str] = []

    write_tsv(scores_path, score_rows, SCORE_COLUMNS)
    write_tsv(regions_path, regions, REGION_COLUMNS)
    write_tsv(summary_path, summary_rows, SUMMARY_COLUMNS)
    write_tsv(llps_summary_path, llps_summary_rows, LLPS_SUMMARY_COLUMNS)
    write_tsv(llps_features_path, llps_features, LLPS_FEATURE_COLUMNS)
    if not args.no_plots:
        plot_paths = write_profile_plots(root, score_rows, regions, llps_features)

    status = "error" if errors else ("success" if args.execute else "planned")
    result = {
        "skill": "protein-idr-disorder-annotation",
        "status": status,
        "execute": args.execute,
        "run_id": run_id,
        "created_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "tools": tools,
        "input_fasta": str(input_fasta),
        "iupred3_table_input": str(iupred3_table_input) if iupred3_table_input else "",
        "commands_file": str(commands_path),
        "plans": plans,
        "execution": execution,
        "outputs": {
            "summary_tsv": str(summary_path),
            "regions_tsv": str(regions_path),
            "residue_scores_tsv": str(scores_path),
            "llps_summary_tsv": str(llps_summary_path),
            "llps_features_tsv": str(llps_features_path),
            "plots": plot_paths,
            "result_json": str(result_path),
        },
        "counts": {
            "records": len(records),
            "residue_score_rows": len(score_rows),
            "regions": len(regions),
            "llps_summary_rows": len(llps_summary_rows),
            "llps_features": len(llps_features),
            "plots": len(plot_paths),
        },
        "warnings": warnings,
        "errors": errors,
    }
    write_json(result_path, result)
    print(f"saved summary: {summary_path}")
    print(f"saved regions: {regions_path}")
    print(f"saved scores: {scores_path}")
    print(f"saved llps summary: {llps_summary_path}")
    print(f"saved llps features: {llps_features_path}")
    if plot_paths:
        print(f"saved plots: {root / 'plots'}")
    print(f"saved result: {result_path}")
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
