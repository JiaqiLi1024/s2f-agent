#!/usr/bin/env python3
"""Plan or run InterProScan6 and eggNOG-mapper protein annotation workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan or run InterProScan6 and eggNOG-mapper annotation."
    )
    parser.add_argument("--input", required=True, help="Protein FASTA input path.")
    parser.add_argument(
        "--tools",
        choices=["both", "interproscan6", "eggnog"],
        default="both",
        help="Annotation backend selection.",
    )
    parser.add_argument("--run-id", default=None, help="Run label; defaults to input stem.")
    parser.add_argument(
        "--outdir",
        default="output/protein-domain-motif-annotation",
        help="Run output root.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute commands. Without this flag only command plans are written.",
    )

    parser.add_argument("--nextflow-bin", default="nextflow")
    parser.add_argument("--interpro-revision", default="6.0.1")
    parser.add_argument("--interpro-release", default=None)
    parser.add_argument("--interpro-profile", default="singularity")
    parser.add_argument("--interpro-datadir", default=None)
    parser.add_argument("--interpro-outdir", default=None)
    parser.add_argument("--interpro-workdir", default=None)
    parser.add_argument("--interpro-outprefix", default=None)
    parser.add_argument("--interpro-formats", default="TSV,JSON,GFF3")
    parser.add_argument("--interpro-max-workers", type=int, default=4)
    parser.add_argument("--interpro-cpus", type=int, default=4)
    parser.add_argument("--nucleic", action="store_true")
    parser.add_argument("--no-goterms", action="store_true")
    parser.add_argument("--no-pathways", action="store_true")
    parser.add_argument(
        "--interpro-use-matches-api",
        action="store_true",
        help="Allow the InterPro matches API. Default adds --no-matches-api.",
    )
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument(
        "--interpro-extra-args",
        default="",
        help="Additional InterProScan6 Nextflow workflow arguments as a shell-style string.",
    )

    parser.add_argument("--emapper-bin", default="emapper.py")
    parser.add_argument("--eggnog-data-dir", default=None)
    parser.add_argument("--eggnog-output-dir", default=None)
    parser.add_argument("--eggnog-output-prefix", default=None)
    parser.add_argument(
        "--eggnog-method",
        choices=["diamond", "mmseqs", "hmmer", "no_search"],
        default="diamond",
    )
    parser.add_argument(
        "--eggnog-itype",
        choices=["proteins", "CDS", "genome"],
        default="proteins",
    )
    parser.add_argument("--eggnog-cpu", type=int, default=32)
    parser.add_argument(
        "--eggnog-extra-args",
        default="",
        help="Additional emapper.py arguments as a shell-style string.",
    )
    return parser.parse_args()


def sanitize_label(raw: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw.strip())
    return label.strip("._-") or "protein_annotation"


def shell_join(cmd: Iterable[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in cmd)


def split_extra_args(raw: str) -> List[str]:
    if not raw.strip():
        return []
    return shlex.split(raw)


def count_fasta_records(path: Path) -> Optional[int]:
    try:
        count = 0
        with path.open() as handle:
            for line in handle:
                if line.startswith(">"):
                    count += 1
        return count
    except OSError:
        return None


def count_non_comment_lines(path: Path) -> Optional[int]:
    try:
        count = 0
        with path.open(errors="replace") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    count += 1
        return count
    except OSError:
        return None


def discover_prefixed_files(directory: Path, prefix: str) -> List[str]:
    if not directory.exists():
        return []
    return sorted(str(path) for path in directory.glob(f"{prefix}*") if path.is_file())


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def run_command(cmd: List[str], log_path: Path) -> Dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as log:
        log.write(f"$ {shell_join(cmd)}\n\n")
        log.flush()
        process = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=False)
    return {
        "returncode": process.returncode,
        "log": str(log_path),
        "ok": process.returncode == 0,
    }


def default_interpro_datadir() -> Path:
    ips6_home = os.environ.get("IPS6_HOME")
    if ips6_home:
        return Path(ips6_home).expanduser() / "data"
    return Path.home() / "interproscan6" / "data"


def build_interpro_command(args: argparse.Namespace, input_path: Path, run_id: str, root: Path) -> Dict[str, Any]:
    outprefix = args.interpro_outprefix or input_path.name
    outdir = Path(args.interpro_outdir).expanduser() if args.interpro_outdir else root / "interproscan6" / run_id
    workdir = Path(args.interpro_workdir).expanduser() if args.interpro_workdir else root / "work" / "interproscan6" / run_id
    datadir = Path(args.interpro_datadir).expanduser() if args.interpro_datadir else default_interpro_datadir()

    cmd = [
        args.nextflow_bin,
        "run",
        "ebi-pf-team/interproscan6",
        "-r",
        args.interpro_revision,
        "-profile",
        args.interpro_profile,
        "--input",
        str(input_path),
        "--datadir",
        str(datadir),
    ]
    if args.interpro_release:
        cmd.extend(["--interpro", args.interpro_release])
    if args.nucleic:
        cmd.append("--nucleic")
    if not args.interpro_use_matches_api:
        cmd.append("--no-matches-api")
    if not args.no_goterms:
        cmd.append("--goterms")
    if not args.no_pathways:
        cmd.append("--pathways")
    cmd.extend(
        [
            "--formats",
            args.interpro_formats,
            "--outdir",
            str(outdir),
            "--outprefix",
            outprefix,
            "--maxWorkers",
            str(args.interpro_max_workers),
            "--cpus",
            str(args.interpro_cpus),
            "-w",
            str(workdir),
        ]
    )
    cmd.extend(split_extra_args(args.interpro_extra_args))
    if not args.no_resume:
        cmd.append("-resume")

    formats = [fmt.strip().lower() for fmt in args.interpro_formats.split(",") if fmt.strip()]
    expected = [str(outdir / f"{outprefix}.{fmt}") for fmt in formats]
    return {
        "command": cmd,
        "command_string": shell_join(cmd),
        "outdir": str(outdir),
        "workdir": str(workdir),
        "datadir": str(datadir),
        "outprefix": outprefix,
        "expected_files": expected,
        "log": str(root / "logs" / f"{run_id}.interproscan6.log"),
    }


def build_eggnog_command(args: argparse.Namespace, input_path: Path, run_id: str, root: Path) -> Dict[str, Any]:
    outprefix = args.eggnog_output_prefix or run_id
    outdir = Path(args.eggnog_output_dir).expanduser() if args.eggnog_output_dir else root / "eggnog"
    data_dir_raw = args.eggnog_data_dir or os.environ.get("EGGNOG_DATA_DIR")
    data_dir = Path(data_dir_raw).expanduser() if data_dir_raw else None

    cmd = [
        args.emapper_bin,
        "-i",
        str(input_path),
        "--itype",
        args.eggnog_itype,
        "-m",
        args.eggnog_method,
        "--cpu",
        str(args.eggnog_cpu),
    ]
    if data_dir:
        cmd.extend(["--data_dir", str(data_dir)])
    cmd.extend(["--output_dir", str(outdir), "-o", outprefix])
    cmd.extend(split_extra_args(args.eggnog_extra_args))

    expected = [
        str(outdir / f"{outprefix}.emapper.annotations"),
        str(outdir / f"{outprefix}.emapper.seed_orthologs"),
        str(outdir / f"{outprefix}.emapper.log"),
    ]
    return {
        "command": cmd,
        "command_string": shell_join(cmd),
        "outdir": str(outdir),
        "data_dir": str(data_dir) if data_dir else None,
        "outprefix": outprefix,
        "expected_files": expected,
        "log": str(root / "logs" / f"{run_id}.eggnog.log"),
    }


def summarize_outputs(tool_name: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    outdir = Path(plan["outdir"])
    prefix = plan["outprefix"]
    discovered = discover_prefixed_files(outdir, prefix)
    file_summaries = []
    for file_name in discovered:
        path = Path(file_name)
        file_summaries.append(
            {
                "path": file_name,
                "size_bytes": path.stat().st_size if path.exists() else None,
                "non_comment_lines": count_non_comment_lines(path),
            }
        )
    return {
        "tool": tool_name,
        "outdir": str(outdir),
        "expected_files": plan.get("expected_files", []),
        "discovered_files": discovered,
        "files": file_summaries,
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser()
    root = Path(args.outdir).expanduser()
    root.mkdir(parents=True, exist_ok=True)

    run_id = sanitize_label(args.run_id or input_path.stem)
    warnings: List[str] = []
    errors: List[str] = []
    selected_tools = ["interproscan6", "eggnog"] if args.tools == "both" else [args.tools]

    if not input_path.exists():
        errors.append(f"Input FASTA does not exist: {input_path}")
    elif not input_path.is_file():
        errors.append(f"Input path is not a file: {input_path}")

    fasta_records = count_fasta_records(input_path) if input_path.exists() else None
    if fasta_records == 0:
        warnings.append("Input file contains zero FASTA records.")

    plans: Dict[str, Dict[str, Any]] = {}
    if "interproscan6" in selected_tools:
        plans["interproscan6"] = build_interpro_command(args, input_path, run_id, root)
        if shutil.which(args.nextflow_bin) is None:
            message = f"nextflow binary not found on PATH: {args.nextflow_bin}"
            if args.execute:
                errors.append(message)
            else:
                warnings.append(message)
    if "eggnog" in selected_tools:
        plans["eggnog"] = build_eggnog_command(args, input_path, run_id, root)
        if shutil.which(args.emapper_bin) is None:
            message = f"emapper.py binary not found on PATH: {args.emapper_bin}"
            if args.execute:
                errors.append(message)
            else:
                warnings.append(message)
        if not plans["eggnog"].get("data_dir"):
            message = "eggNOG data directory is not set; pass --eggnog-data-dir or EGGNOG_DATA_DIR."
            if args.execute:
                errors.append(message)
            else:
                warnings.append(message)

    commands_path = root / "commands.sh"
    with commands_path.open("w") as commands:
        commands.write("#!/usr/bin/env bash\nset -euo pipefail\n\n")
        for tool_name in selected_tools:
            commands.write(f"# {tool_name}\n")
            commands.write(plans[tool_name]["command_string"])
            commands.write("\n\n")
    commands_path.chmod(0o755)

    execution: Dict[str, Any] = {}
    if args.execute and not errors:
        for tool_name in selected_tools:
            plan = plans[tool_name]
            Path(plan["outdir"]).mkdir(parents=True, exist_ok=True)
            if tool_name == "interproscan6":
                Path(plan["workdir"]).mkdir(parents=True, exist_ok=True)
            result = run_command(plan["command"], Path(plan["log"]))
            execution[tool_name] = result
            if not result["ok"]:
                errors.append(f"{tool_name} failed with exit code {result['returncode']}; see {result['log']}")

    outputs = {
        tool_name: summarize_outputs(tool_name, plans[tool_name])
        for tool_name in selected_tools
    }

    if errors:
        status = "failed" if args.execute else "planned_with_errors"
    elif args.execute:
        status = "success"
    else:
        status = "planned"

    result = {
        "skill": "protein-domain-motif-annotation",
        "status": status,
        "execute": args.execute,
        "input": str(input_path),
        "input_exists": input_path.exists(),
        "fasta_records": fasta_records,
        "run_id": run_id,
        "tools": selected_tools,
        "commands_file": str(commands_path),
        "plans": plans,
        "execution": execution,
        "outputs": outputs,
        "warnings": warnings,
        "errors": errors,
    }

    result_path = root / "protein_domain_motif_annotation.result.json"
    write_json(result_path, result)
    print(f"saved result: {result_path}")
    print(f"saved commands: {commands_path}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2 if not args.execute else 1

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
