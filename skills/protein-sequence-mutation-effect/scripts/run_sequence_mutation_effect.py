#!/usr/bin/env python3
"""Run or plan auditable protein sequence mutation-effect scoring."""
from __future__ import annotations

import argparse
import csv
import gzip
import importlib.metadata
import json
import math
import os
import re
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from itertools import chain

from mutation_io import (
    AA20,
    canonical_group,
    first_value,
    load_mutation_requests,
    open_text,
    parse_mutation_group,
    read_fasta,
    read_table,
    sha256_file,
    write_tsv,
)

MODELS = ("esm-1v", "esmc-300m", "msa-profile", "poet", "alphamissense")
ALIASES = {
    "esm1v": "esm-1v", "esm_1v": "esm-1v", "esm-c": "esmc-300m", "esmc": "esmc-300m",
    "esmc300m": "esmc-300m", "msa": "msa-profile", "msa_profile": "msa-profile",
    "alpha-missense": "alphamissense", "alpha_missense": "alphamissense",
}
NORM_FIELDS = ["protein_id", "variant_id", "mutation_group", "mutation_count", "positions", "mutated_sequence", "status", "error"]
SCORE_FIELDS = [
    "protein_id", "variant_id", "mutation_group", "model_id", "score_name", "effect_axis",
    "raw_score", "higher_is", "status", "error", "score_unit", "aggregation", "evidence_source",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasta", required=True, help="WT protein FASTA")
    parser.add_argument("--mutations-file", help="TSV/CSV with protein_id, variant_id, mutation_group")
    parser.add_argument("--mutation", action="append", default=[], help="Mutation group; repeatable")
    parser.add_argument("--mutations", help="Semicolon-delimited mutation groups")
    parser.add_argument("--protein-id", help="Default protein ID for command-line mutations")
    parser.add_argument("--models", required=True, help="Comma list: " + ",".join(MODELS))
    parser.add_argument("--mode", choices=("plan", "execute", "import"), required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--msa", help="Aligned FASTA/A3M for MSA profile or PoET")
    parser.add_argument("--msa-pseudocount", type=float, default=1.0)
    parser.add_argument("--alphamissense-table", help="Released AlphaMissense TSV/CSV[.gz]")
    parser.add_argument("--import-scores", help="Standardized TSV/CSV scores for requested models")
    parser.add_argument("--poet-scores", help="PoET .npy or table, used in import mode")
    parser.add_argument("--poet-repo", help="Clone of OpenProteinAI/PoET for native execution")
    parser.add_argument("--poet-python", default=sys.executable)
    parser.add_argument("--poet-batch-size", type=int, default=8)
    parser.add_argument("--esm1v-models", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--esmc-model-id", default="biohub/ESMC-300M")
    parser.add_argument("--esmc-model-revision", default="a59b831785f907e96e6a246b1d142bfb76df31ee")
    parser.add_argument("--device", default="auto", help="auto, cpu, cuda, cuda:0, or mps")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--hf-token-env", default="HF_TOKEN")
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--archive-intermediates", action="store_true")
    parser.add_argument("--cleanup-intermediates", action="store_true")
    return parser


def score_row(request: dict[str, str], model: str, *, score_name: str, effect_axis: str,
              raw_score: Any = "", higher_is: str, status: str, error: str = "",
              score_unit: str = "", aggregation: str = "", evidence_source: str = "") -> dict[str, Any]:
    return {
        "protein_id": request["protein_id"], "variant_id": request["variant_id"],
        "mutation_group": request["mutation_group"], "model_id": model, "score_name": score_name,
        "effect_axis": effect_axis, "raw_score": raw_score, "higher_is": higher_is, "status": status,
        "error": error, "score_unit": score_unit, "aggregation": aggregation,
        "evidence_source": evidence_source,
    }


def status_rows(requests: list[dict[str, str]], model: str, status: str, error: str) -> list[dict[str, Any]]:
    meta = model_metadata(model)
    return [score_row(r, model, status=("invalid_input" if r["status"] != "valid" else status),
                      error=(r["error"] if r["status"] != "valid" else error), **meta) for r in requests]


def model_metadata(model: str) -> dict[str, str]:
    if model in ("esm-1v", "esmc-300m"):
        return {"score_name": "masked_marginal_log_odds", "effect_axis": "sequence_plausibility",
                "higher_is": "more_sequence_plausible", "score_unit": "natural_log_odds",
                "aggregation": "sum_of_independent_single-site_WT_context_scores"}
    if model == "msa-profile":
        return {"score_name": "msa_profile_log_odds", "effect_axis": "evolutionary_preference",
                "higher_is": "more_evolutionarily_preferred", "score_unit": "natural_log_odds",
                "aggregation": "sum_of_independent_column_log_odds"}
    if model == "poet":
        return {"score_name": "poet_native_score", "effect_axis": "family_conditioned_sequence_fitness",
                "higher_is": "more_fit", "score_unit": "model_native",
                "aggregation": "native_full_variant_score"}
    return {"score_name": "am_pathogenicity", "effect_axis": "pathogenicity",
            "higher_is": "more_pathogenic", "score_unit": "probability_like_0_to_1",
            "aggregation": "single_substitution_lookup"}


def requested_models(text: str) -> list[str]:
    values = []
    for token in text.split(","):
        name = token.strip().lower()
        name = ALIASES.get(name, name)
        if name not in MODELS:
            raise ValueError(f"unknown model {token!r}; choose from {','.join(MODELS)}")
        if name not in values:
            values.append(name)
    if not values:
        raise ValueError("--models is empty")
    return values


def select_device(requested: str, torch: Any) -> str:
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def score_msa(requests: list[dict[str, str]], fasta: dict[str, str], msa_path: str | None,
              pseudocount: float) -> list[dict[str, Any]]:
    if not msa_path:
        return status_rows(requests, "msa-profile", "unavailable", "--msa is required")
    if pseudocount <= 0:
        return status_rows(requests, "msa-profile", "failed", "--msa-pseudocount must be > 0")
    try:
        msa = read_fasta(msa_path, aligned=True)
        lengths = {len(seq) for seq in msa.values()}
        if len(lengths) != 1:
            raise ValueError("MSA records have unequal aligned lengths after removing A3M insertions")
        columns = list(zip(*msa.values()))
        profiles = [Counter(aa for aa in col if aa in AA20) for col in columns]
        query_alignment: dict[str, str] = {}
        for protein_id, sequence in fasta.items():
            matches = [(key, aligned) for key, aligned in msa.items() if aligned.replace("-", "").replace(".", "") == sequence]
            exact = [(key, aligned) for key, aligned in matches if key == protein_id]
            selected = exact or matches
            if len(selected) != 1:
                raise ValueError(f"expected one MSA query matching {protein_id}; found {len(selected)}")
            query_alignment[protein_id] = selected[0][1]
        rows = []
        for request in requests:
            if request["status"] != "valid":
                rows.extend(status_rows([request], "msa-profile", "unavailable", ""))
                continue
            aligned = query_alignment[request["protein_id"]]
            residue_to_column: dict[int, int] = {}
            pos = 0
            for col_index, aa in enumerate(aligned):
                if aa not in ("-", "."):
                    pos += 1
                    residue_to_column[pos] = col_index
            total = 0.0
            for ref, position, alt in parse_mutation_group(request["mutation_group"]):
                col = residue_to_column[position]
                counts = profiles[col]
                denominator = sum(counts.values()) + 20.0 * pseudocount
                ref_p = (counts[ref] + pseudocount) / denominator
                alt_p = (counts[alt] + pseudocount) / denominator
                total += math.log(alt_p) - math.log(ref_p)
            meta = model_metadata("msa-profile")
            rows.append(score_row(request, "msa-profile", raw_score=f"{total:.12g}", status="ok",
                                  evidence_source=f"{Path(msa_path).name};depth={len(msa)};pseudocount={pseudocount}", **meta))
        return rows
    except Exception as exc:
        return status_rows(requests, "msa-profile", "failed", str(exc))


def score_esm1v(requests: list[dict[str, str]], fasta: dict[str, str], device_request: str,
                 ensemble_size: int) -> list[dict[str, Any]]:
    try:
        import torch
        import esm
        device = select_device(device_request, torch)
        valid = [r for r in requests if r["status"] == "valid"]
        totals = {r["variant_id"]: 0.0 for r in valid}
        needed = {(r["protein_id"], pos) for r in valid for _, pos, _ in parse_mutation_group(r["mutation_group"])}
        for member in range(1, ensemble_size + 1):
            loader = getattr(esm.pretrained, f"esm1v_t33_650M_UR90S_{member}")
            model, alphabet = loader()
            model = model.eval().to(device)
            converter = alphabet.get_batch_converter()
            cache: dict[tuple[str, int], dict[str, float]] = {}
            for protein_id in sorted({key for key, _ in needed}):
                _, _, tokens = converter([(protein_id, fasta[protein_id])])
                tokens = tokens.to(device)
                for key, pos in sorted(k for k in needed if k[0] == protein_id):
                    masked_tokens = tokens.clone()
                    masked_tokens[0, pos] = alphabet.mask_idx
                    with torch.inference_mode():
                        masked_logits = model(masked_tokens, repr_layers=[], return_contacts=False)["logits"][0, pos]
                        masked_log_probs = torch.log_softmax(masked_logits, dim=-1)
                    cache[(key, pos)] = {aa: float(masked_log_probs[alphabet.get_idx(aa)].item()) for aa in AA20}
            for request in valid:
                value = 0.0
                for ref, pos, alt in parse_mutation_group(request["mutation_group"]):
                    value += cache[(request["protein_id"], pos)][alt] - cache[(request["protein_id"], pos)][ref]
                totals[request["variant_id"]] += value / ensemble_size
            del model
            if device.startswith("cuda"):
                torch.cuda.empty_cache()
        rows = []
        for request in requests:
            if request["status"] != "valid":
                rows.extend(status_rows([request], "esm-1v", "unavailable", ""))
            else:
                meta = model_metadata("esm-1v")
                rows.append(score_row(request, f"esm-1v-ensemble-{ensemble_size}", raw_score=f"{totals[request['variant_id']]:.12g}",
                                      status="ok", evidence_source=f"facebookresearch/esm;members=1-{ensemble_size};device={device}", **meta))
        return rows
    except Exception as exc:
        return status_rows(requests, "esm-1v", "unavailable", f"ESM-1v adapter unavailable: {exc}")


def _single_token_id(tokenizer: Any, aa: str) -> int:
    encoded = tokenizer(aa, add_special_tokens=False)["input_ids"]
    if encoded and isinstance(encoded[0], list):
        encoded = encoded[0]
    if len(encoded) != 1:
        raise ValueError(f"tokenizer does not encode {aa} as one token")
    return int(encoded[0])


def score_esmc(requests: list[dict[str, str]], fasta: dict[str, str], args: argparse.Namespace) -> list[dict[str, Any]]:
    try:
        import torch
        try:
            import esm  # noqa: F401 - registers Biohub ESMC classes with Transformers
        except Exception:
            pass
        from transformers import AutoModelForMaskedLM, AutoTokenizer
        device = select_device(args.device, torch)
        token = os.environ.get(args.hf_token_env) or None
        kwargs = {"local_files_only": args.local_files_only, "trust_remote_code": args.trust_remote_code, "revision": args.esmc_model_revision}
        if token:
            kwargs["token"] = token
        tokenizer = AutoTokenizer.from_pretrained(args.esmc_model_id, **kwargs)
        model = AutoModelForMaskedLM.from_pretrained(args.esmc_model_id, **kwargs).eval().to(device)
        if tokenizer.mask_token is None or tokenizer.mask_token_id is None:
            raise ValueError("ESMC tokenizer has no mask token")
        needed = {(r["protein_id"], pos) for r in requests if r["status"] == "valid" for _, pos, _ in parse_mutation_group(r["mutation_group"])}
        cache: dict[tuple[str, int], dict[str, float]] = {}
        aa_ids = {aa: _single_token_id(tokenizer, aa) for aa in AA20}
        for protein_id, pos in sorted(needed):
            sequence = fasta[protein_id]
            masked = sequence[:pos - 1] + tokenizer.mask_token + sequence[pos:]
            inputs = tokenizer(masked, return_tensors="pt")
            mask_positions = (inputs["input_ids"][0] == tokenizer.mask_token_id).nonzero(as_tuple=False).flatten()
            if len(mask_positions) != 1:
                raise ValueError(f"could not locate one mask token for {protein_id}:{pos}")
            inputs = {key: value.to(device) for key, value in inputs.items()}
            with torch.inference_mode():
                logits = model(**inputs).logits[0, int(mask_positions[0])]
                lp = torch.log_softmax(logits, dim=-1)
            cache[(protein_id, pos)] = {aa: float(lp[token_id].item()) for aa, token_id in aa_ids.items()}
        rows = []
        for request in requests:
            if request["status"] != "valid":
                rows.extend(status_rows([request], "esmc-300m", "unavailable", ""))
                continue
            total = sum(cache[(request["protein_id"], pos)][alt] - cache[(request["protein_id"], pos)][ref]
                        for ref, pos, alt in parse_mutation_group(request["mutation_group"]))
            meta = model_metadata("esmc-300m")
            rows.append(score_row(request, args.esmc_model_id, raw_score=f"{total:.12g}", status="ok",
                                  evidence_source=f"huggingface:{args.esmc_model_id}@{args.esmc_model_revision};device={device}", **meta))
        return rows
    except Exception as exc:
        return status_rows(requests, "esmc-300m", "unavailable", f"ESMC adapter unavailable: {exc}")


def _table_reader(path: str) -> Iterable[dict[str, str]]:
    with open_text(path) as handle:
        header = ""
        for line in handle:
            if line.strip() and not line.startswith("##"):
                header = line.lstrip("#")
                break
        if not header:
            return
        delimiter = "," if str(path).lower().endswith((".csv", ".csv.gz")) else "\t"
        yield from csv.DictReader(chain([header], handle), delimiter=delimiter)


def score_alphamissense(requests: list[dict[str, str]], table: str | None) -> list[dict[str, Any]]:
    if not table:
        return status_rows(requests, "alphamissense", "unavailable", "--alphamissense-table is required; trained weights are not released")
    valid_single = [r for r in requests if r["status"] == "valid" and len(parse_mutation_group(r["mutation_group"])) == 1]
    found: dict[str, list[tuple[str, str]]] = {r["variant_id"]: [] for r in valid_single}
    targets: dict[tuple[str, str], list[str]] = {}
    mutation_only: dict[str, list[str]] = {}
    for request in valid_single:
        ids = {request["protein_id"], *request["protein_id"].split("|")}
        for protein_id in ids:
            targets.setdefault((protein_id, request["mutation_group"]), []).append(request["variant_id"])
        mutation_only.setdefault(request["mutation_group"], []).append(request["variant_id"])
    try:
        for row in _table_reader(table):
            protein = first_value(row, ("uniprot_id", "protein_id", "uniprot", "protein"))
            variant = first_value(row, ("protein_variant", "mutation_group", "mutation", "mutant", "variant"))
            score = first_value(row, ("am_pathogenicity", "pathogenicity", "alphamissense_score", "score"))
            classification = first_value(row, ("am_class", "classification", "class"))
            if not variant or not score:
                continue
            try:
                variant = canonical_group(parse_mutation_group(variant))
            except ValueError:
                continue
            ids = targets.get((protein, variant), []) if protein else (mutation_only.get(variant, []) if len(mutation_only.get(variant, [])) == 1 else [])
            for variant_id in ids:
                found[variant_id].append((score, classification))
        rows = []
        for request in requests:
            if request["status"] != "valid":
                rows.extend(status_rows([request], "alphamissense", "unavailable", ""))
            elif len(parse_mutation_group(request["mutation_group"])) != 1:
                rows.extend(status_rows([request], "alphamissense", "unavailable", "AlphaMissense lookup supports single substitutions only"))
            elif len(found.get(request["variant_id"], [])) == 1:
                score, classification = found[request["variant_id"]][0]
                value = float(score)
                meta = model_metadata("alphamissense")
                rows.append(score_row(request, "AlphaMissense-v2023", raw_score=f"{value:.12g}", status="ok",
                                      evidence_source=f"{Path(table).name};class={classification or 'not_provided'}", **meta))
            elif not found.get(request["variant_id"]):
                rows.extend(status_rows([request], "alphamissense", "not_found", "no unambiguous protein+variant match in released table"))
            else:
                rows.extend(status_rows([request], "alphamissense", "failed", "multiple matching AlphaMissense rows"))
        return rows
    except Exception as exc:
        return status_rows(requests, "alphamissense", "failed", str(exc))


def _import_native_scores(requests: list[dict[str, str]], path: str, model: str) -> list[dict[str, Any]]:
    try:
        if path.lower().endswith(".npy"):
            import numpy as np
            values = np.load(path)
            if values.ndim != 1 or len(values) != len(requests):
                raise ValueError(f"npy must be a 1-D array with {len(requests)} entries in normalized input order")
            mapped = {request["variant_id"]: str(float(value)) for request, value in zip(requests, values)}
        else:
            rows = read_table(path)
            mapped = {}
            for row in rows:
                variant_id = first_value(row, ("variant_id", "id"))
                group = first_value(row, ("mutation_group", "mutant", "mutation", "protein_variant"))
                score = first_value(row, ("raw_score", "score", "model_score", "poet_score"))
                key = variant_id or group
                if key and score:
                    mapped[key] = score
        out = []
        meta = model_metadata(model)
        for request in requests:
            key = request["variant_id"] if request["variant_id"] in mapped else request["mutation_group"]
            if request["status"] != "valid":
                out.extend(status_rows([request], model, "unavailable", ""))
            elif key in mapped:
                out.append(score_row(request, model, raw_score=f"{float(mapped[key]):.12g}", status="ok",
                                     evidence_source=f"import:{Path(path).name}", **meta))
            else:
                out.extend(status_rows([request], model, "not_found", "no imported score matching variant_id or mutation_group"))
        return out
    except Exception as exc:
        return status_rows(requests, model, "failed", f"score import failed: {exc}")


def bash_command(parts: list[str]) -> str:
    rendered = [str(part) for part in parts]
    if rendered and re.match(r"^[A-Za-z]:[\\/]", rendered[0]):
        drive = rendered[0][0].lower()
        suffix = rendered[0][2:].replace("\\", "/").lstrip("/")
        rendered[0] = f"/mnt/{drive}/{suffix}"
    return shlex.join(rendered)


def score_poet(requests: list[dict[str, str]], args: argparse.Namespace, raw_dir: Path, commands: list[str]) -> list[dict[str, Any]]:
    if args.mode == "import":
        if not args.poet_scores and not args.import_scores:
            return status_rows(requests, "poet", "unavailable", "--poet-scores or --import-scores is required in import mode")
        return _import_native_scores(requests, args.poet_scores or args.import_scores, "poet")
    if not args.msa:
        return status_rows(requests, "poet", "unavailable", "--msa is required")
    if not args.poet_repo:
        return status_rows(requests, "poet", "unavailable", "--poet-repo is required for execute mode")
    if len({r["protein_id"] for r in requests if r["status"] == "valid"}) > 1:
        return status_rows(requests, "poet", "unavailable", "one PoET execution accepts variants from one protein family")
    score_script = Path(args.poet_repo).resolve() / "scripts" / "score.py"
    if not score_script.is_file():
        return status_rows(requests, "poet", "unavailable", f"PoET score script not found: {score_script}")
    variants_path = raw_dir / "poet_variants.fasta"
    with variants_path.open("w", encoding="utf-8") as handle:
        for request in requests:
            if request["status"] == "valid":
                handle.write(f">{request['variant_id']}\n{request['mutated_sequence']}\n")
    output_path = raw_dir / "poet_scores.npy"
    command = [args.poet_python, str(score_script), "--msa_a3m_path", str(Path(args.msa).resolve()),
               "--variants_fasta_path", str(variants_path.resolve()), "--output_npy_path", str(output_path.resolve()),
               "--batch_size", str(args.poet_batch_size)]
    commands.append(bash_command(command))
    try:
        completed = subprocess.run(command, cwd=str(Path(args.poet_repo).resolve()), capture_output=True, text=True, check=False)
        (raw_dir / "poet.stdout.log").write_text(completed.stdout, encoding="utf-8")
        (raw_dir / "poet.stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"PoET exited {completed.returncode}; see raw/poet.stderr.log")
        valid = [r for r in requests if r["status"] == "valid"]
        imported = _import_native_scores(valid, str(output_path), "poet")
        invalid = [r for r in requests if r["status"] != "valid"]
        return imported + status_rows(invalid, "poet", "unavailable", "")
    except Exception as exc:
        return status_rows(requests, "poet", "failed", str(exc))


def generic_import(requests: list[dict[str, str]], path: str, model: str) -> list[dict[str, Any]]:
    return _import_native_scores(requests, path, model)


def planned_command(args: argparse.Namespace, model: str) -> str:
    script = Path(__file__).resolve()
    parts = [sys.executable, str(script), "--fasta", str(Path(args.fasta).resolve()), "--models", model,
             "--mode", "execute", "--output-dir", f"<OUTPUT_DIR>/{model}"]
    if args.mutations_file:
        parts.extend(["--mutations-file", str(Path(args.mutations_file).resolve())])
    if args.msa:
        parts.extend(["--msa", str(Path(args.msa).resolve())])
    if args.alphamissense_table:
        parts.extend(["--alphamissense-table", str(Path(args.alphamissense_table).resolve())])
    if args.poet_repo:
        parts.extend(["--poet-repo", str(Path(args.poet_repo).resolve())])
    if model == "esmc-300m":
        parts.extend(["--esmc-model-id", args.esmc_model_id, "--esmc-model-revision", args.esmc_model_revision])
    return bash_command(parts)


def package_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for name in ("torch", "transformers", "fair-esm", "esm", "numpy"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def archive_and_cleanup(output_dir: Path, cleanup: bool) -> str:
    archive = output_dir / "intermediates.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for name in ("raw", "intermediate"):
            target = output_dir / name
            if target.is_dir():
                bundle.add(target, arcname=name)
    if cleanup:
        # Resolve and prove both targets are direct children of this run before removal.
        root = output_dir.resolve()
        for name in ("raw", "intermediate"):
            raw_target = output_dir / name
            if raw_target.is_symlink():
                raise RuntimeError(f"refusing cleanup symlink: {raw_target}")
            target = raw_target.resolve()
            if target.parent != root or target.name not in {"raw", "intermediate"}:
                raise RuntimeError(f"refusing unsafe cleanup target: {target}")
            if target.is_dir():
                shutil.rmtree(target)
    return str(archive)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.cleanup_intermediates and not args.archive_intermediates:
        parser.error("--cleanup-intermediates requires --archive-intermediates")
    try:
        models = requested_models(args.models)
        fasta = read_fasta(args.fasta)
        cli_mutations = list(args.mutation)
        if args.mutations:
            cli_mutations.extend(item for item in args.mutations.split(";") if item.strip())
        requests = load_mutation_requests(fasta, args.mutations_file, cli_mutations, args.protein_id)
    except Exception as exc:
        parser.error(str(exc))
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    intermediate_dir = output_dir / "intermediate"
    log_dir = output_dir / "logs"
    raw_dir.mkdir(exist_ok=True)
    intermediate_dir.mkdir(exist_ok=True)
    log_dir.mkdir(exist_ok=True)
    normalized_path = output_dir / "normalized_mutations.tsv"
    write_tsv(normalized_path, requests, NORM_FIELDS)
    commands: list[str] = []
    scores: list[dict[str, Any]] = []
    started = time.time()
    for model in models:
        if args.mode == "plan":
            commands.append(planned_command(args, model))
            scores.extend(status_rows(requests, model, "planned", "execution not requested"))
            continue
        if args.mode == "import" and args.import_scores and model not in ("alphamissense", "poet"):
            scores.extend(generic_import(requests, args.import_scores, model))
        elif model == "msa-profile":
            scores.extend(score_msa(requests, fasta, args.msa, args.msa_pseudocount))
        elif model == "alphamissense":
            scores.extend(score_alphamissense(requests, args.alphamissense_table))
        elif model == "poet":
            scores.extend(score_poet(requests, args, raw_dir, commands))
        elif args.mode == "import":
            scores.extend(status_rows(requests, model, "unavailable", "--import-scores is required for this model in import mode"))
        elif model == "esm-1v":
            scores.extend(score_esm1v(requests, fasta, args.device, args.esm1v_models))
        elif model == "esmc-300m":
            scores.extend(score_esmc(requests, fasta, args))
    scores_path = output_dir / "scores.tsv"
    write_tsv(scores_path, scores, SCORE_FIELDS)
    commands_path = output_dir / "commands.sh"
    with commands_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("#!/usr/bin/env bash\nset -euo pipefail\n" + "\n".join(commands) + ("\n" if commands else ""))
    commands_path.chmod(0o755)
    counts = Counter(str(row["status"]) for row in scores)
    summary = {
        "schema_version": 1, "task": "protein-sequence-mutation-effect", "mode": args.mode,
        "models": models, "input_records": len(requests), "valid_input_records": sum(r["status"] == "valid" for r in requests),
        "score_rows": len(scores), "status_counts": dict(sorted(counts.items())),
        "coordinate_system": "one-based-protein", "score_table": str(scores_path),
        "normalized_mutations": str(normalized_path), "duration_seconds": round(time.time() - started, 3),
        "software_versions": package_versions(),
        "warnings": ["Model-native axes are not directly comparable.", "This output is not a clinical diagnosis."],
    }
    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log_path = log_dir / "run.log"
    log_path.write_text(f"mode={args.mode}\nmodels={','.join(models)}\nstatus_counts={json.dumps(dict(counts), sort_keys=True)}\n", encoding="utf-8")
    archive_path = ""
    if args.archive_intermediates:
        archive_path = archive_and_cleanup(output_dir, args.cleanup_intermediates)
    inputs = [Path(args.fasta)]
    for candidate in (args.mutations_file, args.msa, args.alphamissense_table, args.import_scores, args.poet_scores):
        if candidate and Path(candidate).is_file():
            inputs.append(Path(candidate))
    manifest = {
        "schema_version": 1,
        "inputs": [{"path": str(path.resolve()), "sha256": sha256_file(path), "size_bytes": path.stat().st_size} for path in inputs],
        "artifacts": [], "archive": archive_path,
        "cleanup_performed": bool(args.cleanup_intermediates),
    }
    for path in (normalized_path, scores_path, summary_path, commands_path, log_path):
        if path.is_file():
            manifest["artifacts"].append({"path": str(path.relative_to(output_dir)), "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    if archive_path:
        path = Path(archive_path)
        manifest["artifacts"].append({"path": path.name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), "status_counts": dict(counts)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
