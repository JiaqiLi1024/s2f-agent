#!/usr/bin/env python3
"""Plan, execute, or import provenance-rich multi-model protein mutation scores."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MODELS = {
    "esm-1v": ("sequence", "sequence_plausibility", "masked_marginal_log_odds", "more_tolerated"),
    "esmc-300m": ("sequence", "sequence_plausibility", "masked_marginal_log_odds", "more_tolerated"),
    "msa-profile": ("sequence", "evolutionary_profile", "profile_log_odds", "more_tolerated"),
    "poet": ("sequence", "sequence_plausibility", "conditional_log_likelihood_ratio", "more_tolerated"),
    "alphamissense": ("sequence", "human_missense_prior", "alphamissense_score", "more_deleterious"),
    "saprot": ("structure", "structure_conditioned_likelihood", "masked_marginal_log_odds", "more_tolerated"),
    "thermompnn": ("structure", "stability", "predicted_ddg", "less_stable"),
    "proteinmpnn": ("structure", "structure_conditioned_likelihood", "conditional_log_likelihood_ratio", "more_tolerated"),
    "esm-if1": ("structure", "structure_conditioned_likelihood", "conditional_log_likelihood_ratio", "more_tolerated"),
}
MODEL_ALIASES = {
    "esm1v": "esm-1v",
    "esm_1v": "esm-1v",
    "esmc": "esmc-300m",
}
SCORE_COLUMNS = [
    "protein_id", "variant_id", "mutation_group", "mutation", "model_family", "model_id",
    "model_revision", "score_name", "effect_axis", "native_effect_axis", "raw_score", "score_unit",
    "higher_is", "native_higher_is", "status", "error", "source_path",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORE_COLUMNS, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in SCORE_COLUMNS})

def write_structure_mutation_table(path: Path, variants: list[dict[str, str]], chain: str) -> None:
    """Expand canonical grouped variants into one structure-adapter row per substitution."""
    fields = ["protein_id", "variant_id", "mutation_group", "mutation", "chain", "numbering"]
    rows: list[dict[str, str]] = []
    for variant in variants:
        for mutation in variant["mutation_group"].split(":"):
            rows.append({
                "protein_id": variant["protein_id"],
                "variant_id": variant["variant_id"],
                "mutation_group": variant["mutation_group"],
                "mutation": mutation,
                "chain": chain,
                "numbering": "sequence",
            })
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def shell_command(parts: list[str]) -> str:
    rendered = [str(part) for part in parts]
    if rendered and re.match(r"^[A-Za-z]:[\\/]", rendered[0]):
        drive = rendered[0][0].lower()
        suffix = rendered[0][2:].replace("\\", "/").lstrip("/")
        rendered[0] = f"/mnt/{drive}/{suffix}"
    return " ".join(shlex.quote(part) for part in rendered)


def unavailable_reason(model: str, args: argparse.Namespace) -> str:
    if model in {"msa-profile", "poet"}:
        if not args.msa:
            return "missing_required_msa"
        if not Path(args.msa).is_file():
            return "msa_not_found"
    if model == "poet":
        if not args.poet_repo:
            return "missing_required_poet_repo"
        if not (Path(args.poet_repo) / "scripts" / "score.py").is_file():
            return "poet_score_script_not_found"
    if model == "alphamissense":
        if not args.alphamissense_table:
            return "missing_precomputed_alphamissense_table"
        if not Path(args.alphamissense_table).is_file():
            return "alphamissense_table_not_found"
    if MODELS[model][0] == "structure":
        if not args.structure:
            return "missing_required_structure"
        if not Path(args.structure).is_file():
            return "structure_not_found"
        structure_error = getattr(args, "structure_validation_error", "")
        if structure_error:
            return structure_error
    return ""


def status_row(variant: dict[str, str], model: str, status: str, error: str = "") -> dict[str, object]:
    family, axis, score_name, higher_is = MODELS[model]
    return {
        "protein_id": variant["protein_id"],
        "variant_id": variant["variant_id"],
        "mutation_group": variant["mutation_group"],
        "mutation": variant["mutation_group"],
        "native_effect_axis": axis,
        "model_family": family,
        "model_id": model,
        "model_revision": "",
        "score_name": score_name,
        "effect_axis": axis,
        "raw_score": "",
        "score_unit": "",
        "higher_is": higher_is,
        "native_higher_is": higher_is,
        "status": status,
        "error": error,
        "source_path": "",
    }


def canonical_model_id(raw_model: str) -> str:
    token = raw_model.strip().lower()
    if token.startswith("esm-1v-ensemble-"):
        return "esm-1v"
    if token in {"biohub/esmc-300m", "esmc-300m"}:
        return "esmc-300m"
    return MODEL_ALIASES.get(token, "alphamissense" if token.startswith("alphamissense") else token)


def normalize_import(path: Path, success_status: str = "imported") -> list[dict[str, object]]:
    delimiter = "\t"
    with path.open(encoding="utf-8-sig") as handle:
        first = handle.readline()
        if "\t" not in first and "," in first:
            delimiter = ","
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=delimiter))
    required_identity = {"protein_id", "model_id"}
    if not rows or not required_identity.issubset(rows[0]) or not ({"variant_id", "mutation", "mutation_group"} & set(rows[0])):
        raise ValueError(f"import_schema_error:{path}")
    output: list[dict[str, object]] = []
    for row in rows:
        raw_model = row.get("model_id", "")
        lookup_model = canonical_model_id(raw_model)
        known = MODELS.get(lookup_model)
        model = lookup_model if known else raw_model
        native_axis = row.get("native_effect_axis", row.get("effect_axis", "backend_defined"))
        family, axis, score_name, higher_is = known if known else (
            row.get("model_family", "imported"),
            native_axis,
            row.get("score_name", "imported_score"),
            row.get("higher_is", "backend_documented"),
        )
        incoming_status = row.get("status", "").strip().lower()
        raw_value = row.get("raw_score", row.get("score", ""))
        if incoming_status in {"ok", "completed", "imported"} and raw_value != "":
            normalized_status = success_status
        elif incoming_status in {"planned", "unavailable", "failed", "excluded"}:
            normalized_status = incoming_status
        elif incoming_status == "invalid_input":
            normalized_status = "failed"
        else:
            normalized_status = success_status if raw_value != "" else "excluded"
        native_higher_is = row.get("native_higher_is", row.get("higher_is", higher_is))
        output.append({
            "protein_id": row.get("protein_id", ""),
            "variant_id": row.get("variant_id", row.get("mutation", row.get("mutation_group", ""))),
            "mutation": row.get("mutation", row.get("mutation_group", "")),
            "mutation_group": row.get("mutation_group", row.get("mutation", "")),
            "model_family": family if known else row.get("model_family", family),
            "model_id": model,
            "model_revision": row.get("model_revision", "") or (raw_model if raw_model != model else ""),
            "score_name": row.get("score_name", score_name),
            "effect_axis": axis,
            "native_effect_axis": native_axis,
            "raw_score": raw_value if normalized_status in {"completed", "imported"} else "",
            "score_unit": row.get("score_unit", ""),
            "higher_is": higher_is,
            "native_higher_is": native_higher_is,
            "status": normalized_status,
            "error": row.get("error", ""),
            "source_path": str(path),
        })
    return output


def validate_import_identity(rows: list[dict[str, object]], variants: list[dict[str, str]],
                             requested: list[str]) -> list[dict[str, object]]:
    expected = {
        (variant["protein_id"], variant["variant_id"], variant["mutation_group"])
        for variant in variants
    }
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for row in rows:
        model = str(row.get("model_id", ""))
        if model not in requested:
            raise ValueError(f"import_model_not_requested:{model}")
        identity = (
            str(row.get("protein_id", "")),
            str(row.get("variant_id", "")),
            str(row.get("mutation_group", "")),
        )
        if identity not in expected:
            raise ValueError(f"import_identity_mismatch:{'|'.join(identity)}")
        duplicate_key = identity + (
            str(row.get("mutation", "")), model, str(row.get("score_name", "")),
        )
        if duplicate_key in seen:
            raise ValueError(f"duplicate_import_score:{'|'.join(duplicate_key)}")
        seen.add(duplicate_key)
    return rows


def missing_import_rows(rows: list[dict[str, object]], variants: list[dict[str, str]],
                        requested: list[str]) -> list[dict[str, object]]:
    observed = {
        (str(row.get("protein_id", "")), str(row.get("variant_id", "")),
         str(row.get("mutation_group", "")), str(row.get("model_id", "")))
        for row in rows
    }
    return [
        status_row(variant, model, "excluded", "missing_imported_score")
        for variant in variants for model in requested
        if (variant["protein_id"], variant["variant_id"], variant["mutation_group"], model) not in observed
    ]


def find_component_scores(directory: Path) -> list[Path]:
    preferred = [directory / "scores.tsv", directory / "structure_mutation_scores.tsv"]
    if any(path.is_file() for path in preferred):
        return [path.resolve() for path in preferred if path.is_file()]
    candidates: list[Path] = []
    for pattern in ("*scores*.tsv", "*score*.tsv"):
        candidates.extend(directory.rglob(pattern))
    return sorted({path.resolve() for path in candidates if path.is_file()})


def run_component(command: list[str], log_path: Path) -> tuple[int, str]:
    proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log_path.write_text(proc.stdout, encoding="utf-8")
    return proc.returncode, proc.stdout


def safe_cleanup(output_dir: Path) -> None:
    output = output_dir.resolve()
    raw_target = output / "intermediate"
    if raw_target.is_symlink():
        raise ValueError("unsafe_intermediate_symlink")
    target = raw_target.resolve()
    if output in {Path("/").resolve(), Path.home().resolve()}:
        raise ValueError("unsafe_output_directory")
    if target != output / "intermediate" or target.parent != output or target.is_symlink():
        raise ValueError("unsafe_intermediate_directory")
    if target.exists():
        shutil.rmtree(target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--sequence")
    source.add_argument("--fasta")
    parser.add_argument("--protein-id", default="protein_1")
    parser.add_argument("--mutation", action="append", default=[])
    parser.add_argument("--mutations-file")
    parser.add_argument("--models", default="esm-1v,esmc-300m,msa-profile,saprot,thermompnn,poet,proteinmpnn,esm-if1,alphamissense")
    parser.add_argument("--structure")
    parser.add_argument("--chain", default="A", help="Structure chain passed to structure-aware adapters.")
    parser.add_argument("--min-structure-coverage", type=float, default=0.8)
    parser.add_argument("--min-structure-identity", type=float, default=0.9)
    parser.add_argument("--msa")
    parser.add_argument("--alphamissense-table")
    parser.add_argument("--poet-repo", help="Pinned OpenProteinAI/PoET checkout for execute mode.")
    parser.add_argument("--poet-python", default=sys.executable)
    parser.add_argument("--import-scores", action="append", default=[])
    parser.add_argument("--mode", choices=("plan", "execute", "import"), default="plan")
    parser.add_argument("--output-dir", required=True)
    lifecycle = parser.add_mutually_exclusive_group()
    lifecycle.add_argument("--archive-intermediates", action="store_true")
    lifecycle.add_argument("--cleanup-intermediates", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    requested = list(dict.fromkeys([
        MODEL_ALIASES.get(x.strip().lower(), x.strip().lower())
        for x in args.models.split(",") if x.strip()
    ]))
    unknown = sorted(set(requested) - set(MODELS))
    if unknown:
        print(json.dumps({"status": "invalid", "error": f"unknown_models:{','.join(unknown)}"}), file=sys.stderr)
        return 2
    if not (0.0 <= args.min_structure_coverage <= 1.0 and 0.0 <= args.min_structure_identity <= 1.0):
        print(json.dumps({"status": "invalid", "error": "structure_thresholds_must_be_between_0_and_1"}), file=sys.stderr)
        return 2
    for attribute in ("fasta", "mutations_file", "structure", "msa", "alphamissense_table", "poet_repo"):
        value = getattr(args, attribute, None)
        if value:
            setattr(args, attribute, str(Path(value).expanduser().resolve()))
    args.import_scores = [
        str(Path(item).expanduser().resolve())
        for item in args.import_scores
    ]
    output = Path(args.output_dir).expanduser().resolve()
    for subdir in ("inputs", "raw", "intermediate", "logs"):
        (output / subdir).mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[3]
    normalizer = Path(__file__).with_name("normalize_protein_mutations.py")
    normalize_cmd = [sys.executable, str(normalizer), "--output-dir", str(output / "inputs")]
    if args.sequence:
        normalize_cmd += ["--sequence", args.sequence, "--protein-id", args.protein_id]
    else:
        normalize_cmd += ["--fasta", args.fasta]
    for mutation in args.mutation:
        normalize_cmd += ["--mutation", mutation]
    if args.mutations_file:
        normalize_cmd += ["--mutations-file", args.mutations_file]
    normalize_proc = subprocess.run(normalize_cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    (output / "logs" / "normalization.log").write_text(normalize_proc.stdout + normalize_proc.stderr, encoding="utf-8")
    if normalize_proc.returncode != 0:
        print(normalize_proc.stderr, file=sys.stderr)
        return normalize_proc.returncode
    fasta_path = output / "inputs" / "normalized_sequences.fasta"
    mutations_path = output / "inputs" / "normalized_mutations.tsv"
    variants = read_tsv(mutations_path)
    structure_mutations_path = output / "intermediate" / "structure_mutations.tsv"
    if any(MODELS[model][0] == "structure" for model in requested):
        write_structure_mutation_table(structure_mutations_path, variants, args.chain)
    args.structure_validation_error = ""
    if (any(MODELS[model][0] == "structure" for model in requested)
            and args.structure and Path(args.structure).is_file()):
        validator = repo_root / "skills" / "protein-structure-mutation-effect" / "scripts" / "validate_structure_mutations.py"
        validation_dir = output / "intermediate" / "structure_validation"
        validation_cmd = [
            sys.executable, str(validator),
            "--fasta", str(fasta_path), "--structure", args.structure,
            "--chain", args.chain, "--mutations-file", str(structure_mutations_path),
            "--numbering", "sequence", "--output-dir", str(validation_dir),
        ]
        validation_proc = subprocess.run(
            validation_cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        (output / "logs" / "structure_validation.log").write_text(
            validation_proc.stdout, encoding="utf-8",
        )
        if validation_proc.returncode != 0:
            args.structure_validation_error = "structure_validation_failed"
        else:
            try:
                validation = json.loads((validation_dir / "validation.json").read_text(encoding="utf-8"))
                alignment = validation["alignment"]
                canonical_length = int(alignment["canonical_length"])
                coverage = float(alignment["mapped_positions"]) / canonical_length if canonical_length else 0.0
                identity = float(alignment["mapped_identity"])
                if coverage < args.min_structure_coverage:
                    args.structure_validation_error = "structure_mapping_insufficient_coverage"
                elif identity < args.min_structure_identity:
                    args.structure_validation_error = "structure_mapping_insufficient_identity"
            except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                args.structure_validation_error = "structure_validation_summary_invalid"
    commands = ["# Input normalization", shell_command(normalize_cmd)]
    score_rows: list[dict[str, object]] = []

    if args.mode == "import":
        if not args.import_scores:
            print(json.dumps({"status": "invalid", "error": "import_mode_requires_import_scores"}), file=sys.stderr)
            return 2
        try:
            for item in args.import_scores:
                score_rows.extend(normalize_import(Path(item), success_status="imported"))
            score_rows = validate_import_identity(score_rows, variants, requested)
            score_rows.extend(missing_import_rows(score_rows, variants, requested))
        except (OSError, ValueError, csv.Error) as exc:
            print(json.dumps({"status": "invalid", "error": str(exc)}), file=sys.stderr)
            return 2
        commands.append("# Imported existing score tables; no model command executed.")
    elif args.mode == "plan":
        for model in requested:
            reason = unavailable_reason(model, args)
            for variant in variants:
                score_rows.append(status_row(variant, model, "unavailable" if reason else "planned", reason))
        commands.append("# Plan mode: commands below are reproducibility plans and were not executed.")
    else:
        runnable = [model for model in requested if not unavailable_reason(model, args)]
        for model in requested:
            reason = unavailable_reason(model, args)
            if reason:
                score_rows.extend(status_row(variant, model, "unavailable", reason) for variant in variants)
        component_specs = [
            (
                "sequence",
                repo_root / "skills" / "protein-sequence-mutation-effect" / "scripts" / "run_sequence_mutation_effect.py",
                [model for model in runnable if MODELS[model][0] == "sequence"],
            ),
            (
                "structure",
                repo_root / "skills" / "protein-structure-mutation-effect" / "scripts" / "run_structure_mutation_effect.py",
                [model for model in runnable if MODELS[model][0] == "structure"],
            ),
        ]
        for family, runner, models in component_specs:
            if not models:
                continue
            component_out = output / "intermediate" / family
            command = [
                sys.executable, str(runner), "--fasta", str(fasta_path),
                "--mutations-file", str(structure_mutations_path if family == "structure" else mutations_path),
                "--models", ",".join(models),
                "--mode", "execute", "--output-dir", str(component_out),
            ]
            if family == "structure" and args.structure:
                command += ["--structure", str(Path(args.structure).expanduser().resolve()), "--chain", args.chain]
            if family == "sequence" and args.msa:
                command += ["--msa", args.msa]
            if family == "sequence" and args.alphamissense_table:
                command += ["--alphamissense-table", args.alphamissense_table]
            if family == "sequence" and "poet" in models:
                command += ["--poet-repo", args.poet_repo, "--poet-python", args.poet_python]
            commands += [f"# {family} component", shell_command(command)]
            if not runner.is_file():
                score_rows.extend(status_row(variant, model, "unavailable", "component_runner_not_found") for model in models for variant in variants)
                continue
            code, _ = run_component(command, output / "logs" / f"{family}.log")
            imported_before = len(score_rows)
            if code == 0:
                try:
                    component_rows: list[dict[str, object]] = []
                    for candidate in find_component_scores(component_out):
                        component_rows.extend(normalize_import(candidate, success_status="completed"))
                    score_rows.extend(validate_import_identity(component_rows, variants, models))
                except (OSError, ValueError, csv.Error) as exc:
                    with (output / "logs" / f"{family}.log").open("a", encoding="utf-8") as handle:
                        handle.write(f"\nroot_import_validation_error:{exc}\n")
            if len(score_rows) == imported_before:
                error = f"component_exit_{code}_without_importable_scores"
                score_rows.extend(status_row(variant, model, "failed", error) for model in models for variant in variants)

    if args.mode == "plan":
        sequence_models = [m for m in requested if MODELS[m][0] == "sequence" and not unavailable_reason(m, args)]
        structure_models = [m for m in requested if MODELS[m][0] == "structure" and not unavailable_reason(m, args)]
        if sequence_models:
            cmd = [
                sys.executable,
                str(repo_root / "skills" / "protein-sequence-mutation-effect" / "scripts" / "run_sequence_mutation_effect.py"),
                "--fasta", str(fasta_path), "--mutations-file", str(mutations_path),
                "--models", ",".join(sequence_models), "--mode", "execute",
                "--output-dir", str(output / "intermediate" / "sequence"),
            ]
            if args.msa:
                cmd += ["--msa", args.msa]
            if args.alphamissense_table:
                cmd += ["--alphamissense-table", args.alphamissense_table]
            if "poet" in sequence_models:
                cmd += ["--poet-repo", args.poet_repo, "--poet-python", args.poet_python]
            commands.append(shell_command(cmd))
        if structure_models:
            cmd = [
                sys.executable,
                str(repo_root / "skills" / "protein-structure-mutation-effect" / "scripts" / "run_structure_mutation_effect.py"),
                "--fasta", str(fasta_path), "--mutations-file", str(structure_mutations_path),
                "--structure", str(Path(args.structure).expanduser().resolve()), "--chain", args.chain,
                "--models", ",".join(structure_models), "--mode", "execute",
                "--output-dir", str(output / "intermediate" / "structure"),
            ]
            commands.append(shell_command(cmd))

    scores_path = output / "protein_mutation_scores.tsv"
    write_tsv(scores_path, score_rows)
    counts = Counter(str(row.get("status", "")) for row in score_rows)
    axes = Counter(str(row.get("effect_axis", "")) for row in score_rows)
    summary = {
        "status": "completed" if args.mode == "import" else "planned" if args.mode == "plan" else "completed_with_status_rows",
        "execution_mode": args.mode,
        "requested_models": requested,
        "variant_count": len(variants),
        "score_row_count": len(score_rows),
        "status_counts": dict(sorted(counts.items())),
        "effect_axis_counts": dict(sorted(axes.items())),
        "warnings": ["Raw scores from different effect axes were not averaged."],
        "artifacts": {
            "scores": str(scores_path),
            "mutations": str(mutations_path),
            "sequences": str(fasta_path),
        },
    }
    summary_path = output / "protein_mutation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    commands_path = output / "commands.sh"
    with commands_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("#!/usr/bin/env bash\nset -euo pipefail\n\n" + "\n".join(commands) + "\n")
    commands_path.chmod(0o755)
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "execution_mode": args.mode,
        "command_arguments": vars(args),
        "runtime": {
            "python_version": sys.version,
            "python_executable": sys.executable,
            "conda_environment": os.environ.get("CONDA_DEFAULT_ENV"),
        },
        "cwd": os.getcwd(),
        "requested_models": requested,
        "model_revisions": {
            str(row.get("model_id")): str(row.get("model_revision"))
            for row in score_rows
            if row.get("model_id") and row.get("model_revision")
        },
        "input_hashes": {
            str(fasta_path): sha256_file(fasta_path),
            str(mutations_path): sha256_file(mutations_path),
            **{
                str(Path(value)): sha256_file(Path(value))
                for value in [args.fasta, args.mutations_file, args.structure, args.msa,
                              args.alphamissense_table, *args.import_scores]
                if value and Path(value).is_file()
            },
        },
        "component_manifests": [
            str(path)
            for path in sorted((output / "intermediate").rglob("*manifest.json"))
        ],
        "artifacts": {
            "scores": str(scores_path),
            "summary": str(summary_path),
            "commands": str(commands_path),
        },
        "lifecycle": {"intermediates": "kept"},
        "secrets_recorded": False,
    }
    manifest_path = output / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.archive_intermediates:
        archive = output / "intermediates.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            handle.add(output / "intermediate", arcname="intermediate")
        with tarfile.open(archive, "r:gz") as handle:
            handle.getmembers()
        summary["artifacts"]["intermediate_archive"] = str(archive)
        manifest["artifacts"]["intermediate_archive"] = str(archive)
        manifest["lifecycle"]["intermediates"] = "archived_and_kept"
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif args.cleanup_intermediates:
        safe_cleanup(output)
        summary["intermediates_cleaned"] = True
        manifest["lifecycle"]["intermediates"] = "cleaned"
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
