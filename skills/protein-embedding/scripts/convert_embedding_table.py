#!/usr/bin/env python3
"""Convert per-protein embeddings from NPZ to a TSV table."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert protein_embeddings in NPZ to TSV.")
    parser.add_argument("--npz", required=True, help="NPZ produced by run_real_protein_embedding_workflow.py")
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--precision", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        import numpy as np

        data = np.load(args.npz, allow_pickle=False)
        if "protein_embeddings" not in data or "protein_ids" not in data:
            raise ValueError("NPZ does not contain protein_embeddings and protein_ids arrays")
        matrix = data["protein_embeddings"]
        ids = [str(x) for x in data["protein_ids"]]
        if matrix.ndim != 2:
            raise ValueError(f"protein_embeddings must be 2D, got shape {matrix.shape}")
        if len(ids) != matrix.shape[0]:
            raise ValueError("protein_ids length does not match protein_embeddings rows")

        output = Path(args.output_tsv)
        output.parent.mkdir(parents=True, exist_ok=True)
        fmt = f"{{:.{args.precision}g}}"
        with output.open("w", encoding="utf-8") as handle:
            handle.write("\t".join(["protein_id"] + [f"dim_{i}" for i in range(matrix.shape[1])]) + "\n")
            for protein_id, row in zip(ids, matrix):
                handle.write("\t".join([protein_id] + [fmt.format(float(x)) for x in row]) + "\n")
        print(f"saved tsv: {output}")
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
