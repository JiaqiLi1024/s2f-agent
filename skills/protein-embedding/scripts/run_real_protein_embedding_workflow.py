#!/usr/bin/env python3
"""Extract standardized protein language model embeddings.

The dry-run path validates inputs and resolves output metadata without importing
heavy ML dependencies or downloading model weights.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
AMBIGUOUS_AA = set("BXZJ")
RARE_AA = set("UO")
UNKNOWN_AA = set("X")
T5_REPLACE_RE = re.compile(r"[UZOB]", flags=re.IGNORECASE)

DEFAULT_MODELS = {
    "esm2": "facebook/esm2_t12_35M_UR50D",
    "esmc": "biohub/ESMC-300M",
    "prott5": "Rostlab/prot_t5_xl_uniref50",
    "ankh": "ElnaggarLab/ankh-base",
    "saprot": "westlake-repl/SaProt_650M_AF2",
}

DEFAULT_FORGE_MODELS = {
    "esmc": "esmc-300m-2024-12",
}


@dataclass
class ProteinRecord:
    protein_id: str
    sequence: str
    description: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract per-protein and/or per-residue PLM embeddings."
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--fasta", help="Input FASTA file")
    input_group.add_argument("--sequence", help="Single amino-acid sequence")
    input_group.add_argument("--uniprot", help="UniProt accession to fetch")
    parser.add_argument("--protein-id", default=None, help="ID for --sequence or --uniprot")
    parser.add_argument(
        "--model-family",
        choices=sorted(DEFAULT_MODELS),
        default="esm2",
        help="Protein language model family.",
    )
    parser.add_argument("--model-id", default=None, help="Hugging Face model id or local path")
    parser.add_argument(
        "--backend",
        choices=["hf-transformers", "biohub-forge"],
        default="hf-transformers",
        help="Embedding backend. Use biohub-forge only for ESMC SDK/API workflows.",
    )
    parser.add_argument(
        "--representation",
        choices=["hidden-state", "sae-feature"],
        default="hidden-state",
        help="Dense transformer hidden states or ESMC SAE feature activations.",
    )
    parser.add_argument(
        "--layer",
        default="last",
        help="Hidden-state layer: last, all, or comma-separated integer indices. Index 0 is the embedding layer for backends that expose it.",
    )
    parser.add_argument(
        "--embedding-type",
        choices=["per-protein", "per-residue", "both"],
        default="per-protein",
    )
    parser.add_argument(
        "--pooling",
        choices=["mean", "cls", "bos", "first"],
        default="mean",
        help="Pooling for per-protein embeddings.",
    )
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=None, help="Tokenizer max_length")
    parser.add_argument("--allow-ambiguous-aa", action="store_true")
    parser.add_argument("--allow-rare-aa", action="store_true")
    parser.add_argument(
        "--replace-rare-aa",
        action="store_true",
        help="Replace U/Z/O/B with X for T5-style models before tokenization.",
    )
    parser.add_argument(
        "--saprot-input-mode",
        choices=["aa-only", "sa-token"],
        default="aa-only",
        help="Label SaProt input as ordinary AA-only sequence or structure-aware AA+3Di tokens.",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda", "mps"],
        default="auto",
        help="Execution device.",
    )
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--biohub-url", default="https://biohub.ai", help="Biohub Forge URL")
    parser.add_argument(
        "--biohub-token-env",
        default="BIOHUB_API_TOKEN",
        help="Environment variable containing the Biohub token; falls back to ESM_API_KEY.",
    )
    parser.add_argument(
        "--sae-model-name",
        default=None,
        help="ESMC SAE model name, for example esmc-6b-2024-12-sae-layer60-k64-codebook16384.",
    )
    parser.add_argument(
        "--sae-normalize-features",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Normalize SAE features when supported by the requested SAE model.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", default="output/protein-embedding")
    parser.add_argument("--output-prefix", default="")
    parser.add_argument("--timeout-sec", type=int, default=30)
    return parser.parse_args()


def parse_fasta(path: Path) -> list[ProteinRecord]:
    records: list[ProteinRecord] = []
    current_id: str | None = None
    current_desc = ""
    chunks: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_id is not None:
                records.append(ProteinRecord(current_id, "".join(chunks), current_desc))
            header = line[1:].strip()
            if not header:
                raise ValueError("FASTA header is empty")
            parts = header.split(None, 1)
            current_id = parts[0]
            current_desc = parts[1] if len(parts) > 1 else ""
            chunks = []
        else:
            if current_id is None:
                raise ValueError("FASTA sequence encountered before first header")
            chunks.append(line)

    if current_id is not None:
        records.append(ProteinRecord(current_id, "".join(chunks), current_desc))

    if not records:
        raise ValueError(f"No FASTA records found: {path}")
    return records


def fetch_uniprot_sequence(accession: str, timeout_sec: int) -> ProteinRecord:
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.fasta"
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as response:
            text = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to fetch UniProt FASTA for {accession}: {exc}") from exc

    tmp = Path("/tmp") / f"{accession}.fasta"
    tmp.write_text(text, encoding="utf-8")
    records = parse_fasta(tmp)
    record = records[0]
    return ProteinRecord(accession, record.sequence, record.description)


def normalize_plain_sequence(raw: str) -> str:
    return re.sub(r"\s+", "", raw).upper()


def validate_records(
    records: Iterable[ProteinRecord],
    *,
    allow_ambiguous: bool,
    allow_rare: bool,
    saprot_mode: str,
    model_family: str,
) -> tuple[list[ProteinRecord], list[str]]:
    normalized: list[ProteinRecord] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for record in records:
        if not record.protein_id:
            raise ValueError("Protein ID cannot be empty")
        if record.protein_id in seen:
            raise ValueError(f"Duplicate protein ID: {record.protein_id}")
        seen.add(record.protein_id)

        seq = record.sequence if model_family == "saprot" and saprot_mode == "sa-token" else normalize_plain_sequence(record.sequence)
        if not seq:
            raise ValueError(f"{record.protein_id}: sequence is empty")

        if model_family == "saprot" and saprot_mode == "sa-token":
            invalid = sorted(set(seq) - set("ACDEFGHIKLMNPQRSTVWYUOXBZJ#abcdefghijklmnopqrstuvwxyz"))
            if invalid:
                raise ValueError(
                    f"{record.protein_id}: invalid SaProt token characters: {''.join(invalid)}"
                )
        else:
            invalid = sorted(set(seq) - CANONICAL_AA - AMBIGUOUS_AA - RARE_AA - UNKNOWN_AA)
            if invalid:
                raise ValueError(f"{record.protein_id}: invalid amino-acid characters: {''.join(invalid)}")
            ambiguous = sorted((set(seq) & AMBIGUOUS_AA) - UNKNOWN_AA)
            rare = sorted(set(seq) & RARE_AA)
            if ambiguous and not allow_ambiguous:
                raise ValueError(
                    f"{record.protein_id}: ambiguous residues require --allow-ambiguous-aa: {''.join(ambiguous)}"
                )
            if rare and not allow_rare:
                raise ValueError(
                    f"{record.protein_id}: rare residues require --allow-rare-aa or --replace-rare-aa: {''.join(rare)}"
                )
            if "X" in seq:
                warnings.append(f"{record.protein_id}: contains X unknown residues")

        normalized.append(ProteinRecord(record.protein_id, seq, record.description))

    return normalized, warnings


def safe_key(raw: str) -> str:
    key = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw.strip())
    return key or "protein"


def preprocess_for_model(seq: str, model_family: str, replace_rare: bool) -> str:
    if model_family in {"prott5", "ankh"}:
        if replace_rare:
            seq = T5_REPLACE_RE.sub("X", seq)
        return " ".join(seq)
    return seq


def choose_device(raw: str):
    import torch

    if raw == "cpu":
        return torch.device("cpu")
    if raw == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
        return torch.device("cuda")
    if raw == "mps":
        if not getattr(torch.backends, "mps", None) or not torch.backends.mps.is_available():
            raise RuntimeError("MPS requested but torch.backends.mps.is_available() is false")
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_model_and_tokenizer(model_family: str, model_id: str, trust_remote_code: bool, local_files_only: bool):
    if model_family in {"prott5", "ankh"}:
        from transformers import AutoTokenizer, T5EncoderModel

        tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            do_lower_case=False,
            local_files_only=local_files_only,
        )
        model = T5EncoderModel.from_pretrained(
            model_id,
            local_files_only=local_files_only,
        )
        return tokenizer, model

    if model_family == "saprot":
        from transformers import EsmForMaskedLM, EsmTokenizer

        tokenizer = EsmTokenizer.from_pretrained(model_id, local_files_only=local_files_only)
        model = EsmForMaskedLM.from_pretrained(model_id, local_files_only=local_files_only)
        return tokenizer, model

    from transformers import AutoModelForMaskedLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        trust_remote_code=trust_remote_code,
        local_files_only=local_files_only,
    )
    model = AutoModelForMaskedLM.from_pretrained(
        model_id,
        trust_remote_code=trust_remote_code,
        local_files_only=local_files_only,
    )
    return tokenizer, model


def validate_backend_args(args: argparse.Namespace) -> None:
    if args.backend == "biohub-forge" and args.model_family != "esmc":
        raise ValueError("--backend biohub-forge is supported only with --model-family esmc")
    if args.backend == "hf-transformers" and args.representation == "sae-feature":
        raise ValueError("--representation sae-feature requires --backend biohub-forge")
    if args.representation == "sae-feature" and not args.sae_model_name:
        raise ValueError("--representation sae-feature requires --sae-model-name")
    if args.backend == "biohub-forge" and args.local_files_only:
        raise ValueError("--local-files-only is incompatible with --backend biohub-forge")


def resolve_layer_indices(layer_spec: str, layer_count: int) -> list[int]:
    spec = layer_spec.strip().lower()
    if not spec:
        raise ValueError("--layer cannot be empty")
    if spec in {"last", "final"}:
        return [layer_count - 1]
    if spec == "all":
        return list(range(layer_count))

    indices: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            idx = int(part)
        except ValueError as exc:
            raise ValueError("--layer must be last, all, or comma-separated integers") from exc
        if idx < 0:
            idx = layer_count + idx
        if idx < 0 or idx >= layer_count:
            raise ValueError(f"Layer index {part} is out of range for {layer_count} available layers")
        indices.append(idx)
    if not indices:
        raise ValueError("--layer did not resolve to any layer indices")
    return indices


def get_hidden_state_tuple(outputs):
    if hasattr(outputs, "hidden_states") and outputs.hidden_states:
        return tuple(outputs.hidden_states)
    if hasattr(outputs, "last_hidden_state"):
        return (outputs.last_hidden_state,)
    if isinstance(outputs, tuple) and outputs:
        return (outputs[0],)
    raise RuntimeError("Model output did not include hidden states")


def token_keep_mask(input_ids, attention_mask, tokenizer):
    import torch

    mask = attention_mask.bool()
    special_ids = set(tokenizer.all_special_ids or [])
    if special_ids:
        special = torch.zeros_like(mask)
        for token_id in special_ids:
            special |= input_ids.eq(token_id)
        mask &= ~special
    return mask


def pool_embedding(hidden, keep_mask, pooling: str):
    if pooling == "mean":
        selected = hidden[keep_mask]
        if selected.numel() == 0:
            selected = hidden
        return selected.mean(dim=0)
    if pooling in {"cls", "bos"}:
        return hidden[0]
    if pooling == "first":
        idx = keep_mask.nonzero(as_tuple=False)
        return hidden[int(idx[0])] if idx.numel() else hidden[0]
    raise ValueError(f"Unsupported pooling: {pooling}")


def write_tsv(path: Path, ids: list[str], matrix) -> None:
    with path.open("w", encoding="utf-8") as handle:
        if matrix.size == 0:
            handle.write("protein_id\n")
            return
        header = ["protein_id"] + [f"dim_{i}" for i in range(matrix.shape[1])]
        handle.write("\t".join(header) + "\n")
        for protein_id, row in zip(ids, matrix):
            values = [protein_id] + [f"{float(x):.8g}" for x in row]
            handle.write("\t".join(values) + "\n")


def build_summary(args: argparse.Namespace, records: list[ProteinRecord], warnings: list[str], model_id: str, status: str) -> dict:
    return {
        "skill_id": "protein-embedding",
        "status": status,
        "input": {
            "fasta": args.fasta,
            "sequence_provided": args.sequence is not None,
            "uniprot": args.uniprot,
        },
        "backend": args.backend,
        "model_family": args.model_family,
        "model_id": model_id,
        "representation": args.representation,
        "embedding_type": args.embedding_type,
        "pooling": args.pooling,
        "layer_spec": args.layer,
        "selected_layers": None,
        "layer_indexing": None,
        "protein_count": len(records),
        "protein_ids": [r.protein_id for r in records],
        "sequence_lengths": {r.protein_id: len(r.sequence) for r in records},
        "dry_run": bool(args.dry_run),
        "warnings": warnings,
        "outputs": {},
    }


def load_records(args: argparse.Namespace) -> list[ProteinRecord]:
    if args.fasta:
        return parse_fasta(Path(args.fasta))
    if args.sequence:
        return [ProteinRecord(args.protein_id or "query", args.sequence)]
    if args.uniprot:
        record = fetch_uniprot_sequence(args.uniprot, args.timeout_sec)
        return [ProteinRecord(args.protein_id or args.uniprot, record.sequence, record.description)]
    raise ValueError("No input provided")


def select_model_id(args: argparse.Namespace) -> str:
    if args.model_id:
        return args.model_id
    if args.backend == "biohub-forge":
        return DEFAULT_FORGE_MODELS[args.model_family]
    return DEFAULT_MODELS[args.model_family]


def infer_forge_layer_count(model_id: str) -> int | None:
    lowered = model_id.lower()
    if "300m" in lowered or "300-" in lowered:
        return 31
    if "600m" in lowered or "600-" in lowered:
        return 37
    if "6b" in lowered:
        return 81
    return None


def to_numpy_array(value):
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "to_dense"):
        value = value.to_dense()
    if hasattr(value, "numpy"):
        return value.numpy()
    import numpy as np

    return np.asarray(value)


def strip_special_tokens_from_matrix(matrix, sequence_length: int):
    if matrix.ndim == 3 and matrix.shape[0] == 1:
        matrix = matrix[0]
    if matrix.ndim >= 2 and matrix.shape[0] >= sequence_length + 2:
        return matrix[1 : sequence_length + 1]
    return matrix[:sequence_length]


def normalize_forge_layer_array(array, sequence_length: int | None = None):
    arr = to_numpy_array(array)
    if arr.ndim == 4 and arr.shape[1] == 1:
        arr = arr[:, 0, :, :]
    if arr.ndim == 3 and sequence_length is not None:
        layers = [strip_special_tokens_from_matrix(arr[i], sequence_length) for i in range(arr.shape[0])]
        import numpy as np

        return np.stack(layers, axis=0)
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    return arr


def run_hf_transformers_embedding(
    args: argparse.Namespace,
    records: list[ProteinRecord],
    model_id: str,
    output_dir: Path,
    summary: dict,
) -> dict:
    import numpy as np
    import torch

    device = choose_device(args.device)
    tokenizer, model = load_model_and_tokenizer(
        args.model_family,
        model_id,
        trust_remote_code=args.trust_remote_code,
        local_files_only=args.local_files_only,
    )
    model.to(device)
    model.eval()

    protein_vectors: list[np.ndarray] = []
    protein_layer_vectors: list[np.ndarray] = []
    protein_ids: list[str] = []
    npz_payload: dict[str, object] = {}
    residue_keys: dict[str, str] = {}
    residue_layer_keys: dict[str, str] = {}
    selected_layers: list[int] | None = None
    available_layer_count: int | None = None

    for start in range(0, len(records), args.batch_size):
        batch = records[start : start + args.batch_size]
        texts = [
            preprocess_for_model(r.sequence, args.model_family, args.replace_rare_aa)
            for r in batch
        ]
        encoded = tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=args.max_length is not None,
            max_length=args.max_length,
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.inference_mode():
            outputs = model(**encoded, output_hidden_states=True)
        hidden_tuple = get_hidden_state_tuple(outputs)
        if selected_layers is None:
            available_layer_count = len(hidden_tuple)
            selected_layers = resolve_layer_indices(args.layer, available_layer_count)
        elif available_layer_count != len(hidden_tuple):
            raise RuntimeError("Model returned a different number of hidden-state layers across batches")

        keep_batch = token_keep_mask(encoded["input_ids"], encoded["attention_mask"], tokenizer)
        selected_hidden_batches = [hidden_tuple[i] for i in selected_layers]

        for idx, record in enumerate(batch):
            keep = keep_batch[idx].detach().cpu()
            layer_vectors: list[np.ndarray] = []
            layer_residue_mats: list[np.ndarray] = []

            for hidden_batch in selected_hidden_batches:
                hidden = hidden_batch[idx].detach().cpu()
                kept_hidden = hidden[keep]
                if kept_hidden.numel() == 0:
                    kept_hidden = hidden
                if args.embedding_type in {"per-protein", "both"}:
                    vector = pool_embedding(hidden, keep, args.pooling).detach().cpu().numpy()
                    layer_vectors.append(vector)
                if args.embedding_type in {"per-residue", "both"}:
                    layer_residue_mats.append(kept_hidden.numpy())

            if args.embedding_type in {"per-protein", "both"}:
                protein_ids.append(record.protein_id)
                if len(layer_vectors) == 1:
                    protein_vectors.append(layer_vectors[0])
                else:
                    protein_layer_vectors.append(np.stack(layer_vectors, axis=0))

            if args.embedding_type in {"per-residue", "both"}:
                if len(layer_residue_mats) == 1:
                    key = f"residue_embeddings__{safe_key(record.protein_id)}"
                    npz_payload[key] = layer_residue_mats[0]
                    residue_keys[record.protein_id] = key
                else:
                    key = f"residue_layer_embeddings__{safe_key(record.protein_id)}"
                    npz_payload[key] = np.stack(layer_residue_mats, axis=0)
                    residue_layer_keys[record.protein_id] = key

    embedding_dim = None
    tsv_path: Path | None = None
    if protein_vectors:
        protein_matrix = np.vstack(protein_vectors)
        npz_payload["protein_embeddings"] = protein_matrix
        npz_payload["protein_ids"] = np.asarray(protein_ids, dtype=str)
        embedding_dim = int(protein_matrix.shape[1])
        tsv_path = output_dir / "protein_embeddings.tsv"
        write_tsv(tsv_path, protein_ids, protein_matrix)
    elif protein_layer_vectors:
        protein_layer_matrix = np.stack(protein_layer_vectors, axis=0)
        npz_payload["protein_layer_embeddings"] = protein_layer_matrix
        npz_payload["protein_ids"] = np.asarray(protein_ids, dtype=str)
        npz_payload["selected_layers"] = np.asarray(selected_layers, dtype=int)
        embedding_dim = int(protein_layer_matrix.shape[2])
    elif residue_keys:
        first_key = next(iter(residue_keys.values()))
        embedding_dim = int(npz_payload[first_key].shape[-1])
    elif residue_layer_keys:
        first_key = next(iter(residue_layer_keys.values()))
        embedding_dim = int(npz_payload[first_key].shape[-1])

    npz_path = output_dir / "embeddings.npz"
    np.savez_compressed(npz_path, **npz_payload)

    summary["status"] = "ok"
    summary["device"] = str(device)
    summary["embedding_dim"] = embedding_dim
    summary["selected_layers"] = selected_layers
    summary["available_layer_count"] = available_layer_count
    summary["layer_indexing"] = "hf-transformers hidden_states tuple; index 0 is the embedding layer when the model exposes it, and the last index is the final transformer state"
    summary["outputs"] = {
        "run_summary_json": str(output_dir / "run_summary.json"),
        "embeddings_npz": str(npz_path),
        "protein_embeddings_tsv": str(tsv_path) if tsv_path else None,
        "protein_embeddings_key": "protein_embeddings" if protein_vectors else None,
        "protein_layer_embeddings_key": "protein_layer_embeddings" if protein_layer_vectors else None,
        "residue_embedding_keys": residue_keys,
        "residue_layer_embedding_keys": residue_layer_keys,
    }
    return summary


def run_biohub_forge_embedding(
    args: argparse.Namespace,
    records: list[ProteinRecord],
    model_id: str,
    output_dir: Path,
    summary: dict,
) -> dict:
    import numpy as np

    token = os.environ.get(args.biohub_token_env) or os.environ.get("ESM_API_KEY")
    if not token:
        raise RuntimeError(
            f"Biohub Forge backend requires {args.biohub_token_env} or ESM_API_KEY in the environment"
        )

    from esm.sdk import esmc_client
    from esm.sdk.api import ESMProtein, ESMProteinError, LogitsConfig, SAEConfig

    model = esmc_client(
        model=model_id,
        url=args.biohub_url,
        token=token,
        request_timeout=args.timeout_sec,
    )

    npz_payload: dict[str, object] = {}
    protein_vectors: list[np.ndarray] = []
    protein_layer_vectors: list[np.ndarray] = []
    protein_ids: list[str] = []
    residue_keys: dict[str, str] = {}
    residue_layer_keys: dict[str, str] = {}
    selected_layers: list[int] | None = None
    available_layer_count = infer_forge_layer_count(model_id)

    if args.representation == "hidden-state":
        if available_layer_count is None:
            if args.layer in {"last", "final"}:
                raise ValueError("Cannot resolve --layer last for unknown ESMC Forge model layer count")
            if args.layer != "all":
                available_layer_count = max(int(x.strip()) for x in args.layer.split(",") if x.strip()) + 1
        if args.layer == "all" and model_id.lower().find("6b") != -1:
            raise ValueError("ESMC 6B Forge does not support requesting all hidden-state layers at once")
        selected_layers = resolve_layer_indices(args.layer, available_layer_count)
        request_layer = selected_layers[0] if len(selected_layers) == 1 else -1

    for record in records:
        protein = ESMProtein(sequence=record.sequence)
        protein_tensor = model.encode(protein)
        if isinstance(protein_tensor, ESMProteinError):
            raise RuntimeError(str(protein_tensor))

        if args.representation == "sae-feature":
            output = model.logits(
                protein_tensor,
                LogitsConfig(
                    sae_config=SAEConfig(
                        models=[args.sae_model_name],
                        normalize_features=args.sae_normalize_features,
                    )
                ),
            )
            if not output.sae_outputs or args.sae_model_name not in output.sae_outputs:
                raise RuntimeError(f"SAE output missing for {args.sae_model_name}")
            features = strip_special_tokens_from_matrix(
                to_numpy_array(output.sae_outputs[args.sae_model_name]),
                len(record.sequence),
            )
            if args.embedding_type in {"per-protein", "both"}:
                protein_ids.append(record.protein_id)
                protein_vectors.append(features.mean(axis=0))
            if args.embedding_type in {"per-residue", "both"}:
                key = f"sae_features__{safe_key(record.protein_id)}"
                npz_payload[key] = features
                residue_keys[record.protein_id] = key
            continue

        output = model.logits(
            protein_tensor,
            LogitsConfig(
                return_hidden_states=args.embedding_type in {"per-residue", "both"},
                return_mean_hidden_states=args.embedding_type in {"per-protein", "both"},
                ith_hidden_layer=request_layer,
            ),
        )

        if args.embedding_type in {"per-protein", "both"}:
            mean_hidden = normalize_forge_layer_array(output.mean_hidden_state)
            if mean_hidden.ndim == 1:
                mean_hidden = mean_hidden[None, :]
            if len(selected_layers) == 1:
                vector = mean_hidden[0]
                protein_vectors.append(vector)
            else:
                protein_layer_vectors.append(mean_hidden[selected_layers])
            protein_ids.append(record.protein_id)

        if args.embedding_type in {"per-residue", "both"}:
            hidden = normalize_forge_layer_array(output.hidden_states, len(record.sequence))
            if len(selected_layers) == 1:
                key = f"residue_embeddings__{safe_key(record.protein_id)}"
                npz_payload[key] = hidden[0] if hidden.ndim == 3 else hidden
                residue_keys[record.protein_id] = key
            else:
                key = f"residue_layer_embeddings__{safe_key(record.protein_id)}"
                npz_payload[key] = hidden[selected_layers]
                residue_layer_keys[record.protein_id] = key

    embedding_dim = None
    tsv_path: Path | None = None
    if protein_vectors:
        protein_matrix = np.vstack(protein_vectors)
        npz_payload["protein_embeddings"] = protein_matrix
        npz_payload["protein_ids"] = np.asarray(protein_ids, dtype=str)
        embedding_dim = int(protein_matrix.shape[1])
        tsv_path = output_dir / "protein_embeddings.tsv"
        write_tsv(tsv_path, protein_ids, protein_matrix)
    elif protein_layer_vectors:
        protein_layer_matrix = np.stack(protein_layer_vectors, axis=0)
        npz_payload["protein_layer_embeddings"] = protein_layer_matrix
        npz_payload["protein_ids"] = np.asarray(protein_ids, dtype=str)
        npz_payload["selected_layers"] = np.asarray(selected_layers, dtype=int)
        embedding_dim = int(protein_layer_matrix.shape[2])
    elif residue_keys:
        first_key = next(iter(residue_keys.values()))
        embedding_dim = int(npz_payload[first_key].shape[-1])
    elif residue_layer_keys:
        first_key = next(iter(residue_layer_keys.values()))
        embedding_dim = int(npz_payload[first_key].shape[-1])

    npz_path = output_dir / "embeddings.npz"
    np.savez_compressed(npz_path, **npz_payload)

    summary["status"] = "ok"
    summary["device"] = "biohub-forge"
    summary["embedding_dim"] = embedding_dim
    summary["selected_layers"] = selected_layers
    summary["available_layer_count"] = available_layer_count
    summary["layer_indexing"] = "Biohub ESMC LogitsConfig ith_hidden_layer indexing; index 0 is the embedding layer"
    summary["outputs"] = {
        "run_summary_json": str(output_dir / "run_summary.json"),
        "embeddings_npz": str(npz_path),
        "protein_embeddings_tsv": str(tsv_path) if tsv_path else None,
        "protein_embeddings_key": "protein_embeddings" if protein_vectors else None,
        "protein_layer_embeddings_key": "protein_layer_embeddings" if protein_layer_vectors else None,
        "residue_embedding_keys": residue_keys,
        "residue_layer_embedding_keys": residue_layer_keys,
        "sae_model_name": args.sae_model_name if args.representation == "sae-feature" else None,
    }
    return summary


def main() -> int:
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    try:
        validate_backend_args(args)
        model_id = select_model_id(args)
        records_raw = load_records(args)
        records, validation_warnings = validate_records(
            records_raw,
            allow_ambiguous=args.allow_ambiguous_aa or args.replace_rare_aa,
            allow_rare=args.allow_rare_aa or args.replace_rare_aa,
            saprot_mode=args.saprot_input_mode,
            model_family=args.model_family,
        )
        warnings.extend(validation_warnings)
    except Exception as exc:
        summary = {
            "skill_id": "protein-embedding",
            "status": "error",
            "error": str(exc),
            "backend": args.backend,
            "model_family": args.model_family,
            "warnings": warnings,
        }
        (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2), file=sys.stderr)
        return 1

    if args.model_family == "saprot" and args.saprot_input_mode == "aa-only":
        warnings.append(
            "SaProt run is labeled aa-only; SaProt 35M/650M frozen embeddings are intended for structure-aware AA+3Di tokens."
        )
    if args.model_family in {"prott5", "ankh"} and not args.replace_rare_aa:
        warnings.append("T5-style protein models commonly replace U/Z/O/B with X; consider --replace-rare-aa.")

    summary = build_summary(args, records, warnings, model_id, "planned" if args.dry_run else "running")
    summary["outputs"] = {
        "run_summary_json": str(output_dir / "run_summary.json"),
        "embeddings_npz": None if args.dry_run else str(output_dir / "embeddings.npz"),
        "protein_embeddings_tsv": None if args.dry_run else str(output_dir / "protein_embeddings.tsv"),
    }

    if args.dry_run:
        summary["status"] = "dry_run_ok"
        (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0

    try:
        if args.backend == "biohub-forge":
            summary = run_biohub_forge_embedding(args, records, model_id, output_dir, summary)
        else:
            summary = run_hf_transformers_embedding(args, records, model_id, output_dir, summary)
        (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0
    except Exception as exc:
        summary["status"] = "error"
        summary["error"] = str(exc)
        (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
