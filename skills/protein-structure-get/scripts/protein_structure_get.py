#!/usr/bin/env python3
"""Retrieve protein-structure context for a gene, UniProt accession, or sequence.

Public data sources:
  UniProt REST API, RCSB PDB Search/Data APIs, AlphaFold DB API,
  and hosted ESMFold via ESM Atlas.

Runtime dependencies are declared in requirements.txt and intentionally use
the common scientific Python stack: requests, pandas, numpy, and matplotlib.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


UNIPROT_BASE = "https://rest.uniprot.org"
RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_GRAPHQL = "https://data.rcsb.org/graphql"
ALPHAFOLD_BASE = "https://alphafold.ebi.ac.uk/api"
ESMFOLD_PDB_API = "https://api.esmatlas.com/foldSequence/v1/pdb/"

USER_AGENT = "s2f-agent-protein-structure-get/0.1"
ESMFOLD_MIN_SEQUENCE_LENGTH = 15
ESMFOLD_MAX_SEQUENCE_LENGTH = 400
CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
AMBIGUOUS_AA = set("BXZJUO")

FEATURE_COLORS = {
    "Domain": "#4E79A7",
    "Region": "#F28E2B",
    "Motif": "#59A14F",
    "Binding site": "#E15759",
    "Active site": "#B07AA1",
    "Signal": "#76B7B2",
    "Transmembrane": "#FF9DA7",
    "Coiled coil": "#9C755F",
    "Compositional bias": "#BAB0AC",
    "Other": "#D3D3D3",
}

DISPLAY_FEATURE_PREFIXES = (
    "Domain",
    "Region",
    "Motif",
    "Binding site",
    "Active site",
    "Signal",
    "Transmembrane",
    "Coiled coil",
)


np = None
pd = None
requests = None
plt = None
mpatches = None


class PublicApiError(RuntimeError):
    """Public API request or response error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RuntimeDependencyError(RuntimeError):
    """Required Python package is not installed."""


def load_runtime_dependencies() -> None:
    global mpatches, np, pd, plt, requests
    if requests is not None and pd is not None and np is not None and plt is not None and mpatches is not None:
        return
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.patches as _mpatches
        import matplotlib.pyplot as _plt
        import numpy as _np
        import pandas as _pd
        import requests as _requests
    except ImportError as exc:
        raise RuntimeDependencyError(
            "Missing runtime dependency. Install with: "
            "python -m pip install -r skills/protein-structure-get/requirements.txt"
        ) from exc

    mpatches = _mpatches
    np = _np
    pd = _pd
    plt = _plt
    requests = _requests


def safe_name(value: str) -> str:
    clean = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in value.strip())
    return clean or "protein"


def sequence_hash(sequence: str) -> str:
    return hashlib.sha256(sequence.encode("utf-8")).hexdigest()


def read_sequence_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def normalize_amino_acid_sequence(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        lines.append(stripped)
    return "".join(lines).replace(" ", "").replace("\t", "").upper()


def validate_amino_acid_sequence(
    raw: str,
    min_length: int,
    max_length: int,
    allow_ambiguous: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    if min_length < 1:
        raise ValueError("--esmfold-min-length must be at least 1")
    if max_length > ESMFOLD_MAX_SEQUENCE_LENGTH:
        raise ValueError(
            f"--esmfold-max-length cannot exceed the hosted ESMFold API maximum {ESMFOLD_MAX_SEQUENCE_LENGTH}"
        )
    if min_length > max_length:
        raise ValueError("--esmfold-min-length cannot be greater than --esmfold-max-length")

    sequence = normalize_amino_acid_sequence(raw)
    allowed = CANONICAL_AA | (AMBIGUOUS_AA if allow_ambiguous else set())
    invalid = sorted({char for char in sequence if char not in allowed})

    if not sequence:
        raise ValueError("Amino-acid sequence is empty after removing FASTA headers and whitespace")
    if invalid:
        raise ValueError(
            "Amino-acid sequence contains unsupported residue code(s): "
            + ",".join(invalid)
            + ". Use 20 canonical one-letter amino-acid codes"
            + (" or pass --allow-ambiguous-aa for B/X/Z/J/U/O." if not allow_ambiguous else ".")
        )
    if len(sequence) < min_length:
        raise ValueError(f"Amino-acid sequence length {len(sequence)} is shorter than the minimum {min_length}")
    if len(sequence) > max_length:
        raise ValueError(f"Amino-acid sequence length {len(sequence)} exceeds the ESMFold API maximum {max_length}")

    composition = {aa: sequence.count(aa) for aa in sorted(allowed) if sequence.count(aa)}
    return sequence, {
        "length": len(sequence),
        "sha256": sequence_hash(sequence),
        "alphabet": "canonical" if not allow_ambiguous else "canonical+ambiguous",
        "composition": composition,
    }


def ensure_outdir(path: str) -> Path:
    outdir = Path(path)
    outdir.mkdir(parents=True, exist_ok=True)
    return outdir


def json_get(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Any:
    load_runtime_dependencies()
    try:
        response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        raise PublicApiError(f"GET {response.url} failed with HTTP {status_code}", status_code) from exc
    except requests.RequestException as exc:
        raise PublicApiError(f"GET {url} failed: {exc}") from exc
    except ValueError as exc:
        raise PublicApiError(f"GET {url} returned invalid JSON") from exc


def json_post(url: str, payload: Dict[str, Any], timeout: int = 30) -> Any:
    load_runtime_dependencies()
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        raise PublicApiError(f"POST {url} failed with HTTP {status_code}", status_code) from exc
    except requests.RequestException as exc:
        raise PublicApiError(f"POST {url} failed: {exc}") from exc
    except ValueError as exc:
        raise PublicApiError(f"POST {url} returned invalid JSON") from exc


def text_post(url: str, data: str, timeout: int = 120) -> str:
    load_runtime_dependencies()
    try:
        response = requests.post(
            url,
            data=data.encode("utf-8"),
            headers={"User-Agent": USER_AGENT, "Content-Type": "text/plain"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.text
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        body = ""
        if exc.response is not None:
            body = exc.response.text.strip()
        detail = f": {body}" if body else ""
        raise PublicApiError(f"POST {url} failed with HTTP {status_code}{detail}", status_code) from exc
    except requests.RequestException as exc:
        raise PublicApiError(f"POST {url} failed: {exc}") from exc


def download_url(url: str, destination: Path, timeout: int = 60) -> None:
    load_runtime_dependencies()
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
        destination.write_bytes(response.content)
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        raise PublicApiError(f"Download {url} failed with HTTP {status_code}", status_code) from exc
    except requests.RequestException as exc:
        raise PublicApiError(f"Download {url} failed: {exc}") from exc


def taxon_id(organism: str) -> str:
    aliases = {"human": "9606", "mouse": "10090", "rat": "10116"}
    return aliases.get(organism.strip().lower(), organism.strip())


def as_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_protein_name(entry: Dict[str, Any]) -> str:
    desc = entry.get("proteinDescription") or {}
    recommended = desc.get("recommendedName") or {}
    full_name = recommended.get("fullName") or {}
    return full_name.get("value") or entry.get("uniProtkbId") or ""


def extract_primary_gene(entry: Dict[str, Any]) -> str:
    genes = entry.get("genes") or []
    if not genes:
        return ""
    return ((genes[0].get("geneName") or {}).get("value")) or ""


def is_reviewed(entry: Dict[str, Any]) -> bool:
    entry_type = entry.get("entryType") or ""
    return "reviewed" in entry_type.lower() or entry.get("reviewed") is True


def resolve_uniprot(gene: str, organism: str, timeout: int) -> Tuple[str, Dict[str, Any], List[str]]:
    warnings: List[str] = []
    taxon = taxon_id(organism)
    fields = "accession,id,gene_names,protein_name,length,organism_name,reviewed"

    queries = [
        f"gene_exact:{gene} AND organism_id:{taxon} AND reviewed:true",
        f"gene_exact:{gene} AND organism_id:{taxon}",
        f"gene:{gene} AND organism_id:{taxon} AND reviewed:true",
        f"gene:{gene} AND organism_id:{taxon}",
    ]

    for idx, query in enumerate(queries):
        data = json_get(
            f"{UNIPROT_BASE}/uniprotkb/search",
            params={"query": query, "fields": fields, "format": "json", "size": 5},
            timeout=timeout,
        )
        results = data.get("results") or []
        if results:
            if idx > 0:
                warnings.append(f"uniprot_resolution_relaxed_query:{query}")
            accession = results[0].get("primaryAccession")
            if not accession:
                raise PublicApiError("UniProt result did not contain primaryAccession")
            return accession, results[0], warnings

    raise ValueError(f"Could not resolve gene '{gene}' for organism '{organism}' in UniProt")


def fetch_uniprot_entry(accession: str, timeout: int) -> Dict[str, Any]:
    return json_get(f"{UNIPROT_BASE}/uniprotkb/{accession}", params={"format": "json"}, timeout=timeout)


def feature_location(feature: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    location = feature.get("location") or {}
    start = as_int((location.get("start") or {}).get("value"))
    end = as_int((location.get("end") or {}).get("value"))
    return start, end


def parse_features(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for feature in entry.get("features") or []:
        start, end = feature_location(feature)
        if start is None or end is None:
            continue
        feature_type = feature.get("type") or "Other"
        description = feature.get("description") or feature_type
        rows.append(
            {
                "type": feature_type,
                "description": description,
                "start": start,
                "end": end,
                "length": end - start + 1,
            }
        )
    return rows


def uniprot_summary(accession: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    sequence = entry.get("sequence") or {}
    organism = entry.get("organism") or {}
    return {
        "accession": accession,
        "entry_name": entry.get("uniProtkbId") or accession,
        "protein_name": extract_protein_name(entry),
        "gene_name": extract_primary_gene(entry),
        "organism": organism.get("scientificName") or "",
        "seq_length": sequence.get("length") or 0,
        "reviewed": is_reviewed(entry),
        "uniprot_url": f"https://www.uniprot.org/uniprotkb/{accession}/entry",
    }


def fetch_pdb_structures(accession: str, max_pdb: int, timeout: int) -> List[Dict[str, Any]]:
    query = {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                "operator": "exact_match",
                "value": accession,
            },
        },
        "request_options": {
            "paginate": {"start": 0, "rows": max_pdb},
            "sort": [{"sort_by": "score", "direction": "desc"}],
        },
        "return_type": "entry",
    }
    data = json_post(RCSB_SEARCH, query, timeout=timeout)
    result_set = data.get("result_set") or []
    pdb_ids = [item.get("identifier", "").upper() for item in result_set if item.get("identifier")]
    rows: List[Dict[str, Any]] = []
    for pdb_id in pdb_ids:
        try:
            rows.append(fetch_pdb_metadata(pdb_id, timeout=timeout))
        except PublicApiError as exc:
            rows.append(
                {
                    "pdb_id": pdb_id,
                    "title": "",
                    "method": "",
                    "resolution_A": "",
                    "n_protein_chains": "",
                    "n_atoms": "",
                    "pubmed_id": "",
                    "authors": "",
                    "deposition_date": "",
                    "rcsb_url": f"https://www.rcsb.org/structure/{pdb_id}",
                    "metadata_error": str(exc),
                }
            )
    return rows


def fetch_pdb_metadata(pdb_id: str, timeout: int) -> Dict[str, Any]:
    payload = {
        "query": """
        query($id: String!) {
          entry(entry_id: $id) {
            rcsb_id
            struct { title }
            rcsb_entry_info {
              resolution_combined
              experimental_method
              deposited_atom_count
              polymer_entity_count_protein
            }
            rcsb_entry_container_identifiers { pubmed_id }
            audit_author { name }
            pdbx_audit_revision_history { revision_date }
          }
        }
        """,
        "variables": {"id": pdb_id.upper()},
    }
    data = json_post(RCSB_GRAPHQL, payload, timeout=timeout)
    entry = ((data.get("data") or {}).get("entry")) or {}
    info = entry.get("rcsb_entry_info") or {}
    identifiers = entry.get("rcsb_entry_container_identifiers") or {}
    authors = entry.get("audit_author") or []
    revisions = entry.get("pdbx_audit_revision_history") or []
    resolution = info.get("resolution_combined") or []
    author_names = [a.get("name", "") for a in authors[:3] if a.get("name")]
    if len(authors) > 3:
        author_names.append(f"et al. (+{len(authors) - 3})")
    return {
        "pdb_id": pdb_id.upper(),
        "title": (entry.get("struct") or {}).get("title", ""),
        "method": info.get("experimental_method", ""),
        "resolution_A": round(float(resolution[0]), 2) if resolution else "",
        "n_protein_chains": info.get("polymer_entity_count_protein", ""),
        "n_atoms": info.get("deposited_atom_count", ""),
        "pubmed_id": identifiers.get("pubmed_id", ""),
        "authors": "; ".join(author_names),
        "deposition_date": (revisions[0] or {}).get("revision_date", "") if revisions else "",
        "rcsb_url": f"https://www.rcsb.org/structure/{pdb_id.upper()}",
    }


def fetch_alphafold_entry(accession: str, timeout: int) -> Optional[Dict[str, Any]]:
    try:
        data = json_get(f"{ALPHAFOLD_BASE}/prediction/{accession}", timeout=timeout)
    except PublicApiError as exc:
        if exc.status_code == 404:
            return None
        raise
    if not data:
        return None
    entry = data[0]
    return {
        "alphafold_id": entry.get("entryId") or "",
        "uniprot_accession": entry.get("uniprotAccession") or accession,
        "gene": entry.get("gene") or "",
        "organism": entry.get("organismScientificName") or "",
        "seq_length": entry.get("sequenceLength") or "",
        "model_created": entry.get("modelCreatedDate") or "",
        "latest_version": entry.get("latestVersion") or "",
        "pdb_url": entry.get("pdbUrl") or "",
        "cif_url": entry.get("cifUrl") or "",
        "pae_image_url": entry.get("paeImageUrl") or "",
        "alphafold_page": f"https://alphafold.ebi.ac.uk/entry/{accession}",
    }


def pdb_bfactor_stats(pdb_text: str) -> Dict[str, Any]:
    values: List[float] = []
    for line in pdb_text.splitlines():
        if not line.startswith(("ATOM  ", "HETATM")):
            continue
        try:
            values.append(float(line[60:66]))
        except ValueError:
            continue
    if not values:
        return {
            "mean_confidence_raw": "",
            "min_confidence_raw": "",
            "max_confidence_raw": "",
            "confidence_scale": "",
            "mean_confidence_0_100": "",
            "n_atoms": 0,
        }
    raw_mean = sum(values) / len(values)
    raw_min = min(values)
    raw_max = max(values)
    scale_factor = 100.0 if raw_max <= 1.0 else 1.0
    return {
        "mean_confidence_raw": round(raw_mean, 3),
        "min_confidence_raw": round(raw_min, 3),
        "max_confidence_raw": round(raw_max, 3),
        "confidence_scale": "0-1" if scale_factor == 100.0 else "0-100",
        "mean_confidence_0_100": round(raw_mean * scale_factor, 2),
        "n_atoms": len(values),
    }


def fold_sequence_with_esmfold(
    sequence: str,
    sequence_info: Dict[str, Any],
    sequence_name: str,
    outdir: Path,
    timeout: int,
) -> Dict[str, Any]:
    pdb_text = text_post(ESMFOLD_PDB_API, sequence, timeout=timeout)
    if not pdb_text.startswith(("HEADER", "ATOM", "MODEL", "TITLE")):
        raise PublicApiError("ESMFold API response did not look like a PDB file")

    target = safe_name(sequence_name)
    pdb_path = outdir / f"{target}.esmfold.pdb"
    fasta_path = outdir / f"{target}.sequence.fasta"
    metadata_path = outdir / f"{target}.esmfold.tsv"

    pdb_path.write_text(pdb_text, encoding="utf-8")
    fasta_path.write_text(f">{target}|sha256={sequence_info['sha256']}\n{sequence}\n", encoding="utf-8")

    stats = pdb_bfactor_stats(pdb_text)
    metadata = {
        "sequence_name": target,
        "sequence_length": sequence_info["length"],
        "sequence_sha256": sequence_info["sha256"],
        "model_source": "ESMFold hosted API",
        "api_url": ESMFOLD_PDB_API,
        "pdb_path": str(pdb_path),
        "fasta_path": str(fasta_path),
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **stats,
    }
    write_tsv(metadata_path, [metadata], list(metadata.keys()))
    metadata["metadata_tsv"] = str(metadata_path)
    return metadata


def pml_quote(value: Path) -> str:
    return '"' + str(value).replace("\\", "/").replace('"', '\\"') + '"'


def pymol_object_name(value: str) -> str:
    clean = safe_name(value).replace(".", "_").replace("-", "_")
    if clean and clean[0].isdigit():
        clean = f"obj_{clean}"
    return clean or "protein_model"


def build_pymol_residue_selection(raw: str) -> str:
    if not raw.strip():
        return ""

    scoped: Dict[str, List[str]] = {}
    unscoped: List[str] = []
    for token in re.split(r"[,;\s]+", raw.strip()):
        if not token:
            continue
        chain = ""
        residue_token = token
        if ":" in token:
            chain, residue_token = token.split(":", 1)
            chain = chain.strip()

        match = re.match(r"(\d+[A-Za-z]?)", residue_token.strip())
        if not match:
            continue
        residue_id = match.group(1)
        if chain:
            scoped.setdefault(chain, []).append(residue_id)
        else:
            unscoped.append(residue_id)

    clauses: List[str] = []
    for chain, residues in sorted(scoped.items()):
        clauses.append(f"(chain {chain} and resi {'+'.join(residues)})")
    if unscoped:
        clauses.append(f"(resi {'+'.join(unscoped)})")
    return " or ".join(clauses)


def write_pymol_script(
    structure_path: Path,
    label: str,
    outdir: Path,
    color_mode: str,
    highlight_residues: str,
) -> Dict[str, str]:
    object_name = pymol_object_name(label)
    base = outdir / f"{safe_name(label)}.pymol"
    script_path = Path(f"{base}.pml")
    pse_path = Path(f"{base}.pse")
    png_path = Path(f"{base}.png")
    selection = build_pymol_residue_selection(highlight_residues)

    lines = [
        "reinitialize",
        f"load {pml_quote(structure_path)}, {object_name}",
        "hide everything",
        f"show cartoon, {object_name}",
        f"set cartoon_transparency, 0.08, {object_name}",
        "bg_color white",
        "set ray_opaque_background, off",
        "set antialias, 2",
    ]
    if color_mode == "confidence":
        lines.append(f"spectrum b, red_yellow_green, {object_name}")
    else:
        lines.append(f"color gray70, {object_name}")
        lines.append(f"spectrum chain, rainbow, {object_name}")

    if selection:
        lines.extend(
            [
                f"select {object_name}_highlight, ({selection}) and {object_name}",
                f"show sticks, {object_name}_highlight",
                f"color yelloworange, {object_name}_highlight",
                f"set stick_radius, 0.18, {object_name}_highlight",
                f"label ({object_name}_highlight and name CA), chain + ':' + resn + resi",
            ]
        )

    lines.extend(
        [
            f"zoom {object_name}",
            f"save {pml_quote(pse_path)}",
            f"png {pml_quote(png_path)}, width=1600, height=1200, dpi=300, ray=1",
            "",
        ]
    )
    script_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "structure_file": str(structure_path),
        "pymol_script": str(script_path),
        "pse_path": str(pse_path),
        "png_path": str(png_path),
        "object_name": object_name,
    }


def run_pymol_script(script_path: Path, pymol_bin: str, timeout: int, warnings: List[str]) -> Optional[str]:
    binary = shutil.which(pymol_bin) or (pymol_bin if Path(pymol_bin).exists() else "")
    if not binary:
        warnings.append(f"pymol_binary_not_found:{pymol_bin}")
        return None

    log_path = script_path.with_suffix(".pymol.log")
    try:
        completed = subprocess.run(
            [binary, "-cq", str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        warnings.append(f"pymol_timeout:{script_path}")
        return None

    log_path.write_text(
        "STDOUT\n======\n"
        + completed.stdout
        + "\nSTDERR\n======\n"
        + completed.stderr
        + f"\nRETURN_CODE\n===========\n{completed.returncode}\n",
        encoding="utf-8",
    )
    if completed.returncode != 0:
        warnings.append(f"pymol_failed:{script_path}:exit_{completed.returncode}")
    return str(log_path)


def generate_pymol_outputs(
    structure_files: Sequence[Tuple[str, Path]],
    outdir: Path,
    args: argparse.Namespace,
    warnings: List[str],
) -> List[Dict[str, str]]:
    if not (args.pymol or args.run_pymol):
        return []
    outdir.mkdir(parents=True, exist_ok=True)
    if not structure_files:
        warnings.append("pymol_requested_but_no_local_structure_file_available")
        return []

    outputs: List[Dict[str, str]] = []
    for label, structure_path in structure_files:
        if not structure_path.exists():
            warnings.append(f"pymol_structure_missing:{structure_path}")
            continue
        item = write_pymol_script(
            structure_path,
            label,
            outdir,
            args.pymol_color_mode,
            args.pymol_highlight_residues,
        )
        if args.run_pymol:
            log_path = run_pymol_script(Path(item["pymol_script"]), args.pymol_bin, max(args.timeout_sec, 120), warnings)
            if log_path:
                item["pymol_log"] = log_path
        outputs.append(item)
    return outputs


def write_tsv(path: Path, rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> None:
    load_runtime_dependencies()
    frame = pd.DataFrame(rows, columns=list(columns))
    frame.to_csv(path, sep="\t", index=False)


def write_summary_txt(path: Path, summary: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for key in sorted(summary):
            handle.write(f"{key}: {summary[key]}\n")


def feature_color(feature_type: str) -> str:
    for prefix, color in FEATURE_COLORS.items():
        if feature_type.lower().startswith(prefix.lower()):
            return color
    return FEATURE_COLORS["Other"]


def render_domain_map(
    features: Sequence[Dict[str, Any]],
    seq_length: int,
    target: str,
    accession: str,
    outdir: Path,
) -> Tuple[Optional[Path], Optional[Path], Optional[str]]:
    load_runtime_dependencies()
    plot_features = [
        f
        for f in features
        if any(str(f.get("type", "")).lower().startswith(p.lower()) for p in DISPLAY_FEATURE_PREFIXES)
    ]

    rows: List[List[Dict[str, Any]]] = []
    for feature in sorted(plot_features, key=lambda item: int(item.get("start", 0))):
        placed = False
        for row in rows:
            if all(int(feature["start"]) > int(existing["end"]) + 5 for existing in row):
                row.append(feature)
                placed = True
                break
        if not placed:
            rows.append([feature])

    row_count = max(len(rows), 1)
    fig_height = float(max(2.5, 1.2 + np.ceil(row_count) * 0.55))
    fig, ax = plt.subplots(figsize=(12, fig_height), dpi=300)
    ax.barh(0, seq_length, left=1, height=0.18, color="#CCCCCC", zorder=2)

    legend_handles: Dict[str, Any] = {}
    for row_idx, row in enumerate(rows):
        y = -(row_idx * 0.55)
        for feature in row:
            start = int(feature["start"])
            length = int(feature["length"])
            feature_type = str(feature.get("type") or "Other")
            color = feature_color(feature_type)
            ax.barh(y, length, left=start, height=0.40, color=color, edgecolor="white", linewidth=0.4, zorder=3)
            if length > float(seq_length) * 0.04:
                label = str(feature.get("description") or feature_type)[:22]
                ax.text(start + length / 2, y, label, ha="center", va="center", fontsize=6.5, color="white", fontweight="bold", zorder=4, clip_on=True)
            if feature_type not in legend_handles:
                legend_handles[feature_type] = mpatches.Patch(color=color, label=feature_type)

    ax.set_xlim(0, seq_length + 10)
    ax.set_ylim(-(row_count * 0.55) - 0.4, 0.6)
    ax.set_xlabel("Amino acid position", fontsize=11)
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title(f"{target} ({accession})  |  {seq_length} aa", fontsize=13, fontweight="bold", pad=10)
    if legend_handles:
        ax.legend(handles=list(legend_handles.values()), loc="upper right", fontsize=8, framealpha=0.9, ncol=min(4, len(legend_handles)))

    plt.tight_layout()
    base = outdir / f"{target}.{accession}.domain_map"
    png_path = base.with_suffix(".png")
    pdf_path = base.with_suffix(".pdf")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    return png_path, pdf_path, None


def parse_modules(raw: str, sequence_mode: bool = False) -> List[str]:
    all_modules = ["uniprot", "pdb", "alphafold", "domain_map"]
    sequence_modules = ["esmfold"]
    if raw.strip().lower() == "all":
        return sequence_modules if sequence_mode else all_modules
    modules = [m.strip().lower() for m in raw.split(",") if m.strip()]
    valid = set(all_modules + sequence_modules)
    invalid = sorted(set(modules) - valid)
    if invalid:
        raise ValueError(f"Unknown module(s): {', '.join(invalid)}")
    if sequence_mode:
        non_sequence = sorted(set(modules) - set(sequence_modules))
        if non_sequence:
            raise ValueError(
                "Sequence input only supports module 'esmfold'. "
                f"Unsupported for sequence input: {', '.join(non_sequence)}"
            )
    elif "esmfold" in modules:
        raise ValueError("Module 'esmfold' requires --sequence or --sequence-file")
    if "domain_map" in modules and "uniprot" not in modules:
        modules.insert(0, "uniprot")
    return modules


def status_from_result(errors: Sequence[str], warnings: Sequence[str]) -> str:
    if errors:
        return "error"
    if warnings:
        return "partial"
    return "ok"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retrieve protein structure context from UniProt/RCSB/AlphaFold DB, or fold an amino-acid sequence with hosted ESMFold.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--gene", help="Gene symbol, for example TP53, EGFR, BRCA1")
    target.add_argument("--uniprot", help="UniProt accession, for example P04637")
    target.add_argument("--sequence", help="Amino-acid sequence for hosted ESMFold prediction")
    target.add_argument("--sequence-file", help="FASTA or plain-text amino-acid sequence file for hosted ESMFold prediction")
    parser.add_argument("--sequence-name", default=None, help="Stable output label for --sequence or --sequence-file")
    parser.add_argument("--organism", default="human", help="Organism alias or NCBI taxon ID")
    parser.add_argument("--modules", default="all", help="Comma-separated modules: uniprot,pdb,alphafold,domain_map,esmfold; or all")
    parser.add_argument("--max-pdb", type=int, default=20, help="Maximum RCSB PDB entries to collect")
    parser.add_argument("--download-structure", action="store_true", help="Download AlphaFold DB structure file when available")
    parser.add_argument("--download-format", choices=["cif", "pdb", "both"], default="cif", help="Structure file format to download")
    parser.add_argument("--esmfold-min-length", type=int, default=ESMFOLD_MIN_SEQUENCE_LENGTH, help="Minimum accepted amino-acid sequence length for ESMFold")
    parser.add_argument("--esmfold-max-length", type=int, default=ESMFOLD_MAX_SEQUENCE_LENGTH, help="Maximum accepted amino-acid sequence length for the hosted ESMFold API")
    parser.add_argument("--allow-ambiguous-aa", action="store_true", help="Allow ambiguous amino-acid codes B/X/Z/J/U/O in ESMFold sequence input")
    parser.add_argument("--pymol", action="store_true", help="Write PyMOL .pml visualization scripts for local structure outputs")
    parser.add_argument("--run-pymol", action="store_true", help="Run PyMOL headless to create .pse and .png outputs from generated .pml scripts")
    parser.add_argument("--pymol-bin", default="pymol", help="PyMOL executable name or path for --run-pymol")
    parser.add_argument("--pymol-color-mode", choices=["chain", "confidence"], default="chain", help="PyMOL coloring mode")
    parser.add_argument("--pymol-highlight-residues", default="", help="Residues to highlight in PyMOL, for example A:42,A:57 or 42,57")
    parser.add_argument("--timeout-sec", type=int, default=30, help="Timeout per public API request")
    parser.add_argument("--outdir", required=True, help="Output directory")
    return parser


def run(args: argparse.Namespace) -> Tuple[int, Dict[str, Any]]:
    load_runtime_dependencies()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    outdir = ensure_outdir(args.outdir)
    sequence_mode = bool(args.sequence or args.sequence_file)
    modules = parse_modules(args.modules, sequence_mode=sequence_mode)
    sequence = ""
    sequence_info: Dict[str, Any] = {}
    if sequence_mode:
        raw_sequence = args.sequence if args.sequence else read_sequence_file(args.sequence_file)
        sequence, sequence_info = validate_amino_acid_sequence(
            raw_sequence,
            min_length=args.esmfold_min_length,
            max_length=args.esmfold_max_length,
            allow_ambiguous=args.allow_ambiguous_aa,
        )
    sequence_label = args.sequence_name or (Path(args.sequence_file).stem if args.sequence_file else "")
    if not sequence_label and sequence_mode:
        sequence_label = f"sequence_{sequence_info['length']}_{sequence_info['sha256'][:10]}"
    target = safe_name(args.gene or args.uniprot or sequence_label or "protein")
    warnings: List[str] = []
    errors: List[str] = []
    outputs: Dict[str, Any] = {}
    module_status: Dict[str, Any] = {}
    local_structure_files: List[Tuple[str, Path]] = []

    result: Dict[str, Any] = {
        "status": "error",
        "query": {
            "gene": args.gene,
            "uniprot": args.uniprot,
            "sequence_name": sequence_label if sequence_mode else None,
            "sequence_length": sequence_info.get("length") if sequence_mode else None,
            "sequence_sha256": sequence_info.get("sha256") if sequence_mode else None,
            "organism": args.organism,
            "modules": modules,
            "max_pdb": args.max_pdb,
            "download_structure": args.download_structure,
            "download_format": args.download_format,
            "esmfold_min_length": args.esmfold_min_length,
            "esmfold_max_length": args.esmfold_max_length,
            "allow_ambiguous_aa": args.allow_ambiguous_aa,
            "pymol": args.pymol,
            "run_pymol": args.run_pymol,
            "pymol_bin": args.pymol_bin,
            "pymol_color_mode": args.pymol_color_mode,
            "pymol_highlight_residues": args.pymol_highlight_residues,
            "timeout_sec": args.timeout_sec,
        },
        "resolved": {},
        "modules": module_status,
        "outputs": outputs,
        "warnings": warnings,
        "errors": errors,
        "started_utc": started,
    }

    if sequence_mode:
        result["resolved"] = {
            "source": "amino_acid_sequence",
            "sequence_name": target,
            "seq_length": sequence_info["length"],
            "sequence_sha256": sequence_info["sha256"],
            "alphabet": sequence_info["alphabet"],
        }
        try:
            esmfold_metadata = fold_sequence_with_esmfold(
                sequence,
                sequence_info,
                target,
                outdir,
                timeout=max(args.timeout_sec, 120),
            )
            outputs["esmfold_pdb"] = esmfold_metadata["pdb_path"]
            outputs["sequence_fasta"] = esmfold_metadata["fasta_path"]
            outputs["esmfold_tsv"] = esmfold_metadata["metadata_tsv"]
            local_structure_files.append((f"{target}.esmfold", Path(esmfold_metadata["pdb_path"])))
            module_status["esmfold"] = {
                "status": "ok",
                "sequence_length": sequence_info["length"],
                "sequence_sha256": sequence_info["sha256"],
                "mean_confidence_raw": esmfold_metadata.get("mean_confidence_raw", ""),
                "min_confidence_raw": esmfold_metadata.get("min_confidence_raw", ""),
                "max_confidence_raw": esmfold_metadata.get("max_confidence_raw", ""),
                "confidence_scale": esmfold_metadata.get("confidence_scale", ""),
                "mean_confidence_0_100": esmfold_metadata.get("mean_confidence_0_100", ""),
                "n_atoms": esmfold_metadata.get("n_atoms", ""),
            }
        except PublicApiError as exc:
            errors.append(str(exc))
            module_status["esmfold"] = {"status": "error", "error": str(exc)}

        pymol_outputs = generate_pymol_outputs(local_structure_files, outdir, args, warnings)
        if pymol_outputs:
            outputs["pymol"] = pymol_outputs

        summary = {
            "query_gene": "",
            "query_uniprot": "",
            "query_sequence_name": target,
            "organism_query": "",
            "accession": "",
            "entry_name": "",
            "protein_name": "",
            "gene_name": "",
            "organism": "",
            "seq_length": sequence_info["length"],
            "sequence_sha256": sequence_info["sha256"],
            "esmfold_pdb": outputs.get("esmfold_pdb", ""),
            "esmfold_mean_confidence_raw": module_status.get("esmfold", {}).get("mean_confidence_raw", ""),
            "esmfold_confidence_scale": module_status.get("esmfold", {}).get("confidence_scale", ""),
            "esmfold_mean_confidence_0_100": module_status.get("esmfold", {}).get("mean_confidence_0_100", ""),
            "status": status_from_result(errors, warnings),
        }
        summary_path = outdir / "protein_structure_summary.tsv"
        write_tsv(summary_path, [summary], list(summary.keys()))
        outputs["summary_tsv"] = str(summary_path)
        summary_txt = outdir / "summary.txt"
        write_summary_txt(summary_txt, summary)
        outputs["summary_txt"] = str(summary_txt)
        result["status"] = status_from_result(errors, warnings)
        result["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return 0 if not errors else 1, result

    try:
        if args.uniprot:
            accession = args.uniprot.strip()
            search_hint: Dict[str, Any] = {}
        else:
            accession, search_hint, relax_warnings = resolve_uniprot(args.gene, args.organism, args.timeout_sec)
            warnings.extend(relax_warnings)

        entry = fetch_uniprot_entry(accession, args.timeout_sec)
        resolved = uniprot_summary(accession, entry)
        if search_hint and not resolved.get("entry_name"):
            resolved["entry_name"] = search_hint.get("uniProtkbId", accession)
        result["resolved"] = resolved
        seq_length = as_int(resolved.get("seq_length")) or 0
    except ValueError as exc:
        errors.append(str(exc))
        result["status"] = "error"
        return 2, result
    except PublicApiError as exc:
        errors.append(str(exc))
        result["status"] = "error"
        return 3, result

    features: List[Dict[str, Any]] = []

    if "uniprot" in modules:
        features = parse_features(entry)
        feature_columns = ["type", "description", "start", "end", "length"]
        feature_path = outdir / f"{target}.{accession}.features.tsv"
        write_tsv(feature_path, features, feature_columns)
        outputs["features_tsv"] = str(feature_path)
        module_status["uniprot"] = {
            "status": "ok",
            "n_features": len(features),
            "feature_types": sorted({str(f.get("type", "")) for f in features if f.get("type")}),
        }

    if "pdb" in modules:
        try:
            pdb_rows = fetch_pdb_structures(accession, max_pdb=args.max_pdb, timeout=args.timeout_sec)
            pdb_columns = [
                "pdb_id",
                "title",
                "method",
                "resolution_A",
                "n_protein_chains",
                "n_atoms",
                "pubmed_id",
                "authors",
                "deposition_date",
                "rcsb_url",
            ]
            pdb_path = outdir / f"{target}.{accession}.pdb_structures.tsv"
            write_tsv(pdb_path, pdb_rows, pdb_columns)
            outputs["pdb_structures_tsv"] = str(pdb_path)
            pdb_frame = pd.DataFrame(pdb_rows)
            resolution_values = pd.to_numeric(pdb_frame.get("resolution_A", pd.Series(dtype=float)), errors="coerce")
            best_resolution = None if resolution_values.dropna().empty else float(np.nanmin(resolution_values))
            module_status["pdb"] = {
                "status": "ok",
                "n_structures": len(pdb_rows),
                "best_resolution_A": best_resolution,
                "pdb_ids": [r.get("pdb_id") for r in pdb_rows if r.get("pdb_id")],
            }
        except PublicApiError as exc:
            warning = f"pdb_lookup_failed:{exc}"
            warnings.append(warning)
            module_status["pdb"] = {"status": "warning", "error": str(exc)}

    af_entry: Optional[Dict[str, Any]] = None
    if "alphafold" in modules:
        try:
            af_entry = fetch_alphafold_entry(accession, timeout=args.timeout_sec)
            if af_entry:
                af_columns = [
                    "alphafold_id",
                    "uniprot_accession",
                    "gene",
                    "organism",
                    "seq_length",
                    "model_created",
                    "latest_version",
                    "pdb_url",
                    "cif_url",
                    "pae_image_url",
                    "alphafold_page",
                ]
                af_path = outdir / f"{target}.{accession}.alphafold.tsv"
                write_tsv(af_path, [af_entry], af_columns)
                outputs["alphafold_tsv"] = str(af_path)
                module_status["alphafold"] = {
                    "status": "ok",
                    "alphafold_available": True,
                    "latest_version": af_entry.get("latest_version"),
                    "alphafold_page": af_entry.get("alphafold_page"),
                }
            else:
                module_status["alphafold"] = {"status": "ok", "alphafold_available": False}
        except PublicApiError as exc:
            warning = f"alphafold_lookup_failed:{exc}"
            warnings.append(warning)
            module_status["alphafold"] = {"status": "warning", "error": str(exc), "alphafold_available": False}

    if args.download_structure:
        if not af_entry:
            warnings.append("download_structure_requested_but_alphafold_entry_unavailable")
        else:
            downloads: List[str] = []
            choices = ["cif", "pdb"] if args.download_format == "both" else [args.download_format]
            for choice in choices:
                url_key = "cif_url" if choice == "cif" else "pdb_url"
                url = af_entry.get(url_key)
                if not url:
                    warnings.append(f"alphafold_{choice}_url_missing")
                    continue
                suffix = "cif" if choice == "cif" else "pdb"
                dest = outdir / f"{target}.{accession}.alphafold_model.{suffix}"
                try:
                    download_url(str(url), dest, timeout=max(args.timeout_sec, 60))
                    downloads.append(str(dest))
                    local_structure_files.append((f"{target}.{accession}.alphafold_model.{suffix}", dest))
                except PublicApiError as exc:
                    warnings.append(f"download_{choice}_failed:{exc}")
            if downloads:
                outputs["downloaded_structure_files"] = downloads

    if (args.pymol or args.run_pymol) and not local_structure_files:
        if not af_entry:
            warnings.append("pymol_requested_but_alphafold_entry_unavailable")
        else:
            url = af_entry.get("pdb_url")
            if not url:
                warnings.append("pymol_requested_but_alphafold_pdb_url_missing")
            else:
                dest = outdir / f"{target}.{accession}.alphafold_model.pdb"
                try:
                    download_url(str(url), dest, timeout=max(args.timeout_sec, 60))
                    local_structure_files.append((f"{target}.{accession}.alphafold_model.pdb", dest))
                    outputs.setdefault("downloaded_structure_files", []).append(str(dest))
                except PublicApiError as exc:
                    warnings.append(f"pymol_structure_download_failed:{exc}")

    pymol_outputs = generate_pymol_outputs(local_structure_files, outdir, args, warnings)
    if pymol_outputs:
        outputs["pymol"] = pymol_outputs

    if "domain_map" in modules:
        if not features:
            features = parse_features(entry)
        png_path, pdf_path, warning = render_domain_map(features, seq_length, target, accession, outdir)
        if warning:
            warnings.append(warning)
            module_status["domain_map"] = {"status": "warning", "generated": False, "error": warning}
        else:
            outputs["domain_map_png"] = str(png_path)
            outputs["domain_map_pdf"] = str(pdf_path)
            module_status["domain_map"] = {"status": "ok", "generated": True}

    summary = {
        "query_gene": args.gene or "",
        "query_uniprot": args.uniprot or "",
        "organism_query": args.organism,
        "accession": result["resolved"].get("accession", accession),
        "entry_name": result["resolved"].get("entry_name", ""),
        "protein_name": result["resolved"].get("protein_name", ""),
        "gene_name": result["resolved"].get("gene_name", ""),
        "organism": result["resolved"].get("organism", ""),
        "seq_length": result["resolved"].get("seq_length", ""),
        "reviewed": result["resolved"].get("reviewed", ""),
        "n_features": module_status.get("uniprot", {}).get("n_features", ""),
        "n_pdb_structures": module_status.get("pdb", {}).get("n_structures", ""),
        "best_resolution_A": module_status.get("pdb", {}).get("best_resolution_A", ""),
        "alphafold_available": module_status.get("alphafold", {}).get("alphafold_available", ""),
        "status": status_from_result(errors, warnings),
    }
    summary_path = outdir / "protein_structure_summary.tsv"
    write_tsv(summary_path, [summary], list(summary.keys()))
    outputs["summary_tsv"] = str(summary_path)
    summary_txt = outdir / "summary.txt"
    write_summary_txt(summary_txt, summary)
    outputs["summary_txt"] = str(summary_txt)

    result["status"] = status_from_result(errors, warnings)
    result["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return 0 if not errors else 1, result


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    outdir = ensure_outdir(args.outdir)
    try:
        exit_code, result = run(args)
    except ValueError as exc:
        result = {"status": "error", "errors": [str(exc)], "warnings": [], "outputs": {}}
        exit_code = 2
    except RuntimeDependencyError as exc:
        result = {"status": "error", "errors": [str(exc)], "warnings": [], "outputs": {}}
        exit_code = 4
    result_path = outdir / "protein_structure_get.result.json"
    result.setdefault("outputs", {})["result_json"] = str(result_path)
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": result.get("status"), "result_json": str(result_path)}, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
