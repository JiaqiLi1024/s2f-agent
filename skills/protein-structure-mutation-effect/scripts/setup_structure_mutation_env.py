#!/usr/bin/env python3
"""Plan or execute pinned model-specific structure-mutation environments."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

PINS = {
    "saprot": {
        "url": "https://github.com/westlake-repl/SaProt.git",
        "commit": "e91e4858b55944523f1f8d385f7b96a0d3d34c1d",
        "license": "MIT code; review the checkpoint model card and Foldseek GPL-3.0 terms",
    },
    "thermompnn": {
        "url": "https://github.com/Kuhlman-Lab/ThermoMPNN.git",
        "commit": "2b04fd370e399911b1fa5848112cc9013f084110",
        "license": "MIT",
    },
    "proteinmpnn": {
        "url": "https://github.com/dauparas/ProteinMPNN.git",
        "commit": "8907e6671bfbfc92303b5f79c4b5e6ce47cdef57",
        "license": "MIT",
    },
    "esm-if1": {
        "url": "https://github.com/facebookresearch/esm.git",
        "commit": "2b369911bb5b4b0dda914521b9475cad1656b2ac",
        "license": "MIT",
    },
}


def command_plan(backend: str, env_name: str, source_root: Path, cache_root: Path,
                 download_model: bool, accept_model_license: bool) -> tuple[Path, list[list[str]]]:
    info = PINS[backend]
    target = source_root / backend
    commands: list[list[str]] = [
        ["conda", "create", "-y", "-n", env_name, "python=3.10"],
        ["git", "clone", info["url"], str(target)],
        ["git", "-C", str(target), "checkout", "--detach", info["commit"]],
    ]
    if backend == "saprot":
        commands.extend([
            ["conda", "run", "-n", env_name, "python", "-m", "pip", "install", "-r", str(target / "requirements.txt")],
            ["conda", "install", "-y", "-n", env_name, "-c", "conda-forge", "-c", "bioconda", "foldseek=10.941cd33"],
        ])
        if download_model:
            if not accept_model_license:
                raise ValueError("--download-model requires --accept-model-license after reviewing the model card")
            commands.extend([
                ["conda", "run", "-n", env_name, "python", "-m", "pip", "install", "huggingface_hub"],
                ["conda", "run", "-n", env_name, "hf", "download", "westlake-repl/SaProt_650M_AF2", "--local-dir", str(cache_root / "SaProt_650M_AF2")],
            ])
    elif backend == "thermompnn":
        commands.extend([
            ["conda", "install", "-y", "-n", env_name, "-c", "pytorch", "-c", "conda-forge", "pytorch", "torchvision", "torchaudio", "pytorch-lightning"],
            ["conda", "install", "-y", "-n", env_name, "-c", "bioconda", "-c", "conda-forge", "joblib", "omegaconf", "pandas", "numpy", "tqdm", "mmseqs2", "wandb", "biopython"],
        ])
    elif backend == "proteinmpnn":
        commands.append(["conda", "install", "-y", "-n", env_name, "-c", "pytorch", "pytorch", "numpy"])
    elif backend == "esm-if1":
        commands.extend([
            ["conda", "run", "-n", env_name, "python", "-m", "pip", "install", "-e", str(target)],
            ["conda", "run", "-n", env_name, "python", "-c", "import esm; print(esm.__version__ if hasattr(esm, '__version__') else 'esm-import-ok')"],
        ])
        if download_model:
            cache_code = (
                "import os; "
                f"os.environ['TORCH_HOME']={str(cache_root.resolve())!r}; "
                "import esm; esm.pretrained.esm_if1_gvp4_t16_142M_UR50(); print('esm-if1-checkpoint-ready')"
            )
            commands.append(["conda", "run", "-n", env_name, "python", "-c", cache_code])
    return target, commands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, choices=tuple(PINS))
    parser.add_argument("--env-name", required=True)
    parser.add_argument("--source-root", type=Path, default=Path("external"))
    parser.add_argument("--cache-root", type=Path, default=Path("model-cache"))
    parser.add_argument("--mode", choices=("plan", "execute"), default="plan")
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--accept-model-license", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        target, commands = command_plan(args.backend, args.env_name, args.source_root,
                                        args.cache_root, args.download_model,
                                        args.accept_model_license)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1
    payload = {
        "status": "planned", "mode": args.mode, "backend": args.backend,
        "env_name": args.env_name, "source_target": str(target.resolve()),
        "source": PINS[args.backend], "commands": commands,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "steps": [],
        "limitations": [
            "GPU/CUDA builds must be selected for the local driver before production inference",
            "checkpoint model-card terms are separate from repository code licenses",
            "heavy-model inference is not implied by a successful wrapper smoke test",
        ],
    }
    exit_code = 0
    if args.mode == "execute":
        args.source_root.mkdir(parents=True, exist_ok=True)
        args.cache_root.mkdir(parents=True, exist_ok=True)
        if target.exists() and any(target.iterdir()):
            payload["status"] = "failed"
            payload["error"] = f"refusing to clone into non-empty target: {target}"
            exit_code = 1
        else:
            for command in commands:
                started = dt.datetime.now(dt.timezone.utc).isoformat()
                try:
                    completed = subprocess.run(command, text=True, capture_output=True, check=False)
                    step = {
                        "command": command, "started_at": started, "returncode": completed.returncode,
                        "stdout": completed.stdout[-8000:], "stderr": completed.stderr[-8000:],
                    }
                except FileNotFoundError as exc:
                    step = {"command": command, "started_at": started, "returncode": 127, "stderr": str(exc)}
                payload["steps"].append(step)
                if step["returncode"] != 0:
                    payload["status"] = "failed"
                    payload["error"] = f"setup command failed: {command[0]}"
                    exit_code = 1
                    break
            else:
                payload["status"] = "completed"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
