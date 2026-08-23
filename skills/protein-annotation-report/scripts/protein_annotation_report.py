#!/usr/bin/env python3
"""Build standardized TSV/JSON protein annotation reports."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


UNIPROT_BASE = "https://rest.uniprot.org"
USER_AGENT = "s2f-agent-protein-annotation-report/0.1"
CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
AMBIGUOUS_AA = set("BXZJUO")

AA_WEIGHTS = {
    "A": 89.09,
    "R": 174.20,
    "N": 132.12,
    "D": 133.10,
    "C": 121.15,
    "Q": 146.15,
    "E": 147.13,
    "G": 75.07,
    "H": 155.16,
    "I": 131.18,
    "L": 131.18,
    "K": 146.19,
    "M": 149.21,
    "F": 165.19,
    "P": 115.13,
    "S": 105.09,
    "T": 119.12,
    "W": 204.23,
    "Y": 181.19,
    "V": 117.15,
}

KYTE_DOOLITTLE = {
    "A": 1.8,
    "R": -4.5,
    "N": -3.5,
    "D": -3.5,
    "C": 2.5,
    "Q": -3.5,
    "E": -3.5,
    "G": -0.4,
    "H": -3.2,
    "I": 4.5,
    "L": 3.8,
    "K": -3.9,
    "M": 1.9,
    "F": 2.8,
    "P": -1.6,
    "S": -0.8,
    "T": -0.7,
    "W": -0.9,
    "Y": -1.3,
    "V": 4.2,
}

MOTIF_PATTERNS = [
    ("NLS_basic_cluster", r"K[KR]{2,4}"),
    ("NES_leucine_rich", r"[LIVFM].{2,3}[LIVFM].{2,3}[LIVFM].{1,3}[LIVFM]"),
    ("RGD_integrin_binding", r"RGD"),
    ("CAAX_prenylation", r"C[AVILM]{2}[AVILM]$"),
    ("N_glycosylation", r"N[^P][ST]"),
    ("SH2_binding_candidate", r"Y[A-Z]{2}[LIVMF]"),
    ("SH3_binding_candidate", r"P.{2}P"),
]

DEFAULT_UNIPROT_FEATURE_TYPES = {
    "Active site",
    "Binding site",
    "Calcium binding",
    "Chain",
    "Coiled coil",
    "Compositional bias",
    "Cross-link",
    "Disulfide bond",
    "DNA binding",
    "Domain",
    "Glycosylation",
    "Helix",
    "Initiator methionine",
    "Intramembrane",
    "Lipidation",
    "Modified residue",
    "Motif",
    "Peptide",
    "Propeptide",
    "Region",
    "Repeat",
    "Signal peptide",
    "Site",
    "Transit peptide",
    "Transmembrane",
    "Topological domain",
    "Turn",
    "Zinc finger",
}

SUMMARY_COLUMNS = [
    "query_id",
    "input_type",
    "source_ids",
    "uniprot_accession",
    "reviewed",
    "protein_name",
    "gene_names",
    "organism",
    "length",
    "sequence_sha256",
    "molecular_weight_da",
    "gravy",
    "aromaticity",
    "predicted_function",
    "subcellular_location",
    "domains",
    "motifs",
    "degrons",
    "interpro_ids",
    "pfam_ids",
    "eggnog_ogs",
    "go_terms",
    "ec_numbers",
    "kegg_ko",
    "pathways",
    "mean_disorder_score",
    "fraction_disordered",
    "n_disordered_residues",
    "n_idr_regions",
    "longest_idr",
    "n_binding_regions",
    "n_linker_regions",
    "pLLPS",
    "mean_aggregation_score",
    "fraction_aggregation_prone",
    "n_aggregation_prone_residues",
    "n_aggregation_regions",
    "n_dpr_regions",
    "n_hotspot_regions",
    "n_degron_candidates",
    "n_terminal_degrons",
    "n_phosphodegrons",
    "feature_count",
    "annotation_sources",
    "warnings",
]

FEATURE_COLUMNS = [
    "query_id",
    "source",
    "feature_type",
    "start",
    "end",
    "length",
    "accession",
    "name",
    "description",
    "database",
    "interpro_accession",
    "interpro_description",
    "go_terms",
    "pathways",
    "score",
    "evalue",
    "evidence",
    "note",
]


class ReportBuilder:
    def __init__(self) -> None:
        self.summaries: Dict[str, Dict[str, Any]] = {}
        self.feature_rows: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.source_files: List[str] = []
        self.raw_uniprot_outputs: List[str] = []

    def summary(self, query_id: str, input_type: str = "") -> Dict[str, Any]:
        query_id = query_id or "protein"
        if query_id not in self.summaries:
            self.summaries[query_id] = {column: "" for column in SUMMARY_COLUMNS}
            self.summaries[query_id]["query_id"] = query_id
            self.summaries[query_id]["input_type"] = input_type
            self.summaries[query_id]["_sets"] = {
                "source_ids": set(),
                "domains": set(),
                "motifs": set(),
                "degrons": set(),
                "interpro_ids": set(),
                "pfam_ids": set(),
                "eggnog_ogs": set(),
                "go_terms": set(),
                "ec_numbers": set(),
                "kegg_ko": set(),
                "pathways": set(),
                "annotation_sources": set(),
                "warnings": set(),
            }
        elif input_type and not self.summaries[query_id].get("input_type"):
            self.summaries[query_id]["input_type"] = input_type
        return self.summaries[query_id]

    def add_set(self, query_id: str, field: str, values: Iterable[Any]) -> None:
        summary = self.summary(query_id)
        store = summary["_sets"].setdefault(field, set())
        for value in values:
            text = str(value).strip()
            if text and text not in {"-", "NA", "None", "none"}:
                store.add(text)

    def set_if_present(self, query_id: str, field: str, value: Any) -> None:
        text = "" if value is None else str(value).strip()
        if text:
            summary = self.summary(query_id)
            if not summary.get(field):
                summary[field] = text

    def add_warning(self, warning: str, query_id: Optional[str] = None) -> None:
        if warning not in self.warnings:
            self.warnings.append(warning)
        if query_id:
            self.add_set(query_id, "warnings", [warning])

    def add_feature(self, row: Dict[str, Any]) -> None:
        complete = {column: "" for column in FEATURE_COLUMNS}
        complete.update({key: value for key, value in row.items() if key in complete})
        query_id = str(complete.get("query_id") or "protein")
        self.feature_rows.append(complete)
        source = str(complete.get("source") or "")
        if source:
            self.add_set(query_id, "annotation_sources", [source])
        feature_type = str(complete.get("feature_type") or "")
        name = str(complete.get("name") or complete.get("description") or "")
        database = str(complete.get("database") or "")
        if feature_type.lower() in {"domain", "region", "repeat", "family"} or "domain" in feature_type.lower():
            self.add_set(query_id, "domains", [name])
        if "motif" in feature_type.lower() or "site" in feature_type.lower():
            self.add_set(query_id, "motifs", [name])
        if "degron" in feature_type.lower() or "degron" in name.lower():
            self.add_set(query_id, "motifs", [name])
            self.add_set(query_id, "degrons", [name])
        if complete.get("interpro_accession"):
            self.add_set(query_id, "interpro_ids", [complete["interpro_accession"]])
        if database.lower() == "pfam" or str(complete.get("accession", "")).startswith("PF"):
            self.add_set(query_id, "pfam_ids", [complete.get("accession")])
        self.add_set(query_id, "go_terms", split_multi(complete.get("go_terms", "")))
        self.add_set(query_id, "pathways", split_multi(complete.get("pathways", "")))

    def finalize(self) -> List[Dict[str, str]]:
        feature_counts: Dict[str, int] = {}
        degron_counts: Dict[str, int] = {}
        terminal_degron_counts: Dict[str, int] = {}
        phosphodegron_counts: Dict[str, int] = {}
        for row in self.feature_rows:
            query_id = str(row.get("query_id") or "protein")
            feature_counts[query_id] = feature_counts.get(query_id, 0) + 1
            feature_text = " ".join(
                str(row.get(key) or "")
                for key in ("feature_type", "name", "description", "note")
            ).lower()
            if "degron" in feature_text:
                degron_counts[query_id] = degron_counts.get(query_id, 0) + 1
                if "terminal" in feature_text or "n-degron" in feature_text or "c-degron" in feature_text:
                    terminal_degron_counts[query_id] = terminal_degron_counts.get(query_id, 0) + 1
                if "phosphodegron" in feature_text or "phospho" in feature_text:
                    phosphodegron_counts[query_id] = phosphodegron_counts.get(query_id, 0) + 1

        rows: List[Dict[str, str]] = []
        for query_id in sorted(self.summaries):
            summary = self.summaries[query_id]
            sets = summary.pop("_sets")
            for field, values in sets.items():
                summary[field] = join_values(values)
            summary["feature_count"] = str(feature_counts.get(query_id, 0))
            summary["n_degron_candidates"] = str(degron_counts.get(query_id, 0))
            summary["n_terminal_degrons"] = str(terminal_degron_counts.get(query_id, 0))
            summary["n_phosphodegrons"] = str(phosphodegron_counts.get(query_id, 0))
            rows.append({column: stringify(summary.get(column, "")) for column in SUMMARY_COLUMNS})
        return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create standardized protein annotation report tables.")
    parser.add_argument("--sequence", help="Single amino-acid sequence.")
    parser.add_argument("--sequence-name", default="query_sequence", help="Identifier for --sequence.")
    parser.add_argument("--fasta", action="append", default=[], help="Protein FASTA file; may be repeated.")
    parser.add_argument("--uniprot", action="append", default=[], help="UniProt accession; may be repeated.")
    parser.add_argument("--gene", action="append", default=[], help="Gene symbol to resolve through UniProt.")
    parser.add_argument("--protein-name", action="append", default=[], help="Protein name text to resolve through UniProt.")
    parser.add_argument("--organism", default="human", help="Organism name or NCBI taxon ID; default human.")
    parser.add_argument("--raw-uniprot-json", action="append", default=[], help="Local UniProtKB JSON file.")
    parser.add_argument("--save-raw-uniprot", action="store_true", help="Save fetched UniProt JSON next to the report.")
    parser.add_argument(
        "--all-uniprot-features",
        action="store_true",
        help="Export all UniProt feature types, including variants and sequence conflicts.",
    )
    parser.add_argument("--interpro-tsv", action="append", default=[], help="InterProScan TSV output; may be repeated.")
    parser.add_argument("--eggnog-annotations", action="append", default=[], help="eggNOG .emapper.annotations file.")
    parser.add_argument("--idr-summary-tsv", action="append", default=[], help="protein_idr_summary.tsv from protein-idr-disorder-annotation.")
    parser.add_argument("--idr-regions-tsv", action="append", default=[], help="protein_idr_regions.tsv from protein-idr-disorder-annotation.")
    parser.add_argument("--llps-summary-tsv", action="append", default=[], help="protein_llps_summary.tsv from protein-idr-disorder-annotation.")
    parser.add_argument("--llps-features-tsv", action="append", default=[], help="protein_llps_features.tsv from protein-idr-disorder-annotation.")
    parser.add_argument("--degron-features-tsv", action="append", default=[], help="protein_degron_features.tsv from protein-degron-annotation.")
    parser.add_argument("--features-tsv", action="append", default=[], help="Existing features.tsv file to import.")
    parser.add_argument("--motifs-tsv", action="append", default=[], help="Existing motifs.tsv file to import.")
    parser.add_argument(
        "--imported-motif-base",
        choices=["zero-based-half-open", "one-based-closed"],
        default="zero-based-half-open",
        help="Coordinate convention for imported motifs.tsv files.",
    )
    parser.add_argument(
        "--annotation-result-json",
        action="append",
        default=[],
        help="protein_domain_motif_annotation.result.json from the domain/motif skill.",
    )
    parser.add_argument(
        "--idr-result-json",
        action="append",
        default=[],
        help="protein_idr_disorder_annotation.result.json from the IDR/disorder skill.",
    )
    parser.add_argument(
        "--degron-result-json",
        action="append",
        default=[],
        help="protein_degron_annotation.result.json from the degron annotation skill.",
    )
    parser.add_argument("--run-id", default=None, help="Run label; defaults to best input label.")
    parser.add_argument("--outdir", default="output/protein-annotation-report", help="Output directory.")
    parser.add_argument("--timeout-sec", type=int, default=30)
    parser.add_argument("--no-uniprot", action="store_true", help="Disable UniProt API calls.")
    parser.add_argument("--allow-ambiguous-aa", action="store_true", help="Allow B/X/Z/J/U/O in local sequences.")
    return parser.parse_args()


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def join_values(values: Iterable[Any]) -> str:
    return ";".join(sorted({str(value).strip() for value in values if str(value).strip()}))


def split_multi(value: Any) -> List[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text or text in {"-", "NA"}:
        return []
    parts = re.split(r"[;,|]\s*|\s*,\s*", text)
    return [part.strip() for part in parts if part.strip() and part.strip() != "-"]


def safe_name(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return clean.strip("._-") or "protein_annotation"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def taxon_id(organism: str) -> str:
    aliases = {"human": "9606", "mouse": "10090", "rat": "10116", "arabidopsis": "3702"}
    return aliases.get(organism.strip().lower(), organism.strip())


def normalize_sequence(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        lines.append(stripped)
    return "".join(lines).replace(" ", "").replace("\t", "").upper()


def validate_sequence(sequence: str, allow_ambiguous: bool = False) -> List[str]:
    allowed = CANONICAL_AA | (AMBIGUOUS_AA if allow_ambiguous else set())
    invalid = sorted({char for char in sequence if char not in allowed})
    return invalid


def read_fasta(path: Path) -> List[Tuple[str, str, str]]:
    records: List[Tuple[str, str, str]] = []
    header: Optional[str] = None
    seq_parts: List[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(">"):
                if header is not None:
                    sequence = normalize_sequence("\n".join(seq_parts))
                    records.append((header.split()[0], header, sequence))
                header = stripped[1:].strip() or f"record_{len(records) + 1}"
                seq_parts = []
            else:
                seq_parts.append(stripped)
    if header is not None:
        sequence = normalize_sequence("\n".join(seq_parts))
        records.append((header.split()[0], header, sequence))
    return records


def sequence_properties(sequence: str) -> Dict[str, Any]:
    length = len(sequence)
    weights = [AA_WEIGHTS.get(aa, 0.0) for aa in sequence]
    hydropathy = [KYTE_DOOLITTLE.get(aa, 0.0) for aa in sequence if aa in KYTE_DOOLITTLE]
    molecular_weight = sum(weights) - max(length - 1, 0) * 18.015
    gravy = sum(hydropathy) / len(hydropathy) if hydropathy else ""
    aromatic = sum(sequence.count(aa) for aa in "FWY") / length if length else ""
    return {
        "length": length,
        "sequence_sha256": sha256_text(sequence),
        "molecular_weight_da": round(molecular_weight, 3) if length else "",
        "gravy": round(gravy, 4) if gravy != "" else "",
        "aromaticity": round(aromatic, 4) if aromatic != "" else "",
    }


def add_sequence_record(builder: ReportBuilder, query_id: str, sequence: str, input_type: str, allow_ambiguous: bool) -> None:
    summary = builder.summary(query_id, input_type)
    invalid = validate_sequence(sequence, allow_ambiguous=allow_ambiguous)
    if invalid:
        builder.add_warning(f"invalid_amino_acid_codes:{','.join(invalid)}", query_id)
    props = sequence_properties(sequence)
    for field, value in props.items():
        summary[field] = stringify(value)
    builder.add_set(query_id, "annotation_sources", ["local_sequence"])
    scan_sequence_motifs(builder, query_id, sequence)


def scan_sequence_motifs(builder: ReportBuilder, query_id: str, sequence: str) -> None:
    for motif_name, pattern in MOTIF_PATTERNS:
        for match in re.finditer(pattern, sequence):
            start = match.start() + 1
            end = match.end()
            builder.add_feature(
                {
                    "query_id": query_id,
                    "source": "local_motif_scan",
                    "feature_type": "motif_candidate",
                    "start": start,
                    "end": end,
                    "length": end - start + 1,
                    "name": motif_name,
                    "description": match.group(0),
                    "evidence": "regex_scan",
                    "note": "Heuristic motif candidate; validate with domain databases or experiments.",
                }
            )


def url_json(path: str, params: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    query = urllib.parse.urlencode(params, doseq=True)
    url = f"{UNIPROT_BASE}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GET {url} failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {url} failed: {exc.reason}") from exc


def resolve_uniprot_by_query(kind: str, value: str, organism: str, timeout: int) -> Tuple[str, List[str]]:
    taxon = taxon_id(organism)
    fields = "accession,id,gene_names,protein_name,length,organism_name,reviewed"
    warnings: List[str] = []
    if kind == "gene":
        queries = [
            f"gene_exact:{value} AND organism_id:{taxon} AND reviewed:true",
            f"gene_exact:{value} AND organism_id:{taxon}",
            f"gene:{value} AND organism_id:{taxon} AND reviewed:true",
            f"gene:{value} AND organism_id:{taxon}",
        ]
    else:
        escaped = value.replace('"', '\\"')
        queries = [
            f'protein_name:"{escaped}" AND organism_id:{taxon} AND reviewed:true',
            f'protein_name:"{escaped}" AND organism_id:{taxon}',
            f'"{escaped}" AND organism_id:{taxon} AND reviewed:true',
            f'"{escaped}" AND organism_id:{taxon}',
        ]

    for idx, query in enumerate(queries):
        data = url_json(
            "uniprotkb/search",
            {"query": query, "fields": fields, "format": "json", "size": 5},
            timeout=timeout,
        )
        results = data.get("results") or []
        if results:
            if idx > 0:
                warnings.append(f"uniprot_resolution_relaxed_query:{query}")
            accession = results[0].get("primaryAccession")
            if not accession:
                raise RuntimeError("UniProt search result did not contain primaryAccession")
            return accession, warnings
    raise RuntimeError(f"Could not resolve {kind} '{value}' for organism '{organism}' in UniProt")


def fetch_uniprot_entry(accession: str, timeout: int) -> Dict[str, Any]:
    return url_json(f"uniprotkb/{accession}", {"format": "json"}, timeout=timeout)


def text_value(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("value") or "")
    return str(item or "")


def extract_protein_name(entry: Dict[str, Any]) -> str:
    desc = entry.get("proteinDescription") or {}
    recommended = desc.get("recommendedName") or {}
    full_name = recommended.get("fullName") or {}
    value = text_value(full_name)
    if value:
        return value
    submission_names = desc.get("submissionNames") or []
    if submission_names:
        full_name = (submission_names[0] or {}).get("fullName") or {}
        value = text_value(full_name)
        if value:
            return value
    return str(entry.get("uniProtkbId") or entry.get("primaryAccession") or "")


def extract_gene_names(entry: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for gene in entry.get("genes") or []:
        primary = (gene.get("geneName") or {}).get("value")
        if primary:
            names.append(str(primary))
        for synonym in gene.get("synonyms") or []:
            value = synonym.get("value")
            if value:
                names.append(str(value))
    return sorted(set(names))


def is_reviewed(entry: Dict[str, Any]) -> bool:
    entry_type = str(entry.get("entryType") or "")
    return "reviewed" in entry_type.lower() or entry.get("reviewed") is True


def feature_location(feature: Dict[str, Any]) -> Tuple[str, str, str]:
    location = feature.get("location") or {}
    start = ((location.get("start") or {}).get("value"))
    end = ((location.get("end") or {}).get("value"))
    start_s = stringify(start)
    end_s = stringify(end)
    length = ""
    try:
        length = str(int(end_s) - int(start_s) + 1)
    except (TypeError, ValueError):
        pass
    return start_s, end_s, length


def extract_comment_texts(entry: Dict[str, Any], comment_type: str) -> List[str]:
    values: List[str] = []
    for comment in entry.get("comments") or []:
        if str(comment.get("commentType") or "").upper() != comment_type.upper():
            continue
        for text in comment.get("texts") or []:
            value = text.get("value")
            if value:
                values.append(str(value))
        if comment_type.upper() == "SUBCELLULAR LOCATION":
            for location_block in comment.get("subcellularLocations") or []:
                location = (location_block.get("location") or {}).get("value")
                topology = (location_block.get("topology") or {}).get("value")
                orientation = (location_block.get("orientation") or {}).get("value")
                values.extend([v for v in (location, topology, orientation) if v])
    return values


def extract_xrefs(entry: Dict[str, Any]) -> Dict[str, Set[str]]:
    xrefs: Dict[str, Set[str]] = {
        "go_terms": set(),
        "interpro_ids": set(),
        "pfam_ids": set(),
        "kegg_ko": set(),
        "pathways": set(),
    }
    for ref in entry.get("uniProtKBCrossReferences") or []:
        db = str(ref.get("database") or "")
        rid = str(ref.get("id") or "")
        if db == "GO" and rid:
            xrefs["go_terms"].add(rid)
        elif db == "InterPro" and rid:
            xrefs["interpro_ids"].add(rid)
        elif db == "Pfam" and rid:
            xrefs["pfam_ids"].add(rid)
        elif db in {"KEGG", "KO"} and rid:
            xrefs["kegg_ko"].add(rid)
        elif db == "Reactome" and rid:
            xrefs["pathways"].add(f"Reactome:{rid}")
    return xrefs


def extract_ec_numbers(entry: Dict[str, Any]) -> Set[str]:
    values: Set[str] = set()
    desc = entry.get("proteinDescription") or {}
    recommended = desc.get("recommendedName") or {}
    for ec in recommended.get("ecNumbers") or []:
        value = ec.get("value")
        if value:
            values.add(str(value))
    for comment in entry.get("comments") or []:
        reaction = comment.get("reaction") or {}
        ec = reaction.get("ecNumber")
        if ec:
            values.add(str(ec))
    return values


def add_uniprot_entry(
    builder: ReportBuilder,
    entry: Dict[str, Any],
    query_label: str = "",
    all_uniprot_features: bool = False,
) -> str:
    accession = str(entry.get("primaryAccession") or query_label or "uniprot")
    query_id = accession
    summary = builder.summary(query_id, "uniprot")
    sequence = (entry.get("sequence") or {}).get("value") or ""
    organism = (entry.get("organism") or {}).get("scientificName") or ""
    summary["uniprot_accession"] = accession
    summary["reviewed"] = stringify(is_reviewed(entry))
    summary["protein_name"] = extract_protein_name(entry)
    summary["gene_names"] = join_values(extract_gene_names(entry))
    summary["organism"] = str(organism)
    if sequence:
        props = sequence_properties(sequence)
        for field, value in props.items():
            summary[field] = stringify(value)
        scan_sequence_motifs(builder, query_id, sequence)
    builder.add_set(query_id, "source_ids", [accession, entry.get("uniProtkbId")])
    builder.add_set(query_id, "annotation_sources", ["UniProtKB"])
    builder.add_set(query_id, "go_terms", extract_xrefs(entry)["go_terms"])
    builder.add_set(query_id, "interpro_ids", extract_xrefs(entry)["interpro_ids"])
    builder.add_set(query_id, "pfam_ids", extract_xrefs(entry)["pfam_ids"])
    builder.add_set(query_id, "kegg_ko", extract_xrefs(entry)["kegg_ko"])
    builder.add_set(query_id, "pathways", extract_xrefs(entry)["pathways"])
    builder.add_set(query_id, "ec_numbers", extract_ec_numbers(entry))

    functions = extract_comment_texts(entry, "FUNCTION")
    subcellular = extract_comment_texts(entry, "SUBCELLULAR LOCATION")
    if functions:
        summary["predicted_function"] = " ".join(functions)
    if subcellular:
        summary["subcellular_location"] = join_values(subcellular)

    skipped_feature_types: Set[str] = set()
    for feature in entry.get("features") or []:
        start, end, length = feature_location(feature)
        feature_type = str(feature.get("type") or "Other")
        if not all_uniprot_features and feature_type not in DEFAULT_UNIPROT_FEATURE_TYPES:
            skipped_feature_types.add(feature_type)
            continue
        description = str(feature.get("description") or feature_type)
        evidences = []
        for evidence in feature.get("evidences") or []:
            code = evidence.get("evidenceCode") or evidence.get("code")
            source = evidence.get("source")
            evidences.append(":".join([str(x) for x in (code, source) if x]))
        builder.add_feature(
            {
                "query_id": query_id,
                "source": "UniProtKB",
                "feature_type": feature_type,
                "start": start,
                "end": end,
                "length": length,
                "accession": feature.get("featureId") or "",
                "name": description,
                "description": description,
                "database": "UniProtKB",
                "evidence": join_values(evidences),
                "note": "UniProt feature coordinates are 1-based closed.",
            }
        )
    if skipped_feature_types:
        builder.add_warning(
            "uniprot_feature_types_filtered:"
            + ",".join(sorted(skipped_feature_types))
            + ";pass --all-uniprot-features to export every UniProt feature",
            query_id,
        )
    return query_id


def read_tsv_rows(path: Path) -> List[Dict[str, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return []
    header_index: Optional[int] = None
    headers: List[str] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        candidate = stripped.lstrip("#")
        fields = candidate.split("\t")
        lower_fields = {field.lower() for field in fields}
        if "query" in lower_fields or "#query" in lower_fields:
            header_index = idx
            headers = fields
            break
        if {"type", "start", "end"}.issubset(lower_fields) or {"motif", "start", "end"}.issubset(lower_fields):
            header_index = idx
            headers = fields
            break
        if not stripped.startswith("#"):
            header_index = idx
            headers = fields
            break
    if header_index is None:
        return []
    rows: List[Dict[str, str]] = []
    for line in lines[header_index + 1 :]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        values = stripped.split("\t")
        row = {headers[i]: values[i] if i < len(values) else "" for i in range(len(headers))}
        rows.append(row)
    return rows


def parse_interpro_tsv(builder: ReportBuilder, path: Path) -> None:
    builder.source_files.append(str(path))
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for parts in reader:
            if not parts or parts[0].startswith("#"):
                continue
            if parts[0].lower() in {"protein_accession", "protein"}:
                continue
            while len(parts) < 15:
                parts.append("")
            query_id = parts[0]
            sequence_length = parts[2]
            analysis = parts[3]
            signature_accession = parts[4]
            signature_description = parts[5]
            start = parts[6]
            end = parts[7]
            score = parts[8]
            interpro_accession = parts[11]
            interpro_description = parts[12]
            go_terms = parts[13]
            pathways = parts[14]

            summary = builder.summary(query_id, "interproscan6")
            if sequence_length and not summary.get("length"):
                summary["length"] = sequence_length
            builder.add_set(query_id, "annotation_sources", ["InterProScan6"])
            builder.add_set(query_id, "interpro_ids", [interpro_accession])
            builder.add_set(query_id, "go_terms", split_multi(go_terms))
            builder.add_set(query_id, "pathways", split_multi(pathways))
            if signature_accession.startswith("PF"):
                builder.add_set(query_id, "pfam_ids", [signature_accession])
            domain_label = interpro_description or signature_description
            if domain_label:
                builder.add_set(query_id, "domains", [domain_label])

            builder.add_feature(
                {
                    "query_id": query_id,
                    "source": f"InterProScan6:{analysis}" if analysis else "InterProScan6",
                    "feature_type": "domain_or_signature_match",
                    "start": start,
                    "end": end,
                    "length": interval_length(start, end),
                    "accession": signature_accession,
                    "name": signature_description,
                    "description": domain_label,
                    "database": analysis,
                    "interpro_accession": interpro_accession,
                    "interpro_description": interpro_description,
                    "go_terms": go_terms,
                    "pathways": pathways,
                    "score": score,
                    "note": "InterProScan TSV coordinates are protein positions from the source output.",
                }
            )


def parse_eggnog_annotations(builder: ReportBuilder, path: Path) -> None:
    builder.source_files.append(str(path))
    rows = read_tsv_rows(path)
    for row in rows:
        query_id = row.get("query") or row.get("#query") or row.get("query_name") or row.get("qseqid") or ""
        if not query_id:
            continue
        description = row.get("Description", "")
        preferred_name = row.get("Preferred_name", "")
        gos = row.get("GOs", "")
        ec = row.get("EC", "")
        ko = row.get("KEGG_ko", "")
        pathways = row.get("KEGG_Pathway", "")
        ogs = row.get("eggNOG_OGs", "")
        pfams = row.get("PFAMs", "")
        seed_ortholog = row.get("seed_ortholog", "")
        evalue = row.get("evalue", "")
        score = row.get("score", "")

        summary = builder.summary(query_id, "eggnog")
        builder.add_set(query_id, "annotation_sources", ["eggNOG-mapper"])
        builder.add_set(query_id, "source_ids", [seed_ortholog])
        builder.add_set(query_id, "eggnog_ogs", split_multi(ogs))
        builder.add_set(query_id, "pfam_ids", split_multi(pfams))
        builder.add_set(query_id, "go_terms", split_multi(gos))
        builder.add_set(query_id, "ec_numbers", split_multi(ec))
        builder.add_set(query_id, "kegg_ko", split_multi(ko))
        builder.add_set(query_id, "pathways", split_multi(pathways))
        if description and not summary.get("predicted_function"):
            summary["predicted_function"] = description
        if preferred_name and not summary.get("protein_name"):
            summary["protein_name"] = preferred_name

        builder.add_feature(
            {
                "query_id": query_id,
                "source": "eggNOG-mapper",
                "feature_type": "orthology_function",
                "accession": seed_ortholog,
                "name": preferred_name,
                "description": description,
                "database": "eggNOG",
                "go_terms": gos,
                "pathways": pathways,
                "score": score,
                "evalue": evalue,
                "evidence": ogs,
                "note": "Orthology-based functional transfer; no residue coordinates.",
            }
        )


def parse_idr_summary_tsv(builder: ReportBuilder, path: Path) -> None:
    builder.source_files.append(str(path))
    rows = read_tsv_rows(path)
    for row in rows:
        query_id = row.get("query_id") or row.get("protein_id") or ""
        if not query_id:
            continue
        summary = builder.summary(query_id, "protein_idr")
        for field in (
            "length",
            "mean_disorder_score",
            "fraction_disordered",
            "n_disordered_residues",
            "n_idr_regions",
            "longest_idr",
            "n_binding_regions",
            "n_linker_regions",
        ):
            value = row.get(field, "")
            if value != "":
                summary[field] = value
        sources = split_multi(row.get("sources", ""))
        builder.add_set(query_id, "annotation_sources", ["protein-idr-disorder-annotation", *sources])
        warnings = split_multi(row.get("warnings", ""))
        for warning in warnings:
            builder.add_warning(warning, query_id)


def parse_idr_regions_tsv(builder: ReportBuilder, path: Path) -> None:
    builder.source_files.append(str(path))
    rows = read_tsv_rows(path)
    for row in rows:
        query_id = row.get("query_id") or row.get("protein_id") or ""
        if not query_id:
            continue
        region_type = row.get("region_type") or "idr"
        start = row.get("start", "")
        end = row.get("end", "")
        source = row.get("source") or "protein-idr-disorder-annotation"
        evidence = row.get("evidence", "")
        mean_score = row.get("mean_score", "")
        max_score = row.get("max_score", "")
        threshold = row.get("threshold", "")
        builder.summary(query_id, "protein_idr")
        builder.add_feature(
            {
                "query_id": query_id,
                "source": f"protein-idr-disorder-annotation:{source}",
                "feature_type": region_type,
                "start": start,
                "end": end,
                "length": row.get("length") or interval_length(start, end),
                "name": region_type,
                "description": f"{region_type} predicted by {source}",
                "database": source,
                "score": mean_score,
                "evidence": evidence,
                "note": (
                    f"Threshold-derived IDR/disorder feature; mean_score={mean_score}; "
                    f"max_score={max_score}; threshold={threshold}."
                ),
            }
        )


def parse_llps_summary_tsv(builder: ReportBuilder, path: Path) -> None:
    builder.source_files.append(str(path))
    rows = read_tsv_rows(path)
    for row in rows:
        query_id = row.get("query_id") or row.get("protein_id") or ""
        if not query_id:
            continue
        summary = builder.summary(query_id, "protein_llps")
        for field in (
            "length",
            "pLLPS",
            "mean_aggregation_score",
            "fraction_aggregation_prone",
            "n_aggregation_prone_residues",
            "n_aggregation_regions",
            "n_dpr_regions",
            "n_hotspot_regions",
        ):
            value = row.get(field, "")
            if value != "":
                summary[field] = value
        sources = split_multi(row.get("sources", ""))
        builder.add_set(query_id, "annotation_sources", ["protein-idr-disorder-annotation", *sources])
        warnings = split_multi(row.get("warnings", ""))
        for warning in warnings:
            builder.add_warning(warning, query_id)


def parse_llps_features_tsv(builder: ReportBuilder, path: Path) -> None:
    builder.source_files.append(str(path))
    rows = read_tsv_rows(path)
    for row in rows:
        query_id = row.get("query_id") or row.get("protein_id") or ""
        if not query_id:
            continue
        feature_type = row.get("feature_type") or "llps_feature"
        start = row.get("start", "")
        end = row.get("end", "")
        source = row.get("source") or "protein-idr-disorder-annotation"
        score = row.get("score", "")
        threshold = row.get("threshold", "")
        builder.summary(query_id, "protein_llps")
        builder.add_feature(
            {
                "query_id": query_id,
                "source": f"protein-idr-disorder-annotation:{source}",
                "feature_type": feature_type,
                "start": start,
                "end": end,
                "length": row.get("length") or interval_length(start, end),
                "name": feature_type,
                "description": f"{feature_type} predicted by {source}",
                "database": source,
                "score": score,
                "evidence": row.get("evidence", ""),
                "note": f"LLPS/aggregation feature; threshold={threshold}; {row.get('note', '')}".strip(),
            }
        )


def parse_features_tsv(builder: ReportBuilder, path: Path) -> None:
    builder.source_files.append(str(path))
    rows = read_tsv_rows(path)
    fallback_query = safe_name(path.stem.replace(".features", ""))
    for row in rows:
        query_id = row.get("query_id") or row.get("protein_id") or fallback_query
        feature_type = row.get("type") or row.get("feature_type") or "feature"
        description = row.get("description") or row.get("name") or feature_type
        start = row.get("start", "")
        end = row.get("end", "")
        builder.summary(query_id, "features_tsv")
        builder.add_feature(
            {
                "query_id": query_id,
                "source": "features_tsv",
                "feature_type": feature_type,
                "start": start,
                "end": end,
                "length": row.get("length") or interval_length(start, end),
                "name": description,
                "description": description,
                "database": row.get("database", ""),
                "evidence": row.get("evidence", ""),
                "note": f"Imported from {path.name}.",
            }
        )


def parse_degron_features_tsv(builder: ReportBuilder, path: Path) -> None:
    builder.source_files.append(str(path))
    rows = read_tsv_rows(path)
    fallback_query = safe_name(path.stem.replace(".features", ""))
    for row in rows:
        query_id = row.get("query_id") or row.get("protein_id") or fallback_query
        feature_type = row.get("feature_type") or "degron_candidate"
        source = row.get("source") or "protein-degron-annotation"
        name = row.get("name") or row.get("matched_sequence") or "degron_candidate"
        start = row.get("start", "")
        end = row.get("end", "")
        note_parts = [
            row.get("note", ""),
            f"matched_sequence={row.get('matched_sequence', '')}" if row.get("matched_sequence") else "",
            f"location={row.get('degron_location', '')}" if row.get("degron_location") else "",
            f"regex={row.get('degron_regex', '')}" if row.get("degron_regex") else "",
            f"ups_component={row.get('e3_ligase_or_ups_component', '')}" if row.get("e3_ligase_or_ups_component") else "",
            f"license={row.get('license', '')}" if row.get("license") else "",
            f"free_for_any_use={row.get('free_for_any_use', '')}" if row.get("free_for_any_use") else "",
            f"references={row.get('references', '')}" if row.get("references") else "",
        ]
        builder.summary(query_id, "protein_degron")
        builder.add_feature(
            {
                "query_id": query_id,
                "source": source,
                "feature_type": feature_type,
                "start": start,
                "end": end,
                "length": row.get("length") or interval_length(start, end),
                "accession": row.get("accession", ""),
                "name": name,
                "description": row.get("description") or name,
                "database": row.get("database", ""),
                "interpro_accession": row.get("interpro_accession", ""),
                "interpro_description": row.get("interpro_description", ""),
                "go_terms": row.get("go_terms", ""),
                "pathways": row.get("pathways", ""),
                "score": row.get("score", ""),
                "evalue": row.get("evalue", ""),
                "evidence": row.get("evidence", ""),
                "note": "; ".join(part for part in note_parts if part),
            }
        )


def parse_motifs_tsv(builder: ReportBuilder, path: Path, coordinate_base: str) -> None:
    builder.source_files.append(str(path))
    rows = read_tsv_rows(path)
    fallback_query = safe_name(path.stem.replace(".motifs", ""))
    for row in rows:
        query_id = row.get("query_id") or row.get("protein_id") or fallback_query
        start = row.get("start", "")
        end = row.get("end", "")
        note = f"Imported from {path.name}."
        if coordinate_base == "zero-based-half-open":
            try:
                start = str(int(start) + 1)
                end = str(int(end))
                note += " Converted from 0-based half-open to 1-based closed."
            except (TypeError, ValueError):
                pass
        motif = row.get("motif") or row.get("name") or "motif"
        sequence = row.get("sequence") or row.get("match") or ""
        builder.summary(query_id, "motifs_tsv")
        builder.add_feature(
            {
                "query_id": query_id,
                "source": "motifs_tsv",
                "feature_type": "motif",
                "start": start,
                "end": end,
                "length": interval_length(start, end),
                "name": motif,
                "description": sequence or motif,
                "evidence": "imported_motif_tsv",
                "note": note,
            }
        )


def interval_length(start: Any, end: Any) -> str:
    try:
        return str(int(str(end)) - int(str(start)) + 1)
    except (TypeError, ValueError):
        return ""


def discover_from_annotation_result(path: Path) -> Tuple[List[Path], List[Path]]:
    interpro: List[Path] = []
    eggnog: List[Path] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    outputs = data.get("outputs") or {}
    for tool_name, tool_output in outputs.items():
        candidates = []
        candidates.extend(tool_output.get("discovered_files") or [])
        candidates.extend(tool_output.get("expected_files") or [])
        for item in candidates:
            candidate = Path(item)
            if not candidate.exists():
                continue
            name = candidate.name
            if tool_name == "interproscan6" and candidate.suffix.lower() == ".tsv":
                interpro.append(candidate)
            elif tool_name == "eggnog" and name.endswith(".emapper.annotations"):
                eggnog.append(candidate)
            elif name.endswith(".emapper.annotations"):
                eggnog.append(candidate)
    return dedupe_paths(interpro), dedupe_paths(eggnog)


def discover_from_idr_result(path: Path) -> Tuple[List[Path], List[Path], List[Path], List[Path]]:
    summaries: List[Path] = []
    regions: List[Path] = []
    llps_summaries: List[Path] = []
    llps_features: List[Path] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    outputs = data.get("outputs") or {}
    for key in ("summary_tsv", "idr_summary_tsv"):
        value = outputs.get(key)
        if value and Path(value).exists():
            summaries.append(Path(value))
    for key in ("regions_tsv", "idr_regions_tsv"):
        value = outputs.get(key)
        if value and Path(value).exists():
            regions.append(Path(value))
    for key in ("llps_summary_tsv",):
        value = outputs.get(key)
        if value and Path(value).exists():
            llps_summaries.append(Path(value))
    for key in ("llps_features_tsv",):
        value = outputs.get(key)
        if value and Path(value).exists():
            llps_features.append(Path(value))
    return dedupe_paths(summaries), dedupe_paths(regions), dedupe_paths(llps_summaries), dedupe_paths(llps_features)


def discover_from_degron_result(path: Path) -> List[Path]:
    features: List[Path] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    artifacts = data.get("artifacts") or {}
    outputs = data.get("outputs") or {}
    for container in (artifacts, outputs):
        for key in ("features_tsv", "protein_degron_features_tsv", "degron_features_tsv"):
            value = container.get(key)
            if value and Path(value).exists():
                features.append(Path(value))
    return dedupe_paths(features)


def dedupe_paths(paths: Sequence[Path]) -> List[Path]:
    seen: Set[str] = set()
    unique: List[Path] = []
    for path in paths:
        key = str(path)
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return unique


def write_tsv(path: Path, rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: stringify(row.get(column, "")) for column in columns})


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = parse_args()
    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    builder = ReportBuilder()

    interpro_paths = [Path(p).expanduser() for p in args.interpro_tsv]
    eggnog_paths = [Path(p).expanduser() for p in args.eggnog_annotations]
    idr_summary_paths = [Path(p).expanduser() for p in args.idr_summary_tsv]
    idr_regions_paths = [Path(p).expanduser() for p in args.idr_regions_tsv]
    llps_summary_paths = [Path(p).expanduser() for p in args.llps_summary_tsv]
    llps_features_paths = [Path(p).expanduser() for p in args.llps_features_tsv]
    degron_feature_paths = [Path(p).expanduser() for p in args.degron_features_tsv]

    for result_json in args.annotation_result_json:
        path = Path(result_json).expanduser()
        if not path.exists():
            builder.add_warning(f"annotation_result_json_missing:{path}")
            continue
        try:
            discovered_interpro, discovered_eggnog = discover_from_annotation_result(path)
            interpro_paths.extend(discovered_interpro)
            eggnog_paths.extend(discovered_eggnog)
            builder.source_files.append(str(path))
        except (OSError, json.JSONDecodeError) as exc:
            builder.add_warning(f"annotation_result_json_unreadable:{path}:{exc}")

    for result_json in args.idr_result_json:
        path = Path(result_json).expanduser()
        if not path.exists():
            builder.add_warning(f"idr_result_json_missing:{path}")
            continue
        try:
            discovered_summaries, discovered_regions, discovered_llps_summaries, discovered_llps_features = discover_from_idr_result(path)
            idr_summary_paths.extend(discovered_summaries)
            idr_regions_paths.extend(discovered_regions)
            llps_summary_paths.extend(discovered_llps_summaries)
            llps_features_paths.extend(discovered_llps_features)
            builder.source_files.append(str(path))
        except (OSError, json.JSONDecodeError) as exc:
            builder.add_warning(f"idr_result_json_unreadable:{path}:{exc}")

    for result_json in args.degron_result_json:
        path = Path(result_json).expanduser()
        if not path.exists():
            builder.add_warning(f"degron_result_json_missing:{path}")
            continue
        try:
            degron_feature_paths.extend(discover_from_degron_result(path))
            builder.source_files.append(str(path))
        except (OSError, json.JSONDecodeError) as exc:
            builder.add_warning(f"degron_result_json_unreadable:{path}:{exc}")

    if args.sequence:
        sequence = normalize_sequence(args.sequence)
        add_sequence_record(builder, args.sequence_name, sequence, "raw_sequence", args.allow_ambiguous_aa)

    for fasta in args.fasta:
        path = Path(fasta).expanduser()
        if not path.exists():
            builder.add_warning(f"fasta_missing:{path}")
            continue
        builder.source_files.append(str(path))
        for record_id, _header, sequence in read_fasta(path):
            add_sequence_record(builder, record_id, sequence, "fasta", args.allow_ambiguous_aa)

    for raw_json in args.raw_uniprot_json:
        path = Path(raw_json).expanduser()
        if not path.exists():
            builder.add_warning(f"raw_uniprot_json_missing:{path}")
            continue
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            builder.source_files.append(str(path))
            add_uniprot_entry(builder, entry, path.stem, args.all_uniprot_features)
        except (OSError, json.JSONDecodeError) as exc:
            builder.add_warning(f"raw_uniprot_json_unreadable:{path}:{exc}")

    if not args.no_uniprot:
        accessions = list(args.uniprot)
        for gene in args.gene:
            try:
                accession, warnings = resolve_uniprot_by_query("gene", gene, args.organism, args.timeout_sec)
                accessions.append(accession)
                for warning in warnings:
                    builder.add_warning(warning, accession)
            except RuntimeError as exc:
                builder.errors.append(str(exc))
        for protein_name in args.protein_name:
            try:
                accession, warnings = resolve_uniprot_by_query(
                    "protein_name", protein_name, args.organism, args.timeout_sec
                )
                accessions.append(accession)
                for warning in warnings:
                    builder.add_warning(warning, accession)
            except RuntimeError as exc:
                builder.errors.append(str(exc))
        for accession in sorted(set(accessions)):
            try:
                entry = fetch_uniprot_entry(accession, args.timeout_sec)
                query_id = add_uniprot_entry(builder, entry, accession, args.all_uniprot_features)
                if args.save_raw_uniprot:
                    raw_path = outdir / f"{safe_name(query_id)}.uniprot.json"
                    write_json(raw_path, entry)
                    builder.raw_uniprot_outputs.append(str(raw_path))
            except RuntimeError as exc:
                builder.errors.append(str(exc))
    elif args.gene or args.protein_name or args.uniprot:
        builder.add_warning("uniprot_queries_skipped_by_no_uniprot")

    for path in dedupe_paths(interpro_paths):
        if path.exists():
            parse_interpro_tsv(builder, path)
        else:
            builder.add_warning(f"interpro_tsv_missing:{path}")

    for path in dedupe_paths(eggnog_paths):
        if path.exists():
            parse_eggnog_annotations(builder, path)
        else:
            builder.add_warning(f"eggnog_annotations_missing:{path}")

    for path in dedupe_paths(idr_summary_paths):
        if path.exists():
            parse_idr_summary_tsv(builder, path)
        else:
            builder.add_warning(f"idr_summary_tsv_missing:{path}")

    for path in dedupe_paths(idr_regions_paths):
        if path.exists():
            parse_idr_regions_tsv(builder, path)
        else:
            builder.add_warning(f"idr_regions_tsv_missing:{path}")

    for path in dedupe_paths(llps_summary_paths):
        if path.exists():
            parse_llps_summary_tsv(builder, path)
        else:
            builder.add_warning(f"llps_summary_tsv_missing:{path}")

    for path in dedupe_paths(llps_features_paths):
        if path.exists():
            parse_llps_features_tsv(builder, path)
        else:
            builder.add_warning(f"llps_features_tsv_missing:{path}")

    for path in dedupe_paths(degron_feature_paths):
        if path.exists():
            parse_degron_features_tsv(builder, path)
        else:
            builder.add_warning(f"degron_features_tsv_missing:{path}")

    for features_tsv in args.features_tsv:
        path = Path(features_tsv).expanduser()
        if path.exists():
            parse_features_tsv(builder, path)
        else:
            builder.add_warning(f"features_tsv_missing:{path}")

    for motifs_tsv in args.motifs_tsv:
        path = Path(motifs_tsv).expanduser()
        if path.exists():
            parse_motifs_tsv(builder, path, args.imported_motif_base)
        else:
            builder.add_warning(f"motifs_tsv_missing:{path}")

    if not builder.summaries and not builder.feature_rows:
        builder.errors.append("No usable input annotations or sequences were provided.")

    summary_rows = builder.finalize()
    run_id = safe_name(args.run_id or (summary_rows[0]["query_id"] if summary_rows else "protein_annotation_report"))
    summary_path = outdir / "protein_annotation_summary.tsv"
    features_path = outdir / "protein_annotation_features.tsv"
    report_path = outdir / "protein_annotation_report.json"

    write_tsv(summary_path, summary_rows, SUMMARY_COLUMNS)
    write_tsv(features_path, builder.feature_rows, FEATURE_COLUMNS)
    report = {
        "skill": "protein-annotation-report",
        "status": "error" if builder.errors else ("warning" if builder.warnings else "success"),
        "run_id": run_id,
        "created_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "outputs": {
            "summary_tsv": str(summary_path),
            "features_tsv": str(features_path),
            "report_json": str(report_path),
            "raw_uniprot_json": builder.raw_uniprot_outputs,
        },
        "counts": {
            "summary_rows": len(summary_rows),
            "feature_rows": len(builder.feature_rows),
        },
        "source_files": sorted(set(builder.source_files)),
        "warnings": builder.warnings,
        "errors": builder.errors,
    }
    write_json(report_path, report)
    print(f"saved summary: {summary_path}")
    print(f"saved features: {features_path}")
    print(f"saved report: {report_path}")
    for warning in builder.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in builder.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if builder.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
