#!/usr/bin/env python3
"""
Unit tests for verify_deploy.py

Run with:
    python3 -m pytest tests/test_verify_deploy.py -v
    # or without pytest:
    python3 -m unittest tests.test_verify_deploy -v
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# -------------------------------------------------------------------------
# Add the resources/scripts directory to the Python path so we can import
# verify_deploy without installing it as a package.
# -------------------------------------------------------------------------
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), '..', 'resources', 'scripts')
)

import verify_deploy  # noqa: E402


class TestCheckEnv(unittest.TestCase):
    """Tests for verify_deploy.check_env()."""

    REQUIRED = verify_deploy.REQUIRED_VARS

    def _set_all_vars(self):
        for name in self.REQUIRED:
            os.environ[name] = f"test-{name.lower()}"

    def _clear_all_vars(self):
        for name in self.REQUIRED:
            os.environ.pop(name, None)

    def setUp(self):
        self._clear_all_vars()

    def tearDown(self):
        self._clear_all_vars()

    def test_all_present(self):
        """When every required variable is set, check_env reports ok."""
        self._set_all_vars()
        result = verify_deploy.check_env()
        self.assertTrue(result["ok"])
        self.assertEqual(result["missing"], [])

    def test_all_missing(self):
        """When no variables are set, all are reported missing."""
        result = verify_deploy.check_env()
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["missing"]), len(self.REQUIRED))

    def test_single_missing(self):
        """When one variable is absent, only that one is flagged."""
        self._set_all_vars()
        os.environ.pop("APP_PORT")
        result = verify_deploy.check_env()
        self.assertFalse(result["ok"])
        self.assertIn("APP_PORT", result["missing"])
        self.assertEqual(len(result["missing"]), 1)

    def test_whitespace_treated_as_missing(self):
        """A variable set to whitespace only should count as missing."""
        self._set_all_vars()
        os.environ["DEPLOY_HOST"] = "   "
        result = verify_deploy.check_env()
        self.assertFalse(result["ok"])
        self.assertIn("DEPLOY_HOST", result["missing"])


class TestCheckContainer(unittest.TestCase):
    """Tests for verify_deploy.check_container()."""

    @patch("verify_deploy.subprocess.run")
    def test_running_container(self, mock_run):
        """A container reporting 'running' status should pass."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="running\n", stderr=""
        )
        result = verify_deploy.check_container("10.0.0.1", "my-app-staging")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "running")

    @patch("verify_deploy.subprocess.run")
    def test_exited_container(self, mock_run):
        """A container reporting 'exited' status should fail."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="exited\n", stderr=""
        )
        result = verify_deploy.check_container("10.0.0.1", "my-app-staging")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "exited")

    @patch("verify_deploy.subprocess.run")
    def test_ssh_failure(self, mock_run):
        """A non-zero exit code from SSH should report an error."""
        mock_run.return_value = MagicMock(
            returncode=255, stdout="", stderr="Connection refused"
        )
        result = verify_deploy.check_container("10.0.0.1", "my-app-staging")
        self.assertFalse(result["ok"])
        self.assertIn("Connection refused", result["error"])

    @patch("verify_deploy.subprocess.run")
    def test_timeout(self, mock_run):
        """An SSH timeout should report an error."""
        import subprocess as sp
        mock_run.side_effect = sp.TimeoutExpired(cmd="ssh", timeout=30)
        result = verify_deploy.check_container("10.0.0.1", "my-app-staging")
        self.assertFalse(result["ok"])
        self.assertIn("timed out", result["error"])


class TestCheckHealth(unittest.TestCase):
    """Tests for verify_deploy.check_health()."""

    @patch("verify_deploy.urlopen")
    def test_healthy_endpoint(self, mock_urlopen):
        """A 200 response from /health should pass."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response

        result = verify_deploy.check_health("10.0.0.1", "8080")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 200)

    @patch("verify_deploy.urlopen")
    def test_unhealthy_endpoint(self, mock_urlopen):
        """A non-200 response should fail."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 503
        mock_urlopen.return_value = mock_response

        result = verify_deploy.check_health("10.0.0.1", "8080")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status_code"], 503)

    @patch("verify_deploy.urlopen")
    def test_unreachable_endpoint(self, mock_urlopen):
        """A connection error should report status_code 0 and an error."""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Connection refused")

        result = verify_deploy.check_health("10.0.0.1", "8080")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status_code"], 0)
        self.assertIn("Connection refused", result["error"])


class TestVerify(unittest.TestCase):
    """Tests for the top-level verify_deploy.verify() orchestrator."""

    REQUIRED = verify_deploy.REQUIRED_VARS

    def _set_all_vars(self):
        os.environ["APP_NAME"] = "order-service"
        os.environ["APP_PORT"] = "8080"
        os.environ["DEPLOY_ENV"] = "staging"
        os.environ["DEPLOY_HOST"] = "10.0.0.1"

    def _clear_all_vars(self):
        for name in self.REQUIRED:
            os.environ.pop(name, None)

    def setUp(self):
        self._clear_all_vars()

    def tearDown(self):
        self._clear_all_vars()

    def test_missing_env_skips_all_checks(self):
        """When env vars are missing, container and health checks are skipped."""
        result = verify_deploy.verify()
        self.assertEqual(result["checks_failed"], 3)
        self.assertFalse(result["env"]["ok"])
        self.assertIn("skipped", result["container"]["error"])
        self.assertIn("skipped", result["health"]["error"])

    @patch("verify_deploy.check_health")
    @patch("verify_deploy.check_container")
    def test_all_checks_pass(self, mock_container, mock_health):
        """When env is set and both checks pass, all 3 checks should pass."""
        self._set_all_vars()
        mock_container.return_value = {"ok": True, "status": "running", "error": ""}
        mock_health.return_value = {"ok": True, "status_code": 200, "error": ""}

        result = verify_deploy.verify()
        self.assertEqual(result["checks_passed"], 3)
        self.assertEqual(result["checks_failed"], 0)

    @patch("verify_deploy.check_health")
    @patch("verify_deploy.check_container")
    def test_container_down(self, mock_container, mock_health):
        """When the container is down, exactly 1 check should fail."""
        self._set_all_vars()
        mock_container.return_value = {"ok": False, "status": "exited", "error": ""}
        mock_health.return_value = {"ok": True, "status_code": 200, "error": ""}

        result = verify_deploy.verify()
        self.assertEqual(result["checks_passed"], 2)
        self.assertEqual(result["checks_failed"], 1)

    def test_result_contains_expected_keys(self):
        """The result dict always has the expected top-level keys."""
        result = verify_deploy.verify()
        for key in ("timestamp", "checks_total", "checks_passed",
                     "checks_failed", "env", "container", "health"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_passed_plus_failed_equals_total(self):
        """checks_passed + checks_failed should always equal checks_total."""
        result = verify_deploy.verify()
        self.assertEqual(
            result["checks_passed"] + result["checks_failed"],
            result["checks_total"],
        )


class TestMainExitCodes(unittest.TestCase):
    """Tests that main() calls sys.exit with the correct code."""

    REQUIRED = verify_deploy.REQUIRED_VARS

    def _set_all_vars(self):
        os.environ["APP_NAME"] = "order-service"
        os.environ["APP_PORT"] = "8080"
        os.environ["DEPLOY_ENV"] = "staging"
        os.environ["DEPLOY_HOST"] = "10.0.0.1"

    def _clear_all_vars(self):
        for name in self.REQUIRED:
            os.environ.pop(name, None)

    def setUp(self):
        self._clear_all_vars()

    def tearDown(self):
        self._clear_all_vars()

    @patch("verify_deploy.check_health")
    @patch("verify_deploy.check_container")
    def test_main_exits_0_on_success(self, mock_container, mock_health):
        """main() should call sys.exit(0) when all checks pass."""
        self._set_all_vars()
        mock_container.return_value = {"ok": True, "status": "running", "error": ""}
        mock_health.return_value = {"ok": True, "status_code": 200, "error": ""}

        with self.assertRaises(SystemExit) as ctx:
            verify_deploy.main()
        self.assertEqual(ctx.exception.code, 0)

    def test_main_exits_1_on_failure(self):
        """main() should call sys.exit(1) when checks fail."""
        with self.assertRaises(SystemExit) as ctx:
            verify_deploy.main()
        self.assertEqual(ctx.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
