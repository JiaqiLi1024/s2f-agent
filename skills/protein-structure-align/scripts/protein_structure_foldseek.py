#!/usr/bin/env python3
"""Foldseek wrapper for protein structure similarity search and clustering."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


RESULT_JSON_NAME = "protein_structure_foldseek.result.json"
DEFAULT_FORMAT_OUTPUT = "query,target,evalue,bits,prob,alntmscore,qtmscore,ttmscore,lddt"


def json_safe_path(path: Path) -> str:
    return str(path.resolve())


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def write_summary(outdir: Path, result: Dict[str, Any]) -> None:
    lines = [
        "Protein Structure Foldseek",
        f"status: {result.get('status', 'unknown')}",
        f"mode: {result.get('mode', '')}",
        f"query: {result.get('inputs', {}).get('query', '')}",
        f"target: {result.get('inputs', {}).get('target', '')}",
        f"command: {result.get('command', '')}",
    ]
    if result.get("returncode") is not None:
        lines.append(f"returncode: {result.get('returncode')}")
    if result.get("search_summary"):
        summary = result["search_summary"]
        lines.extend(
            [
                f"hits: {summary.get('hit_count', 0)}",
                f"top_hit: {summary.get('top_hit', '')}",
            ]
        )
    if result.get("cluster_summary"):
        summary = result["cluster_summary"]
        lines.extend(
            [
                f"clusters: {summary.get('cluster_count', 0)}",
                f"members: {summary.get('member_count', 0)}",
            ]
        )
    if result.get("warnings"):
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in result["warnings"])
    if result.get("errors"):
        lines.append("errors:")
        lines.extend(f"- {error}" for error in result["errors"])
    (outdir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_foldseek_binary(binary: str) -> Optional[str]:
    candidate = Path(binary).expanduser()
    if candidate.exists():
        return str(candidate.resolve())
    return shutil.which(binary)


def split_extra_args(extra_args: str) -> List[str]:
    if not extra_args.strip():
        return []
    return shlex.split(extra_args)


def add_option(cmd: List[str], flag: str, value: Any) -> None:
    if value is not None and value != "":
        cmd.extend([flag, str(value)])


def build_command(args: argparse.Namespace, foldseek_bin: str, output_path: Path, tmpdir: Path) -> List[str]:
    if args.mode == "search":
        module = "easy-multimersearch" if args.multimer else "easy-search"
        cmd = [
            foldseek_bin,
            module,
            args.query,
            args.target,
            str(output_path),
            str(tmpdir),
        ]
        if args.format_mode is None:
            add_option(cmd, "--format-output", args.format_output)
        else:
            add_option(cmd, "--format-mode", args.format_mode)
            if args.format_output:
                add_option(cmd, "--format-output", args.format_output)
    else:
        module = "easy-multimercluster" if args.multimer else "easy-cluster"
        cmd = [
            foldseek_bin,
            module,
            args.query,
            str(output_path),
            str(tmpdir),
        ]

    add_option(cmd, "-s", args.sensitivity)
    add_option(cmd, "-c", args.coverage)
    add_option(cmd, "--cov-mode", args.cov_mode)
    add_option(cmd, "-e", args.evalue)
    add_option(cmd, "--min-seq-id", args.min_seq_id)
    add_option(cmd, "--tmscore-threshold", args.tmscore_threshold)
    add_option(cmd, "--tmscore-threshold-mode", args.tmscore_threshold_mode)
    add_option(cmd, "--lddt-threshold", args.lddt_threshold)
    add_option(cmd, "--alignment-type", args.alignment_type)
    add_option(cmd, "--max-seqs", args.max_seqs)
    add_option(cmd, "--threads", args.threads)
    add_option(cmd, "--gpu", args.gpu)
    if args.prefilter_mode is not None:
        add_option(cmd, "--prefilter-mode", args.prefilter_mode)
    cmd.extend(split_extra_args(args.extra_args))
    return cmd


def infer_search_output_path(outdir: Path, prefix: str, args: argparse.Namespace) -> Path:
    if args.output_name:
        return outdir / args.output_name
    if args.format_mode == 3:
        return outdir / f"{prefix}.foldseek_search.html"
    return outdir / f"{prefix}.foldseek_search.tsv"


def infer_cluster_output_prefix(outdir: Path, prefix: str) -> Path:
    return outdir / f"{prefix}.foldseek_cluster"


def run_command(cmd: Sequence[str], outdir: Path, timeout_sec: int) -> Tuple[int, Path, Path]:
    stdout_path = outdir / "foldseek.stdout.txt"
    stderr_path = outdir / "foldseek.stderr.txt"
    completed = subprocess.run(
        list(cmd),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")
    return completed.returncode, stdout_path, stderr_path


def parse_search_tsv(tsv_path: Path, format_output: str, top_n: int) -> Tuple[Dict[str, Any], Optional[Path], List[str]]:
    warnings: List[str] = []
    if not tsv_path.exists() or tsv_path.stat().st_size == 0:
        return {"hit_count": 0, "top_hit": ""}, None, warnings
    fields = [field.strip() for field in format_output.split(",") if field.strip()]
    try:
        frame = pd.read_csv(tsv_path, sep="\t", header=None)
        if fields and len(fields) == frame.shape[1]:
            frame.columns = fields
        elif fields:
            warnings.append(
                f"Search TSV has {frame.shape[1]} columns but format-output has {len(fields)} fields; kept numeric columns."
            )
        preview = frame.head(top_n).copy()
        preview_path = tsv_path.with_name(tsv_path.stem + ".top_hits.tsv")
        preview.to_csv(preview_path, sep="\t", index=False)
        top_hit = ""
        if not preview.empty:
            if "target" in preview.columns:
                top_hit = str(preview.iloc[0]["target"])
            elif preview.shape[1] > 1:
                top_hit = str(preview.iloc[0, 1])
        return {"hit_count": int(frame.shape[0]), "top_hit": top_hit}, preview_path, warnings
    except Exception as exc:  # pragma: no cover - defensive parser fallback
        warnings.append(f"Could not parse Foldseek search TSV: {exc}")
        return {"hit_count": 0, "top_hit": ""}, None, warnings


def find_cluster_tsv(output_prefix: Path, multimer: bool) -> Optional[Path]:
    candidates = []
    if multimer:
        candidates.append(output_prefix.with_name(output_prefix.name + "_cluster.tsv"))
    else:
        candidates.append(output_prefix.with_name(output_prefix.name + "_clu.tsv"))
    candidates.extend(sorted(output_prefix.parent.glob(output_prefix.name + "*cluster*.tsv")))
    candidates.extend(sorted(output_prefix.parent.glob(output_prefix.name + "*clu*.tsv")))
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def parse_cluster_tsv(cluster_tsv: Optional[Path]) -> Tuple[Dict[str, Any], Optional[Path], List[str]]:
    warnings: List[str] = []
    if cluster_tsv is None:
        return {"cluster_count": 0, "member_count": 0}, None, warnings
    try:
        frame = pd.read_csv(cluster_tsv, sep="\t", header=None, names=["representative", "member"])
        summary_path = cluster_tsv.with_name(cluster_tsv.stem + ".summary.tsv")
        summary = (
            frame.groupby("representative", dropna=False)
            .agg(member_count=("member", "count"), members=("member", lambda values: ",".join(map(str, values))))
            .reset_index()
            .sort_values(["member_count", "representative"], ascending=[False, True])
        )
        summary.to_csv(summary_path, sep="\t", index=False)
        return (
            {
                "cluster_count": int(summary.shape[0]),
                "member_count": int(frame.shape[0]),
                "largest_cluster_size": int(summary["member_count"].max()) if not summary.empty else 0,
            },
            summary_path,
            warnings,
        )
    except Exception as exc:  # pragma: no cover - defensive parser fallback
        warnings.append(f"Could not parse Foldseek cluster TSV: {exc}")
        return {"cluster_count": 0, "member_count": 0}, None, warnings


def collect_outputs(outdir: Path, prefix: str, output_path: Path, mode: str) -> Dict[str, str]:
    outputs: Dict[str, str] = {}
    if mode == "search":
        if output_path.exists():
            outputs["search_result"] = json_safe_path(output_path)
        for path in sorted(outdir.glob(f"{prefix}.foldseek_search*")):
            outputs[path.name] = json_safe_path(path)
    else:
        for path in sorted(outdir.glob(f"{prefix}.foldseek_cluster*")):
            outputs[path.name] = json_safe_path(path)
    for name in ["foldseek.stdout.txt", "foldseek.stderr.txt", "summary.txt", RESULT_JSON_NAME]:
        path = outdir / name
        if path.exists() or name in {"summary.txt", RESULT_JSON_NAME}:
            outputs[name] = json_safe_path(path)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Foldseek easy-search/easy-cluster for structure similarity search or clustering."
    )
    parser.add_argument("--mode", choices=["search", "cluster"], required=True, help="Foldseek workflow to run.")
    parser.add_argument("--query", required=True, help="Query structure file, directory, FASTA, or Foldseek DB path.")
    parser.add_argument("--target", help="Target structure file, directory, or Foldseek DB path. Required for search.")
    parser.add_argument("--outdir", required=True, help="Output directory.")
    parser.add_argument("--prefix", default="foldseek", help="Output filename prefix.")
    parser.add_argument("--output-name", help="Override the primary Foldseek search output filename.")
    parser.add_argument("--foldseek-bin", default="foldseek", help="Foldseek executable path or command name.")
    parser.add_argument("--tmpdir", help="Foldseek temporary directory. Defaults under --outdir.")
    parser.add_argument("--multimer", action="store_true", help="Use easy-multimersearch/easy-multimercluster.")
    parser.add_argument(
        "--format-output",
        default=DEFAULT_FORMAT_OUTPUT,
        help="Foldseek --format-output fields for tabular search output.",
    )
    parser.add_argument("--format-mode", type=int, help="Foldseek --format-mode, e.g. 3 for HTML search output.")
    parser.add_argument("-s", "--sensitivity", type=float, help="Foldseek sensitivity parameter.")
    parser.add_argument("-c", "--coverage", type=float, help="Minimum coverage fraction.")
    parser.add_argument("--cov-mode", type=int, help="Foldseek coverage mode.")
    parser.add_argument("-e", "--evalue", type=float, help="Maximum E-value.")
    parser.add_argument("--min-seq-id", type=float, help="Minimum sequence identity for clustering/search filters.")
    parser.add_argument("--tmscore-threshold", type=float, help="Minimum alignment TM-score for clustering.")
    parser.add_argument("--tmscore-threshold-mode", type=int, help="TM-score normalization mode.")
    parser.add_argument("--lddt-threshold", type=float, help="Minimum alignment LDDT for clustering.")
    parser.add_argument("--alignment-type", type=int, help="Foldseek alignment type, e.g. 1 for TMalign realignment.")
    parser.add_argument("--max-seqs", type=int, help="Maximum prefilter sequences handed to alignment.")
    parser.add_argument("--threads", type=int, help="Foldseek thread count.")
    parser.add_argument("--gpu", type=int, choices=[0, 1], help="Enable Foldseek GPU mode with 1 when supported.")
    parser.add_argument("--prefilter-mode", type=int, help="Foldseek prefilter mode.")
    parser.add_argument("--extra-args", default="", help="Additional Foldseek CLI arguments, shell-quoted as one string.")
    parser.add_argument("--top-n", type=int, default=25, help="Rows to keep in the top-hit preview TSV.")
    parser.add_argument("--timeout-sec", type=int, default=3600, help="Foldseek subprocess timeout in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Write planned command JSON without running Foldseek.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    result_path = outdir / RESULT_JSON_NAME
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    warnings: List[str] = []
    errors: List[str] = []

    if args.mode == "search" and not args.target:
        errors.append("--target is required when --mode search")

    tmpdir = Path(args.tmpdir).expanduser() if args.tmpdir else outdir / "foldseek_tmp"
    tmpdir.mkdir(parents=True, exist_ok=True)

    output_path = (
        infer_search_output_path(outdir, args.prefix, args)
        if args.mode == "search"
        else infer_cluster_output_prefix(outdir, args.prefix)
    )

    foldseek_bin = resolve_foldseek_binary(args.foldseek_bin)
    if not foldseek_bin:
        if args.dry_run:
            foldseek_bin = args.foldseek_bin
            warnings.append(f"Foldseek binary was not found on PATH during dry-run: {args.foldseek_bin}")
        else:
            errors.append(
                "Foldseek binary not found. Install it with `conda install -c conda-forge -c bioconda foldseek` "
                "or pass --foldseek-bin /path/to/foldseek."
            )

    result: Dict[str, Any] = {
        "skill": "protein-structure-align",
        "script": "protein_structure_foldseek.py",
        "status": "error" if errors else "planned" if args.dry_run else "running",
        "mode": args.mode,
        "multimer": bool(args.multimer),
        "started_at": started_at,
        "inputs": {
            "query": args.query,
            "target": args.target or "",
            "outdir": json_safe_path(outdir),
            "tmpdir": json_safe_path(tmpdir),
        },
        "parameters": {
            "format_output": args.format_output,
            "format_mode": args.format_mode,
            "sensitivity": args.sensitivity,
            "coverage": args.coverage,
            "cov_mode": args.cov_mode,
            "evalue": args.evalue,
            "min_seq_id": args.min_seq_id,
            "tmscore_threshold": args.tmscore_threshold,
            "tmscore_threshold_mode": args.tmscore_threshold_mode,
            "lddt_threshold": args.lddt_threshold,
            "alignment_type": args.alignment_type,
            "max_seqs": args.max_seqs,
            "threads": args.threads,
            "gpu": args.gpu,
            "prefilter_mode": args.prefilter_mode,
            "extra_args": args.extra_args,
        },
        "warnings": warnings,
        "errors": errors,
        "outputs": {},
    }

    if errors:
        write_json(result_path, result)
        write_summary(outdir, result)
        return 2

    try:
        cmd = build_command(args, foldseek_bin or args.foldseek_bin, output_path, tmpdir)
    except ValueError as exc:
        result["status"] = "error"
        result["errors"].append(f"Could not parse --extra-args: {exc}")
        write_json(result_path, result)
        write_summary(outdir, result)
        return 2

    result["command"] = shlex.join(cmd)
    result["primary_output"] = json_safe_path(output_path)

    if args.dry_run:
        result["outputs"] = collect_outputs(outdir, args.prefix, output_path, args.mode)
        write_json(result_path, result)
        write_summary(outdir, result)
        return 0

    try:
        returncode, stdout_path, stderr_path = run_command(cmd, outdir, args.timeout_sec)
        result["returncode"] = returncode
        result["stdout"] = json_safe_path(stdout_path)
        result["stderr"] = json_safe_path(stderr_path)
    except subprocess.TimeoutExpired:
        result["status"] = "error"
        result["errors"].append(f"Foldseek command timed out after {args.timeout_sec} seconds")
        write_json(result_path, result)
        write_summary(outdir, result)
        return 3
    except OSError as exc:
        result["status"] = "error"
        result["errors"].append(f"Foldseek command failed to start: {exc}")
        write_json(result_path, result)
        write_summary(outdir, result)
        return 2

    if result["returncode"] == 0:
        result["status"] = "ok"
        if args.mode == "search" and args.format_mode is None:
            search_summary, preview_path, parse_warnings = parse_search_tsv(output_path, args.format_output, args.top_n)
            result["search_summary"] = search_summary
            if preview_path:
                result["top_hits_tsv"] = json_safe_path(preview_path)
            result["warnings"].extend(parse_warnings)
        elif args.mode == "cluster":
            cluster_tsv = find_cluster_tsv(output_path, args.multimer)
            cluster_summary, summary_path, parse_warnings = parse_cluster_tsv(cluster_tsv)
            result["cluster_summary"] = cluster_summary
            if cluster_tsv:
                result["cluster_tsv"] = json_safe_path(cluster_tsv)
            if summary_path:
                result["cluster_summary_tsv"] = json_safe_path(summary_path)
            result["warnings"].extend(parse_warnings)
    else:
        result["status"] = "error"
        result["errors"].append(f"Foldseek exited with return code {result['returncode']}")

    result["outputs"] = collect_outputs(outdir, args.prefix, output_path, args.mode)
    write_json(result_path, result)
    write_summary(outdir, result)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
