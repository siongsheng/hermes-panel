"""Tests for _detect_provider_failure helper and fallback retry (F005: Model Family Fallback)."""
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

    def test_503_in_number_does_not_false_positive(self):
        """Number containing '503' as substring (e.g., 15039) should not trigger."""
        module = _load_panel()
        output = "15039 tests passed, 48 failed"
        assert module._detect_provider_failure(output) is False

    def test_503_in_port_number_does_not_false_positive(self):
        """Port number containing 503 should not trigger."""
        module = _load_panel()
        output = "Listening on port 25030"
        assert module._detect_provider_failure(output) is False

    def test_rate_as_word_in_non_limit_context_does_not_false_positive(self):
        """The word 'rate' in normal context should not trigger 'rate limit' pattern."""
        module = _load_panel()
        output = "The error rate decreased by 50% this sprint"
        assert module._detect_provider_failure(output) is False

    def test_model_as_topic_not_false_positive(self):
        """'model' used as a topic word should not trigger if not followed by 'not found/available'."""
        module = _load_panel()
        output = "The new model was deployed to production"
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
        assert "anthropic/claude-sonnet-4" in fallback_cmd


class TestFallbackNotFiredOnLegitimateOutput:
    """Task 6: Verify fallback does NOT fire on legitimate agent output."""

    def _make_mock_proc(self, lines, returncode=0, stderr=""):
        """Create a mock Popen instance."""
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

    def test_number_503_in_output_does_not_trigger_fallback(self):
        """Output containing '503' embedded in a larger number should not trigger fallback.
        Current pattern re.compile(r'503') matches '503' anywhere, including inside 15039.
        This test proves the bug exists and guards against regression."""
        import subprocess
        calls = []

        def mock_popen(cmd, **kwargs):
            calls.append(cmd)
            return self._make_mock_proc(
                ["15039 tests passed, 0 failed\n"],
                returncode=0
            )

        module = _load_panel()
        module.FALLBACK_MODEL = "openrouter/anthropic/claude-sonnet-4"
        module.HERMES_BIN = "/usr/bin/hermes"

        with unittest.mock.patch("subprocess.Popen", mock_popen):
            result = module.spawn_agent("coder", ["test-skill"], "test prompt", timeout=30)

        assert "15039 tests passed" in result
        # Should be exactly 1 call — fallback fired if >1
        assert len(calls) == 1, f"Expected 1 call (no fallback), got {len(calls)}. Fallback incorrectly fired on legitimate output containing '503' as substring."

    def test_app_error_nonzero_exit_does_not_trigger_fallback(self):
        """Non-zero exit with application error in stderr should not trigger fallback."""
        import subprocess
        calls = []

        def mock_popen(cmd, **kwargs):
            calls.append(cmd)
            return self._make_mock_proc(
                ["Task failed: file not found\n"],
                returncode=2,
                stderr="ModuleNotFoundError: No module named 'requests'\n"
            )

        module = _load_panel()
        module.FALLBACK_MODEL = "openrouter/anthropic/claude-sonnet-4"
        module.HERMES_BIN = "/usr/bin/hermes"

        with unittest.mock.patch("subprocess.Popen", mock_popen):
            result = module.spawn_agent("coder", ["test-skill"], "test prompt", timeout=30)

        assert "Task failed: file not found" in result
        assert len(calls) == 1, f"Expected 1 call (no fallback), got {len(calls)}"

    def test_stderr_with_generic_error_does_not_trigger_fallback(self):
        """Stderr with generic system errors should not trigger fallback."""
        import subprocess
        calls = []

        def mock_popen(cmd, **kwargs):
            calls.append(cmd)
            return self._make_mock_proc(
                ["Done\n"],
                returncode=0,
                stderr="warning: deprecated function called\n"
            )

        module = _load_panel()
        module.FALLBACK_MODEL = "openrouter/anthropic/claude-sonnet-4"
        module.HERMES_BIN = "/usr/bin/hermes"

        with unittest.mock.patch("subprocess.Popen", mock_popen):
            result = module.spawn_agent("coder", ["test-skill"], "test prompt", timeout=30)

        assert "Done" in result
        assert len(calls) == 1, f"Expected 1 call (no fallback), got {len(calls)}"

    def test_model_discussion_does_not_trigger_fallback(self):
        """Agent output discussing a model as a topic should not trigger fallback."""
        import subprocess
        calls = []

        def mock_popen(cmd, **kwargs):
            calls.append(cmd)
            return self._make_mock_proc(
                ["I recommend using the GPT-4 model for this task\n"],
                returncode=0
            )

        module = _load_panel()
        module.FALLBACK_MODEL = "openrouter/anthropic/claude-sonnet-4"
        module.HERMES_BIN = "/usr/bin/hermes"

        with unittest.mock.patch("subprocess.Popen", mock_popen):
            result = module.spawn_agent("coder", ["test-skill"], "test prompt", timeout=30)

        assert "GPT-4 model" in result
        assert len(calls) == 1, f"Expected 1 call (no fallback), got {len(calls)}"

    def test_multi_line_agent_code_output_does_not_trigger_fallback(self):
        """Multi-line legitimate code output should not trigger fallback."""
        import subprocess
        calls = []

        def mock_popen(cmd, **kwargs):
            calls.append(cmd)
            return self._make_mock_proc(
                ["Here is the implementation:\n",
                 "def hello():\n",
                 "    print('Hello, world!')\n",
                 "returncode: 0\n"],
                returncode=0
            )

        module = _load_panel()
        module.FALLBACK_MODEL = "openrouter/anthropic/claude-sonnet-4"
        module.HERMES_BIN = "/usr/bin/hermes"

        with unittest.mock.patch("subprocess.Popen", mock_popen):
            result = module.spawn_agent("coder", ["test-skill"], "test prompt", timeout=30)

        assert "Hello, world!" in result
        assert len(calls) == 1, f"Expected 1 call (no fallback), got {len(calls)}"
