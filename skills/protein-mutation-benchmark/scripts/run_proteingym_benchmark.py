#!/usr/bin/env python3
"""Align project mutation scores to ProteinGym-style truth and compute deterministic metrics."""

from __future__ import annotations

import argparse
import platform
import re
import shlex
import shutil
import sys
import tarfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from proteingym_utils import (
    file_sha256,
    matthews_corrcoef,
    ndcg,
    roc_auc,
    spearman,
    write_json,
    write_tsv,
)
from validate_proteingym_table import normalize_table


METRIC_FIELDS = [
    "assay_id",
    "model_id",
    "score_name",
    "metric",
    "value",
    "n",
    "status",
    "reason",
    "task",
    "higher_is",
]

ALIGNMENT_FIELDS = [
    "assay_id",
    "protein_id",
    "mutation",
    "mutation_type",
    "dms_score",
    "label",
    "model_id",
    "score_name",
    "raw_score",
    "higher_is",
    "oriented_score",
]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--assay-data", required=True, help="ProteinGym-like assay CSV/TSV")
    result.add_argument("--scores", required=True, help="Project long-form model score CSV/TSV")
    result.add_argument("--output-dir", required=True, help="New or existing run directory")
    result.add_argument("--assay-id", help="Fallback ID for single-assay files without an assay column")
    result.add_argument("--task", choices=("auto", "regression", "classification", "both"), default="auto")
    result.add_argument("--classification-threshold", type=float, help="Oriented score threshold for MCC")
    result.add_argument("--ndcg-k", type=int, help="NDCG cutoff; default evaluates all aligned variants")
    result.add_argument("--ndcg-relevance", choices=("rank", "raw-clipped"), default="rank")
    result.add_argument("--min-aligned", type=int, default=2)
    result.add_argument("--assay-mutation-column")
    result.add_argument("--assay-score-column")
    result.add_argument("--assay-label-column")
    result.add_argument("--assay-id-column")
    result.add_argument("--assay-protein-column")
    result.add_argument("--score-mutation-column")
    result.add_argument("--score-value-column")
    result.add_argument("--score-model-column")
    result.add_argument("--score-name-column")
    result.add_argument("--score-higher-is-column")
    result.add_argument("--score-assay-column")
    result.add_argument("--score-protein-column")
    result.add_argument(
        "--allow-existing-output",
        action="store_true",
        help="Allow writing into a nonempty output directory; inspect its manifest first",
    )
    cleanup = result.add_mutually_exclusive_group()
    cleanup.add_argument(
        "--archive-intermediates",
        action="store_true",
        help="Create intermediate.tar.gz, then remove intermediate/",
    )
    cleanup.add_argument(
        "--cleanup-intermediates",
        action="store_true",
        help="Remove only this run's intermediate/ after success",
    )
    return result


def validation_args(
    *,
    kind: str,
    input_path: Path,
    output_path: Path,
    report_path: Path,
    fallback_assay: str,
    args: argparse.Namespace,
) -> argparse.Namespace:
    if kind == "assay":
        return argparse.Namespace(
            input=str(input_path),
            kind=kind,
            output_tsv=str(output_path),
            report_json=str(report_path),
            assay_id=fallback_assay,
            mutation_column=args.assay_mutation_column,
            assay_column=args.assay_id_column,
            protein_column=args.assay_protein_column,
            score_column=args.assay_score_column,
            label_column=args.assay_label_column,
            model_column=None,
            score_name_column=None,
            higher_is_column=None,
            allow_invalid=True,
        )
    return argparse.Namespace(
        input=str(input_path),
        kind=kind,
        output_tsv=str(output_path),
        report_json=str(report_path),
        assay_id=fallback_assay,
        mutation_column=args.score_mutation_column,
        assay_column=args.score_assay_column,
        protein_column=args.score_protein_column,
        score_column=args.score_value_column,
        label_column=None,
        model_column=args.score_model_column,
        score_name_column=args.score_name_column,
        higher_is_column=args.score_higher_is_column,
        allow_invalid=True,
    )


def metric_row(
    group_key: tuple[str, str, str],
    name: str,
    value,
    n: int,
    task: str,
    higher_is: str,
    reason: str = "",
) -> dict:
    assay_id, model_id, score_name = group_key
    return {
        "assay_id": assay_id,
        "model_id": model_id,
        "score_name": score_name,
        "metric": name,
        "value": value,
        "n": n,
        "status": "computed" if value is not None else "not_computed",
        "reason": "" if value is not None else reason,
        "task": task,
        "higher_is": higher_is,
    }


def safe_cleanup(run_dir: Path, intermediate: Path, archive: bool) -> str | None:
    run_resolved = run_dir.resolve()
    if intermediate.is_symlink():
        raise RuntimeError(f"Refusing cleanup symlink: {intermediate}")
    target = intermediate.resolve()
    if target.name != "intermediate" or target.parent != run_resolved:
        raise RuntimeError(f"Refusing unsafe cleanup target: {target}")
    archive_path = None
    if archive and target.exists():
        archive_path = run_resolved / "intermediate.tar.gz"
        with tarfile.open(archive_path, "w:gz") as handle:
            handle.add(target, arcname="intermediate")
    if target.exists():
        shutil.rmtree(target)
    return str(archive_path) if archive_path else None


def bash_command(parts: list[str]) -> str:
    rendered = [str(part) for part in parts]
    if rendered and re.match(r"^[A-Za-z]:[\\/]", rendered[0]):
        drive = rendered[0][0].lower()
        suffix = rendered[0][2:].replace("\\", "/").lstrip("/")
        rendered[0] = f"/mnt/{drive}/{suffix}"
    return shlex.join(rendered)


def main() -> int:
    args = parser().parse_args()
    if args.min_aligned < 2:
        print("ERROR: --min-aligned must be >= 2", file=sys.stderr)
        return 2
    if args.ndcg_k is not None and args.ndcg_k < 1:
        print("ERROR: --ndcg-k must be >= 1", file=sys.stderr)
        return 2
    assay_path = Path(args.assay_data).expanduser().resolve()
    score_path = Path(args.scores).expanduser().resolve()
    if not assay_path.is_file() or not score_path.is_file():
        print("ERROR: --assay-data and --scores must be existing files", file=sys.stderr)
        return 2

    run_dir = Path(args.output_dir).expanduser().resolve()
    if run_dir.exists() and any(run_dir.iterdir()) and not args.allow_existing_output:
        print(
            "ERROR: output directory is not empty; use a new directory or explicitly add --allow-existing-output",
            file=sys.stderr,
        )
        return 2
    raw_dir = run_dir / "raw"
    intermediate = run_dir / "intermediate"
    logs_dir = run_dir / "logs"
    for directory in (run_dir, raw_dir, intermediate, logs_dir):
        directory.mkdir(parents=True, exist_ok=True)
    replay_args = list(sys.argv[1:])
    for flag, value in (("--assay-data", assay_path), ("--scores", score_path), ("--output-dir", run_dir)):
        index = replay_args.index(flag)
        replay_args[index + 1] = str(value)
    if "--allow-existing-output" not in replay_args:
        replay_args.append("--allow-existing-output")
    command = bash_command([sys.executable, str(Path(__file__).resolve()), *replay_args])
    with (run_dir / "commands.sh").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("#!/usr/bin/env bash\nset -euo pipefail\n" + command + "\n")
    started_at = datetime.now(timezone.utc).isoformat()
    log_lines = [f"started_at={started_at}", f"command={command}"]

    copied_assay = raw_dir / f"assay{assay_path.suffix.lower()}"
    copied_scores = raw_dir / f"scores{score_path.suffix.lower()}"
    shutil.copy2(assay_path, copied_assay)
    shutil.copy2(score_path, copied_scores)
    fallback_assay = args.assay_id or assay_path.stem

    try:
        assays, assay_report = normalize_table(
            validation_args(
                kind="assay",
                input_path=copied_assay,
                output_path=intermediate / "normalized_assay.tsv",
                report_path=run_dir / "assay_validation.json",
                fallback_assay=fallback_assay,
                args=args,
            )
        )
        scores, score_report = normalize_table(
            validation_args(
                kind="scores",
                input_path=copied_scores,
                output_path=intermediate / "normalized_scores.tsv",
                report_path=run_dir / "score_validation.json",
                fallback_assay=fallback_assay,
                args=args,
            )
        )
    except (FileNotFoundError, ValueError) as exc:
        write_json(run_dir / "summary.json", {"status": "failed_validation", "error": str(exc)})
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    assay_lookup = {(str(row["assay_id"]), str(row["mutation"])): row for row in assays}
    aligned: list[dict] = []
    exclusions: list[dict] = []
    for score in scores:
        key = (str(score["assay_id"]), str(score["mutation"]))
        truth = assay_lookup.get(key)
        if truth is None:
            exclusions.append(
                {
                    "source": "scores",
                    "source_row": score["source_row"],
                    "assay_id": score["assay_id"],
                    "protein_id": score["protein_id"],
                    "mutation": score["mutation"],
                    "model_id": score["model_id"],
                    "reason": "no_matching_assay_mutation",
                }
            )
            continue
        if score["protein_id"] and truth["protein_id"] and score["protein_id"] != truth["protein_id"]:
            exclusions.append(
                {
                    "source": "scores",
                    "source_row": score["source_row"],
                    "assay_id": score["assay_id"],
                    "protein_id": score["protein_id"],
                    "mutation": score["mutation"],
                    "model_id": score["model_id"],
                    "reason": "protein_id_mismatch",
                }
            )
            continue
        raw_score = float(score["raw_score"])
        oriented = raw_score if score["higher_is"] == "higher" else -raw_score
        aligned.append(
            {
                "assay_id": truth["assay_id"],
                "protein_id": truth["protein_id"] or score["protein_id"],
                "mutation": truth["mutation"],
                "mutation_type": truth["mutation_type"],
                "dms_score": truth["dms_score"],
                "label": truth["label"],
                "model_id": score["model_id"],
                "score_name": score["score_name"],
                "raw_score": raw_score,
                "higher_is": score["higher_is"],
                "oriented_score": oriented,
            }
        )

    write_tsv(run_dir / "aligned_scores.tsv", aligned, ALIGNMENT_FIELDS)
    exclusion_fields = ["source", "source_row", "assay_id", "protein_id", "mutation", "model_id", "reason"]
    write_tsv(run_dir / "exclusions.tsv", exclusions, exclusion_fields)

    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in aligned:
        groups[(row["assay_id"], row["model_id"], row["score_name"])].append(row)
    metrics: list[dict] = []
    group_summaries: list[dict] = []
    for key in sorted(groups):
        rows = groups[key]
        dms_rows = [row for row in rows if row["dms_score"] != ""]
        label_rows = [row for row in rows if row["label"] != ""]
        direction_values = sorted({row["higher_is"] for row in rows})
        direction = direction_values[0] if len(direction_values) == 1 else "mixed-oriented"
        use_regression = args.task in {"regression", "both"} or (args.task == "auto" and bool(dms_rows))
        use_classification = args.task in {"classification", "both"} or (
            args.task == "auto" and bool(label_rows)
        )
        if use_regression:
            truth = [float(row["dms_score"]) for row in dms_rows]
            predicted = [float(row["oriented_score"]) for row in dms_rows]
            enough = len(dms_rows) >= args.min_aligned
            rho = spearman(truth, predicted) if enough else None
            metrics.append(
                metric_row(
                    key,
                    "spearman",
                    rho,
                    len(dms_rows),
                    "regression",
                    direction,
                    "too_few_rows_or_constant_values",
                )
            )
            rank_metric = ndcg(truth, predicted, args.ndcg_k, args.ndcg_relevance) if enough else None
            metric_name = f"ndcg@{args.ndcg_k}" if args.ndcg_k else "ndcg@all"
            metrics.append(
                metric_row(
                    key,
                    metric_name,
                    rank_metric,
                    len(dms_rows),
                    "ranking",
                    direction,
                    "too_few_rows_or_zero_relevance",
                )
            )
        if use_classification:
            labels = [int(row["label"]) for row in label_rows]
            predicted = [float(row["oriented_score"]) for row in label_rows]
            enough = len(label_rows) >= args.min_aligned
            auc = roc_auc(labels, predicted) if enough else None
            metrics.append(
                metric_row(
                    key,
                    "roc_auc",
                    auc,
                    len(label_rows),
                    "classification",
                    direction,
                    "too_few_rows_or_single_class",
                )
            )
            if args.classification_threshold is None:
                mcc = None
                reason = "classification_threshold_not_provided"
            else:
                predicted_labels = [int(value >= args.classification_threshold) for value in predicted]
                mcc = matthews_corrcoef(labels, predicted_labels) if enough else None
                reason = "too_few_rows_or_degenerate_confusion_matrix"
            metrics.append(metric_row(key, "mcc", mcc, len(label_rows), "classification", direction, reason))
        group_summaries.append(
            {
                "assay_id": key[0],
                "model_id": key[1],
                "score_name": key[2],
                "aligned_rows": len(rows),
                "dms_rows": len(dms_rows),
                "label_rows": len(label_rows),
            }
        )

    write_tsv(run_dir / "metrics.tsv", metrics, METRIC_FIELDS)
    alignment_report = {
        "assay_rows": len(assays),
        "score_rows": len(scores),
        "aligned_score_rows": len(aligned),
        "excluded_score_rows": len(exclusions),
        "assay_validation_exclusions": assay_report["excluded_rows"],
        "score_validation_exclusions": score_report["excluded_rows"],
        "groups": group_summaries,
    }
    write_json(run_dir / "alignment_report.json", alignment_report)
    computed = sum(row["status"] == "computed" for row in metrics)
    status = "completed" if computed else "completed_without_computable_metrics"
    summary = {
        "status": status,
        "role": "benchmark-data-evaluation-substrate",
        "not_a_prediction_model": True,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "task": args.task,
        "classification_threshold": args.classification_threshold,
        "ndcg": {"k": args.ndcg_k, "relevance": args.ndcg_relevance},
        "alignment": alignment_report,
        "metrics_computed": computed,
        "metrics_not_computed": len(metrics) - computed,
        "artifacts": {
            "metrics": str((run_dir / "metrics.tsv").resolve()),
            "aligned_scores": str((run_dir / "aligned_scores.tsv").resolve()),
            "exclusions": str((run_dir / "exclusions.tsv").resolve()),
            "alignment_report": str((run_dir / "alignment_report.json").resolve()),
        },
        "limitations": [
            "Metrics are mutation-level within each assay/model/score group; no cross-assay aggregate is inferred.",
            "MCC is omitted unless an explicit oriented-score threshold is supplied.",
            "NDCG rank relevance is a local diagnostic and must be labeled separately from official ProteinGym leaderboard metrics.",
        ],
    }
    write_json(run_dir / "summary.json", summary)
    archive_path = None
    if args.archive_intermediates or args.cleanup_intermediates:
        archive_path = safe_cleanup(run_dir, intermediate, args.archive_intermediates)
        summary["intermediate_cleanup"] = {"removed": True, "archive": archive_path}
        write_json(run_dir / "summary.json", summary)
    log_lines.extend([f"status={status}", f"aligned={len(aligned)}", f"metrics_computed={computed}"])
    (logs_dir / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "tool": "protein-mutation-benchmark",
        "python": platform.python_version(),
        "command": command,
        "inputs": [
            {
                "role": "assay_data",
                "source": str(assay_path.resolve()),
                "raw_copy": str(copied_assay.resolve()),
                "sha256": file_sha256(copied_assay),
            },
            {
                "role": "scores",
                "source": str(score_path.resolve()),
                "raw_copy": str(copied_scores.resolve()),
                "sha256": file_sha256(copied_scores),
            },
        ],
        "artifacts": sorted(
            {
                "manifest.json",
                *(str(path.relative_to(run_dir)) for path in run_dir.rglob("*") if path.is_file()),
            }
        ),
    }
    write_json(run_dir / "manifest.json", manifest)
    print(f"{status}: {computed} metrics computed; outputs in {run_dir}")
    return 0 if computed else 3


if __name__ == "__main__":
    raise SystemExit(main())
