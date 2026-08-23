#!/usr/bin/env python3
"""Plan or create isolated environments for sequence mutation-effect backends."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path

DEFAULT_ENV = {"validation": "s2f-protein-mutation", "esm-1v": "s2f-esm1v", "esmc-300m": "s2f-esmc300m", "poet": "poet"}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backend", required=True, choices=tuple(DEFAULT_ENV))
    p.add_argument("--mode", choices=("plan", "execute"), default="plan")
    p.add_argument("--manager", choices=("conda", "mamba"), default="conda")
    p.add_argument("--env-name", help="Environment name (PoET upstream Makefile creates 'poet')")
    p.add_argument("--poet-repo", default="third_party/PoET")
    p.add_argument("--biohub-esm-revision", default="67838dc8ac76f4145613e6cb36c5f3d758542f7c", help="Biohub/esm full commit")
    p.add_argument("--biohub-transformers-revision", default="ef32577f55da19a4989cd7b22e004dc43a4998cb", help="Biohub/transformers full commit")
    p.add_argument("--esmc-model-revision", default="a59b831785f907e96e6a246b1d142bfb76df31ee", help="Hugging Face model revision")
    p.add_argument("--poet-revision", default="9b2239be84ee39691ec6ad4184925156f2ac332f", help="OpenProteinAI/PoET full commit")
    p.add_argument("--download-model", action="store_true")
    p.add_argument("--accept-poet-noncommercial-license", action="store_true")
    p.add_argument("--output-json")
    return p


def commands(args: argparse.Namespace) -> list[list[str]]:
    env = args.env_name or DEFAULT_ENV[args.backend]
    if args.backend == "validation":
        return [[args.manager, "create", "-y", "-n", env, "python=3.11"]]
    if args.backend == "esm-1v":
        cmds = [
            [args.manager, "create", "-y", "-n", env, "python=3.10", "pip"],
            [args.manager, "run", "-n", env, "python", "-m", "pip", "install", "fair-esm==2.0.0", "torch"],
        ]
        if args.download_model:
            cmds.append([args.manager, "run", "-n", env, "python", "-c", "import esm; esm.pretrained.esm1v_t33_650M_UR90S_1()"])
        return cmds
    if args.backend == "esmc-300m":
        package = f"esm@git+https://github.com/Biohub/esm.git@{args.biohub_esm_revision}"
        transformers_package = (
            "transformers@git+https://github.com/Biohub/transformers.git@"
            f"{args.biohub_transformers_revision}"
        )
        cmds = [
            [args.manager, "create", "-y", "-n", env, "python=3.12", "pip"],
            [args.manager, "run", "-n", env, "python", "-m", "pip", "install", package, "huggingface_hub"],
            [
                args.manager,
                "run",
                "-n",
                env,
                "python",
                "-m",
                "pip",
                "install",
                "--force-reinstall",
                "--no-deps",
                transformers_package,
            ],
        ]
        if args.download_model:
            cmds.append([args.manager, "run", "-n", env, "hf", "download", "biohub/ESMC-300M", "--revision", args.esmc_model_revision])
        return cmds
    repo = Path(args.poet_repo)
    cmds = [["mamba", "--version"], ["conda-lock", "--version"]]
    if not repo.exists():
        cmds.append(["git", "clone", "https://github.com/OpenProteinAI/PoET.git", str(repo)])
    else:
        cmds.append(["git", "-C", str(repo), "diff", "--quiet"])
    cmds.append(["git", "-C", str(repo), "checkout", "--detach", args.poet_revision])
    cmds.append(["make", "-C", str(repo), "create_conda_env"])
    if args.download_model:
        if not args.accept_poet_noncommercial_license:
            raise ValueError("PoET weights are CC BY-NC-SA 4.0; pass --accept-poet-noncommercial-license after review")
        cmds.append(["make", "-C", str(repo), "download_model"])
    return cmds


def main() -> int:
    args = parser().parse_args()
    try:
        cmds = commands(args)
    except ValueError as exc:
        parser().error(str(exc))
    summary = {"schema_version": 1, "backend": args.backend, "mode": args.mode,
               "environment": args.env_name or DEFAULT_ENV[args.backend],
               "commands": [shlex.join(cmd) for cmd in cmds], "results": []}
    if args.mode == "execute":
        if args.backend == "poet":
            Path(args.poet_repo).parent.mkdir(parents=True, exist_ok=True)
        for cmd in cmds:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
            result = {"command": shlex.join(cmd), "returncode": completed.returncode,
                      "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:]}
            summary["results"].append(result)
            if completed.returncode:
                summary["status"] = "failed"
                break
        else:
            summary["status"] = "ok"
    else:
        summary["status"] = "planned"
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if summary["status"] != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
