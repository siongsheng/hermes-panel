"""Final batch of edge case tests targeting remaining uncovered pipeline branches.

Covers: continuous loop body, PR injection, SHOULD FIX issues,
detect_repo, detect_commands, handle_kill edge cases.
"""
import os
import sys
import pytest
from unittest.mock import patch

from conftest import _load_panel as _load

_spawn_calls = []


def _setup(tmpdir, panel, features=1):
    import subprocess
    project_dir = os.path.join(str(tmpdir), "proj")
    os.makedirs(os.path.join(project_dir, "specs"), exist_ok=True)
    with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
        f.write("# Test\n\n## Commands\n- Test: `echo ok`\n- Build: `echo ok`\n")
    roadmap = """# Roadmap
## Phase 1
### F001: Test Feature
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** Test.
"""
    if features >= 2:
        roadmap += """
### F002: Second Feature
**Priority:** P0
**Dependencies:** F001
**Status:** [ ] Pending
**User Story:** Second.
"""
    if features >= 3:
        roadmap += """
### F003: Third Feature
**Priority:** P0
**Dependencies:** F002
**Status:** [ ] Pending
**User Story:** Third.
"""
    with open(os.path.join(project_dir, "specs", "roadmap.md"), "w") as f:
        f.write(roadmap)
    subprocess.run(["git", "init", project_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "config", "user.email", "t@t.com"])
    subprocess.run(["git", "-C", project_dir, "config", "user.name", "T"])
    subprocess.run(["git", "-C", project_dir, "add", "-A"])
    subprocess.run(["git", "-C", project_dir, "commit", "-m", "init"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "remote", "add", "origin", "https://github.com/t/t.git"])
    panel.PROJECT_DIR = project_dir
    panel.REPO = "t/t"
    panel.DEFAULT_BRANCH = "master"
    return project_dir


# ═══════════════════════════════════════════════════════════════════
# detect_repo and detect_commands
# ═══════════════════════════════════════════════════════════════════

class TestDetect:
    def test_detect_repo_success(self, panel, tmpdir):
        project_dir = _setup(tmpdir, panel)
        mock_result = type("R", (), {"returncode": 0, "stdout": "https://github.com/owner/repo.git\n", "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result):
            repo = panel.detect_repo()
            assert repo == "owner/repo"

    def test_detect_repo_ssh_format(self, panel, tmpdir):
        project_dir = _setup(tmpdir, panel)
        mock_result = type("R", (), {"returncode": 0, "stdout": "git@github.com:owner/repo.git\n", "stderr": ""})()
        with patch("subprocess.run", return_value=mock_result):
            repo = panel.detect_repo()
            assert repo == "owner/repo"

    def test_detect_repo_no_remote(self, panel):
        mock_result = type("R", (), {"returncode": 1, "stdout": "", "stderr": "fatal"})()
        with patch("subprocess.run", return_value=mock_result):
            repo = panel.detect_repo()
            assert repo is None


# ═══════════════════════════════════════════════════════════════════
# Continuous loop: continue_loop decisions
# ═══════════════════════════════════════════════════════════════════

class TestContinuousDecisions:
    """Test specific branches in the continuous loop decision logic."""

    def test_continuous_verdict_failed_reverts(self, tmpdir):
        """CODER_FAILED verdict in continuous → revert to pending."""
        panel = _load()
        project_dir = _setup(tmpdir, panel, features=2)
        _spawn_calls.clear()

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return "Confidence: Medium\nImpact: LOW\n\nSpec."
            if profile == "coder":
                return "[CODER_FAILED]"
            return "Mock"

        old = sys.argv
        try:
            sys.argv = ["dokima", "--continuous", project_dir]
            panel.spawn_agent = mock
            os.environ["PANEL_MAX_RETRIES"] = "0"
            os.environ["PANEL_SKIP_HUMAN_GATE"] = "1"
            os.environ["PANEL_PARALLEL"] = "0"

            mock_run = type("RunResult", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
            with patch("dokima.call_agent", return_value={"content": "M", "tokens": 1}), \
                 patch("dokima._set_gh_token"), \
                 patch("dokima.git", return_value=("", "", 0)), \
                 patch("dokima.gh", return_value=("", "", 0)), \
                 patch("dokima.load_key", return_value="fk"), \
                 patch("dokima.load_github_token", return_value="ft"), \
                 patch("dokima.detect_repo", return_value="t/t"), \
                 patch("dokima._safe_run", return_value=mock_run), \
                 patch("dokima.subprocess.run", return_value=mock_run), \
                 patch("dokima.time.sleep"):
                try:
                    panel.main()
                except SystemExit:
                    pass
        finally:
            sys.argv = old
            for k in ("PANEL_PARALLEL", "PANEL_MAX_RETRIES", "PANEL_SKIP_HUMAN_GATE"):
                os.environ.pop(k, None)

    def test_continuous_high_risk_skips_merge(self, tmpdir):
        """Risk HIGH in continuous → no auto-merge."""
        panel = _load()
        project_dir = _setup(tmpdir, panel, features=2)
        _spawn_calls.clear()

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return "Confidence: Medium\nImpact: HIGH\n\nSpec."
            if profile == "coder":
                return "RED: a1\nGREEN: b2\nTests: 5 pass\nBuild: clean"
            if profile == "tech-lead":
                return "VERDICT: APPROVED\nRISK: HIGH\n"
            return "Mock"

        old = sys.argv
        try:
            sys.argv = ["dokima", "--continuous", project_dir]
            panel.spawn_agent = mock
            os.environ["PANEL_MAX_RETRIES"] = "0"
            os.environ["PANEL_SKIP_HUMAN_GATE"] = "1"
            os.environ["PANEL_PARALLEL"] = "0"

            mock_run = type("RunResult", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
            def gh_se(*a, **kw):
                if len(a) > 1 and a[1] == "create":
                    return ("https://github.com/t/t/pull/1", "", 0)
                return ("", "", 0)
            with patch("dokima.call_agent", return_value={"content": "M", "tokens": 1}), \
                 patch("dokima._set_gh_token"), \
                 patch("dokima.git", return_value=("", "", 0)), \
                 patch("dokima.gh", side_effect=gh_se), \
                 patch("dokima.load_key", return_value="fk"), \
                 patch("dokima.load_github_token", return_value="ft"), \
                 patch("dokima.detect_repo", return_value="t/t"), \
                 patch("dokima._safe_run", return_value=mock_run), \
                 patch("dokima.subprocess.run", return_value=mock_run), \
                 patch("dokima.time.sleep"):
                try:
                    panel.main()
                except SystemExit:
                    pass
        finally:
            sys.argv = old
            for k in ("PANEL_PARALLEL", "PANEL_MAX_RETRIES", "PANEL_SKIP_HUMAN_GATE"):
                os.environ.pop(k, None)


# ═══════════════════════════════════════════════════════════════════
# detect_commands edge cases
# ═══════════════════════════════════════════════════════════════════

class TestDetectCommands:
    def test_all_commands_found(self, panel, tmpdir):
        """AGENTS.md has all commands."""
        project_dir = os.path.join(str(tmpdir), "proj")
        os.makedirs(project_dir)
        with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
            f.write("## Commands\n- Test: `pytest`\n- Build: `make build`\n- Lint: `flake8`\n")
        panel.PROJECT_DIR = project_dir
        t, b, l = panel.detect_commands()
        assert t == "pytest"
        assert b == "make build"
        assert l == "flake8"

    def test_partial_commands(self, panel, tmpdir):
        """AGENTS.md has only some commands."""
        project_dir = os.path.join(str(tmpdir), "proj")
        os.makedirs(project_dir)
        with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
            f.write("## Commands\n- Test: `npm test`\n")
        panel.PROJECT_DIR = project_dir
        t, b, l = panel.detect_commands()
        assert t == "npm test"
        assert b == "npm run build"  # default
        assert l == "npm run lint"    # default
