"""Continuous loop integration test — --continuous with multiple features."""
import os
import sys
import pytest
from unittest.mock import patch

from conftest import _load_panel as _load

_spawn_calls = []


def _setup_two_features(tmpdir, panel):
    import subprocess
    project_dir = os.path.join(str(tmpdir), "cont-test")
    os.makedirs(os.path.join(project_dir, "specs"), exist_ok=True)
    with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
        f.write("# Test\n\n## Commands\n- Test: `echo ok`\n- Build: `echo ok`\n")
    with open(os.path.join(project_dir, "specs", "roadmap.md"), "w") as f:
        f.write("""# Roadmap

## Phase 1

### F001: First Feature
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** First.

### F002: Second Feature
**Priority:** P0
**Dependencies:** F001
**Status:** [ ] Pending
**User Story:** Second.
""")
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


def test_continuous_loop_two_features(tmpdir):
    """--continuous with 2 features → F001 completes → loop picks F002."""
    panel = _load()
    project_dir = _setup_two_features(tmpdir, panel)
    _spawn_calls.clear()

    # Set test env vars for this test
    os.environ["PANEL_MAX_RETRIES"] = "0"
    os.environ["PANEL_SKIP_HUMAN_GATE"] = "1"
    os.environ["PANEL_PARALLEL"] = "0"  # simplify: no parallel coders

    def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
        _spawn_calls.append(profile)
        if profile == "strategist":
            return "Confidence: High\nImpact: MEDIUM\n\nSpec for feature."
        if profile == "coder":
            return "RED commit: a1b2c3 — test: tests\nGREEN commit: d4e5f6 — feat: impl\nTests: 5 passed, 0 failed\nBuild: clean, 0 errors\n"
        if profile == "tech-lead":
            return "VERDICT: APPROVED\nRISK: LOW\n"
        return "Mock output"

    old_argv = sys.argv
    try:
        sys.argv = ["dokima", "--continuous", project_dir]
        panel.spawn_agent = mock

        def gh_se(*args, **kwargs):
            if args and args[0] == "pr" and args[1] == "create":
                return ("https://github.com/t/t/pull/1", "", 0)
            return ("", "", 0)

        mock_run = type("RunResult", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        with patch("dokima.call_agent", return_value={"content": "M", "tokens": 1}), \
             patch("dokima._set_gh_token"), \
             patch("dokima.git", return_value=("", "", 0)), \
             patch("dokima.gh", side_effect=gh_se), \
             patch("dokima.load_key", return_value="fk"), \
             patch("dokima.load_github_token", return_value="ft"), \
             patch("dokima.detect_repo", return_value="t/t"), \
             patch("dokima._safe_run", return_value=mock_run), \
             patch("dokima.try_auto_merge", return_value="merged"), \
             patch("dokima.subprocess.run", return_value=mock_run), \
             patch("dokima.time.sleep"):
            try:
                panel.main()
            except SystemExit:
                pass
    finally:
        sys.argv = old_argv
        # Clean up env vars
        for key in ("PANEL_PARALLEL", "PANEL_MAX_RETRIES", "PANEL_SKIP_HUMAN_GATE"):
            os.environ.pop(key, None)

    # Should have spawned at least 2 strategists (one per feature)
    strat_count = sum(1 for c in _spawn_calls if c == "strategist")
    assert strat_count >= 2, f"Expected >=2 strategist calls (F001 + F002), got {strat_count}. Calls: {_spawn_calls}"
