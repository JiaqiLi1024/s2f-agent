#!/usr/bin/env python3
"""Foldseek web/API wrapper for remote structure similarity search."""

from __future__ import annotations

import argparse
import html
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple



RESULT_JSON_NAME = "protein_structure_foldseek_web.result.json"
DEFAULT_API_BASE = "https://search.foldseek.com/api"
DEFAULT_WEB_BASE = "https://search.foldseek.com"
DEFAULT_DATABASE = "afdb50"
TERMINAL_ERROR_STATUSES = {"ERROR", "FAILED", "UNKNOWN", "RATELIMIT", "MAINTENANCE"}


def json_safe_path(path: Path) -> str:
    return str(path.resolve())


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def normalize_api_base(api_base: str) -> str:
    return api_base.rstrip("/")


def infer_web_base(api_base: str, web_base: Optional[str]) -> str:
    if web_base:
        return web_base.rstrip("/")
    api_base = normalize_api_base(api_base)
    if api_base.endswith("/api"):
        return api_base[:-4]
    return DEFAULT_WEB_BASE


def endpoint(api_base: str, path: str) -> str:
    return f"{normalize_api_base(api_base)}/{path.lstrip('/')}"


def split_database_args(values: Optional[Sequence[str]]) -> List[str]:
    databases: List[str] = []
    if not values:
        return [DEFAULT_DATABASE]
    for value in values:
        for part in value.split(","):
            db = part.strip()
            if db and db not in databases:
                databases.append(db)
    return databases or [DEFAULT_DATABASE]


def response_json(response: requests.Response, label: str) -> Dict[str, Any]:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        text = response.text[:500] if response.text else ""
        raise RuntimeError(f"{label} failed with HTTP {response.status_code}: {text}") from exc
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"{label} did not return JSON") from exc


def fetch_databases(session: requests.Session, api_base: str, request_timeout_sec: int) -> List[Dict[str, Any]]:
    response = session.get(endpoint(api_base, "databases"), timeout=request_timeout_sec)
    data = response_json(response, "Foldseek database listing")
    databases = data.get("databases", [])
    if not isinstance(databases, list):
        raise RuntimeError("Foldseek database listing did not contain a databases array")
    return [db for db in databases if isinstance(db, dict)]


def database_frame(databases: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for db in databases:
        rows.append(
            {
                "name": db.get("name", ""),
                "version": db.get("version", ""),
                "path": db.get("path", ""),
                "default": db.get("default", ""),
                "order": db.get("order", ""),
                "complex": db.get("complex", ""),
                "motif": db.get("motif", ""),
                "taxonomy": db.get("taxonomy", ""),
                "status": db.get("status", ""),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["order", "name", "path"], kind="stable")
    return frame


def write_databases_outputs(outdir: Path, databases: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    outputs: Dict[str, str] = {}
    json_path = outdir / "foldseek_web_databases.json"
    json_path.write_text(json.dumps({"databases": list(databases)}, indent=2, sort_keys=True), encoding="utf-8")
    outputs["databases_json"] = json_safe_path(json_path)

    frame = database_frame(databases)
    tsv_path = outdir / "foldseek_web_databases.tsv"
    frame.to_csv(tsv_path, sep="\t", index=False)
    outputs["databases_tsv"] = json_safe_path(tsv_path)

    html_path = outdir / "foldseek_web_databases.html"
    body = frame.to_html(index=False, escape=True, classes="hits") if not frame.empty else "<p>No databases returned.</p>"
    html_path.write_text(
        make_html_page(
            title="Foldseek Web Databases",
            heading="Foldseek Web Databases",
            summary_rows=[("API", DEFAULT_API_BASE), ("database_count", str(len(databases)))],
            body=body,
        ),
        encoding="utf-8",
    )
    outputs["databases_html"] = json_safe_path(html_path)
    return outputs


def validate_database_choices(
    databases: Sequence[Dict[str, Any]], requested: Sequence[str]
) -> Tuple[List[str], List[str]]:
    available = {str(db.get("path", "")) for db in databases}
    warnings: List[str] = []
    errors: List[str] = []
    for db in requested:
        if db not in available:
            errors.append(
                f"Database '{db}' was not listed by the Foldseek web API. "
                "Run --list-databases to inspect available database paths."
            )
    incomplete = [
        db
        for db in requested
        for record in databases
        if record.get("path") == db and str(record.get("status", "")).upper() not in {"", "COMPLETE"}
    ]
    if incomplete:
        warnings.append(f"Requested databases are not marked COMPLETE by the API: {', '.join(incomplete)}")
    return warnings, errors


def submit_ticket(
    session: requests.Session,
    api_base: str,
    query_path: Path,
    databases: Sequence[str],
    foldseek_mode: str,
    email: str,
    taxfilter: str,
    endpoint_suffix: str,
    request_timeout_sec: int,
) -> Dict[str, Any]:
    url = endpoint(api_base, "ticket" + (f"/{endpoint_suffix.strip('/')}" if endpoint_suffix else ""))
    data: List[Tuple[str, str]] = []
    for db in databases:
        data.append(("database[]", db))
    data.append(("mode", foldseek_mode))
    data.append(("email", email or ""))
    if taxfilter:
        data.append(("taxfilter", taxfilter))

    with query_path.open("rb") as handle:
        files = {"q": (query_path.name, handle)}
        response = session.post(url, data=data, files=files, timeout=request_timeout_sec)
    return response_json(response, "Foldseek ticket submission")


def poll_ticket(
    session: requests.Session,
    api_base: str,
    ticket: str,
    poll_interval_sec: int,
    timeout_sec: int,
    request_timeout_sec: int,
) -> Tuple[str, List[Dict[str, Any]]]:
    history: List[Dict[str, Any]] = []
    deadline = time.monotonic() + timeout_sec
    last_status = "UNKNOWN"

    while True:
        response = session.get(endpoint(api_base, f"ticket/{ticket}"), timeout=request_timeout_sec)
        payload = response_json(response, "Foldseek ticket status")
        last_status = str(payload.get("status", "UNKNOWN")).upper()
        history.append({"time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": last_status})

        if last_status == "COMPLETE" or last_status in TERMINAL_ERROR_STATUSES:
            return last_status, history
        if time.monotonic() >= deadline:
            return "TIMEOUT", history
        time.sleep(max(1, poll_interval_sec))


def fetch_result_json(
    session: requests.Session, api_base: str, ticket: str, entry: int, request_timeout_sec: int
) -> Dict[str, Any]:
    response = session.get(endpoint(api_base, f"result/{ticket}/{entry}"), timeout=request_timeout_sec)
    return response_json(response, "Foldseek result fetch")


def download_archive(
    session: requests.Session, api_base: str, ticket: str, out_path: Path, request_timeout_sec: int
) -> None:
    response = session.get(endpoint(api_base, f"result/download/{ticket}"), stream=True, timeout=request_timeout_sec)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        text = response.text[:500] if response.text else ""
        raise RuntimeError(f"Foldseek result download failed with HTTP {response.status_code}: {text}") from exc
    with out_path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)


def scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return json.dumps(value, sort_keys=True)


def flatten_alignments(result_data: Dict[str, Any]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    queries = result_data.get("queries", [])
    legacy_query = result_data.get("query", {})
    query_records = queries if isinstance(queries, list) else []
    query_header = legacy_query.get("header", "") if isinstance(legacy_query, dict) else ""
    query_sequence_length = len(legacy_query.get("sequence", "")) if isinstance(legacy_query, dict) else ""

    def query_meta(index: int) -> Tuple[str, Any]:
        if index < len(query_records) and isinstance(query_records[index], dict):
            record = query_records[index]
            return str(record.get("header", "")), len(str(record.get("sequence", "")))
        return query_header, query_sequence_length

    for db_result in result_data.get("results", []):
        if not isinstance(db_result, dict):
            continue
        db = str(db_result.get("db", ""))
        alignments = db_result.get("alignments", [])
        if not isinstance(alignments, list):
            continue
        rank = 0
        for query_index, alignment_block in enumerate(alignments):
            block = alignment_block if isinstance(alignment_block, list) else [alignment_block]
            current_query_header, current_query_length = query_meta(query_index)
            for aln in block:
                if not isinstance(aln, dict):
                    continue
                rank += 1
                row: Dict[str, Any] = {
                    "database": db,
                    "rank": rank,
                    "query_index": query_index,
                    "query_header": current_query_header,
                    "query_sequence_length": current_query_length,
                }
                for key, value in aln.items():
                    row[key] = scalar(value)
                rows.append(row)
    return pd.DataFrame(rows)


def write_hits_outputs(outdir: Path, prefix: str, result_data: Dict[str, Any], top_n: int) -> Tuple[Dict[str, str], Dict[str, Any]]:
    outputs: Dict[str, str] = {}
    frame = flatten_alignments(result_data)
    summary = {
        "hit_count": int(frame.shape[0]),
        "database_count": int(frame["database"].nunique()) if "database" in frame.columns and not frame.empty else 0,
        "top_hit": "",
    }
    if not frame.empty:
        if "target" in frame.columns:
            summary["top_hit"] = str(frame.iloc[0]["target"])
        tsv_path = outdir / f"{prefix}.foldseek_web_hits.tsv"
        frame.to_csv(tsv_path, sep="\t", index=False)
        outputs["hits_tsv"] = json_safe_path(tsv_path)

        top_path = outdir / f"{prefix}.foldseek_web_top_hits.tsv"
        frame.head(top_n).to_csv(top_path, sep="\t", index=False)
        outputs["top_hits_tsv"] = json_safe_path(top_path)
    else:
        empty_path = outdir / f"{prefix}.foldseek_web_hits.tsv"
        frame.to_csv(empty_path, sep="\t", index=False)
        outputs["hits_tsv"] = json_safe_path(empty_path)
    return outputs, summary


def make_html_page(title: str, heading: str, summary_rows: Sequence[Tuple[str, str]], body: str) -> str:
    escaped_title = html.escape(title)
    escaped_heading = html.escape(heading)
    summary_html = "\n".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>" for key, value in summary_rows
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #17202a;
      background: #f7f8fa;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 22px 44px;
    }}
    h1 {{
      margin: 0 0 18px;
      font-size: 28px;
      font-weight: 650;
    }}
    h2 {{
      margin-top: 28px;
      font-size: 19px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      background: white;
    }}
    th, td {{
      border: 1px solid #d9dee7;
      padding: 7px 9px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }}
    th {{
      background: #eef1f6;
      font-weight: 650;
    }}
    .summary {{
      max-width: 880px;
      margin-bottom: 22px;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid #d9dee7;
      background: white;
    }}
    a {{
      color: #0b5cad;
    }}
    code {{
      background: #edf0f5;
      padding: 2px 5px;
      border-radius: 4px;
    }}
  </style>
</head>
<body>
<main>
  <h1>{escaped_heading}</h1>
  <table class="summary">
    <tbody>
{summary_html}
    </tbody>
  </table>
{body}
</main>
</body>
</html>
"""


def write_result_html(
    outdir: Path,
    prefix: str,
    result: Dict[str, Any],
    result_data: Optional[Dict[str, Any]],
    hits_frame: pd.DataFrame,
    top_n: int,
) -> Path:
    outputs = result.get("outputs", {})
    ticket = str(result.get("ticket", ""))
    api_base = str(result.get("api_base", DEFAULT_API_BASE)).rstrip("/")
    web_base = str(result.get("web_base", DEFAULT_WEB_BASE)).rstrip("/")
    web_result_url = f"{web_base}/result/{ticket}/0" if ticket else ""
    api_result_url = f"{api_base}/result/{ticket}/0" if ticket else ""
    download_url = f"{api_base}/result/download/{ticket}" if ticket else ""

    links: List[str] = []
    if web_result_url:
        links.append(f'<a href="{html.escape(web_result_url)}">Open Foldseek web result</a>')
    if api_result_url:
        links.append(f'<a href="{html.escape(api_result_url)}">API result JSON</a>')
    if download_url:
        links.append(f'<a href="{html.escape(download_url)}">Download API result archive</a>')
    link_html = " | ".join(links)

    if hits_frame.empty:
        table_html = "<p>No alignments were returned for entry 0.</p>"
    else:
        table_html = '<div class="table-wrap">' + hits_frame.head(top_n).to_html(index=False, escape=True) + "</div>"

    body = f"""
  <p>{link_html}</p>
  <h2>Top Hits</h2>
  {table_html}
"""
    summary_rows = [
        ("status", str(result.get("status", ""))),
        ("ticket", ticket),
        ("query", str(result.get("inputs", {}).get("query", ""))),
        ("databases", ",".join(result.get("inputs", {}).get("databases", []))),
        ("mode", str(result.get("parameters", {}).get("foldseek_mode", ""))),
        ("hit_count", str(result.get("search_summary", {}).get("hit_count", 0))),
        ("top_hit", str(result.get("search_summary", {}).get("top_hit", ""))),
        ("raw_result_json", str(outputs.get("api_result_json", ""))),
    ]
    if result_data and isinstance(result_data.get("query"), dict):
        summary_rows.append(("query_header", str(result_data["query"].get("header", ""))))
    html_path = outdir / f"{prefix}.foldseek_web_results.html"
    html_path.write_text(
        make_html_page("Foldseek Web Results", "Foldseek Web Results", summary_rows, body),
        encoding="utf-8",
    )
    return html_path


def write_summary(outdir: Path, result: Dict[str, Any]) -> None:
    lines = [
        "Protein Structure Foldseek Web/API",
        f"status: {result.get('status', 'unknown')}",
        f"ticket: {result.get('ticket', '')}",
        f"api_base: {result.get('api_base', '')}",
        f"query: {result.get('inputs', {}).get('query', '')}",
        f"databases: {','.join(result.get('inputs', {}).get('databases', []))}",
        f"mode: {result.get('parameters', {}).get('foldseek_mode', '')}",
    ]
    if result.get("search_summary"):
        summary = result["search_summary"]
        lines.extend(
            [
                f"hits: {summary.get('hit_count', 0)}",
                f"top_hit: {summary.get('top_hit', '')}",
            ]
        )
    if result.get("outputs"):
        lines.append("outputs:")
        for key, value in sorted(result["outputs"].items()):
            lines.append(f"- {key}: {value}")
    if result.get("warnings"):
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in result["warnings"])
    if result.get("errors"):
        lines.append("errors:")
        lines.extend(f"- {error}" for error in result["errors"])
    (outdir / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Use the Foldseek web/API service for remote structure similarity search and local HTML reports."
    )
    parser.add_argument("--query", help="Local PDB/mmCIF/FASTA query file to upload to the Foldseek web API.")
    parser.add_argument(
        "--database",
        action="append",
        help="Foldseek web database path. Repeat or comma-separate values. Default: afdb50.",
    )
    parser.add_argument(
        "--foldseek-mode",
        "--mode-param",
        dest="foldseek_mode",
        default="3diaa",
        choices=["3diaa", "tmalign", "lolalign"],
        help="Foldseek web search mode. Default matches the web server default.",
    )
    parser.add_argument("--email", default="", help="Optional email notification address for the remote job.")
    parser.add_argument("--taxfilter", default="", help="Optional Foldseek web API taxonomic filter.")
    parser.add_argument(
        "--endpoint-suffix",
        default="",
        help="Optional API ticket suffix such as folddisco. Leave empty for normal Foldseek search.",
    )
    parser.add_argument("--ticket", help="Fetch results for an existing Foldseek web API ticket instead of submitting.")
    parser.add_argument("--entry", type=int, default=0, help="Query entry index to fetch from a completed ticket.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="Foldseek web API base URL.")
    parser.add_argument("--web-base", help="Foldseek web frontend base URL for report links.")
    parser.add_argument("--outdir", required=True, help="Output directory.")
    parser.add_argument("--prefix", default="foldseek_web", help="Output filename prefix.")
    parser.add_argument("--top-n", type=int, default=25, help="Rows to show in the HTML and top-hit TSV.")
    parser.add_argument("--poll-interval-sec", type=int, default=10, help="Seconds between ticket status polls.")
    parser.add_argument("--timeout-sec", type=int, default=1800, help="Maximum remote job wait time.")
    parser.add_argument("--request-timeout-sec", type=int, default=60, help="HTTP request timeout.")
    parser.add_argument("--list-databases", action="store_true", help="List Foldseek web databases and exit.")
    parser.add_argument("--download-archive", action="store_true", help="Download the API result archive when complete.")
    parser.add_argument("--no-html", action="store_true", help="Skip local HTML report generation.")
    parser.add_argument(
        "--confirm-remote-upload",
        action="store_true",
        help="Required for new submissions; confirms the query file can be uploaded to the public Foldseek web service.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Write planned request metadata without uploading.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    global pd, requests
    try:
        import pandas as pd
        import requests
    except ImportError as exc:
        parser.error(f"Missing Python dependency: {exc}. Install with: python -m pip install -r skills/protein-structure-align/requirements.txt")

    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    result_path = outdir / RESULT_JSON_NAME
    api_base = normalize_api_base(args.api_base)
    web_base = infer_web_base(api_base, args.web_base)
    databases = split_database_args(args.database)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    warnings: List[str] = []
    errors: List[str] = []
    query_path: Optional[Path] = None

    if args.query:
        query_path = Path(args.query).expanduser()
        if not query_path.exists():
            errors.append(f"Query file does not exist: {args.query}")
        elif not query_path.is_file():
            errors.append(f"Query path is not a file: {args.query}")

    if not args.list_databases and not args.ticket:
        if not args.query:
            errors.append("--query is required unless --list-databases or --ticket is used")
        if not args.confirm_remote_upload and not args.dry_run:
            errors.append(
                "Remote Foldseek web/API search uploads the query structure to a public web service. "
                "Rerun with --confirm-remote-upload only after the user confirms this is acceptable."
            )

    result: Dict[str, Any] = {
        "skill": "protein-structure-align",
        "script": "protein_structure_foldseek_web.py",
        "backend": "foldseek-web-api",
        "api_base": api_base,
        "web_base": web_base,
        "status": "error" if errors else "planned" if args.dry_run else "running",
        "started_at": started_at,
        "inputs": {
            "query": json_safe_path(query_path) if query_path and query_path.exists() else args.query or "",
            "databases": databases,
            "outdir": json_safe_path(outdir),
        },
        "parameters": {
            "foldseek_mode": args.foldseek_mode,
            "email": args.email,
            "taxfilter": args.taxfilter,
            "endpoint_suffix": args.endpoint_suffix,
            "entry": args.entry,
            "top_n": args.top_n,
            "download_archive": bool(args.download_archive),
            "confirm_remote_upload": bool(args.confirm_remote_upload),
        },
        "warnings": warnings,
        "errors": errors,
        "outputs": {},
    }

    session = requests.Session()
    session.headers.update({"User-Agent": "s2f-agent-protein-structure-align-foldseek-web/0.1"})

    if errors:
        write_json(result_path, result)
        write_summary(outdir, result)
        return 2

    try:
        if args.list_databases:
            database_records = fetch_databases(session, api_base, args.request_timeout_sec)
            result["status"] = "ok"
            result["database_count"] = len(database_records)
            result["outputs"].update(write_databases_outputs(outdir, database_records))
            result["outputs"][RESULT_JSON_NAME] = json_safe_path(result_path)
            write_json(result_path, result)
            write_summary(outdir, result)
            return 0

        if not args.ticket and not args.dry_run:
            database_records = fetch_databases(session, api_base, args.request_timeout_sec)
            db_warnings, db_errors = validate_database_choices(database_records, databases)
            result["warnings"].extend(db_warnings)
            result["errors"].extend(db_errors)
            if db_errors:
                result["status"] = "error"
                write_json(result_path, result)
                write_summary(outdir, result)
                return 2
    except requests.RequestException as exc:
        result["status"] = "error"
        result["errors"].append(f"Foldseek web API request failed: {exc}")
        write_json(result_path, result)
        write_summary(outdir, result)
        return 3
    except RuntimeError as exc:
        result["status"] = "error"
        result["errors"].append(str(exc))
        write_json(result_path, result)
        write_summary(outdir, result)
        return 3

    if args.dry_run:
        ticket_url = endpoint(api_base, "ticket" + (f"/{args.endpoint_suffix.strip('/')}" if args.endpoint_suffix else ""))
        result["request"] = {
            "method": "POST",
            "url": ticket_url,
            "multipart_file_field": "q",
            "form_fields": {
                "database[]": databases,
                "mode": args.foldseek_mode,
                "email": args.email,
                "taxfilter": args.taxfilter,
            },
        }
        result["outputs"][RESULT_JSON_NAME] = json_safe_path(result_path)
        write_json(result_path, result)
        write_summary(outdir, result)
        return 0

    try:
        if args.ticket:
            ticket = args.ticket
            ticket_status = "COMPLETE"
            poll_history: List[Dict[str, Any]] = []
        else:
            assert query_path is not None
            ticket_response = submit_ticket(
                session,
                api_base,
                query_path,
                databases,
                args.foldseek_mode,
                args.email,
                args.taxfilter,
                args.endpoint_suffix,
                args.request_timeout_sec,
            )
            ticket = str(ticket_response.get("id", ""))
            ticket_status = str(ticket_response.get("status", "UNKNOWN")).upper()
            result["ticket_submission"] = ticket_response
            if not ticket:
                raise RuntimeError("Foldseek ticket submission did not return an id")
            if ticket_status != "COMPLETE":
                ticket_status, poll_history = poll_ticket(
                    session,
                    api_base,
                    ticket,
                    args.poll_interval_sec,
                    args.timeout_sec,
                    args.request_timeout_sec,
                )
            else:
                poll_history = [{"time_utc": started_at, "status": ticket_status}]

        result["ticket"] = ticket
        result["ticket_status"] = ticket_status
        result["poll_history"] = poll_history
        if ticket_status != "COMPLETE":
            result["status"] = "error"
            result["errors"].append(f"Foldseek ticket did not complete: {ticket_status}")
            write_json(result_path, result)
            write_summary(outdir, result)
            return 3

        api_result = fetch_result_json(session, api_base, ticket, args.entry, args.request_timeout_sec)
        api_result_path = outdir / f"{args.prefix}.foldseek_web_result.json"
        api_result_path.write_text(json.dumps(api_result, indent=2, sort_keys=True), encoding="utf-8")
        result["outputs"]["api_result_json"] = json_safe_path(api_result_path)

        hits_outputs, search_summary = write_hits_outputs(outdir, args.prefix, api_result, args.top_n)
        result["outputs"].update(hits_outputs)
        result["search_summary"] = search_summary

        hits_frame = flatten_alignments(api_result)
        if not args.no_html:
            html_path = write_result_html(outdir, args.prefix, result, api_result, hits_frame, args.top_n)
            result["outputs"]["results_html"] = json_safe_path(html_path)

        if args.download_archive:
            archive_path = outdir / f"{args.prefix}.foldseek_web_result_archive.tar.gz"
            download_archive(session, api_base, ticket, archive_path, args.request_timeout_sec)
            result["outputs"]["result_archive"] = json_safe_path(archive_path)

        result["status"] = "ok"
        result["outputs"][RESULT_JSON_NAME] = json_safe_path(result_path)
        write_json(result_path, result)
        write_summary(outdir, result)
        return 0
    except requests.RequestException as exc:
        result["status"] = "error"
        result["errors"].append(f"Foldseek web API request failed: {exc}")
    except RuntimeError as exc:
        result["status"] = "error"
        result["errors"].append(str(exc))
    except OSError as exc:
        result["status"] = "error"
        result["errors"].append(f"Could not read or write Foldseek web/API files: {exc}")

    result["outputs"][RESULT_JSON_NAME] = json_safe_path(result_path)
    write_json(result_path, result)
    write_summary(outdir, result)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
