#!/usr/bin/env python3
"""
validate_env.py — Pre-flight Environment Validator

Runs at the very start of the Jenkins pipeline to verify that all required
environment variables and secrets are present *before* any compute-heavy
stages execute.  Uses only Python standard-library modules so it works on
bare-bones Jenkins worker nodes.

Exit codes:
    0 — all checks passed
    1 — one or more required variables are missing

Environment variable requirements are defined inline in REQUIRED_VARS below.
Each entry is a dict with:
    name        (str)  — the env-var name to check
    description (str)  — human-readable purpose (used in error messages)
    stage       (str)  — which pipeline stage needs it
"""

import os
import sys
import json
from datetime import datetime, timezone

# ──────────────────────────────────────────────────────────────────────────────
# Configuration: define every variable your pipeline depends on
# ──────────────────────────────────────────────────────────────────────────────
REQUIRED_VARS = [
    # --- Core pipeline metadata (set by standardMicroservicePipeline) --------
    {
        "name": "APP_NAME",
        "description": "Application / service name",
        "stage": "all",
    },
    {
        "name": "DEPLOY_ENV",
        "description": "Target deployment environment (e.g. staging, production)",
        "stage": "deploy",
    },
    {
        "name": "DOCKER_REGISTRY",
        "description": "Container registry URL (e.g. registry.example.com)",
        "stage": "build-container",
    },
    # --- Docker credentials (injected via Jenkins Credentials Binding) -------
    {
        "name": "DOCKER_USER",
        "description": "Docker registry username",
        "stage": "build-container",
    },
    {
        "name": "DOCKER_PASS",
        "description": "Docker registry password / token",
        "stage": "build-container",
    },
    # --- Deployment target ---------------------------------------------------
    {
        "name": "DEPLOY_HOST",
        "description": "Target host IP or hostname for deployment",
        "stage": "deploy",
    },
]


def validate(required_vars: list[dict]) -> dict:
    """Check every entry in *required_vars* against the live environment.

    Returns a results dict:
        {
            "timestamp": "...",
            "total":     int,
            "passed":    int,
            "failed":    int,
            "missing":   [ { "name": ..., "description": ..., "stage": ... }, ... ]
        }
    """
    missing = []
    for var in required_vars:
        value = os.environ.get(var["name"])
        if not value or value.strip() == "":
            missing.append(var)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(required_vars),
        "passed": len(required_vars) - len(missing),
        "failed": len(missing),
        "missing": missing,
    }


def print_report(results: dict) -> None:
    """Pretty-print a human-readable validation report to stdout."""
    divider = "=" * 62
    print()
    print(divider)
    print("  PRE-FLIGHT ENVIRONMENT VALIDATION")
    print(divider)
    print(f"  Timestamp : {results['timestamp']}")
    print(f"  Checked   : {results['total']} variables")
    print(f"  Passed    : {results['passed']}")
    print(f"  Failed    : {results['failed']}")
    print(divider)

    if results["missing"]:
        print()
        print("  MISSING VARIABLES:")
        print()
        for var in results["missing"]:
            print(f"    • {var['name']}")
            print(f"      ↳ {var['description']}")
            print(f"      ↳ Required by stage: {var['stage']}")
            print()
    else:
        print()
        print("  All required environment variables are present.")
        print()

    print(divider)


def main() -> None:
    results = validate(REQUIRED_VARS)
    print_report(results)

    # Also dump machine-readable JSON for downstream tooling
    print("\n--- JSON Report ---")
    print(json.dumps(results, indent=2))

    if results["failed"] > 0:
        print(
            f"\nValidation FAILED: {results['failed']} variable(s) missing. "
            "Pipeline will abort to save resources.\n"
        )
        sys.exit(1)

    print("\nValidation PASSED: proceeding with pipeline.\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
