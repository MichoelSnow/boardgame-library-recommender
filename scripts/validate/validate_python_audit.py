#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Python dependency vulnerabilities with baseline allowlist. "
            "Fails only when new advisories appear."
        )
    )
    parser.add_argument(
        "--allowlist",
        default=".github/pip_audit_allowlist.json",
        help="Path to allowlist JSON file",
    )
    return parser.parse_args()


def run_pip_audit() -> dict[str, Any]:
    command = ["pip-audit", "--format", "json", "--progress-spinner", "off"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "pip-audit is not installed. Install with "
            "`poetry run python -m pip install pip-audit`."
        ) from exc
    payload_text = result.stdout.strip() or result.stderr.strip()
    if not payload_text:
        raise RuntimeError("pip-audit returned no JSON payload.")
    try:
        return json.loads(payload_text)
    except json.JSONDecodeError as exc:
        preview = payload_text[:400].replace("\n", " ")
        raise RuntimeError(
            "Failed to parse pip-audit JSON output. "
            f"pip-audit likely failed before JSON emission. Preview: {preview}"
        ) from exc


def extract_vuln_ids(vuln: dict[str, Any]) -> set[str]:
    """Return normalized advisory IDs from one vulnerability record."""
    ids: set[str] = set()

    primary_id = vuln.get("id")
    if primary_id:
        ids.add(str(primary_id))

    advisory = vuln.get("advisory")
    if isinstance(advisory, dict):
        advisory_id = advisory.get("id")
        if advisory_id:
            ids.add(str(advisory_id))
        advisory_aliases = advisory.get("aliases", [])
        if isinstance(advisory_aliases, list):
            ids.update(str(alias) for alias in advisory_aliases if alias)
    elif advisory:
        ids.add(str(advisory))

    aliases = vuln.get("aliases", [])
    if isinstance(aliases, list):
        ids.update(str(alias) for alias in aliases if alias)

    return ids


def extract_vulnerability_ids(audit_payload: dict[str, Any]) -> set[str]:
    dependency_records = audit_payload.get("dependencies", [])
    advisory_ids: set[str] = set()
    for dep in dependency_records:
        for vuln in dep.get("vulns", []):
            if isinstance(vuln, dict):
                advisory_ids.update(extract_vuln_ids(vuln))
    return advisory_ids


def extract_unexpected_advisories(
    audit_payload: dict[str, Any], allowed_ids: set[str]
) -> list[tuple[str, str, str]]:
    """Return (advisory_id, package_name, package_version) tuples."""
    dependency_records = audit_payload.get("dependencies", [])
    rows: list[tuple[str, str, str]] = []
    for dep in dependency_records:
        package_name = str(dep.get("name", "unknown"))
        package_version = str(dep.get("version", "unknown"))
        for vuln in dep.get("vulns", []):
            if not isinstance(vuln, dict):
                continue
            for advisory_id in sorted(extract_vuln_ids(vuln)):
                if advisory_id and advisory_id not in allowed_ids:
                    rows.append((advisory_id, package_name, package_version))
    rows.sort(key=lambda row: (row[0], row[1], row[2]))
    return rows


def load_allowlist(path: Path) -> set[str]:
    payload = json.loads(path.read_text())
    values = payload.get("allowed_vulnerability_ids", [])
    if not isinstance(values, list):
        raise RuntimeError("Allowlist key allowed_vulnerability_ids must be a list.")
    return {str(item) for item in values}


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    allowlist_input = Path(args.allowlist)
    allowlist_candidates = (
        [allowlist_input]
        if allowlist_input.is_absolute()
        else [Path.cwd() / allowlist_input, repo_root / allowlist_input]
    )
    allowlist_path = next(
        (path.resolve() for path in allowlist_candidates if path.exists()),
        None,
    )
    if allowlist_path is None:
        raise RuntimeError(f"Allowlist file not found: {args.allowlist}")

    try:
        audit_payload = run_pip_audit()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1
    advisory_ids = extract_vulnerability_ids(audit_payload)
    allowed_ids = load_allowlist(allowlist_path)

    unexpected = sorted(advisory_ids - allowed_ids)
    if unexpected:
        unexpected_rows = extract_unexpected_advisories(audit_payload, allowed_ids)
        print("ERROR: New Python dependency advisories detected:")
        for advisory_id in unexpected:
            matching_rows = [
                row for row in unexpected_rows if row[0] == advisory_id
            ] or [(advisory_id, "unknown", "unknown")]
            for _, package_name, package_version in matching_rows:
                print(f"- {advisory_id} ({package_name}=={package_version})")
        print("")
        print("Update dependencies or add advisory IDs to allowlist with rationale.")
        return 1

    print(
        "Python dependency audit passed under baseline policy. "
        f"Observed advisories: {len(advisory_ids)}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
