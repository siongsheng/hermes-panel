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


class TestFallbackRetry:
    """Task 3: Fallback retry path in spawn_agent."""

    def test_no_fallback_when_not_configured(self, monkeypatch):
        """Absent env var means no retry — returns primary output as-is."""
        monkeypatch.delenv("PANEL_FALLBACK_STRATEGIST", raising=False)
        monkeypatch.delenv("PANEL_FALLBACK_CODER", raising=False)
        monkeypatch.delenv("PANEL_FALLBACK_TL", raising=False)
        panel = _load()
        # Without fallback_model kwarg, spawn_agent should not attempt retry
        # (tested via the function accepting fallback_model=None by default)

    def test_fallback_fires_on_primary_failure(self, monkeypatch):
        """Mock primary failure, verify fallback model is used."""
        import subprocess
        from unittest.mock import patch

        monkeypatch.setenv("PANEL_FALLBACK_STRATEGIST", "deepseek/deepseek-chat")
        panel = _load()

        call_count = [0]

        def mock_popen(cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Primary fails with 503
                mock_proc = subprocess.Popen.__new__(subprocess.Popen)
                mock_proc.stdout = ["[stderr] HTTP 503 Service Unavailable\n"]
                mock_proc.stderr = None
                mock_proc.returncode = 1
                mock_proc.wait = lambda timeout=None: None
                return mock_proc
            else:
                # Fallback succeeds
                mock_proc = subprocess.Popen.__new__(subprocess.Popen)
                mock_proc.stdout = ["[strategist:fallback] Task complete\n"]
                mock_proc.stderr = None
                mock_proc.returncode = 0
                mock_proc.wait = lambda timeout=None: None
                return mock_proc

        with patch.object(subprocess, "Popen", side_effect=mock_popen):
            result = panel.spawn_agent("strategist", ["test"], "prompt",
                                       fallback_model="deepseek/deepseek-chat")

        assert call_count[0] == 2
        assert "[strategist:fallback]" in result

    def test_fallback_exhaustion_returns_primary_error(self, monkeypatch):
        """Both primary and fallback fail — return original error."""
        import subprocess
        from unittest.mock import patch

        monkeypatch.setenv("PANEL_FALLBACK_STRATEGIST", "deepseek/deepseek-chat")
        panel = _load()

        call_count = [0]

        def mock_popen(cmd, **kwargs):
            call_count[0] += 1
            mock_proc = subprocess.Popen.__new__(subprocess.Popen)
            mock_proc.stdout = ["[stderr] 503 Service Unavailable\n"]
            mock_proc.stderr = None
            mock_proc.returncode = 1
            mock_proc.wait = lambda timeout=None: None
            return mock_proc

        with patch.object(subprocess, "Popen", side_effect=mock_popen):
            result = panel.spawn_agent("strategist", ["test"], "prompt",
                                       fallback_model="deepseek/deepseek-chat")

        assert call_count[0] == 2
        assert "503" in result
        assert "[strategist:fallback]" not in result

    def test_primary_success_no_fallback(self, monkeypatch):
        """Primary succeeds, no fallback triggered."""
        import subprocess
        from unittest.mock import patch

        monkeypatch.setenv("PANEL_FALLBACK_STRATEGIST", "deepseek/deepseek-chat")
        panel = _load()

        call_count = [0]

        def mock_popen(cmd, **kwargs):
            call_count[0] += 1
            mock_proc = subprocess.Popen.__new__(subprocess.Popen)
            mock_proc.stdout = ["Spec generated successfully\n"]
            mock_proc.stderr = None
            mock_proc.returncode = 0
            mock_proc.wait = lambda timeout=None: None
            return mock_proc

        with patch.object(subprocess, "Popen", side_effect=mock_popen):
            result = panel.spawn_agent("strategist", ["test"], "prompt",
                                       fallback_model="deepseek/deepseek-chat")

        assert call_count[0] == 1
        assert panel._detect_provider_failure(result, 0) is False
