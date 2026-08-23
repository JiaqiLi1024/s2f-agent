#!/usr/bin/env python3
"""Tiny test wrapper that mimics a local IUPred3 batch TSV interface."""

from __future__ import annotations

import csv
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: mock_iupred3_table_wrapper.py input.tsv [long|short|glob]", file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        writer = csv.writer(sys.stdout, delimiter="\t")
        writer.writerow(["Identifier", "Sequence", "IUPred_scores", "Average_IUPred_score", "ANCHOR_scores", "Average_ANCHOR_score"])
        for name, sequence in reader:
            disorder = [0.2] * len(sequence)
            anchor = [0.1] * len(sequence)
            for idx in range(4, min(12, len(sequence))):
                disorder[idx] = 0.7
            for idx in range(6, min(11, len(sequence))):
                anchor[idx] = 0.6
            writer.writerow(
                [
                    name,
                    sequence,
                    ",".join(f"{score:.2f}" for score in disorder),
                    f"{sum(disorder) / len(disorder):.4f}" if disorder else "",
                    ",".join(f"{score:.2f}" for score in anchor),
                    f"{sum(anchor) / len(anchor):.4f}" if anchor else "",
                ]
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
