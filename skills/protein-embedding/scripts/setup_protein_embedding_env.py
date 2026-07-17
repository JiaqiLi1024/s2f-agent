#!/usr/bin/env python3
"""Create and verify a local environment for protein embedding models."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_MODELS = {
    "esm2": "facebook/esm2_t6_8M_UR50D",
    "esmc": "biohub/ESMC-300M",
    "prott5": "Rostlab/prot_t5_xl_uniref50",
    "ankh": "ElnaggarLab/ankh-base",
    "saprot": "westlake-repl/SaProt_650M_AF2",
}

BASE_PACKAGES = [
    "torch",
    "transformers>=4.40",
    "huggingface_hub",
    "numpy",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up a venv and optionally download/test protein embedding models."
    )
    parser.add_argument("--env-dir", required=True, help="Virtualenv path to create or reuse")
    parser.add_argument(
        "--model-family",
        choices=sorted(DEFAULT_MODELS),
        default="esm2",
        help="Model family to prepare.",
    )
    parser.add_argument("--model-id", default=None, help="Hugging Face model id")
    parser.add_argument("--python", default=sys.executable, help="Python executable used to create venv")
    parser.add_argument("--upgrade-pip", action="store_true", help="Upgrade pip before package install")
    parser.add_argument("--skip-install", action="store_true", help="Do not install packages")
    parser.add_argument("--download-model", action="store_true", help="Pre-download model with huggingface_hub")
    parser.add_argument("--run-smoke-test", action="store_true", help="Run a tiny embedding smoke test")
    parser.add_argument("--include-biohub-esm", action="store_true", help="Install Biohub esm package for ESMC extras")
    parser.add_argument(
        "--verify-biohub-token-env",
        default=None,
        help="Verify that this Biohub token env var, or ESM_API_KEY, is present without printing its value.",
    )
    parser.add_argument("--hf-disable-xet", action="store_true", help="Set HF_HUB_DISABLE_XET=1 for downloads")
    parser.add_argument("--local-files-only", action="store_true", help="Use already cached model files only")
    parser.add_argument("--output-dir", default="output/protein-embedding/setup")
    parser.add_argument("--smoke-output-dir", default=None)
    return parser.parse_args()


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> dict:
    proc = subprocess.run(cmd, text=True, capture_output=True, env=env, check=False)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def venv_python(env_dir: Path) -> Path:
    bin_dir = "Scripts" if os.name == "nt" else "bin"
    exe = "python.exe" if os.name == "nt" else "python"
    return env_dir / bin_dir / exe


def main() -> int:
    args = parse_args()
    env_dir = Path(args.env_dir).resolve()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_id = args.model_id or DEFAULT_MODELS[args.model_family]
    py = venv_python(env_dir)
    env = os.environ.copy()
    if args.hf_disable_xet:
        env["HF_HUB_DISABLE_XET"] = "1"
    if args.local_files_only:
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"

    steps: list[dict] = []
    status = "ok"

    if not py.exists():
        steps.append(run([args.python, "-m", "venv", str(env_dir)], env=env))
        if steps[-1]["returncode"] != 0:
            status = "error"
    if status == "ok" and args.upgrade_pip:
        steps.append(run([str(py), "-m", "pip", "install", "--upgrade", "pip"], env=env))
        if steps[-1]["returncode"] != 0:
            status = "error"

    if status == "ok" and not args.skip_install:
        packages = list(BASE_PACKAGES)
        if args.include_biohub_esm:
            packages.append("esm@git+https://github.com/Biohub/esm.git@main")
        steps.append(run([str(py), "-m", "pip", "install", *packages], env=env))
        if steps[-1]["returncode"] != 0:
            status = "error"

    if status == "ok" and args.download_model:
        code = (
            "from huggingface_hub import snapshot_download; "
            f"print(snapshot_download({model_id!r}, local_files_only={bool(args.local_files_only)!r}))"
        )
        steps.append(run([str(py), "-c", code], env=env))
        if steps[-1]["returncode"] != 0:
            status = "error"

    biohub_token_present = None
    if status == "ok" and args.verify_biohub_token_env:
        biohub_token_present = bool(env.get(args.verify_biohub_token_env) or env.get("ESM_API_KEY"))
        steps.append(
            {
                "cmd": ["env-check", args.verify_biohub_token_env, "or", "ESM_API_KEY"],
                "returncode": 0 if biohub_token_present else 1,
                "stdout_tail": "Biohub token env var is present" if biohub_token_present else "",
                "stderr_tail": "" if biohub_token_present else "Biohub token env var is missing",
            }
        )
        if not biohub_token_present:
            status = "error"

    smoke_output = args.smoke_output_dir or str(output_dir / f"{args.model_family}_smoke")
    if status == "ok" and args.run_smoke_test:
        workflow = Path(__file__).resolve().parent / "run_real_protein_embedding_workflow.py"
        cmd = [
            str(py),
            str(workflow),
            "--sequence",
            "ACDEFGHIKLMNPQRSTVWY",
            "--protein-id",
            f"{args.model_family}_smoke",
            "--model-family",
            args.model_family,
            "--model-id",
            model_id,
            "--embedding-type",
            "both",
            "--device",
            "cpu",
            "--output-dir",
            smoke_output,
        ]
        if args.model_family in {"prott5", "ankh"}:
            cmd.append("--replace-rare-aa")
        if args.model_family == "saprot":
            cmd.extend(["--saprot-input-mode", "aa-only"])
        if args.download_model or args.local_files_only:
            cmd.append("--local-files-only")
        steps.append(run(cmd, env=env))
        if steps[-1]["returncode"] != 0:
            status = "error"

    summary = {
        "skill_id": "protein-embedding",
        "status": status,
        "env_dir": str(env_dir),
        "python": str(py),
        "model_family": args.model_family,
        "model_id": model_id,
        "download_model": bool(args.download_model),
        "local_files_only": bool(args.local_files_only),
        "run_smoke_test": bool(args.run_smoke_test),
        "biohub_token_env": args.verify_biohub_token_env,
        "biohub_token_present": biohub_token_present,
        "smoke_output_dir": smoke_output if args.run_smoke_test else None,
        "steps": steps,
    }
    summary_path = output_dir / "setup_summary.json"
    summary["outputs"] = {"setup_summary_json": str(summary_path)}
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
