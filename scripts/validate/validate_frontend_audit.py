#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


HIGH_SEVERITIES = {"high", "critical"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate frontend npm audit with baseline allowlist. "
            "Fails only when new high/critical vulnerable packages appear."
        )
    )
    parser.add_argument(
        "--frontend-dir",
        default="frontend",
        help="Path to frontend directory containing package.json",
    )
    parser.add_argument(
        "--allowlist",
        default=".github/npm_audit_allowlist.json",
        help="Path to allowlist JSON file",
    )
    return parser.parse_args()


def run_npm_audit(frontend_dir: Path) -> dict:
    command = ["npm", "audit", "--omit=dev", "--json"]
    result = subprocess.run(
        command,
        cwd=frontend_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    # npm audit returns non-zero when vulnerabilities are present; still parse output.
    payload_text = result.stdout.strip() or result.stderr.strip()
    if not payload_text:
        raise RuntimeError("npm audit returned no JSON payload.")

    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse npm audit JSON output: {exc}") from exc

    return payload


def extract_high_critical_packages(audit_payload: dict) -> set[str]:
    vulnerabilities = audit_payload.get("vulnerabilities", {})
    risky_packages: set[str] = set()
    for package_name, details in vulnerabilities.items():
        severity = str(details.get("severity", "")).lower()
        if severity in HIGH_SEVERITIES:
            risky_packages.add(package_name)
    return risky_packages


def load_allowlist(path: Path) -> set[str]:
    payload = json.loads(path.read_text())
    values = payload.get("allowed_high_or_critical_packages", [])
    if not isinstance(values, list):
        raise RuntimeError("Allowlist key allowed_high_or_critical_packages must be a list.")
    return {str(item) for item in values}


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    frontend_input = Path(args.frontend_dir)
    frontend_candidates = (
        [frontend_input]
        if frontend_input.is_absolute()
        else [Path.cwd() / frontend_input, repo_root / frontend_input]
    )
    frontend_dir = next((path.resolve() for path in frontend_candidates if path.exists()), None)
    if frontend_dir is None:
        cwd_frontend = Path.cwd()
        if (cwd_frontend / "package.json").exists():
            frontend_dir = cwd_frontend.resolve()
        else:
            raise RuntimeError(f"Frontend directory not found: {args.frontend_dir}")

    allowlist_input = Path(args.allowlist)
    allowlist_candidates = (
        [allowlist_input]
        if allowlist_input.is_absolute()
        else [Path.cwd() / allowlist_input, repo_root / allowlist_input]
    )
    allowlist_path = next((path.resolve() for path in allowlist_candidates if path.exists()), None)
    if allowlist_path is None:
        raise RuntimeError(f"Allowlist file not found: {args.allowlist}")

    audit_payload = run_npm_audit(frontend_dir)
    risky_packages = extract_high_critical_packages(audit_payload)
    allowed_packages = load_allowlist(allowlist_path)

    unexpected = sorted(risky_packages - allowed_packages)
    if unexpected:
        print("ERROR: New high/critical frontend vulnerabilities detected:")
        for package_name in unexpected:
            print(f"- {package_name}")
        print("")
        print("Update dependencies or intentionally add packages to allowlist with rationale.")
        return 1

    print(
        "Frontend audit passed under baseline policy. "
        f"Observed high/critical packages: {len(risky_packages)}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
