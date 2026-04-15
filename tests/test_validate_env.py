#!/usr/bin/env python3
"""
Unit tests for validate_env.py

Run with:
    python3 -m pytest tests/test_validate_env.py -v
    # or without pytest:
    python3 -m unittest tests.test_validate_env -v
"""

import os
import sys
import unittest

# ──────────────────────────────────────────────────────────────────────────────
# Add the resources/scripts directory to the Python path so we can import
# validate_env without installing it as a package.
# ──────────────────────────────────────────────────────────────────────────────
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), '..', 'resources', 'scripts')
)

import validate_env  # noqa: E402


class TestValidateFunction(unittest.TestCase):
    """Tests for validate_env.validate()."""

    # The full list of required variable names from the production config
    ALL_VAR_NAMES = [v["name"] for v in validate_env.REQUIRED_VARS]

    def _set_all_vars(self):
        """Inject all required env vars with dummy values."""
        for name in self.ALL_VAR_NAMES:
            os.environ[name] = f"test-value-{name.lower()}"

    def _clear_all_vars(self):
        """Remove all required env vars."""
        for name in self.ALL_VAR_NAMES:
            os.environ.pop(name, None)

    def setUp(self):
        """Start each test with a clean slate."""
        self._clear_all_vars()

    def tearDown(self):
        """Clean up after each test."""
        self._clear_all_vars()

    # ── Happy path ───────────────────────────────────────────────────────────

    def test_all_vars_present_passes(self):
        """When every required variable is set, validation passes with 0 failures."""
        self._set_all_vars()
        result = validate_env.validate(validate_env.REQUIRED_VARS)

        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["passed"], len(self.ALL_VAR_NAMES))
        self.assertEqual(result["missing"], [])

    # ── Failure paths ────────────────────────────────────────────────────────

    def test_no_vars_present_fails_all(self):
        """When no variables are set, every one should be reported missing."""
        result = validate_env.validate(validate_env.REQUIRED_VARS)

        self.assertEqual(result["failed"], len(self.ALL_VAR_NAMES))
        self.assertEqual(result["passed"], 0)
        self.assertEqual(len(result["missing"]), len(self.ALL_VAR_NAMES))

    def test_single_missing_var(self):
        """When exactly one variable is missing, only that one is flagged."""
        self._set_all_vars()
        os.environ.pop("DOCKER_PASS")  # Remove just one

        result = validate_env.validate(validate_env.REQUIRED_VARS)

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["passed"], len(self.ALL_VAR_NAMES) - 1)
        missing_names = [v["name"] for v in result["missing"]]
        self.assertIn("DOCKER_PASS", missing_names)

    def test_empty_string_treated_as_missing(self):
        """A variable set to an empty string should count as missing."""
        self._set_all_vars()
        os.environ["DEPLOY_HOST"] = ""

        result = validate_env.validate(validate_env.REQUIRED_VARS)

        self.assertEqual(result["failed"], 1)
        missing_names = [v["name"] for v in result["missing"]]
        self.assertIn("DEPLOY_HOST", missing_names)

    def test_whitespace_only_treated_as_missing(self):
        """A variable with only whitespace should count as missing."""
        self._set_all_vars()
        os.environ["DOCKER_USER"] = "   "

        result = validate_env.validate(validate_env.REQUIRED_VARS)

        self.assertEqual(result["failed"], 1)
        missing_names = [v["name"] for v in result["missing"]]
        self.assertIn("DOCKER_USER", missing_names)

    # ── Result structure ─────────────────────────────────────────────────────

    def test_result_contains_expected_keys(self):
        """The result dict always has the expected top-level keys."""
        result = validate_env.validate(validate_env.REQUIRED_VARS)

        for key in ("timestamp", "total", "passed", "failed", "missing"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_total_equals_input_length(self):
        """'total' should always equal the number of vars we checked."""
        result = validate_env.validate(validate_env.REQUIRED_VARS)
        self.assertEqual(result["total"], len(validate_env.REQUIRED_VARS))

    def test_passed_plus_failed_equals_total(self):
        """passed + failed should always equal total."""
        self._set_all_vars()
        os.environ.pop("APP_NAME")
        os.environ.pop("DEPLOY_ENV")

        result = validate_env.validate(validate_env.REQUIRED_VARS)
        self.assertEqual(result["passed"] + result["failed"], result["total"])

    # ── Custom var list ──────────────────────────────────────────────────────

    def test_custom_var_list(self):
        """validate() should work with any list of var dicts, not just the default."""
        custom_vars = [
            {"name": "MY_CUSTOM_VAR", "description": "test", "stage": "test"},
        ]

        # Not set → should fail
        result = validate_env.validate(custom_vars)
        self.assertEqual(result["failed"], 1)

        # Set → should pass
        os.environ["MY_CUSTOM_VAR"] = "hello"
        result = validate_env.validate(custom_vars)
        self.assertEqual(result["failed"], 0)

        os.environ.pop("MY_CUSTOM_VAR", None)


class TestMainExitCodes(unittest.TestCase):
    """Tests that main() calls sys.exit with the correct code."""

    ALL_VAR_NAMES = [v["name"] for v in validate_env.REQUIRED_VARS]

    def _set_all_vars(self):
        for name in self.ALL_VAR_NAMES:
            os.environ[name] = f"test-value-{name.lower()}"

    def _clear_all_vars(self):
        for name in self.ALL_VAR_NAMES:
            os.environ.pop(name, None)

    def setUp(self):
        self._clear_all_vars()

    def tearDown(self):
        self._clear_all_vars()

    def test_main_exits_0_on_success(self):
        """main() should call sys.exit(0) when all vars are present."""
        self._set_all_vars()
        with self.assertRaises(SystemExit) as ctx:
            validate_env.main()
        self.assertEqual(ctx.exception.code, 0)

    def test_main_exits_1_on_failure(self):
        """main() should call sys.exit(1) when vars are missing."""
        with self.assertRaises(SystemExit) as ctx:
            validate_env.main()
        self.assertEqual(ctx.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
