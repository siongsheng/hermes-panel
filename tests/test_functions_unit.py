"""Unit tests for functions that are normally patched in integration tests.

Tests call_agent (error paths), _safe_run, git, halt_and_revert with real
or minimally-mocked execution.
"""
import os
import sys
import tempfile
import pytest
from unittest.mock import patch

from conftest import _load_panel as _load


class TestSafeRun:
    """_safe_run(cmd_str, cwd, timeout) — safe subprocess execution."""

    def test_echo_command(self, panel):
        result = panel._safe_run("echo hello", cwd="/tmp", timeout=5)
        assert result.returncode == 0
        assert "hello" in result.stdout

class TestGit:
    """git(*args) — thin wrapper around git -C PROJECT_DIR."""

    def test_git_rev_parse(self, panel, tmpdir):
        import subprocess
        project_dir = os.path.join(str(tmpdir), "git-test")
        os.makedirs(project_dir)
        subprocess.run(["git", "init", project_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        panel.PROJECT_DIR = project_dir
        stdout, stderr, rc = panel.git("rev-parse", "--git-dir")
        assert rc == 0
        assert ".git" in stdout

    def test_git_in_nongit_dir(self, panel, tmpdir):
        panel.PROJECT_DIR = str(tmpdir)
        stdout, stderr, rc = panel.git("status")
        assert rc != 0


class TestHaltAndRevert:
    """halt_and_revert(reason, phase, branch) — cleanup on pipeline failure."""

    def test_halt_calls_git_cleanup(self, panel):
        panel.DEFAULT_BRANCH = "main"
        panel.OUTPUT_LOG = "/dev/null"
        git_calls = []
        def fake_git(*args):
            git_calls.append(args)
            return ("", "", 0)
        panel.git = fake_git
        panel.halt_and_revert("test failure", "PHASE 2", "feat/test-branch")
        assert ("checkout", "main") in git_calls
        assert any("test-branch" in str(c) for c in git_calls)
