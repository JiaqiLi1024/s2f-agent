#!/usr/bin/env python3
"""Tiny test wrapper that mimics a single-record local IUPred3 CLI."""

from __future__ import annotations

import sys


def read_fasta(path: str) -> tuple[str, str]:
    name = "query"
    seq_parts: list[str] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(">"):
                name = stripped[1:].split()[0] or name
            else:
                seq_parts.append(stripped)
    return name, "".join(seq_parts)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: mock_iupred3_single.py input.fasta [long|short|glob]", file=sys.stderr)
        return 2
    _name, sequence = read_fasta(sys.argv[1])
    for idx, residue in enumerate(sequence, start=1):
        disorder = 0.72 if 5 <= idx <= 12 else 0.18
        anchor = 0.63 if 7 <= idx <= 11 else 0.10
        print(f"{idx}\t{residue}\t{disorder:.2f}\t{anchor:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
