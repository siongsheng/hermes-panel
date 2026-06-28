"""Tests for _detect_provider_failure helper (F005: Model Family Fallback)."""
import sys
import os
import types
import unittest


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


class TestSpawnAgentFallbackRetry:
    """Task 3: spawn_agent retries with FALLBACK_MODEL on provider failure."""

    def _make_mock_proc(self, lines, returncode=0, stderr=""):
        """Create a mock Popen instance that yields given lines on stdout."""
        class MockProc:
            def __init__(self, lines, returncode, stderr):
                self._lines = lines
                self.returncode = returncode
                self._stderr = stderr

            @property
            def stdout(self):
                class StdoutIter:
                    def __init__(self, lines):
                        self._lines = lines
                        self._idx = 0
                    def __iter__(self):
                        return self
                    def __next__(self):
                        if self._idx >= len(self._lines):
                            raise StopIteration
                        self._idx += 1
                        return self._lines[self._idx - 1]
                return StdoutIter(self._lines)

            @property
            def stderr(self):
                class StderrReader:
                    def __init__(self, text):
                        self._text = text
                    def read(self):
                        return self._text
                return StderrReader(self._stderr)

            def wait(self, timeout=None):
                return None

            def kill(self):
                pass

            def terminate(self):
                pass

            def communicate(self, timeout=None):
                return (None, self._stderr)

        return MockProc(lines, returncode, stderr)

    def test_fallback_triggers_on_provider_failure(self):
        """When first spawn fails with provider error, fallback model is used."""
        import subprocess
        calls = []

        def mock_popen(cmd, **kwargs):
            calls.append(cmd)
            # First call: fail with provider error
            if len(calls) == 1:
                proc = self._make_mock_proc(
                    ["Error output"],
                    returncode=1,
                    stderr="rate limit exceeded\n"
                )
                proc.returncode = 1
                return proc
            # Second call: succeed
            return self._make_mock_proc(
                ["Fallback agent response\n"],
                returncode=0
            )

        module = _load_panel()
        module.FALLBACK_MODEL = "openrouter/anthropic/claude-sonnet-4"
        module.HERMES_BIN = "/usr/bin/hermes"

        with unittest.mock.patch("subprocess.Popen", mock_popen):
            result = module.spawn_agent("coder", ["test-skill"], "test prompt", timeout=30)

        assert "Fallback agent response" in result, f"Expected fallback output, got: {result}"
        assert len(calls) == 2, f"Expected 2 calls (original + fallback), got {len(calls)}"

    def test_fallback_suppressed_when_model_unset(self):
        """When FALLBACK_MODEL is empty, no retry occurs."""
        import subprocess
        calls = []

        def mock_popen(cmd, **kwargs):
            calls.append(cmd)
            return self._make_mock_proc(
                ["Error output"],
                returncode=1,
                stderr="503 Service Unavailable\n"
            )

        module = _load_panel()
        module.FALLBACK_MODEL = ""
        module.HERMES_BIN = "/usr/bin/hermes"

        with unittest.mock.patch("subprocess.Popen", mock_popen):
            result = module.spawn_agent("coder", ["test-skill"], "test prompt", timeout=30)

        assert "Error output" in result
        assert len(calls) == 1, f"Expected 1 call (no fallback), got {len(calls)}"

    def test_fallback_does_not_fire_on_legitimate_output(self):
        """Normal agent output should not trigger fallback."""
        import subprocess
        calls = []

        def mock_popen(cmd, **kwargs):
            calls.append(cmd)
            return self._make_mock_proc(
                ["Task completed successfully\n"],
                returncode=0
            )

        module = _load_panel()
        module.FALLBACK_MODEL = "openrouter/anthropic/claude-sonnet-4"
        module.HERMES_BIN = "/usr/bin/hermes"

        with unittest.mock.patch("subprocess.Popen", mock_popen):
            result = module.spawn_agent("coder", ["test-skill"], "test prompt", timeout=30)

        assert "Task completed successfully" in result
        assert len(calls) == 1, f"Expected 1 call (no fallback needed), got {len(calls)}"

    def test_fallback_passes_model_flags_correctly(self):
        """Verify the fallback call includes --provider and -m from FALLBACK_MODEL."""
        import subprocess
        calls = []

        def mock_popen(cmd, **kwargs):
            calls.append(cmd)
            if len(calls) == 1:
                proc = self._make_mock_proc(
                    ["Error output"],
                    returncode=1,
                    stderr="connection refused\n"
                )
                proc.returncode = 1
                return proc
            return self._make_mock_proc(["ok\n"], returncode=0)

        module = _load_panel()
        module.FALLBACK_MODEL = "openrouter/anthropic/claude-sonnet-4"
        module.HERMES_BIN = "/usr/bin/hermes"

        with unittest.mock.patch("subprocess.Popen", mock_popen):
            module.spawn_agent("coder", ["test-skill"], "test prompt", timeout=30)

        assert len(calls) == 2, f"Expected 2 calls, got {len(calls)}"
        fallback_cmd = calls[1]
        assert "--provider" in fallback_cmd, f"Expected --provider in fallback cmd: {fallback_cmd}"
        assert "openrouter" in fallback_cmd
        assert "-m" in fallback_cmd or "--model" in fallback_cmd
        assert "claude-sonnet-4" in fallback_cmd
