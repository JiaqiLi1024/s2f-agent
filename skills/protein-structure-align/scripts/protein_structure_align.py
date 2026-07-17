#!/usr/bin/env python3
"""
Protein Structure Align

Fetch or read two protein structures, superimpose structure 2 onto structure 1
using paired C-alpha atoms, and write RMSD tables, plots, an aligned PDB, an
optional HTML viewer, and a machine-readable result JSON.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

RESULT_JSON_NAME = "protein_structure_align.result.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def extract_outdir_from_argv(argv: List[str]) -> Optional[str]:
    for i, item in enumerate(argv):
        if item == "--outdir" and i + 1 < len(argv):
            return argv[i + 1]
        if item.startswith("--outdir="):
            return item.split("=", 1)[1]
    return None


def write_result_json(outdir: str, result: Dict[str, Any]) -> str:
    os.makedirs(outdir, exist_ok=True)
    result_path = os.path.join(outdir, RESULT_JSON_NAME)
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    return result_path


try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    import requests
    from Bio import PDB
    from Bio.PDB import MMCIFParser, PDBParser, Select, Superimposer
except ImportError as exc:
    outdir = extract_outdir_from_argv(sys.argv[1:])
    if outdir:
        write_result_json(
            outdir,
            {
                "status": "failed",
                "skill": "protein-structure-align",
                "started_at": utc_now(),
                "finished_at": utc_now(),
                "error": f"Missing Python dependency: {exc}",
                "recovery": "Install dependencies with: python -m pip install -r skills/protein-structure-align/requirements.txt",
            },
        )
    raise SystemExit(
        "Missing Python dependency. Install with: "
        "python -m pip install -r skills/protein-structure-align/requirements.txt\n"
        f"Import error: {exc}"
    )


RCSB_FILE = "https://files.rcsb.org/download"
ALPHAFOLD_API = "https://alphafold.ebi.ac.uk/api"
HEADERS = {"User-Agent": "s2f-agent-protein-structure-align/0.1"}

STRUCTURE_COLORS = {"structure1": "#1F77B4", "structure2": "#D62728", "divergent": "#FF851B"}


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def sanitize_label(value: str) -> str:
    value = value.strip().replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_.")
    return value or "structure"


def save_fig(fig: "plt.Figure", base: str) -> None:
    fig.savefig(f"{base}.png", dpi=300, bbox_inches="tight")
    fig.savefig(f"{base}.pdf", bbox_inches="tight")
    plt.close(fig)


def get_url(url: str, params: Optional[dict] = None, timeout: int = 60) -> "requests.Response":
    response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


def fetch_pdb_structure(pdb_id: str, outdir: str) -> str:
    pdb_id = pdb_id.upper()
    out_path = os.path.join(outdir, f"{pdb_id}.pdb")
    if os.path.exists(out_path):
        return out_path
    response = get_url(f"{RCSB_FILE}/{pdb_id}.pdb")
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(response.text)
    print(f"[INFO] Downloaded RCSB PDB {pdb_id}: {out_path}")
    return out_path


def select_alphafold_entry(uniprot_acc: str) -> Dict[str, Any]:
    uniprot_acc = uniprot_acc.upper()
    response = get_url(f"{ALPHAFOLD_API}/prediction/{uniprot_acc}")
    entries = response.json()
    if not entries:
        raise ValueError(f"No AlphaFold DB entry found for UniProt accession {uniprot_acc}")

    def model_version(entry: Dict[str, Any]) -> int:
        try:
            return int(entry.get("modelVersion", 0))
        except Exception:
            return 0

    return sorted(entries, key=model_version, reverse=True)[0]


def fetch_alphafold_structure(uniprot_acc: str, outdir: str) -> Tuple[str, Dict[str, Any]]:
    uniprot_acc = uniprot_acc.upper()
    out_path = os.path.join(outdir, f"AF_{uniprot_acc}.pdb")
    entry = select_alphafold_entry(uniprot_acc)
    if os.path.exists(out_path):
        return out_path, entry

    pdb_url = entry.get("pdbUrl")
    if not pdb_url:
        raise ValueError(f"AlphaFold DB entry for {uniprot_acc} does not include a pdbUrl")

    pdb_response = get_url(pdb_url)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(pdb_response.text)
    print(f"[INFO] Downloaded AlphaFold model {uniprot_acc}: {out_path}")
    return out_path, entry


def parse_structure(path: str, structure_id: str) -> "PDB.Structure.Structure":
    suffix = os.path.splitext(path)[1].lower()
    if suffix in {".cif", ".mmcif"}:
        parser = MMCIFParser(QUIET=True)
    else:
        parser = PDBParser(QUIET=True)
    return parser.get_structure(structure_id, path)


def available_chains(structure: "PDB.Structure.Structure") -> List[str]:
    return [chain.get_id() for chain in structure[0].get_chains()]


def resolve_structure_source(args: argparse.Namespace, side: int, outdir: str) -> Dict[str, Any]:
    pdb_id = getattr(args, f"pdb{side}")
    uniprot = getattr(args, f"uniprot{side}")
    local_file = getattr(args, f"file{side}")

    if pdb_id:
        label = pdb_id.upper()
        return {
            "label": label,
            "kind": "rcsb_pdb",
            "requested": pdb_id,
            "path": fetch_pdb_structure(pdb_id, outdir),
        }
    if uniprot:
        acc = uniprot.upper()
        path, entry = fetch_alphafold_structure(uniprot, outdir)
        return {
            "label": f"AF_{acc}",
            "kind": "alphafold_db",
            "requested": uniprot,
            "path": path,
            "pae_doc_url": entry.get("paeDocUrl") or "",
            "pae_image_url": entry.get("paeImageUrl") or "",
            "model_version": entry.get("modelVersion", ""),
        }

    if not local_file:
        raise ValueError(f"Structure {side} source is missing")
    if not os.path.exists(local_file):
        raise FileNotFoundError(f"Local structure file not found for structure {side}: {local_file}")

    label = sanitize_label(os.path.splitext(os.path.basename(local_file))[0])
    return {
        "label": label,
        "kind": "local_file",
        "requested": local_file,
        "path": local_file,
    }


def validate_requested_chain(
    structure: "PDB.Structure.Structure",
    chain_id: Optional[str],
    side_label: str,
) -> None:
    if not chain_id:
        return
    chains = available_chains(structure)
    if chain_id not in chains:
        raise ValueError(f"Requested {side_label} chain '{chain_id}' was not found. Available chains: {','.join(chains)}")


def get_ca_records(
    structure: "PDB.Structure.Structure",
    chain_id: Optional[str] = None,
    res_start: Optional[int] = None,
    res_end: Optional[int] = None,
) -> List[Dict[str, Any]]:
    model = structure[0]
    records: List[Dict[str, Any]] = []
    order = 0

    for chain in model.get_chains():
        cid = chain.get_id()
        if chain_id and cid != chain_id:
            continue
        for residue in chain.get_residues():
            hetflag, resseq, icode = residue.get_id()
            if hetflag.strip():
                continue
            if res_start is not None and resseq < res_start:
                continue
            if res_end is not None and resseq > res_end:
                continue
            if "CA" not in residue:
                continue
            records.append(
                {
                    "atom": residue["CA"],
                    "chain": cid,
                    "resseq": int(resseq),
                    "icode": icode.strip() or "",
                    "resname": residue.get_resname(),
                    "order": order,
                }
            )
            order += 1

    return records


def choose_pairing_method(pairing: str, chain1: Optional[str], chain2: Optional[str]) -> str:
    if pairing != "auto":
        return pairing
    if chain1 or chain2:
        return "resseq"
    return "chain_resseq"


def pair_key(record: Dict[str, Any], method: str) -> Tuple[Any, ...]:
    if method == "chain_resseq":
        return (record["chain"], record["resseq"], record["icode"])
    if method == "resseq":
        return (record["resseq"], record["icode"])
    raise ValueError(f"Unsupported map pairing method: {method}")


def records_to_map(records: List[Dict[str, Any]], method: str, warnings: List[str], label: str) -> Dict[Tuple[Any, ...], Dict[str, Any]]:
    mapped: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    duplicate_count = 0
    for record in records:
        key = pair_key(record, method)
        if key in mapped:
            duplicate_count += 1
            continue
        mapped[key] = record
    if duplicate_count:
        warnings.append(f"{label} had {duplicate_count} duplicate C-alpha pairing keys under pairing={method}; first occurrence was used")
    return mapped


def pair_ca_records(
    records1: List[Dict[str, Any]],
    records2: List[Dict[str, Any]],
    pairing: str,
    chain1: Optional[str],
    chain2: Optional[str],
    warnings: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    if not records1:
        raise ValueError("No C-alpha atoms found in structure 1 after chain/range filtering")
    if not records2:
        raise ValueError("No C-alpha atoms found in structure 2 after chain/range filtering")

    method = choose_pairing_method(pairing, chain1, chain2)

    if method == "order":
        n = min(len(records1), len(records2))
        if n == 0:
            raise ValueError("No C-alpha atoms available for order-based pairing")
        if len(records1) != len(records2):
            warnings.append(
                f"Order-based pairing used the first {n} C-alpha atoms; "
                f"structure 1 had {len(records1)} and structure 2 had {len(records2)}"
            )
        return records1[:n], records2[:n], method

    map1 = records_to_map(records1, method, warnings, "structure1")
    map2 = records_to_map(records2, method, warnings, "structure2")
    common = sorted(set(map1) & set(map2))
    if not common:
        raise ValueError(
            f"No common C-alpha pairs found with pairing={method}. "
            "Specify --chain1/--chain2, restrict --res-start/--res-end, or use --pairing order "
            "for already matched structures with incompatible numbering."
        )
    return [map1[key] for key in common], [map2[key] for key in common], method


def superimpose_structures(
    structure1: "PDB.Structure.Structure",
    structure2: "PDB.Structure.Structure",
    chain1: Optional[str],
    chain2: Optional[str],
    res_start: Optional[int],
    res_end: Optional[int],
    pairing: str,
    warnings: List[str],
) -> Tuple[float, pd.DataFrame, "PDB.Structure.Structure", str, List[List[float]], List[float]]:
    records1 = get_ca_records(structure1, chain1, res_start, res_end)
    records2 = get_ca_records(structure2, chain2, res_start, res_end)
    paired1, paired2, pairing_used = pair_ca_records(records1, records2, pairing, chain1, chain2, warnings)

    if len(paired1) < 3:
        raise ValueError(f"At least 3 paired C-alpha atoms are required for stable superimposition; found {len(paired1)}")

    atoms1 = [record["atom"] for record in paired1]
    atoms2 = [record["atom"] for record in paired2]

    superimposer = Superimposer()
    superimposer.set_atoms(atoms1, atoms2)
    superimposer.apply(list(structure2.get_atoms()))

    rows: List[Dict[str, Any]] = []
    for idx, (record1, record2) in enumerate(zip(paired1, paired2), start=1):
        coord1 = record1["atom"].get_vector().get_array()
        coord2 = record2["atom"].get_vector().get_array()
        distance = float(np.linalg.norm(coord1 - coord2))
        rows.append(
            {
                "pair_index": idx,
                "chain1": record1["chain"],
                "resseq1": record1["resseq"],
                "icode1": record1["icode"],
                "resname1": record1["resname"],
                "chain2": record2["chain"],
                "resseq2": record2["resseq"],
                "icode2": record2["icode"],
                "resname2": record2["resname"],
                "x1": float(coord1[0]),
                "y1": float(coord1[1]),
                "z1": float(coord1[2]),
                "x2": float(coord2[0]),
                "y2": float(coord2[1]),
                "z2": float(coord2[2]),
                "ca_dist_A": distance,
            }
        )

    rotation, translation = superimposer.rotran
    return (
        float(superimposer.rms),
        pd.DataFrame(rows),
        structure2,
        pairing_used,
        rotation.tolist(),
        translation.tolist(),
    )


def save_superimposed_pdb(structure2: "PDB.Structure.Structure", outdir: str, prefix: str) -> str:
    writer = PDB.PDBIO()
    writer.set_structure(structure2)
    out_path = os.path.join(outdir, f"{prefix}.superimposed.pdb")
    writer.save(out_path)
    print(f"[INFO] Superimposed structure 2 saved: {out_path}")
    return out_path


def format_pdb_atom_line(serial: int, atom: Any, residue: Any, chain_id: str) -> str:
    _, resseq, icode = residue.get_id()
    x, y, z = atom.coord
    atom_name = atom.get_fullname()[:4]
    altloc = atom.get_altloc()
    if altloc == " ":
        altloc = ""
    occupancy = atom.get_occupancy()
    bfactor = atom.get_bfactor()
    element = (getattr(atom, "element", "") or atom.get_name()[:1]).strip().upper()
    return (
        f"ATOM  {serial:5d} {atom_name:>4}{altloc[:1]:1}{residue.get_resname():>3} {chain_id[:1]:1}"
        f"{int(resseq):4d}{str(icode).strip()[:1]:1}   "
        f"{float(x):8.3f}{float(y):8.3f}{float(z):8.3f}"
        f"{float(occupancy if occupancy is not None else 1.0):6.2f}"
        f"{float(bfactor if bfactor is not None else 0.0):6.2f}          "
        f"{element[:2]:>2}\n"
    )


def save_aligned_complex_pdb(
    structure1: "PDB.Structure.Structure",
    aligned_structure2: "PDB.Structure.Structure",
    source_chain1: str,
    source_chain2: str,
    complex_chain1: str,
    complex_chain2: str,
    outdir: str,
    prefix: str,
) -> str:
    out_path = os.path.join(outdir, f"{prefix}.aligned_complex.pdb")
    serial = 1
    with open(out_path, "w", encoding="utf-8") as handle:
        for source_structure, source_chain, complex_chain in (
            (structure1, source_chain1, complex_chain1),
            (aligned_structure2, source_chain2, complex_chain2),
        ):
            for residue in standard_ca_residues(source_structure, source_chain):
                for atom in residue.get_atoms():
                    handle.write(format_pdb_atom_line(serial, atom, residue, complex_chain))
                    serial += 1
            handle.write("TER\n")
        handle.write("END\n")
    print(f"[INFO] Aligned hypothetical complex saved: {out_path}")
    return out_path


def plot_per_residue_rmsd(
    per_residue_df: pd.DataFrame,
    rmsd: float,
    label1: str,
    label2: str,
    outdir: str,
    prefix: str,
    close_threshold: float,
    divergence_threshold: float,
) -> str:
    fig, ax = plt.subplots(figsize=(14, 4), dpi=300)
    x = np.arange(len(per_residue_df))
    distances = per_residue_df["ca_dist_A"].values

    colors = []
    for distance in distances:
        if distance < close_threshold:
            colors.append("#2ECC40")
        elif distance < divergence_threshold:
            colors.append("#FF851B")
        else:
            colors.append("#D62728")

    ax.bar(x, distances, color=colors, width=1.0, linewidth=0)
    ax.axhline(close_threshold, color="#2ECC40", lw=0.8, ls="--", alpha=0.8, label=f"{close_threshold:g} A")
    ax.axhline(divergence_threshold, color="#D62728", lw=0.8, ls="--", alpha=0.8, label=f"{divergence_threshold:g} A")

    step = max(1, len(per_residue_df) // 20)
    tick_idx = x[::step]
    tick_labels = [
        f"{row.chain1}:{row.resseq1}" for row in per_residue_df.iloc[::step].itertuples(index=False)
    ]
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(tick_labels, fontsize=8, rotation=45, ha="right")

    ax.set_xlabel("Structure 1 residue", fontsize=11)
    ax.set_ylabel("Post-superposition C-alpha distance (A)", fontsize=11)
    ax.set_title(f"{label1} vs {label2} | global RMSD = {rmsd:.3f} A", fontsize=12)
    ax.legend(fontsize=9, title="Thresholds", title_fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    base = os.path.join(outdir, f"{prefix}.per_residue_rmsd")
    save_fig(fig, base)
    print(f"[INFO] Per-residue RMSD plot saved: {base}.png")
    return f"{base}.png"


def pair_labels(per_residue_df: pd.DataFrame, side: int) -> List[str]:
    return [
        f"{getattr(row, f'chain{side}')}:{getattr(row, f'resseq{side}')}"
        for row in per_residue_df.itertuples(index=False)
    ]


def pairwise_distance_matrix(coords: np.ndarray) -> np.ndarray:
    diff = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2))


def write_matrix_tsv(matrix: np.ndarray, labels: List[str], path: str, col_labels: Optional[List[str]] = None) -> str:
    columns = col_labels if col_labels is not None else labels
    pd.DataFrame(matrix, index=labels, columns=columns).to_csv(path, sep="\t")
    return path


def apply_sparse_ticks(ax: Any, labels: List[str]) -> None:
    if not labels:
        return
    step = max(1, len(labels) // 12)
    ticks = list(range(0, len(labels), step))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([labels[i] for i in ticks], rotation=90, fontsize=6)
    ax.set_yticklabels([labels[i] for i in ticks], fontsize=6)


def save_contact_heatmap(
    matrix: np.ndarray,
    labels: List[str],
    title: str,
    out_base: str,
    is_delta: bool = False,
) -> str:
    fig, ax = plt.subplots(figsize=(7, 6), dpi=300)
    if is_delta:
        im = ax.imshow(matrix, cmap="bwr", vmin=-1, vmax=1, interpolation="nearest")
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, ticks=[-1, 0, 1])
        cbar.ax.set_yticklabels(["lost", "same", "gained"])
    else:
        im = ax.imshow(matrix, cmap="Greys", vmin=0, vmax=1, interpolation="nearest")
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, ticks=[0, 1])
        cbar.ax.set_yticklabels(["no contact", "contact"])

    apply_sparse_ticks(ax, labels)
    ax.set_xlabel("Residue")
    ax.set_ylabel("Residue")
    ax.set_title(title, fontsize=11)
    plt.tight_layout()
    save_fig(fig, out_base)
    return f"{out_base}.png"


def apply_sparse_rect_ticks(ax: Any, row_labels: List[str], col_labels: List[str]) -> None:
    if col_labels:
        x_step = max(1, len(col_labels) // 12)
        x_ticks = list(range(0, len(col_labels), x_step))
        ax.set_xticks(x_ticks)
        ax.set_xticklabels([col_labels[i] for i in x_ticks], rotation=90, fontsize=6)
    if row_labels:
        y_step = max(1, len(row_labels) // 12)
        y_ticks = list(range(0, len(row_labels), y_step))
        ax.set_yticks(y_ticks)
        ax.set_yticklabels([row_labels[i] for i in y_ticks], fontsize=6)


def residue_label(residue: Any, chain_id: str) -> str:
    _, resseq, icode = residue.get_id()
    insertion = str(icode).strip()
    return f"{chain_id}_{residue.get_resname().strip()}{resseq}{insertion}"


def standard_ca_residues(structure: "PDB.Structure.Structure", chain_id: str) -> List[Any]:
    model = structure[0]
    if chain_id not in model.child_dict:
        raise ValueError(f"chain '{chain_id}' was not found. Available chains: {','.join(available_chains(structure))}")
    residues = []
    for residue in model[chain_id]:
        if residue.get_id()[0] == " " and "CA" in residue:
            residues.append(residue)
    if not residues:
        raise ValueError(f"chain '{chain_id}' has no standard residues with C-alpha atoms")
    return residues


def resolve_interface_source_chain(
    structure: "PDB.Structure.Structure",
    requested_chain: Optional[str],
    side_label: str,
) -> str:
    chains = available_chains(structure)
    if requested_chain:
        if requested_chain not in chains:
            raise ValueError(f"{side_label} chain '{requested_chain}' was not found. Available chains: {','.join(chains)}")
        return requested_chain
    if len(chains) == 1:
        return chains[0]
    raise ValueError(
        f"{side_label} has multiple chains ({','.join(chains)}); pass --chain1/--chain2 to choose the protein chain"
    )


def compute_aligned_complex_interface_contact_map(
    structure1: "PDB.Structure.Structure",
    aligned_structure2: "PDB.Structure.Structure",
    source_chain1: str,
    source_chain2: str,
    complex_chain1: str,
    complex_chain2: str,
    threshold: float,
) -> Dict[str, Any]:
    if complex_chain1 == complex_chain2:
        raise ValueError("--interface-chain1 and --interface-chain2 must identify different output complex chain labels")

    residues_a = standard_ca_residues(structure1, source_chain1)
    residues_b = standard_ca_residues(aligned_structure2, source_chain2)
    coords_a = np.asarray([residue["CA"].coord for residue in residues_a], dtype=float)
    coords_b = np.asarray([residue["CA"].coord for residue in residues_b], dtype=float)
    diff = coords_a[:, None, :] - coords_b[None, :, :]
    distances = np.sqrt(np.sum(diff * diff, axis=2))
    contacts = (distances < threshold).astype(int)

    row_labels_all = [residue_label(residue, complex_chain1) for residue in residues_a]
    col_labels_all = [residue_label(residue, complex_chain2) for residue in residues_b]
    row_mask = contacts.any(axis=1)
    col_mask = contacts.any(axis=0)
    n_contacts = int(contacts.sum())

    if row_mask.any() and col_mask.any():
        filtered_contacts = contacts[row_mask][:, col_mask]
        filtered_distances = distances[row_mask][:, col_mask]
        row_labels = [label for label, keep in zip(row_labels_all, row_mask) if keep]
        col_labels = [label for label, keep in zip(col_labels_all, col_mask) if keep]
        interface_only = True
    else:
        filtered_contacts = contacts
        filtered_distances = distances
        row_labels = row_labels_all
        col_labels = col_labels_all
        interface_only = False

    return {
        "contacts": filtered_contacts,
        "distances": filtered_distances,
        "row_labels": row_labels,
        "col_labels": col_labels,
        "n_contacts": n_contacts,
        "n_chain1_residues": len(residues_a),
        "n_chain2_residues": len(residues_b),
        "n_interface_chain1_residues": int(row_mask.sum()),
        "n_interface_chain2_residues": int(col_mask.sum()),
        "interface_only": interface_only,
    }


def save_interface_contact_heatmap(
    matrix: np.ndarray,
    row_labels: List[str],
    col_labels: List[str],
    title: str,
    out_base: str,
) -> str:
    frame = pd.DataFrame(matrix, index=row_labels, columns=col_labels)
    try:
        import seaborn as sns  # type: ignore
    except ImportError:
        print("[WARN] seaborn is not installed; using matplotlib fallback for interface heatmap")
        fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
        im = ax.imshow(matrix, cmap="viridis", vmin=0, vmax=1, aspect="auto", interpolation="nearest")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        ax.set_xticks(range(len(col_labels)))
        ax.set_yticks(range(len(row_labels)))
        ax.set_xticklabels(col_labels, rotation=90, fontsize=6)
        ax.set_yticklabels(row_labels, fontsize=6)
    else:
        fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
        sns.heatmap(frame, cmap="viridis", ax=ax)
        ax.tick_params(axis="x", labelrotation=90, labelsize=6)
        ax.tick_params(axis="y", labelrotation=0, labelsize=6)

    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.tight_layout()
    save_fig(ax.figure, out_base)
    return f"{out_base}.png"


def save_interface_distance_clustermap(
    matrix: np.ndarray,
    row_labels: List[str],
    col_labels: List[str],
    out_base: str,
) -> Optional[str]:
    if matrix.shape[0] < 2 or matrix.shape[1] < 2:
        return None
    try:
        import seaborn as sns  # type: ignore
    except ImportError:
        print("[WARN] seaborn is not installed; interface distance clustermap skipped")
        return None

    frame = pd.DataFrame(matrix, index=row_labels, columns=col_labels)
    try:
        grid = sns.clustermap(frame, metric="euclidean", figsize=(10, 6))
    except Exception as exc:
        print(f"[WARN] interface distance clustermap skipped: {exc}")
        return None
    grid.savefig(f"{out_base}.png", dpi=300, bbox_inches="tight")
    grid.savefig(f"{out_base}.pdf", bbox_inches="tight")
    plt.close(grid.fig)
    return f"{out_base}.png"


def generate_interface_contact_maps(
    args: argparse.Namespace,
    structure1: "PDB.Structure.Structure",
    aligned_structure2: "PDB.Structure.Structure",
    outdir: str,
    prefix: str,
    warnings: List[str],
) -> Optional[Dict[str, Any]]:
    if not args.interface_chain1 and not args.interface_chain2:
        return None
    if not args.interface_chain1 or not args.interface_chain2:
        warnings.append("Interface contact map skipped because both --interface-chain1 and --interface-chain2 are required")
        return None

    try:
        source_chain1 = resolve_interface_source_chain(structure1, args.chain1, "structure 1")
        source_chain2 = resolve_interface_source_chain(aligned_structure2, args.chain2, "structure 2")
        result = compute_aligned_complex_interface_contact_map(
            structure1,
            aligned_structure2,
            source_chain1,
            source_chain2,
            args.interface_chain1,
            args.interface_chain2,
            args.interface_contact_threshold,
        )
        complex_pdb = save_aligned_complex_pdb(
            structure1,
            aligned_structure2,
            source_chain1,
            source_chain2,
            args.interface_chain1,
            args.interface_chain2,
            outdir,
            prefix,
        )
    except ValueError as exc:
        warning = f"Aligned-complex interface contact map skipped: {exc}"
        warnings.append(warning)
        print(f"[WARN] {warning}")
        return None

    contact_path = os.path.join(outdir, f"{prefix}.aligned_complex_interface_contacts.tsv")
    distance_path = os.path.join(outdir, f"{prefix}.aligned_complex_interface_distances.tsv")
    heatmap_base = os.path.join(outdir, f"{prefix}.aligned_complex_interface_contact_map")
    clustermap_base = os.path.join(outdir, f"{prefix}.aligned_complex_interface_distance_clustermap")
    write_matrix_tsv(result["contacts"], result["row_labels"], contact_path, result["col_labels"])
    write_matrix_tsv(np.round(result["distances"], 3), result["row_labels"], distance_path, result["col_labels"])
    png_path = save_interface_contact_heatmap(
        result["contacts"],
        result["row_labels"],
        result["col_labels"],
        (
            f"Aligned complex: chain {args.interface_chain1} vs {args.interface_chain2} "
            f"C-alpha contacts < {args.interface_contact_threshold:g} A"
        ),
        heatmap_base,
    )
    clustermap_png = save_interface_distance_clustermap(
        result["distances"],
        result["row_labels"],
        result["col_labels"],
        clustermap_base,
    )
    print(f"[INFO] Aligned-complex interface contact map saved: {png_path}")
    if clustermap_png:
        print(f"[INFO] Aligned-complex interface distance clustermap saved: {clustermap_png}")
    return {
        "mode": "aligned_hypothetical_complex",
        "source_chain1": source_chain1,
        "source_chain2": source_chain2,
        "complex_chain1": args.interface_chain1,
        "complex_chain2": args.interface_chain2,
        "threshold_A": args.interface_contact_threshold,
        "n_chain1_residues": result["n_chain1_residues"],
        "n_chain2_residues": result["n_chain2_residues"],
        "n_interface_chain1_residues": result["n_interface_chain1_residues"],
        "n_interface_chain2_residues": result["n_interface_chain2_residues"],
        "n_interface_contacts": result["n_contacts"],
        "interface_only_matrix": result["interface_only"],
        "outputs": {
            "aligned_complex_pdb": complex_pdb,
            "contacts_tsv": contact_path,
            "distances_tsv": distance_path,
            "heatmap_png": png_path,
            "heatmap_pdf": f"{heatmap_base}.pdf",
            "distance_clustermap_png": clustermap_png or "",
            "distance_clustermap_pdf": f"{clustermap_base}.pdf" if clustermap_png else "",
        },
    }


def generate_contact_maps(
    per_residue_df: pd.DataFrame,
    outdir: str,
    prefix: str,
    threshold: float,
) -> Dict[str, Any]:
    coords1 = per_residue_df[["x1", "y1", "z1"]].to_numpy(dtype=float)
    coords2 = per_residue_df[["x2", "y2", "z2"]].to_numpy(dtype=float)
    labels1 = pair_labels(per_residue_df, 1)
    labels2 = pair_labels(per_residue_df, 2)

    dist1 = pairwise_distance_matrix(coords1)
    dist2 = pairwise_distance_matrix(coords2)
    contact1 = (dist1 < threshold).astype(int)
    contact2 = (dist2 < threshold).astype(int)
    np.fill_diagonal(contact1, 0)
    np.fill_diagonal(contact2, 0)
    delta = contact2 - contact1

    outputs: Dict[str, str] = {}
    outputs["structure1_contacts_tsv"] = write_matrix_tsv(
        contact1, labels1, os.path.join(outdir, f"{prefix}.contact_map_structure1.tsv")
    )
    outputs["structure2_contacts_tsv"] = write_matrix_tsv(
        contact2, labels2, os.path.join(outdir, f"{prefix}.contact_map_structure2.tsv")
    )
    outputs["delta_contacts_tsv"] = write_matrix_tsv(
        delta, labels1, os.path.join(outdir, f"{prefix}.contact_map_delta.tsv")
    )

    outputs["structure1_contacts_png"] = save_contact_heatmap(
        contact1,
        labels1,
        f"Structure 1 C-alpha contacts < {threshold:g} A",
        os.path.join(outdir, f"{prefix}.contact_map_structure1"),
    )
    outputs["structure2_contacts_png"] = save_contact_heatmap(
        contact2,
        labels2,
        f"Structure 2 C-alpha contacts < {threshold:g} A",
        os.path.join(outdir, f"{prefix}.contact_map_structure2"),
    )
    outputs["delta_contacts_png"] = save_contact_heatmap(
        delta,
        labels1,
        f"Contact map delta: structure2 - structure1 (< {threshold:g} A)",
        os.path.join(outdir, f"{prefix}.contact_map_delta"),
        is_delta=True,
    )

    n_contacts1 = int(contact1.sum() // 2)
    n_contacts2 = int(contact2.sum() // 2)
    n_gained = int(np.sum(delta == 1) // 2)
    n_lost = int(np.sum(delta == -1) // 2)
    print(f"[INFO] Contact maps saved for threshold < {threshold:g} A.")
    return {
        "threshold_A": threshold,
        "n_contacts_structure1": n_contacts1,
        "n_contacts_structure2": n_contacts2,
        "n_contacts_gained": n_gained,
        "n_contacts_lost": n_lost,
        "outputs": outputs,
    }


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def load_json_source(source: str) -> Any:
    if is_url(source):
        return get_url(source, timeout=120).json()
    with open(source, encoding="utf-8") as handle:
        return json.load(handle)


def normalize_pae_payload(payload: Any) -> Tuple[np.ndarray, Optional[float]]:
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        payload = payload[0]
    if isinstance(payload, dict):
        max_error = payload.get("max_predicted_aligned_error")
        for key in ("predicted_aligned_error", "pae", "pae_matrix"):
            if key in payload:
                return np.asarray(payload[key], dtype=float), float(max_error) if max_error is not None else None
        if {"residue1", "residue2", "distance"}.issubset(payload):
            residue1 = np.asarray(payload["residue1"], dtype=int)
            residue2 = np.asarray(payload["residue2"], dtype=int)
            distance = np.asarray(payload["distance"], dtype=float)
            size = int(max(residue1.max(), residue2.max()))
            matrix = np.full((size, size), np.nan, dtype=float)
            matrix[residue1 - 1, residue2 - 1] = distance
            return matrix, float(max_error) if max_error is not None else None
    return np.asarray(payload, dtype=float), None


def plot_pae_matrix(matrix: np.ndarray, max_error: Optional[float], label: str, out_base: str) -> str:
    vmax = max_error if max_error and max_error > 0 else float(np.nanmax(matrix))
    fig, ax = plt.subplots(figsize=(7, 6), dpi=300)
    masked = np.ma.masked_invalid(matrix)
    im = ax.imshow(masked, cmap="viridis_r", vmin=0, vmax=vmax, interpolation="nearest")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Predicted aligned error (A)")
    ax.set_xlabel("Scored residue")
    ax.set_ylabel("Aligned residue")
    ax.set_title(f"PAE: {label}", fontsize=11)
    plt.tight_layout()
    save_fig(fig, out_base)
    return f"{out_base}.png"


def generate_pae_plot(source: str, label: str, side: str, outdir: str, prefix: str) -> Dict[str, Any]:
    payload = load_json_source(source)
    matrix, max_error = normalize_pae_payload(payload)
    if matrix.ndim != 2:
        raise ValueError(f"PAE source for {label} did not resolve to a 2D matrix")

    raw_path = os.path.join(outdir, f"{prefix}.pae_{side}.json")
    with open(raw_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
        handle.write("\n")

    tsv_path = os.path.join(outdir, f"{prefix}.pae_{side}.tsv")
    np.savetxt(tsv_path, matrix, delimiter="\t", fmt="%.4f")
    png_path = plot_pae_matrix(matrix, max_error, label, os.path.join(outdir, f"{prefix}.pae_{side}"))
    print(f"[INFO] PAE plot saved for {label}: {png_path}")
    return {
        "label": label,
        "side": side,
        "source": source,
        "matrix_shape": list(matrix.shape),
        "max_predicted_aligned_error_A": max_error,
        "json": raw_path,
        "tsv": tsv_path,
        "png": png_path,
        "pdf": os.path.join(outdir, f"{prefix}.pae_{side}.pdf"),
    }


def generate_pae_outputs(
    args: argparse.Namespace,
    source1: Dict[str, Any],
    source2: Dict[str, Any],
    outdir: str,
    prefix: str,
    warnings: List[str],
) -> List[Dict[str, Any]]:
    if args.no_pae:
        return []

    pae_sources = [
        ("structure1", source1["label"], args.pae1 or source1.get("pae_doc_url", "")),
        ("structure2", source2["label"], args.pae2 or source2.get("pae_doc_url", "")),
    ]
    outputs: List[Dict[str, Any]] = []
    for side, label, pae_source in pae_sources:
        if not pae_source:
            continue
        try:
            outputs.append(generate_pae_plot(pae_source, label, side, outdir, prefix))
        except Exception as exc:
            message = f"PAE plot skipped for {label}: {exc}"
            warnings.append(message)
            print(f"[WARN] {message}")
    return outputs


class ChainRangeSelect(Select):
    def __init__(self, chain_id: Optional[str], res_start: Optional[int], res_end: Optional[int]) -> None:
        self.chain_id = chain_id
        self.res_start = res_start
        self.res_end = res_end

    def accept_chain(self, chain: Any) -> bool:
        return not self.chain_id or chain.get_id() == self.chain_id

    def accept_residue(self, residue: Any) -> bool:
        hetflag, resseq, _ = residue.get_id()
        if hetflag.strip():
            return False
        if self.res_start is not None and resseq < self.res_start:
            return False
        if self.res_end is not None and resseq > self.res_end:
            return False
        return True


def write_tmalign_input(
    structure: "PDB.Structure.Structure",
    outdir: str,
    prefix: str,
    side: str,
    chain_id: Optional[str],
    res_start: Optional[int],
    res_end: Optional[int],
) -> str:
    out_path = os.path.join(outdir, f"{prefix}.tmalign_{side}.pdb")
    writer = PDB.PDBIO()
    writer.set_structure(structure)
    writer.save(out_path, ChainRangeSelect(chain_id, res_start, res_end))
    return out_path


def resolve_tmalign_binary(binary: str) -> Optional[str]:
    if os.path.sep in binary and os.path.exists(binary):
        return binary
    for candidate in [binary, "TMalign", "tmalign", "TM-align", "TMscore"]:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def parse_tmalign_output(text: str) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    aligned = re.search(
        r"Aligned length\s*=\s*(\d+)\s*,\s*RMSD\s*=\s*([0-9.]+)\s*,\s*Seq_ID=n_identical/n_aligned\s*=\s*([0-9.]+)",
        text,
    )
    if aligned:
        parsed["aligned_length"] = int(aligned.group(1))
        parsed["rmsd_A"] = float(aligned.group(2))
        parsed["seq_id_n_identical_over_n_aligned"] = float(aligned.group(3))

    tm_scores = re.findall(r"TM-score\s*=\s*([0-9.]+)\s*\(([^)]*)\)", text)
    for idx, (score, normalizer) in enumerate(tm_scores, start=1):
        key = f"tm_score_{idx}"
        if "Chain_1" in normalizer or "Structure_1" in normalizer:
            key = "tm_score_normalized_by_structure1"
        elif "Chain_2" in normalizer or "Structure_2" in normalizer:
            key = "tm_score_normalized_by_structure2"
        parsed[key] = float(score)
    if tm_scores:
        parsed["tm_score_max"] = max(float(score) for score, _ in tm_scores)
    return parsed


def run_tmalign(
    args: argparse.Namespace,
    structure1: "PDB.Structure.Structure",
    structure2: "PDB.Structure.Structure",
    outdir: str,
    prefix: str,
    warnings: List[str],
) -> Optional[Dict[str, Any]]:
    if args.no_tmalign:
        warnings.append("TMalign skipped because --no-tmalign was set")
        return None

    binary = resolve_tmalign_binary(args.tmalign_bin)
    if not binary:
        warnings.append("TMalign binary not found; TM-score output was skipped")
        return None

    path1 = write_tmalign_input(structure1, outdir, prefix, "structure1", args.chain1, args.res_start, args.res_end)
    path2 = write_tmalign_input(structure2, outdir, prefix, "structure2", args.chain2, args.res_start, args.res_end)
    raw_path = os.path.join(outdir, f"{prefix}.tmalign.txt")
    tsv_path = os.path.join(outdir, f"{prefix}.tmalign.tsv")

    completed = subprocess.run(
        [binary, path1, path2],
        check=False,
        capture_output=True,
        text=True,
        timeout=args.tmalign_timeout,
    )
    raw_output = completed.stdout + ("\n" + completed.stderr if completed.stderr else "")
    with open(raw_path, "w", encoding="utf-8") as handle:
        handle.write(raw_output)

    if completed.returncode != 0:
        warnings.append(f"TMalign exited with code {completed.returncode}; see {raw_path}")
        return {"status": "failed", "returncode": completed.returncode, "raw_output": raw_path}

    parsed = parse_tmalign_output(raw_output)
    parsed.update({"status": "success", "binary": binary, "raw_output": raw_path, "summary_tsv": tsv_path})
    pd.DataFrame([parsed]).to_csv(tsv_path, sep="\t", index=False)
    print(f"[INFO] TMalign output saved: {tsv_path}")
    return parsed


def add_divergent_styles(view: Any, per_residue_df: pd.DataFrame, threshold: float) -> int:
    divergent = per_residue_df[per_residue_df["ca_dist_A"] >= threshold]
    if divergent.empty:
        return 0

    for chain_id, group in divergent.groupby("chain1"):
        resi = ",".join(str(int(value)) for value in sorted(group["resseq1"].unique()))
        view.addStyle(
            {"model": 0, "chain": chain_id, "resi": resi},
            {"stick": {"color": STRUCTURE_COLORS["divergent"], "radius": 0.22}},
        )

    for chain_id, group in divergent.groupby("chain2"):
        resi = ",".join(str(int(value)) for value in sorted(group["resseq2"].unique()))
        view.addStyle(
            {"model": 1, "chain": chain_id, "resi": resi},
            {"stick": {"color": STRUCTURE_COLORS["divergent"], "radius": 0.22}},
        )

    return int(len(divergent))


def render_superimposed_viewer(
    pdb_path1: str,
    aligned_pdb_path2: str,
    label1: str,
    label2: str,
    per_residue_df: pd.DataFrame,
    rmsd: float,
    outdir: str,
    prefix: str,
    divergence_threshold: float,
) -> Tuple[Optional[str], Optional[str]]:
    try:
        import py3Dmol  # type: ignore
    except ImportError as exc:
        return None, f"py3Dmol not installed; HTML viewer skipped: {exc}"

    with open(pdb_path1, encoding="utf-8", errors="replace") as handle:
        pdb1 = handle.read()
    with open(aligned_pdb_path2, encoding="utf-8", errors="replace") as handle:
        pdb2 = handle.read()

    view = py3Dmol.view(width=950, height=650)
    view.addModel(pdb1, "pdb")
    view.setStyle({"model": 0}, {"cartoon": {"color": STRUCTURE_COLORS["structure1"], "opacity": 0.85}})
    view.addModel(pdb2, "pdb")
    view.setStyle({"model": 1}, {"cartoon": {"color": STRUCTURE_COLORS["structure2"], "opacity": 0.75}})

    n_divergent = add_divergent_styles(view, per_residue_df, divergence_threshold)
    view.setBackgroundColor("white")
    view.zoomTo()

    pct_divergent = 100 * n_divergent / max(len(per_residue_df), 1)
    viewer_html = view._make_html()
    legend = f"""
<div style="font-family:Arial,sans-serif;font-size:13px;padding:10px 8px;background:#f6f6f6;border-top:1px solid #ddd;text-align:center;">
  <span style="color:{STRUCTURE_COLORS['structure1']};font-weight:bold;">&#9632;</span> {label1}
  &nbsp;|&nbsp;
  <span style="color:{STRUCTURE_COLORS['structure2']};font-weight:bold;">&#9632;</span> {label2}
  &nbsp;|&nbsp;
  Global RMSD = <strong>{rmsd:.3f} A</strong>
  &nbsp;|&nbsp;
  <span style="color:{STRUCTURE_COLORS['divergent']};font-weight:bold;">&#9632;</span>
  divergent residues >= {divergence_threshold:g} A ({n_divergent}, {pct_divergent:.1f}%)
</div>
"""
    html = viewer_html.replace("</body>", legend + "\n</body>")
    out_path = os.path.join(outdir, f"{prefix}.superimposed.html")
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(html)
    print(f"[INFO] HTML viewer saved: {out_path}")
    return out_path, None


def collect_outputs(outdir: str, prefix: str) -> Dict[str, List[str]]:
    patterns = {
        "result": [RESULT_JSON_NAME],
        "summary": ["summary.txt", f"{prefix}.alignment_summary.tsv"],
        "per_residue": [f"{prefix}.per_residue_rmsd.tsv"],
        "plots": [
            f"{prefix}.per_residue_rmsd.png",
            f"{prefix}.per_residue_rmsd.pdf",
            f"{prefix}.contact_map_structure1.png",
            f"{prefix}.contact_map_structure1.pdf",
            f"{prefix}.contact_map_structure2.png",
            f"{prefix}.contact_map_structure2.pdf",
            f"{prefix}.contact_map_delta.png",
            f"{prefix}.contact_map_delta.pdf",
            f"{prefix}.aligned_complex_interface_contact_map.png",
            f"{prefix}.aligned_complex_interface_contact_map.pdf",
            f"{prefix}.aligned_complex_interface_distance_clustermap.png",
            f"{prefix}.aligned_complex_interface_distance_clustermap.pdf",
            f"{prefix}.pae_structure1.png",
            f"{prefix}.pae_structure1.pdf",
            f"{prefix}.pae_structure2.png",
            f"{prefix}.pae_structure2.pdf",
        ],
        "contact_maps": [
            f"{prefix}.contact_map_structure1.tsv",
            f"{prefix}.contact_map_structure2.tsv",
            f"{prefix}.contact_map_delta.tsv",
        ],
        "interface_contact_maps": [
            f"{prefix}.aligned_complex_interface_contacts.tsv",
            f"{prefix}.aligned_complex_interface_distances.tsv",
            f"{prefix}.aligned_complex_interface_contact_map.png",
            f"{prefix}.aligned_complex_interface_contact_map.pdf",
            f"{prefix}.aligned_complex_interface_distance_clustermap.png",
            f"{prefix}.aligned_complex_interface_distance_clustermap.pdf",
        ],
        "pae": [
            f"{prefix}.pae_structure1.json",
            f"{prefix}.pae_structure1.tsv",
            f"{prefix}.pae_structure1.png",
            f"{prefix}.pae_structure1.pdf",
            f"{prefix}.pae_structure2.json",
            f"{prefix}.pae_structure2.tsv",
            f"{prefix}.pae_structure2.png",
            f"{prefix}.pae_structure2.pdf",
        ],
        "tmalign": [
            f"{prefix}.tmalign.txt",
            f"{prefix}.tmalign.tsv",
            f"{prefix}.tmalign_structure1.pdb",
            f"{prefix}.tmalign_structure2.pdb",
        ],
        "structures": [f"{prefix}.superimposed.pdb", f"{prefix}.aligned_complex.pdb"],
        "html": [f"{prefix}.superimposed.html"],
    }
    outputs: Dict[str, List[str]] = {}
    for key, names in patterns.items():
        outputs[key] = []
        for name in names:
            path = os.path.join(outdir, name)
            if key == "result":
                outputs[key].append(path)
                continue
            if os.path.exists(path):
                outputs[key].append(path)
    return outputs


def build_summary(
    label1: str,
    label2: str,
    rmsd: float,
    per_residue_df: pd.DataFrame,
    pairing_used: str,
    close_threshold: float,
    divergence_threshold: float,
) -> Dict[str, Any]:
    n_pairs = int(len(per_residue_df))
    n_close = int((per_residue_df["ca_dist_A"] < close_threshold).sum())
    n_medium = int(
        ((per_residue_df["ca_dist_A"] >= close_threshold) & (per_residue_df["ca_dist_A"] < divergence_threshold)).sum()
    )
    n_divergent = int((per_residue_df["ca_dist_A"] >= divergence_threshold).sum())
    return {
        "label1": label1,
        "label2": label2,
        "pairing_used": pairing_used,
        "n_ca_pairs": n_pairs,
        "global_rmsd_A": round(float(rmsd), 6),
        "close_threshold_A": close_threshold,
        "divergence_threshold_A": divergence_threshold,
        "n_close": n_close,
        "n_medium": n_medium,
        "n_divergent": n_divergent,
        "pct_divergent": round(100 * n_divergent / max(n_pairs, 1), 3),
        "max_ca_dist_A": round(float(per_residue_df["ca_dist_A"].max()), 6),
        "median_ca_dist_A": round(float(per_residue_df["ca_dist_A"].median()), 6),
    }


def write_text_summary(outdir: str, summary: Dict[str, Any]) -> str:
    out_path = os.path.join(outdir, "summary.txt")
    with open(out_path, "w", encoding="utf-8") as handle:
        for key, value in summary.items():
            handle.write(f"{key}: {value}\n")
    return out_path


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Superimpose two protein structures and compare RMSD.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group1 = parser.add_mutually_exclusive_group(required=True)
    group1.add_argument("--pdb1", metavar="ID", help="RCSB PDB ID for structure 1")
    group1.add_argument("--uniprot1", metavar="ACC", help="UniProt accession for AlphaFold DB structure 1")
    group1.add_argument("--file1", metavar="PATH", help="Local PDB/mmCIF file for structure 1")

    group2 = parser.add_mutually_exclusive_group(required=True)
    group2.add_argument("--pdb2", metavar="ID", help="RCSB PDB ID for structure 2")
    group2.add_argument("--uniprot2", metavar="ACC", help="UniProt accession for AlphaFold DB structure 2")
    group2.add_argument("--file2", metavar="PATH", help="Local PDB/mmCIF file for structure 2")

    parser.add_argument("--chain1", metavar="CHAIN", default=None, help="Chain ID in structure 1")
    parser.add_argument("--chain2", metavar="CHAIN", default=None, help="Chain ID in structure 2")
    parser.add_argument("--res-start", metavar="N", type=int, default=None, help="First residue number to include")
    parser.add_argument("--res-end", metavar="N", type=int, default=None, help="Last residue number to include")
    parser.add_argument(
        "--pairing",
        choices=["auto", "chain_resseq", "resseq", "order"],
        default="auto",
        help="C-alpha pairing strategy. Default auto uses residue number when chains are specified, otherwise chain+residue.",
    )
    parser.add_argument("--close-threshold", type=float, default=1.0, help="Close residue threshold in Angstroms")
    parser.add_argument("--divergence-threshold", type=float, default=3.0, help="Divergent residue threshold in Angstroms")
    parser.add_argument("--contact-threshold", type=float, default=5.0, help="C-alpha contact threshold in Angstroms")
    parser.add_argument("--no-contact-maps", action="store_true", help="Skip paired contact-map heatmaps and TSV matrices")
    parser.add_argument("--interface-chain1", default=None, help="Output chain label for structure 1 in the aligned hypothetical complex")
    parser.add_argument("--interface-chain2", default=None, help="Output chain label for aligned structure 2 in the aligned hypothetical complex")
    parser.add_argument("--interface-contact-threshold", type=float, default=5.0, help="C-alpha cross-protein interface contact threshold in Angstroms")
    parser.add_argument("--pae1", default=None, help="Local path or URL to PAE JSON for structure 1")
    parser.add_argument("--pae2", default=None, help="Local path or URL to PAE JSON for structure 2")
    parser.add_argument("--no-pae", action="store_true", help="Skip PAE plotting even when AlphaFold DB PAE URLs are available")
    parser.add_argument("--tmalign-bin", default="TMalign", help="TMalign binary name or path")
    parser.add_argument("--tmalign-timeout", type=int, default=120, help="TMalign timeout in seconds")
    parser.add_argument("--no-tmalign", action="store_true", help="Skip optional TMalign TM-score calculation")
    parser.add_argument("--no-viewer", action="store_true", help="Skip py3Dmol HTML viewer generation")
    parser.add_argument("--outdir", default="results", help="Output directory")
    parser.add_argument("--prefix", default=None, help="Output file prefix")

    args = parser.parse_args(argv)
    if args.res_start is not None and args.res_end is not None and args.res_start > args.res_end:
        parser.error("--res-start must be <= --res-end")
    if args.close_threshold < 0 or args.divergence_threshold < 0:
        parser.error("thresholds must be non-negative")
    if args.close_threshold >= args.divergence_threshold:
        parser.error("--close-threshold must be smaller than --divergence-threshold")
    if args.contact_threshold <= 0:
        parser.error("--contact-threshold must be > 0")
    if args.interface_contact_threshold <= 0:
        parser.error("--interface-contact-threshold must be > 0")
    if args.interface_chain1 and len(args.interface_chain1) != 1:
        parser.error("--interface-chain1 must be a single-character output chain label")
    if args.interface_chain2 and len(args.interface_chain2) != 1:
        parser.error("--interface-chain2 must be a single-character output chain label")
    if args.tmalign_timeout <= 0:
        parser.error("--tmalign-timeout must be > 0")
    return args


def run(args: argparse.Namespace) -> Dict[str, Any]:
    started_at = utc_now()
    ensure_dir(args.outdir)
    warnings: List[str] = []

    source1 = resolve_structure_source(args, 1, args.outdir)
    source2 = resolve_structure_source(args, 2, args.outdir)
    label1 = source1["label"]
    label2 = source2["label"]
    prefix = sanitize_label(args.prefix or f"{label1}_vs_{label2}")

    print(f"[INFO] Structure 1: {label1} ({source1['path']})")
    print(f"[INFO] Structure 2: {label2} ({source2['path']})")

    structure1 = parse_structure(source1["path"], label1)
    structure2 = parse_structure(source2["path"], label2)
    chains1 = available_chains(structure1)
    chains2 = available_chains(structure2)
    validate_requested_chain(structure1, args.chain1, "structure 1")
    validate_requested_chain(structure2, args.chain2, "structure 2")

    rmsd, per_residue_df, aligned_structure2, pairing_used, rotation, translation = superimpose_structures(
        structure1=structure1,
        structure2=structure2,
        chain1=args.chain1,
        chain2=args.chain2,
        res_start=args.res_start,
        res_end=args.res_end,
        pairing=args.pairing,
        warnings=warnings,
    )

    aligned_pdb_path = save_superimposed_pdb(aligned_structure2, args.outdir, prefix)
    per_residue_path = os.path.join(args.outdir, f"{prefix}.per_residue_rmsd.tsv")
    per_residue_df.to_csv(per_residue_path, sep="\t", index=False)

    tmalign_summary = run_tmalign(args, structure1, aligned_structure2, args.outdir, prefix, warnings)

    contact_summary: Optional[Dict[str, Any]] = None
    if args.no_contact_maps:
        warnings.append("Contact maps skipped because --no-contact-maps was set")
    else:
        contact_summary = generate_contact_maps(per_residue_df, args.outdir, prefix, args.contact_threshold)

    interface_contact_summary = generate_interface_contact_maps(
        args,
        structure1,
        aligned_structure2,
        args.outdir,
        prefix,
        warnings,
    )

    pae_outputs = generate_pae_outputs(args, source1, source2, args.outdir, prefix, warnings)

    summary = build_summary(
        label1,
        label2,
        rmsd,
        per_residue_df,
        pairing_used,
        args.close_threshold,
        args.divergence_threshold,
    )
    if tmalign_summary:
        for key in (
            "tm_score_normalized_by_structure1",
            "tm_score_normalized_by_structure2",
            "tm_score_max",
            "aligned_length",
            "rmsd_A",
        ):
            if key in tmalign_summary:
                summary[f"tmalign_{key}"] = tmalign_summary[key]
    if contact_summary:
        summary["contact_threshold_A"] = contact_summary["threshold_A"]
        summary["n_contacts_structure1"] = contact_summary["n_contacts_structure1"]
        summary["n_contacts_structure2"] = contact_summary["n_contacts_structure2"]
        summary["n_contacts_gained"] = contact_summary["n_contacts_gained"]
        summary["n_contacts_lost"] = contact_summary["n_contacts_lost"]
    if pae_outputs:
        summary["n_pae_plots"] = len(pae_outputs)
    if interface_contact_summary:
        summary["aligned_complex_interface_contacts"] = interface_contact_summary["n_interface_contacts"]
        summary["aligned_complex_interface_chain1_residues"] = interface_contact_summary["n_interface_chain1_residues"]
        summary["aligned_complex_interface_chain2_residues"] = interface_contact_summary["n_interface_chain2_residues"]
        summary["aligned_complex_source_chain1"] = interface_contact_summary["source_chain1"]
        summary["aligned_complex_source_chain2"] = interface_contact_summary["source_chain2"]

    summary_path = os.path.join(args.outdir, f"{prefix}.alignment_summary.tsv")
    pd.DataFrame([summary]).to_csv(summary_path, sep="\t", index=False)
    write_text_summary(args.outdir, summary)

    plot_per_residue_rmsd(
        per_residue_df,
        rmsd,
        label1,
        label2,
        args.outdir,
        prefix,
        args.close_threshold,
        args.divergence_threshold,
    )

    html_path: Optional[str] = None
    if args.no_viewer:
        warnings.append("HTML viewer skipped because --no-viewer was set")
    else:
        html_path, viewer_warning = render_superimposed_viewer(
            source1["path"],
            aligned_pdb_path,
            label1,
            label2,
            per_residue_df,
            rmsd,
            args.outdir,
            prefix,
            args.divergence_threshold,
        )
        if viewer_warning:
            warnings.append(viewer_warning)
            print(f"[WARN] {viewer_warning}")

    status = "completed_with_warnings" if warnings else "success"
    result = {
        "status": status,
        "skill": "protein-structure-align",
        "started_at": started_at,
        "finished_at": utc_now(),
        "query": {
            "pdb1": args.pdb1,
            "uniprot1": args.uniprot1,
            "file1": args.file1,
            "pdb2": args.pdb2,
            "uniprot2": args.uniprot2,
            "file2": args.file2,
            "chain1": args.chain1,
            "chain2": args.chain2,
            "res_start": args.res_start,
            "res_end": args.res_end,
            "pairing": args.pairing,
            "close_threshold_A": args.close_threshold,
            "divergence_threshold_A": args.divergence_threshold,
            "contact_threshold_A": args.contact_threshold,
            "contact_maps": not args.no_contact_maps,
            "interface_chain1": args.interface_chain1,
            "interface_chain2": args.interface_chain2,
            "interface_contact_threshold_A": args.interface_contact_threshold,
            "pae1": args.pae1,
            "pae2": args.pae2,
            "pae": not args.no_pae,
            "tmalign": not args.no_tmalign,
            "tmalign_bin": args.tmalign_bin,
            "viewer": not args.no_viewer,
            "prefix": prefix,
        },
        "sources": {
            "structure1": {**source1, "available_chains": chains1},
            "structure2": {**source2, "available_chains": chains2},
        },
        "alignment": {
            **summary,
            "rotation_matrix": rotation,
            "translation_vector": translation,
            "superimposed_pdb": aligned_pdb_path,
            "html_viewer": html_path,
            "tmalign": tmalign_summary,
            "contact_maps": contact_summary,
            "interface_contact_maps": interface_contact_summary,
            "pae": pae_outputs,
        },
        "outputs": collect_outputs(args.outdir, prefix),
        "warnings": warnings,
    }
    result_path = write_result_json(args.outdir, result)
    print(f"[DONE] Results written to: {args.outdir}")
    print(f"[DONE] Result JSON: {result_path}")
    return result


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    try:
        run(args)
    except Exception as exc:
        result = {
            "status": "failed",
            "skill": "protein-structure-align",
            "started_at": utc_now(),
            "finished_at": utc_now(),
            "query": vars(args),
            "error": str(exc),
            "recovery": (
                "Check that both structures exist, specify matching chains/ranges, "
                "or use --pairing order for already matched structures with different numbering."
            ),
        }
        result_path = write_result_json(args.outdir, result)
        print(f"[ERROR] {exc}", file=sys.stderr)
        print(f"[ERROR] Result JSON: {result_path}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
