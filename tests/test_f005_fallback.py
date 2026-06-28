"""Tests for _detect_provider_failure helper (F005: Model Family Fallback)."""
import sys
import os
import types


PANEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dokima"))


def _load_panel():
    """Load dokima as a Python module for testing."""
    module = types.ModuleType("dokima")
    module.__file__ = PANEL_PATH
    module.PROJECT_DIR = "/tmp/test-project"
    module.REPO = "test-owner/test-repo"
    module.API_KEY = "test-key"
    module.PANEL_FEATURE = "Test Feature"
    module.DEFAULT_BRANCH = "main"
    module.TEST_CMD = "echo test"
    module.BUILD_CMD = "echo build"
    module.LINT_CMD = "echo lint"
    with open(PANEL_PATH) as f:
        code = compile(f.read(), PANEL_PATH, "exec")
    exec(code, module.__dict__)
    return module


class TestDetectProviderFailure:
    """Task 2: _detect_provider_failure detects provider error patterns."""

    def test_detects_rate_limit(self):
        module = _load_panel()
        assert module._detect_provider_failure("rate limit exceeded") is True

    def test_detects_http_503(self):
        module = _load_panel()
        assert module._detect_provider_failure("HTTP 503 Service Unavailable") is True

    def test_detects_service_unavailable(self):
        module = _load_panel()
        assert module._detect_provider_failure("Service Unavailable") is True

    def test_detects_provider_error(self):
        module = _load_panel()
        assert module._detect_provider_failure("provider.error: upstream timeout") is True

    def test_detects_model_not_found(self):
        module = _load_panel()
        assert module._detect_provider_failure("model 'claude-3' not found") is True

    def test_detects_model_not_available(self):
        module = _load_panel()
        assert module._detect_provider_failure("model.not.available") is True

    def test_detects_connection_refused(self):
        module = _load_panel()
        assert module._detect_provider_failure("connection refused") is True

    def test_returns_false_for_valid_output(self):
        module = _load_panel()
        assert module._detect_provider_failure("Task completed successfully") is False

    def test_handles_empty_string(self):
        module = _load_panel()
        assert module._detect_provider_failure("") is False

    def test_handles_none(self):
        module = _load_panel()
        assert module._detect_provider_failure(None) is False

    def test_does_not_false_positive_on_code_error(self):
        module = _load_panel()
        output = "Error: file not found at /path/to/file"
        assert module._detect_provider_failure(output) is False

    def test_does_not_false_positive_on_normal_rate_usage(self):
        """Words like 'rate' in normal output should not trigger."""
        module = _load_panel()
        output = "The success rate of tests is 100%"
        assert module._detect_provider_failure(output) is False


class TestSelectFallbackModel:
    """Task 4: _select_fallback_model picks the right fallback model on failure."""

    def test_selects_fallback_when_provider_failure(self):
        module = _load_panel()
        result = module._select_fallback_model(
            "deepseek/deepseek-chat", "rate limit exceeded"
        )
        assert result is not None
        assert isinstance(result, str)

    def test_returns_correct_fallback_model(self):
        module = _load_panel()
        result = module._select_fallback_model(
            "deepseek/deepseek-chat", "HTTP 503 Service Unavailable"
        )
        assert result == "openrouter/anthropic/claude-sonnet-4-20250514"

    def test_no_fallback_when_output_valid(self):
        module = _load_panel()
        result = module._select_fallback_model(
            "deepseek/deepseek-chat", "Task completed successfully"
        )
        assert result is None

    def test_no_fallback_for_unknown_model(self):
        module = _load_panel()
        result = module._select_fallback_model(
            "unknown/model", "rate limit exceeded"
        )
        assert result is None

    def test_no_fallback_for_empty_output(self):
        module = _load_panel()
        result = module._select_fallback_model("deepseek/deepseek-chat", "")
        assert result is None

    def test_no_fallback_for_none_output(self):
        module = _load_panel()
        result = module._select_fallback_model("deepseek/deepseek-chat", None)
        assert result is None
