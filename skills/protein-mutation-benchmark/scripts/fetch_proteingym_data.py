#!/usr/bin/env python3
"""Generate or optionally execute a whitelisted ProteinGym release download."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from proteingym_utils import file_sha256, write_json


FILES = {
    "dms-substitutions": "DMS_ProteinGym_substitutions.zip",
    "dms-indels": "DMS_ProteinGym_indels.zip",
    "clinical-substitutions": "clinical_ProteinGym_substitutions.zip",
    "clinical-indels": "clinical_ProteinGym_indels.zip",
    "raw-dms-substitutions": "substitutions_raw_DMS.zip",
    "raw-dms-indels": "indels_raw_DMS.zip",
    "raw-clinical-substitutions": "substitutions_raw_clinical.zip",
    "raw-clinical-indels": "indels_raw_clinical.zip",
    "zero-shot-substitutions": "zero_shot_substitutions_scores.zip",
    "zero-shot-indels": "zero_shot_indels_scores.zip",
    "zero-shot-clinical-substitutions": "zero_shot_clinical_substitutions_scores.zip",
    "zero-shot-clinical-indels": "zero_shot_clinical_indels_scores.zip",
    "supervised-substitutions": "DMS_supervised_substitutions_scores.zip",
    "supervised-indels": "DMS_supervised_indels_scores.zip",
    "dms-msa": "DMS_msa_files.zip",
    "dms-msa-weights": "DMS_msa_weights.zip",
    "clinical-msa": "clinical_msa_files.zip",
    "clinical-msa-weights": "clinical_msa_weights.zip",
    "structures": "ProteinGym_AF2_structures.zip",
    "cv-substitution-singles": "cv_folds_singles_substitutions.zip",
    "cv-substitution-multiples": "cv_folds_multiples_substitutions.zip",
    "cv-indels": "cv_folds_indels.zip",
}


def safe_extract(archive: Path, output_dir: Path) -> None:
    output_root = output_dir.resolve()
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            relative = PurePosixPath(member.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe ZIP member: {member.filename}")
            destination = (output_root / Path(*relative.parts)).resolve()
            if output_root not in destination.parents and destination != output_root:
                raise ValueError(f"ZIP member escapes output directory: {member.filename}")
        handle.extractall(output_root)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--asset", choices=sorted(FILES), help="Whitelisted release asset")
    result.add_argument("--version", default="v1.3", help="Pinned ProteinGym release (default: v1.3)")
    result.add_argument("--output-dir", default="downloads/proteingym")
    result.add_argument("--sha256", help="Expected SHA-256; fail on mismatch")
    result.add_argument("--execute", action="store_true", help="Actually download; default only writes command/manifest")
    result.add_argument("--extract", action="store_true", help="Safely extract after a successful verified download")
    result.add_argument("--list", action="store_true")
    return result


def bash_path(path: Path) -> str:
    rendered = str(path)
    if re.match(r"^[A-Za-z]:[\\/]", rendered):
        drive = rendered[0].lower()
        suffix = rendered[2:].replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{suffix}"
    return rendered


def main() -> int:
    args = parser().parse_args()
    if args.list:
        print(json.dumps(FILES, indent=2))
        return 0
    if not args.asset:
        print("ERROR: --asset is required unless --list is used", file=sys.stderr)
        return 2
    if not args.version.startswith("v") or any(char not in "v0123456789." for char in args.version):
        print("ERROR: --version must look like v1.3", file=sys.stderr)
        return 2
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = FILES[args.asset]
    url = f"https://marks.hms.harvard.edu/proteingym/ProteinGym_{args.version}/{filename}"
    destination = output_dir / filename
    command = f"curl --fail --location --output {shlex.quote(bash_path(destination))} {shlex.quote(url)}"
    commands_path = output_dir / "commands.sh"
    with commands_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("#!/usr/bin/env bash\nset -euo pipefail\n" + command + "\n")
    manifest = {
        "status": "planned" if not args.execute else "running",
        "version": args.version,
        "asset": args.asset,
        "filename": filename,
        "url": url,
        "output": str(destination.resolve()),
        "expected_sha256": args.sha256,
        "note": "ProteinGym does not publish checksums in the main release table; record the observed digest or provide a trusted expected digest.",
    }
    write_json(output_dir / "download_manifest.json", manifest)
    if not args.execute:
        print(command)
        print("Plan only: no data downloaded. Add --execute after checking asset size and storage.")
        return 0
    try:
        urllib.request.urlretrieve(url, destination)
        observed = file_sha256(destination)
        if args.sha256 and observed.casefold() != args.sha256.casefold():
            raise ValueError(f"SHA-256 mismatch: expected {args.sha256}, observed {observed}")
        if args.extract:
            safe_extract(destination, output_dir / destination.stem)
        manifest.update(
            {
                "status": "completed",
                "observed_sha256": observed,
                "bytes": destination.stat().st_size,
                "extracted": bool(args.extract),
            }
        )
        write_json(output_dir / "download_manifest.json", manifest)
        print(f"Downloaded {destination} ({manifest['bytes']} bytes; sha256={observed})")
        return 0
    except Exception as exc:  # network and archive failures share a documented exit contract
        manifest.update({"status": "failed", "error": str(exc)})
        write_json(output_dir / "download_manifest.json", manifest)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
