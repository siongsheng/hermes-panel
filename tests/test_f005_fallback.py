"""F005: Model Family Fallback — Tests.

Tests cover:
  - PANEL_FALLBACK_MODEL env-var parsing (Task 1)
  - _detect_provider_failure helper (Task 2)
  - spawn_agent fallback retry logic (Task 3)
  - No false-positive on legitimate output (Task 6)
"""
import os
import sys
import subprocess
import pytest
from unittest.mock import patch

from conftest import _load_panel as _load


# ── Task 1: FALLBACK_MODEL env-var constant ──────────────────────────

class TestFallbackModelConstant:
    """FALLBACK_MODEL global is read from PANEL_FALLBACK_MODEL at module init."""

    def test_reads_from_env_var(self):
        """FALLBACK_MODEL matches PANEL_FALLBACK_MODEL env var."""
        model = "openrouter/anthropic/claude-sonnet-4"
        os.environ["PANEL_FALLBACK_MODEL"] = model
        try:
            panel = _load()
            assert panel.FALLBACK_MODEL == model
        finally:
            os.environ.pop("PANEL_FALLBACK_MODEL", None)

    def test_defaults_to_empty_string(self):
        """When PANEL_FALLBACK_MODEL is unset, FALLBACK_MODEL is empty string."""
        os.environ.pop("PANEL_FALLBACK_MODEL", None)
        panel = _load()
        assert panel.FALLBACK_MODEL == ""

    def test_does_not_crash_on_missing_var(self):
        """Module loads cleanly even without the env var."""
        os.environ.pop("PANEL_FALLBACK_MODEL", None)
        panel = _load()
        assert hasattr(panel, "FALLBACK_MODEL")
