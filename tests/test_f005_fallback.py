"""Tests for _detect_provider_failure helper (F005: Model Family Fallback).

Covers timeout markers, API 5xx/429 errors, auth failures,
connection refused, empty response, and false-positive avoidance.
"""

import os
from conftest import _load_panel as _load


class TestDetectProviderFailure:
    """Task 1: _detect_provider_failure detects provider error patterns."""

    def test_detects_timeout_marker(self):
        panel = _load()
        output = "TIMEOUT: agent exceeded 900s. Partial output above."
        assert panel._detect_provider_failure(output, 0) is True

    def test_detects_api_503_error(self):
        panel = _load()
        output = "[stderr]\nHTTP 503 Service Unavailable"
        assert panel._detect_provider_failure(output, 1) is True

    def test_detects_api_429_rate_limit(self):
        panel = _load()
        output = "HTTP 429 Too Many Requests"
        assert panel._detect_provider_failure(output, 1) is True

    def test_detects_auth_401(self):
        panel = _load()
        output = "401 Unauthorized"
        assert panel._detect_provider_failure(output, 1) is True

    def test_detects_auth_403(self):
        panel = _load()
        output = "403 Forbidden"
        assert panel._detect_provider_failure(output, 1) is True

    def test_detects_connection_refused(self):
        panel = _load()
        output = "Connection refused"
        assert panel._detect_provider_failure(output, 1) is True

    def test_detects_empty_output_with_nonzero_returncode(self):
        panel = _load()
        assert panel._detect_provider_failure("", 1) is True

    def test_normal_output_returns_false(self):
        panel = _load()
        output = "Task completed successfully\nAll tests pass"
        assert panel._detect_provider_failure(output, 0) is False

    def test_none_output_returns_false(self):
        panel = _load()
        assert panel._detect_provider_failure(None, 0) is False

    def test_zero_returncode_no_error_pattern_returns_false(self):
        panel = _load()
        output = "Error: file not found at /path/to/file"
        assert panel._detect_provider_failure(output, 0) is False

    def test_non_error_code_in_output_not_false_positive(self):
        """Words like 'rate' in normal output should not trigger."""
        panel = _load()
        output = "The success rate of tests is 100%"
        assert panel._detect_provider_failure(output, 0) is False

    def test_detects_empty_response_body(self):
        panel = _load()
        output = "[stderr]\nupstream connect error or disconnect/reset before headers"
        assert panel._detect_provider_failure(output, 1) is True


class TestFallbackConfig:
    """Task 2: Fallback env var config loading and validation."""

    def test_fallback_model_validation_rejects_injection(self, monkeypatch):
        """Shell metacharacters in fallback model env var should be rejected."""
        import os
        monkeypatch.setenv("PANEL_FALLBACK_CODER", "deepseek; rm -rf /")
        panel = _load()
        result = panel._load_fallback_config()
        assert "coder" not in result or result["coder"] is None

    def test_fallback_model_validation_accepts_valid(self, monkeypatch):
        """Valid provider/model format should be accepted."""
        monkeypatch.setenv("PANEL_FALLBACK_STRATEGIST", "openrouter/anthropic/claude-sonnet-4")
        monkeypatch.setenv("PANEL_FALLBACK_CODER", "deepseek/deepseek-chat")
        monkeypatch.setenv("PANEL_FALLBACK_TL", "openai/gpt-4o")
        panel = _load()
        result = panel._load_fallback_config()
        assert result["strategist"] == "openrouter/anthropic/claude-sonnet-4"
        assert result["coder"] == "deepseek/deepseek-chat"
        assert result["tl"] == "openai/gpt-4o"

    def test_fallback_config_absent_vars_skipped(self, monkeypatch):
        """Unset env vars should not appear in config."""
        for var in ("PANEL_FALLBACK_STRATEGIST", "PANEL_FALLBACK_CODER", "PANEL_FALLBACK_TL"):
            monkeypatch.delenv(var, raising=False)
        panel = _load()
        result = panel._load_fallback_config()
        assert result == {}

    def test_fallback_config_partial_vars(self, monkeypatch):
        """Only set env vars should appear in config."""
        monkeypatch.setenv("PANEL_FALLBACK_CODER", "deepseek/deepseek-chat")
        monkeypatch.delenv("PANEL_FALLBACK_STRATEGIST", raising=False)
        monkeypatch.delenv("PANEL_FALLBACK_TL", raising=False)
        panel = _load()
        result = panel._load_fallback_config()
        assert result.get("coder") == "deepseek/deepseek-chat"
        assert "strategist" not in result
        assert "tl" not in result

    def test_fallback_validation_rejects_empty_string(self, monkeypatch):
        """Empty string env var should be treated as absent."""
        monkeypatch.setenv("PANEL_FALLBACK_CODER", "")
        panel = _load()
        result = panel._load_fallback_config()
        assert "coder" not in result or result["coder"] is None
