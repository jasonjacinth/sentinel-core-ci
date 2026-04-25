#!/usr/bin/env python3
"""
verify_deploy.py -- Post-deploy Verification

Runs as the final pipeline stage after deployment to confirm the newly
deployed container is healthy.  Uses only Python standard-library modules
so it works on bare-bones Jenkins worker nodes.

Checks performed:
    1. Container status   -- SSH into DEPLOY_HOST and verify the Docker
                             container is in the "running" state.
    2. HTTP health probe  -- Send a GET request to the app's /health
                             endpoint and assert a 200 response.

Environment variables required:
    APP_NAME     -- application / service name
    APP_PORT     -- port the application listens on
    DEPLOY_ENV   -- target environment (staging, production, etc.)
    DEPLOY_HOST  -- IP or hostname of the deployment target

Exit codes:
    0 -- all checks passed
    1 -- one or more checks failed
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import urlopen

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
REQUIRED_VARS = ["APP_NAME", "APP_PORT", "DEPLOY_ENV", "DEPLOY_HOST"]

HEALTH_ENDPOINT = "/health"
HEALTH_TIMEOUT_SECONDS = 10


def check_env() -> dict:
    """Verify all required environment variables are present.

    Returns a dict with:
        ok      (bool)  -- True if all vars are set
        missing (list)  -- names of missing variables
    """
    missing = [
        name
        for name in REQUIRED_VARS
        if not os.environ.get(name, "").strip()
    ]
    return {"ok": len(missing) == 0, "missing": missing}


def check_container(deploy_host: str, container_name: str) -> dict:
    """SSH into *deploy_host* and check that *container_name* is running.

    Returns a dict with:
        ok      (bool) -- True if the container is in "running" state
        status  (str)  -- raw status string from docker inspect
        error   (str)  -- error message if the check could not be performed
    """
    cmd = (
        f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "
        f"deployer@{deploy_host} "
        f"\"docker inspect -f '{{{{.State.Status}}}}' {container_name}\""
    )
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        status = result.stdout.strip().lower()
        if result.returncode != 0:
            return {
                "ok": False,
                "status": "",
                "error": result.stderr.strip() or "non-zero exit code",
            }
        return {
            "ok": status == "running",
            "status": status,
            "error": "",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "", "error": "SSH command timed out"}
    except Exception as exc:
        return {"ok": False, "status": "", "error": str(exc)}


def check_health(deploy_host: str, app_port: str) -> dict:
    """Send an HTTP GET to the app's health endpoint.

    Returns a dict with:
        ok          (bool) -- True if HTTP 200 was received
        status_code (int)  -- HTTP status code (0 if unreachable)
        error       (str)  -- error message if the probe failed
    """
    url = f"http://{deploy_host}:{app_port}{HEALTH_ENDPOINT}"
    try:
        response = urlopen(url, timeout=HEALTH_TIMEOUT_SECONDS)
        code = response.getcode()
        return {"ok": code == 200, "status_code": code, "error": ""}
    except URLError as exc:
        return {"ok": False, "status_code": 0, "error": str(exc.reason)}
    except Exception as exc:
        return {"ok": False, "status_code": 0, "error": str(exc)}


def verify() -> dict:
    """Run all post-deploy checks and return a structured report.

    Returns:
        {
            "timestamp":       str,
            "checks_total":    int,
            "checks_passed":   int,
            "checks_failed":   int,
            "env":             { "ok": bool, "missing": [...] },
            "container":       { "ok": bool, "status": str, "error": str },
            "health":          { "ok": bool, "status_code": int, "error": str }
        }
    """
    env_result = check_env()

    if not env_result["ok"]:
        # Cannot run further checks without required variables
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks_total": 3,
            "checks_passed": 0,
            "checks_failed": 3,
            "env": env_result,
            "container": {"ok": False, "status": "", "error": "skipped (missing env vars)"},
            "health": {"ok": False, "status_code": 0, "error": "skipped (missing env vars)"},
        }

    deploy_host = os.environ["DEPLOY_HOST"]
    app_name = os.environ["APP_NAME"]
    deploy_env = os.environ["DEPLOY_ENV"]
    app_port = os.environ["APP_PORT"]
    container_name = f"{app_name}-{deploy_env}"

    container_result = check_container(deploy_host, container_name)
    health_result = check_health(deploy_host, app_port)

    results = [env_result, container_result, health_result]
    passed = sum(1 for r in results if r["ok"])

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks_total": 3,
        "checks_passed": passed,
        "checks_failed": 3 - passed,
        "env": env_result,
        "container": container_result,
        "health": health_result,
    }


def print_report(results: dict) -> None:
    """Pretty-print a human-readable verification report to stdout."""
    divider = "=" * 62
    print()
    print(divider)
    print("  POST-DEPLOY VERIFICATION")
    print(divider)
    print(f"  Timestamp : {results['timestamp']}")
    print(f"  Checks    : {results['checks_total']}")
    print(f"  Passed    : {results['checks_passed']}")
    print(f"  Failed    : {results['checks_failed']}")
    print(divider)

    # Environment check
    env = results["env"]
    icon = "[PASS]" if env["ok"] else "[FAIL]"
    print(f"\n  {icon} Environment Variables")
    if not env["ok"]:
        print(f"         Missing: {', '.join(env['missing'])}")

    # Container check
    ctr = results["container"]
    icon = "[PASS]" if ctr["ok"] else "[FAIL]"
    print(f"  {icon} Container Status")
    if ctr["ok"]:
        print(f"         Status: {ctr['status']}")
    elif ctr["error"]:
        print(f"         Error: {ctr['error']}")

    # Health probe
    hlt = results["health"]
    icon = "[PASS]" if hlt["ok"] else "[FAIL]"
    print(f"  {icon} HTTP Health Probe")
    if hlt["ok"]:
        print(f"         HTTP {hlt['status_code']}")
    elif hlt["error"]:
        print(f"         Error: {hlt['error']}")

    print()
    print(divider)


def main() -> None:
    results = verify()
    print_report(results)

    # Machine-readable output for downstream tooling
    print("\n--- JSON Report ---")
    print(json.dumps(results, indent=2))

    if results["checks_failed"] > 0:
        print(
            f"\nVerification FAILED: {results['checks_failed']} check(s) failed. "
            "Review the report above.\n"
        )
        sys.exit(1)

    print("\nVerification PASSED: deployment is healthy.\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
