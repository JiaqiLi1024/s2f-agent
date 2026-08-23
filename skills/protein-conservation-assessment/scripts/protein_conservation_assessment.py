#!/usr/bin/env python3
"""Sequence-first evolutionary conservation assessment for proteins."""

from __future__ import annotations

import argparse
import csv
import gzip
import html
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


VALID_AA = set("ACDEFGHIKLMNPQRSTVWYBXZUOJ")
GAP = "-"
EBI_HMMER_API = "https://www.ebi.ac.uk/Tools/hmmer/api/v1"
HTTP_HEADERS = {"User-Agent": "s2f-agent-protein-conservation-assessment/0.1"}


@dataclass
class SeqRecord:
    seq_id: str
    sequence: str
    description: str = ""


@dataclass
class SiteScore:
    query_id: str
    position: int
    residue: str
    alignment_column: int
    n_sequences: int
    n_non_gap: int
    gap_fraction: float
    consensus_residue: str
    consensus_fraction: float
    query_residue_fraction: float
    entropy: float
    conservation_score: float
    conservation_grade: int
    status: str
    note: str


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    if str(path).endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    return path.read_text(encoding="utf-8", errors="replace")


def read_fasta(path: Path) -> List[SeqRecord]:
    records: List[SeqRecord] = []
    current_id: Optional[str] = None
    current_desc = ""
    chunks: List[str] = []
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_id is not None:
                records.append(SeqRecord(current_id, "".join(chunks).upper(), current_desc))
            header = line[1:].strip()
            parts = header.split(None, 1)
            current_id = parts[0] if parts else f"seq{len(records) + 1}"
            current_desc = parts[1] if len(parts) > 1 else ""
            chunks = []
        else:
            chunks.append("".join(line.split()))
    if current_id is not None:
        records.append(SeqRecord(current_id, "".join(chunks).upper(), current_desc))
    return records


def write_fasta(records: Sequence[SeqRecord], path: Path, width: int = 80) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for rec in records:
            desc = f" {rec.description}" if rec.description else ""
            handle.write(f">{rec.seq_id}{desc}\n")
            seq = rec.sequence
            for i in range(0, len(seq), width):
                handle.write(seq[i : i + width] + "\n")


def parse_stockholm(text: str) -> List[SeqRecord]:
    chunks: Dict[str, List[str]] = {}
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#") or line == "//":
            continue
        parts = line.split()
        if len(parts) >= 2:
            chunks.setdefault(parts[0], []).append(parts[1].replace(".", GAP))
    return [SeqRecord(k, "".join(v).upper()) for k, v in chunks.items()]


def sanitize_sequence(seq: str, allow_ambiguous: bool, sanitize_to_x: bool) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    cleaned = "".join(seq.split()).upper().replace("*", "")
    out: List[str] = []
    for pos, aa in enumerate(cleaned, start=1):
        if aa in VALID_AA:
            if aa not in set("ACDEFGHIKLMNPQRSTVWY") and not allow_ambiguous:
                if sanitize_to_x:
                    out.append("X")
                    warnings.append(f"ambiguous residue {aa} at {pos} converted to X")
                else:
                    raise ValueError(f"Ambiguous residue {aa!r} at position {pos}; use --allow-ambiguous-aa or --sanitize-invalid-to-x.")
            else:
                out.append(aa)
        elif aa == GAP:
            raise ValueError("Raw sequence input must not contain gaps; pass gapped data with --alignment.")
        elif sanitize_to_x and aa.isalpha():
            out.append("X")
            warnings.append(f"invalid residue {aa} at {pos} converted to X")
        else:
            raise ValueError(f"Invalid residue {aa!r} at position {pos}; use --sanitize-invalid-to-x if appropriate.")
    if not out:
        raise ValueError("Protein sequence is empty after cleaning.")
    return "".join(out), warnings


def load_query_records(args: argparse.Namespace) -> Tuple[List[SeqRecord], List[str]]:
    warnings: List[str] = []
    records: List[SeqRecord] = []
    if args.sequence:
        seq, seq_warnings = sanitize_sequence(args.sequence, args.allow_ambiguous_aa, args.sanitize_invalid_to_x)
        warnings.extend(seq_warnings)
        records.append(SeqRecord(args.sequence_name, seq))
    if args.fasta:
        for rec in read_fasta(Path(args.fasta)):
            seq, seq_warnings = sanitize_sequence(rec.sequence, args.allow_ambiguous_aa, args.sanitize_invalid_to_x)
            warnings.extend(f"{rec.seq_id}: {w}" for w in seq_warnings)
            records.append(SeqRecord(rec.seq_id, seq, rec.description))
    return records, warnings


def dedupe_records(records: Sequence[SeqRecord]) -> List[SeqRecord]:
    seen_ids: Dict[str, int] = {}
    seen_seq = set()
    out: List[SeqRecord] = []
    for rec in records:
        if rec.sequence in seen_seq:
            continue
        seen_seq.add(rec.sequence)
        base = rec.seq_id or f"seq{len(out) + 1}"
        count = seen_ids.get(base, 0)
        seen_ids[base] = count + 1
        seq_id = base if count == 0 else f"{base}_{count + 1}"
        out.append(SeqRecord(seq_id, rec.sequence, rec.description))
    return out


def all_same_length(records: Sequence[SeqRecord]) -> bool:
    return len({len(r.sequence) for r in records}) <= 1


def ungapped_sequence(sequence: str) -> str:
    return "".join(c for c in sequence.upper() if c not in {GAP, "."})


def record_matches_query(record: SeqRecord, query: SeqRecord) -> bool:
    if record.seq_id == query.seq_id or record.seq_id.startswith(f"{query.seq_id}/"):
        return True
    query_token = query.seq_id.split("_", 1)[0]
    if query_token and (record.seq_id == query_token or record.seq_id.startswith(f"{query_token}/")):
        return True
    return ungapped_sequence(record.sequence) == ungapped_sequence(query.sequence)


def run_command(cmd: Sequence[str], log_path: Path, stdout_path: Optional[Path] = None) -> None:
    with log_path.open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(cmd) + "\n\n")
        if stdout_path:
            with stdout_path.open("w", encoding="utf-8") as stdout_handle:
                proc = subprocess.run(cmd, stdout=stdout_handle, stderr=log, text=True, check=False)
        else:
            proc = subprocess.run(cmd, stdout=log, stderr=log, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {proc.returncode}: {' '.join(cmd)}. See {log_path}")


def run_mafft(records: Sequence[SeqRecord], mafft_bin: str, outdir: Path, warnings: List[str]) -> Optional[List[SeqRecord]]:
    if shutil.which(mafft_bin) is None:
        warnings.append(f"MAFFT binary not found: {mafft_bin}")
        return None
    input_path = outdir / "mafft_input.fasta"
    output_path = outdir / "alignment.fasta"
    log_path = outdir / "logs" / "mafft.log"
    safe_mkdir(log_path.parent)
    write_fasta(records, input_path)
    run_command([mafft_bin, "--auto", str(input_path)], log_path, stdout_path=output_path)
    return read_fasta(output_path)


def run_biotite_msa(records: Sequence[SeqRecord], outdir: Path, warnings: List[str]) -> Optional[List[SeqRecord]]:
    try:
        import biotite.sequence as seq
        import biotite.sequence.align as align
    except Exception as exc:  # pragma: no cover - optional dependency
        warnings.append(f"Biotite MSA unavailable: {exc}")
        return None
    try:  # pragma: no cover - optional dependency
        sequences = [seq.ProteinSequence(rec.sequence) for rec in records]
        matrix = align.SubstitutionMatrix.std_protein_matrix()
        alignment = align.align_multiple(sequences, matrix)
        lines = [line.strip() for line in str(alignment).splitlines() if line.strip()]
        if len(lines) != len(records):
            warnings.append("Biotite MSA returned an unexpected text representation; falling back.")
            return None
        aligned = [SeqRecord(records[i].seq_id, lines[i].replace(" ", "").upper(), records[i].description) for i in range(len(records))]
        write_fasta(aligned, outdir / "alignment.fasta")
        return aligned
    except Exception as exc:
        warnings.append(f"Biotite MSA failed: {exc}")
        return None


def _decode_response_text(response) -> str:
    content = response.content
    if content.startswith(b"\x1f\x8b"):
        content = gzip.decompress(content)
    return content.decode(response.encoding or "utf-8", errors="replace")


def submit_ebi_jackhmmer(
    query_records: Sequence[SeqRecord],
    args: argparse.Namespace,
    outdir: Path,
    warnings: List[str],
) -> List[SeqRecord]:
    try:
        import requests
        import time
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(f"requests is required for EBI HMMER API execution: {exc}") from exc

    if not query_records:
        raise ValueError("--sequence or --fasta is required for EBI HMMER search.")
    if len(query_records) != 1:
        raise ValueError("EBI HMMER execution currently expects exactly one query sequence.")

    safe_mkdir(outdir / "search")
    safe_mkdir(outdir / "logs")

    query = query_records[0]
    query_fasta = f">{query.seq_id}\n{query.sequence}\n"
    payload = {
        "database": args.hmmer_database,
        "input": query_fasta,
        "input_type": "sequence",
        "iterations": args.hmmer_iterations,
        "E": args.evalue,
        "incE": args.inc_evalue if args.inc_evalue is not None else args.evalue,
    }
    headers = {**HTTP_HEADERS, "Accept": "application/json", "Content-Type": "application/json"}
    submit_url = f"{EBI_HMMER_API}/search/jackhmmer"
    submit = requests.post(submit_url, json=payload, headers=headers, timeout=60)
    if submit.status_code >= 400:
        raise RuntimeError(f"EBI HMMER submission failed (status {submit.status_code}): {submit.text[:500]}")

    data = submit.json()
    job_id = data.get("id")
    if not job_id:
        raise RuntimeError(f"EBI HMMER submission did not return a job id: {data}")
    (outdir / "search" / "ebi_hmmer_submission.json").write_text(
        json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
    )

    current_id = str(job_id)
    waited = 0
    max_wait = 600
    poll_interval = 5
    search_log = outdir / "logs" / "ebi_hmmer.log"
    with search_log.open("w", encoding="utf-8") as log:
        log.write(f"Submitted EBI HMMER jackhmmer job {current_id}\n")
        log.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        while waited < max_wait:
            poll = requests.get(f"{EBI_HMMER_API}/search/{current_id}", headers=HTTP_HEADERS, timeout=30)
            poll.raise_for_status()
            poll_data = poll.json()
            task = poll_data.get("task") or {}
            status = str(task.get("status", "")).upper()
            next_job_id = poll_data.get("next_job_id")
            if next_job_id:
                current_id = str(next_job_id)
            log.write(f"{waited}s status={status} job={current_id}\n")
            if status == "SUCCESS":
                break
            if status in {"FAILURE", "REVOKED"}:
                raise RuntimeError(f"EBI HMMER job failed with status {status}. See {search_log}")
            time.sleep(poll_interval)
            waited += poll_interval
        else:
            raise RuntimeError(f"EBI HMMER job timed out after {max_wait}s. See {search_log}")

    sto_text = download_ebi_hmmer_stockholm(current_id, outdir)
    sto_path = outdir / "search" / "ebi_hmmer_alignment.sto"
    sto_path.write_text(sto_text, encoding="utf-8")
    records = parse_stockholm(sto_text)
    if not records:
        raise RuntimeError("EBI HMMER returned a Stockholm file, but no alignment records were parsed.")

    if args.max_homologs and len(records) > args.max_homologs + 1:
        query_matches = [rec for rec in records if record_matches_query(rec, query)]
        others = [rec for rec in records if rec not in query_matches]
        if query_matches:
            records = query_matches[:1] + others[: args.max_homologs]
        else:
            warnings.append("Query sequence was not identified by ID in the EBI HMMER MSA; truncated from the first record.")
            records = records[: args.max_homologs + 1]
        warnings.append(f"EBI HMMER MSA truncated to {len(records)} sequences by --max-homologs")

    write_fasta(records, outdir / "alignment.fasta")
    return records


def download_ebi_hmmer_stockholm(job_id: str, outdir: Path) -> str:
    import requests
    import time

    headers = {**HTTP_HEADERS, "Accept": "application/json"}
    max_wait = 180
    poll_interval = 5
    for fmt in ("stockholm", "sto"):
        generate_url = f"{EBI_HMMER_API}/download/{job_id}/{fmt}"
        generate = requests.post(generate_url, headers=headers, timeout=30)
        if generate.status_code not in (200, 202, 204, 409, 422):
            generate.raise_for_status()

        waited = 0
        while waited <= max_wait:
            downloads = requests.get(f"{EBI_HMMER_API}/download/{job_id}", headers=headers, timeout=30)
            if downloads.status_code == 200:
                (outdir / "search" / "ebi_hmmer_downloads.json").write_text(
                    json.dumps(downloads.json(), indent=2, sort_keys=True), encoding="utf-8"
                )
                for item in downloads.json():
                    haystack = " ".join(str(item.get(k, "")) for k in ("format", "name", "description")).lower()
                    url = item.get("url")
                    status = str(item.get("status", "")).lower()
                    if "stockholm" in haystack and url and status not in {"pending", "running"}:
                        if url.startswith("/"):
                            url = f"https://www.ebi.ac.uk{url}"
                        file_response = requests.get(url, headers=HTTP_HEADERS, timeout=60)
                        file_response.raise_for_status()
                        text = _decode_response_text(file_response)
                        if "# STOCKHOLM" in text:
                            return text

            direct = requests.get(generate_url, headers=HTTP_HEADERS, timeout=60)
            if direct.status_code == 200:
                text = _decode_response_text(direct)
                if "# STOCKHOLM" in text:
                    return text

            time.sleep(poll_interval)
            waited += poll_interval

    raise RuntimeError("EBI HMMER completed, but no Stockholm MSA download became available.")


def obtain_alignment(args: argparse.Namespace, query_records: Sequence[SeqRecord], outdir: Path, warnings: List[str]) -> List[SeqRecord]:
    if args.alignment:
        path = Path(args.alignment)
        if path.suffix.lower() in {".sto", ".stockholm"} or "# STOCKHOLM" in read_text(path)[:200]:
            records = parse_stockholm(read_text(path))
        else:
            records = read_fasta(path)
        if not records:
            raise ValueError(f"No aligned sequences parsed from {path}")
        write_fasta(records, outdir / "alignment.fasta")
        return records

    homologs: List[SeqRecord] = []
    if args.homolog_fasta:
        homologs.extend(read_fasta(Path(args.homolog_fasta)))

    local_sto = outdir / "search" / "query.homologs.sto"
    if args.execute and args.search_backend == "local-hmmer":
        if not query_records:
            raise ValueError("--sequence or --fasta is required for local HMMER search.")
        if not args.target_db:
            raise ValueError("--target-db is required for local HMMER search.")
        if shutil.which(args.jackhmmer_bin) is None:
            raise RuntimeError(f"jackhmmer binary not found: {args.jackhmmer_bin}")
        safe_mkdir(local_sto.parent)
        query_path = outdir / "normalized_input.fasta"
        write_fasta(query_records, query_path)
        inc_evalue = args.inc_evalue if args.inc_evalue is not None else args.evalue
        cmd = [
            args.jackhmmer_bin,
            "--cpu",
            str(args.cpu),
            "-N",
            str(args.hmmer_iterations),
            "-E",
            str(args.evalue),
            "--incE",
            str(inc_evalue),
            "-A",
            str(local_sto),
            "--tblout",
            str(outdir / "search" / "jackhmmer.tbl"),
            str(query_path),
            str(args.target_db),
        ]
        run_command(cmd, outdir / "logs" / "jackhmmer.log")
        if local_sto.exists():
            records = parse_stockholm(read_text(local_sto))
            if records:
                write_fasta(records, outdir / "alignment.fasta")
                return records
            warnings.append("jackhmmer finished but no Stockholm alignment records were parsed.")

    if args.execute and args.search_backend == "ebi-hmmer":
        return submit_ebi_jackhmmer(query_records, args, outdir, warnings)

    combined = list(query_records) + homologs
    combined = dedupe_records(combined)
    if args.max_homologs and len(combined) > args.max_homologs + len(query_records):
        combined = combined[: args.max_homologs + len(query_records)]
        warnings.append(f"homolog set truncated to {len(combined)} sequences by --max-homologs")

    if len(combined) < 2:
        raise ValueError("At least two aligned or homologous sequences are required for conservation scoring.")

    write_fasta(combined, outdir / "homologs.filtered.fasta")

    if all_same_length(combined):
        write_fasta(combined, outdir / "alignment.fasta")
        return combined

    if args.msa_backend in {"auto", "mafft"}:
        aligned = run_mafft(combined, args.mafft_bin, outdir, warnings)
        if aligned:
            return aligned
        if args.msa_backend == "mafft":
            raise RuntimeError("MAFFT was requested but failed or was unavailable.")

    if args.msa_backend in {"auto", "biotite"}:
        aligned = run_biotite_msa(combined, outdir, warnings)
        if aligned:
            return aligned
        if args.msa_backend == "biotite":
            raise RuntimeError("Biotite MSA was requested but failed or was unavailable.")

    raise RuntimeError("No MSA backend produced an alignment. Provide --alignment or install mafft/biotite.")


def choose_query_record(records: Sequence[SeqRecord], query_records: Sequence[SeqRecord], query_id: Optional[str]) -> SeqRecord:
    candidates = [query_id] if query_id else []
    candidates.extend(rec.seq_id for rec in query_records)
    for cand in candidates:
        if not cand:
            continue
        for rec in records:
            if rec.seq_id == cand:
                return rec
    for query in query_records:
        for rec in records:
            if record_matches_query(rec, query):
                return rec
    return records[0]


def shannon_entropy(counts: Counter, total: int) -> float:
    entropy = 0.0
    for count in counts.values():
        if count <= 0:
            continue
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def score_alignment(
    alignment: Sequence[SeqRecord],
    query: SeqRecord,
    conserved_threshold: float,
    variable_threshold: float,
    max_gap_fraction: float,
) -> List[SiteScore]:
    aln_lengths = {len(rec.sequence) for rec in alignment}
    if len(aln_lengths) != 1:
        raise ValueError(f"Alignment sequences have inconsistent lengths: {sorted(aln_lengths)}")
    ncols = next(iter(aln_lengths))
    nseq = len(alignment)
    query_pos = 0
    scores: List[SiteScore] = []
    query_seq = query.sequence
    for col in range(ncols):
        q_res = query_seq[col] if col < len(query_seq) else GAP
        chars = [(rec.sequence[col] if col < len(rec.sequence) else GAP).upper() for rec in alignment]
        if q_res == GAP:
            continue
        query_pos += 1
        non_gap = [c for c in chars if c != GAP]
        gap_fraction = 1.0 - (len(non_gap) / nseq if nseq else 0.0)
        aa_counts = Counter(c for c in non_gap if c in VALID_AA)
        n_non_gap = sum(aa_counts.values())
        if n_non_gap == 0:
            entropy = 0.0
            score = 0.0
            consensus = ""
            consensus_fraction = 0.0
            query_fraction = 0.0
        else:
            entropy = shannon_entropy(aa_counts, n_non_gap)
            max_entropy = math.log2(20)
            score = max(0.0, min(1.0, 1.0 - entropy / max_entropy))
            consensus, consensus_count = aa_counts.most_common(1)[0]
            consensus_fraction = consensus_count / n_non_gap
            query_fraction = aa_counts.get(q_res, 0) / n_non_gap
        grade = max(1, min(9, int(score * 8) + 1))
        note = ""
        if gap_fraction > max_gap_fraction:
            status = "gap_rich"
            note = f"gap_fraction>{max_gap_fraction}"
        elif score >= conserved_threshold:
            status = "conserved"
        elif score <= variable_threshold:
            status = "variable"
        else:
            status = "intermediate"
        scores.append(
            SiteScore(
                query_id=query.seq_id,
                position=query_pos,
                residue=q_res,
                alignment_column=col + 1,
                n_sequences=nseq,
                n_non_gap=n_non_gap,
                gap_fraction=gap_fraction,
                consensus_residue=consensus,
                consensus_fraction=consensus_fraction,
                query_residue_fraction=query_fraction,
                entropy=entropy,
                conservation_score=score,
                conservation_grade=grade,
                status=status,
                note=note,
            )
        )
    return scores


def call_regions(scores: Sequence[SiteScore], status: str, min_length: int) -> List[Dict[str, object]]:
    regions: List[Dict[str, object]] = []
    current: List[SiteScore] = []
    for site in scores:
        if site.status == status:
            current.append(site)
        else:
            if len(current) >= min_length:
                regions.append(region_from_sites(current, status))
            current = []
    if len(current) >= min_length:
        regions.append(region_from_sites(current, status))
    return regions


def region_from_sites(sites: Sequence[SiteScore], status: str) -> Dict[str, object]:
    return {
        "query_id": sites[0].query_id,
        "region_type": status,
        "start": sites[0].position,
        "end": sites[-1].position,
        "length": sites[-1].position - sites[0].position + 1,
        "mean_conservation_score": round(sum(s.conservation_score for s in sites) / len(sites), 6),
        "mean_gap_fraction": round(sum(s.gap_fraction for s in sites) / len(sites), 6),
        "max_conservation_score": round(max(s.conservation_score for s in sites), 6),
        "min_conservation_score": round(min(s.conservation_score for s in sites), 6),
        "evidence": "MSA entropy conservation",
        "note": "",
    }


def write_tsv(path: Path, rows: Sequence[Dict[str, object]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize(
    query: SeqRecord,
    alignment: Sequence[SeqRecord],
    scores: Sequence[SiteScore],
    regions: Sequence[Dict[str, object]],
    args: argparse.Namespace,
    warnings: Sequence[str],
) -> Dict[str, object]:
    conserved = [s for s in scores if s.status == "conserved"]
    variable = [s for s in scores if s.status == "variable"]
    gap_rich = [s for s in scores if s.status == "gap_rich"]
    mean_score = sum(s.conservation_score for s in scores) / len(scores) if scores else 0.0
    mean_gap = sum(s.gap_fraction for s in scores) / len(scores) if scores else 0.0
    conserved_regions = [r for r in regions if r["region_type"] == "conserved"]
    longest = max((int(r["length"]) for r in conserved_regions), default=0)
    target_database = ""
    if args.search_backend in {"local-hmmer", "mmseqs"}:
        target_database = args.target_db or ""
    elif args.search_backend == "ebi-hmmer":
        target_database = args.hmmer_database or ""
    return {
        "query_id": query.seq_id,
        "query_length": len(query.sequence.replace(GAP, "")),
        "alignment_sequence_count": len(alignment),
        "homolog_sequence_count": max(0, len(alignment) - 1),
        "alignment_length": len(alignment[0].sequence) if alignment else 0,
        "search_backend": args.search_backend,
        "target_database": target_database,
        "msa_backend": args.msa_backend,
        "mean_conservation_score": round(mean_score, 6),
        "mean_gap_fraction": round(mean_gap, 6),
        "fraction_conserved": round(len(conserved) / len(scores), 6) if scores else 0.0,
        "fraction_variable": round(len(variable) / len(scores), 6) if scores else 0.0,
        "fraction_gap_rich": round(len(gap_rich) / len(scores), 6) if scores else 0.0,
        "n_conserved_residues": len(conserved),
        "n_variable_residues": len(variable),
        "n_conserved_regions": len(conserved_regions),
        "longest_conserved_region": longest,
        "conserved_threshold": args.conserved_threshold,
        "variable_threshold": args.variable_threshold,
        "warnings": "; ".join(warnings),
    }


def write_command_plans(args: argparse.Namespace, outdir: Path, query_fasta: Path) -> Dict[str, str]:
    commands_path = outdir / "commands.sh"
    download_path = outdir / "database_download_plan.sh"
    inc_evalue = args.inc_evalue if args.inc_evalue is not None else args.evalue
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Review paths and database choices before running.",
        f"QUERY_FASTA={shell_quote(str(query_fasta))}",
        f"OUTDIR={shell_quote(str(outdir))}",
        "",
    ]
    if args.search_backend == "local-hmmer":
        target = args.target_db or "<TARGET_PROTEIN_FASTA>"
        lines.extend(
            [
                "mkdir -p \"$OUTDIR/search\" \"$OUTDIR/logs\"",
                (
                    f"{args.jackhmmer_bin} --cpu {args.cpu} -N {args.hmmer_iterations} "
                    f"-E {args.evalue} --incE {inc_evalue} "
                    f"-A \"$OUTDIR/search/query.homologs.sto\" "
                    f"--tblout \"$OUTDIR/search/jackhmmer.tbl\" "
                    f"\"$QUERY_FASTA\" {shell_quote(target)} "
                    f"> \"$OUTDIR/logs/jackhmmer.stdout.log\" 2> \"$OUTDIR/logs/jackhmmer.stderr.log\""
                ),
                "",
                "# Then import the Stockholm MSA:",
                (
                    "python skills/protein-conservation-assessment/scripts/protein_conservation_assessment.py "
                    "\"--alignment\" \"$OUTDIR/search/query.homologs.sto\" "
                    "\"--query-id\" <QUERY_ID> "
                    "\"--outdir\" \"$OUTDIR\""
                ),
            ]
        )
    elif args.search_backend == "ebi-hmmer":
        lines.extend(
            [
                "# EBI HMMER API runs on EMBL-EBI hosted databases.",
                "# The database value should be one of: refprot, uniprot, swissprot, pdb, rp15, rp35, rp55, rp75.",
                f"# Selected database: {args.hmmer_database}",
                "# Use the API only when network access is acceptable and results can be cited with search details.",
            ]
        )
    elif args.search_backend == "mmseqs":
        target = args.target_db or "<MMSEQS_TARGET_DB_OR_FASTA>"
        lines.extend(
            [
                "mkdir -p \"$OUTDIR/search\" \"$OUTDIR/tmp\"",
                (
                    f"{args.mmseqs_bin} easy-search \"$QUERY_FASTA\" {shell_quote(target)} "
                    "\"$OUTDIR/search/mmseqs_hits.m8\" \"$OUTDIR/tmp\" "
                    f"--threads {args.cpu} -e {args.evalue} "
                    "--format-output query,target,pident,alnlen,mismatch,gapopen,qstart,qend,tstart,tend,evalue,bits"
                ),
                "# Export matched target sequences to homolog FASTA before MSA, then rerun this script with --homolog-fasta.",
            ]
        )
    else:
        lines.append("# No search backend selected. Provide --homolog-fasta or --alignment for scoring.")
    commands_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(commands_path, 0o755)

    download_lines = build_download_plan(args)
    download_path.write_text("\n".join(download_lines) + "\n", encoding="utf-8")
    os.chmod(download_path, 0o755)
    return {"commands": str(commands_path), "database_download_plan": str(download_path)}


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def shell_path_assignment(value: str) -> str:
    if value.startswith("$HOME/"):
        suffix = value[len("$HOME/") :].replace('"', '\\"')
        return f'"${{HOME}}/{suffix}"'
    if value.startswith("~/"):
        suffix = value[len("~/") :].replace('"', '\\"')
        return f'"${{HOME}}/{suffix}"'
    return shell_quote(value)


def build_download_plan(args: argparse.Namespace) -> List[str]:
    db_dir = args.db_dir or "$HOME/biodata/protein_conservation"
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Do not run this script until the user has approved the database choice, size, and destination.",
        f"DB_DIR={shell_path_assignment(db_dir)}",
        "mkdir -p \"$DB_DIR\"",
        "",
    ]
    if args.db_choice == "swissprot":
        lines.extend(
            [
                "# Swiss-Prot is small enough for testing and reviewed-sequence searches.",
                "curl -L -o \"$DB_DIR/uniprot_sprot.fasta.gz\" https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz",
                "gunzip -k \"$DB_DIR/uniprot_sprot.fasta.gz\"",
                "# Use --target-db \"$DB_DIR/uniprot_sprot.fasta\"",
            ]
        )
    elif args.db_choice == "uniref90":
        lines.extend(
            [
                "# UniRef90 is large; confirm available disk space before running.",
                "curl -L -o \"$DB_DIR/uniref90.fasta.gz\" https://ftp.uniprot.org/pub/databases/uniprot/uniref/uniref90/uniref90.fasta.gz",
                "gunzip -k \"$DB_DIR/uniref90.fasta.gz\"",
                "# Use --target-db \"$DB_DIR/uniref90.fasta\"",
            ]
        )
    elif args.db_choice == "uniref50":
        lines.extend(
            [
                "# UniRef50 is smaller than UniRef90 and useful for broad remote-homolog scans.",
                "curl -L -o \"$DB_DIR/uniref50.fasta.gz\" https://ftp.uniprot.org/pub/databases/uniprot/uniref/uniref50/uniref50.fasta.gz",
                "gunzip -k \"$DB_DIR/uniref50.fasta.gz\"",
                "# Use --target-db \"$DB_DIR/uniref50.fasta\"",
            ]
        )
    elif args.db_choice == "uniprot-reference-proteomes":
        lines.extend(
            [
                "# Reference Proteomes are distributed as grouped archives; inspect the UniProt FTP index first.",
                "# Start here: https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/reference_proteomes/",
                "# Download only the taxonomic subset required for the project.",
            ]
        )
    elif args.db_choice == "custom":
        lines.extend(
            [
                "# Place the user's custom protein FASTA in DB_DIR and pass it with --target-db.",
                "# Example: --target-db \"$DB_DIR/custom_proteins.fasta\"",
            ]
        )
    else:
        lines.append("# No database selected. Re-run with --db-choice swissprot|uniref90|uniref50|uniprot-reference-proteomes|custom.")
    return lines


def create_plots(scores: Sequence[SiteScore], regions: Sequence[Dict[str, object]], outdir: Path, prefix: str, warnings: List[str]) -> Dict[str, str]:
    plot_dir = outdir / "plots"
    safe_mkdir(plot_dir)
    paths: Dict[str, str] = {}
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        warnings.append(f"matplotlib unavailable; plots skipped: {exc}")
        return paths

    if not scores:
        return paths
    x = [s.position for s in scores]
    y = [s.conservation_score for s in scores]
    colors = ["#8b0000" if s.status == "conserved" else "#0072b2" if s.status == "variable" else "#999999" for s in scores]
    fig, ax = plt.subplots(figsize=(max(8, min(18, len(scores) / 18)), 3.2))
    ax.bar(x, y, width=1.0, color=colors, linewidth=0)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Query residue position")
    ax.set_ylabel("Conservation score")
    ax.set_title(f"Evolutionary conservation: {prefix}")
    for region in regions:
        if region["region_type"] == "conserved":
            ax.axvspan(int(region["start"]) - 0.5, int(region["end"]) + 0.5, color="#f4a582", alpha=0.18)
    svg = plot_dir / "conservation_profile.svg"
    png = plot_dir / "conservation_profile.png"
    fig.tight_layout()
    fig.savefig(svg)
    fig.savefig(png, dpi=180)
    plt.close(fig)
    paths["conservation_profile_svg"] = str(svg)
    paths["conservation_profile_png"] = str(png)

    html_path = plot_dir / "conservation_profile.html"
    html_path.write_text(
        "<!doctype html><meta charset='utf-8'><title>Conservation profile</title>"
        f"<h1>{html.escape(prefix)} conservation profile</h1>"
        f"<img src='{html.escape(svg.name)}' alt='Conservation profile'>",
        encoding="utf-8",
    )
    paths["conservation_profile_html"] = str(html_path)
    return paths


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    outdir = Path(args.outdir)
    safe_mkdir(outdir)
    safe_mkdir(outdir / "logs")
    warnings: List[str] = []
    artifacts: Dict[str, str] = {}

    try:
        query_records, query_warnings = load_query_records(args)
        warnings.extend(query_warnings)
        if query_records:
            normalized = outdir / "normalized_input.fasta"
            write_fasta(query_records, normalized)
            artifacts["normalized_input_fasta"] = str(normalized)
        else:
            normalized = outdir / "normalized_input.fasta"
            warnings.append("No raw query sequence/FASTA was provided; query will be inferred from alignment.")

        artifacts.update(write_command_plans(args, outdir, normalized))

        alignment = obtain_alignment(args, query_records, outdir, warnings)
        if not alignment:
            raise ValueError("No alignment records available.")
        artifacts["alignment_fasta"] = str(outdir / "alignment.fasta")

        query = choose_query_record(alignment, query_records, args.query_id)
        scores = score_alignment(alignment, query, args.conserved_threshold, args.variable_threshold, args.max_gap_fraction)
        regions = call_regions(scores, "conserved", args.min_region_length)
        regions.extend(call_regions(scores, "variable", args.min_region_length))

        site_rows = [
            {
                "query_id": s.query_id,
                "position": s.position,
                "residue": s.residue,
                "alignment_column": s.alignment_column,
                "n_sequences": s.n_sequences,
                "n_non_gap": s.n_non_gap,
                "gap_fraction": round(s.gap_fraction, 6),
                "consensus_residue": s.consensus_residue,
                "consensus_fraction": round(s.consensus_fraction, 6),
                "query_residue_fraction": round(s.query_residue_fraction, 6),
                "entropy": round(s.entropy, 6),
                "conservation_score": round(s.conservation_score, 6),
                "conservation_grade": s.conservation_grade,
                "status": s.status,
                "note": s.note,
            }
            for s in scores
        ]
        summary = summarize(query, alignment, scores, regions, args, warnings)
        summary_path = outdir / "protein_conservation_summary.tsv"
        sites_path = outdir / "protein_conservation_sites.tsv"
        regions_path = outdir / "protein_conserved_regions.tsv"
        write_tsv(summary_path, [summary], list(summary.keys()))
        write_tsv(
            sites_path,
            site_rows,
            [
                "query_id",
                "position",
                "residue",
                "alignment_column",
                "n_sequences",
                "n_non_gap",
                "gap_fraction",
                "consensus_residue",
                "consensus_fraction",
                "query_residue_fraction",
                "entropy",
                "conservation_score",
                "conservation_grade",
                "status",
                "note",
            ],
        )
        write_tsv(
            regions_path,
            regions,
            [
                "query_id",
                "region_type",
                "start",
                "end",
                "length",
                "mean_conservation_score",
                "mean_gap_fraction",
                "max_conservation_score",
                "min_conservation_score",
                "evidence",
                "note",
            ],
        )
        artifacts["summary_tsv"] = str(summary_path)
        artifacts["sites_tsv"] = str(sites_path)
        artifacts["regions_tsv"] = str(regions_path)

        if not args.no_plots:
            artifacts.update(create_plots(scores, regions, outdir, args.prefix or query.seq_id, warnings))

        result = {
            "status": "ok",
            "parameters": vars(args),
            "query_id": query.seq_id,
            "artifacts": artifacts,
            "warnings": warnings,
            "summary": summary,
        }
        result_path = outdir / "protein_conservation_assessment.result.json"
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(f"[OK] Conservation assessment written to {outdir}")
        return 0
    except Exception as exc:
        result = {
            "status": "error",
            "error": str(exc),
            "parameters": vars(args),
            "artifacts": artifacts,
            "warnings": warnings,
        }
        result_path = outdir / "protein_conservation_assessment.result.json"
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assess protein evolutionary conservation from homologs or an MSA.")
    parser.add_argument("--sequence", help="Raw amino-acid query sequence.")
    parser.add_argument("--sequence-name", default="query", help="Identifier for --sequence input.")
    parser.add_argument("--fasta", help="Protein FASTA containing one or more query sequences.")
    parser.add_argument("--query-id", help="Query ID to map conservation sites onto. Defaults to sequence input or first alignment record.")
    parser.add_argument("--homolog-fasta", help="FASTA containing homologous proteins. Query is prepended when --sequence/--fasta is also provided.")
    parser.add_argument("--alignment", help="Existing aligned FASTA or Stockholm MSA.")
    parser.add_argument("--search-backend", choices=["none", "local-hmmer", "ebi-hmmer", "mmseqs"], default="none")
    parser.add_argument("--target-db", help="Local target protein FASTA/database for jackhmmer or MMseqs2.")
    parser.add_argument("--hmmer-database", default="refprot", help="EBI HMMER database token, e.g. refprot, uniprot, swissprot, pdb, rp15, rp35, rp55, rp75.")
    parser.add_argument("--hmmer-iterations", type=int, default=3)
    parser.add_argument("--evalue", type=float, default=1e-4)
    parser.add_argument("--inc-evalue", type=float)
    parser.add_argument("--cpu", type=int, default=4)
    parser.add_argument("--jackhmmer-bin", default="jackhmmer")
    parser.add_argument("--mmseqs-bin", default="mmseqs")
    parser.add_argument("--msa-backend", choices=["auto", "mafft", "biotite", "none"], default="auto")
    parser.add_argument("--mafft-bin", default="mafft")
    parser.add_argument("--execute", action="store_true", help="Execute supported local commands instead of only writing command plans.")
    parser.add_argument("--db-choice", choices=["none", "swissprot", "uniref90", "uniref50", "uniprot-reference-proteomes", "custom"], default="none")
    parser.add_argument("--db-dir", help="Destination directory for database download plans.")
    parser.add_argument("--max-homologs", type=int, default=500)
    parser.add_argument("--conserved-threshold", type=float, default=0.75)
    parser.add_argument("--variable-threshold", type=float, default=0.35)
    parser.add_argument("--max-gap-fraction", type=float, default=0.50)
    parser.add_argument("--min-region-length", type=int, default=5)
    parser.add_argument("--allow-ambiguous-aa", action="store_true")
    parser.add_argument("--sanitize-invalid-to-x", action="store_true")
    parser.add_argument("--prefix", default="")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--no-plots", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
