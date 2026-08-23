#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
FIX = SKILL / "tests" / "fixtures"


def rows(path: Path):
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="s2f-seqmut-") as tmp:
        tmp = Path(tmp)
        normalized = tmp / "normalized.tsv"
        subprocess.run([
            sys.executable, str(SKILL / "scripts" / "validate_protein_mutations.py"),
            "--fasta", str(FIX / "wt.fasta"), "--mutations-file", str(FIX / "mutations.tsv"),
            "--output", str(normalized), "--summary-json", str(tmp / "validation.json")
        ], check=True)
        norm = rows(normalized)
        assert [row["mutation_group"] for row in norm] == ["A1V", "C2A:D3E"]
        assert all(row["status"] == "valid" for row in norm)
        out = tmp / "run"
        subprocess.run([
            sys.executable, str(SKILL / "scripts" / "run_sequence_mutation_effect.py"),
            "--fasta", str(FIX / "wt.fasta"), "--mutations-file", str(FIX / "mutations.tsv"),
            "--models", "msa-profile,alphamissense", "--mode", "import",
            "--msa", str(FIX / "homologs.a3m"), "--alphamissense-table", str(FIX / "alphamissense.tsv"),
            "--output-dir", str(out), "--archive-intermediates", "--cleanup-intermediates"
        ], check=True)
        scores = rows(out / "scores.tsv")
        msa = {row["variant_id"]: row for row in scores if row["model_id"] == "msa-profile"}
        assert math.isclose(float(msa["v1"]["raw_score"]), math.log(2 / 3), rel_tol=1e-10)
        assert math.isclose(float(msa["v2"]["raw_score"]), 2 * math.log(1 / 4), rel_tol=1e-10)
        am = {row["variant_id"]: row for row in scores if row["model_id"] == "AlphaMissense-v2023" or row["model_id"] == "alphamissense"}
        assert am["v1"]["status"] == "ok" and float(am["v1"]["raw_score"]) == 0.82
        assert am["v2"]["status"] == "unavailable"
        summary = json.loads((out / "run_summary.json").read_text())
        assert summary["status_counts"]["ok"] == 3
        assert (out / "intermediates.tar.gz").is_file()
        assert not (out / "raw").exists() and not (out / "intermediate").exists()
    print("sequence mutation smoke test: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
