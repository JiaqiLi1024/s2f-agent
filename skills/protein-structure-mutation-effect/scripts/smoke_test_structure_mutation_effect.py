#!/usr/bin/env python3
"""Run deterministic PDB/mmCIF validation, import, and unavailable-status smoke tests."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = SKILL_ROOT / "assets" / "fixtures"


def run(command: list[str]) -> None:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {command}\n{completed.stdout}\n{completed.stderr}")


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def smoke(output_root: Path) -> dict:
    validator = SKILL_ROOT / "scripts" / "validate_structure_mutations.py"
    runner = SKILL_ROOT / "scripts" / "run_structure_mutation_effect.py"
    common = [
        "--fasta", str(FIXTURES / "toy.fasta"), "--chain", "A",
        "--mutations-file", str(FIXTURES / "mutations.tsv"),
    ]
    for structure_name, result_name in (("toy.pdb", "validate-pdb"), ("toy.cif", "validate-cif")):
        run([sys.executable, str(validator), *common, "--structure", str(FIXTURES / structure_name),
             "--output-dir", str(output_root / result_name)])
    imported = output_root / "import"
    run([
        sys.executable, str(runner), *common, "--structure", str(FIXTURES / "toy.pdb"),
        "--models", "saprot,thermompnn", "--mode", "import",
        "--import-file", f"saprot={FIXTURES / 'saprot-import.tsv'}",
        "--import-file", f"thermompnn={FIXTURES / 'thermompnn-import.tsv'}",
        "--output-dir", str(imported), "--archive-intermediates",
    ])
    score_rows = read_tsv(imported / "structure_mutation_scores.tsv")
    assert len(score_rows) == 4
    assert {row["status"] for row in score_rows} == {"imported"}
    thermompnn = [row for row in score_rows if row["model_id"] == "thermompnn"]
    assert thermompnn and {row["higher_is"] for row in thermompnn} == {"more_destabilizing"}
    missing = output_root / "missing-structure"
    run([
        sys.executable, str(runner), *common, "--structure", str(output_root / "absent.pdb"),
        "--models", "saprot,esm-if1", "--mode", "execute", "--output-dir", str(missing),
    ])
    unavailable = read_tsv(missing / "structure_mutation_scores.tsv")
    assert len(unavailable) == 4
    assert {row["status"] for row in unavailable} == {"unavailable"}
    return {
        "status": "passed", "output_root": str(output_root.resolve()),
        "checks": [
            "pdb_mapping", "mmcif_mapping", "saprot_import", "thermompnn_import",
            "ddg_direction_metadata", "archive_creation", "missing_structure_status_rows",
        ],
        "real_heavy_models_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="Preserve outputs here; otherwise use a temporary directory")
    args = parser.parse_args()
    try:
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            result = smoke(args.output_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="s2f-structure-mutation-smoke-") as temp:
                result = smoke(Path(temp))
                result["output_root"] = "temporary_directory_removed"
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
