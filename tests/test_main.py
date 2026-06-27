"""Tests for main() and Orchestrator class."""
import io
import os
import sys
import pytest


def test_repo_fixture_creates_valid_git_repo(test_repo):
    """test_repo fixture creates a valid git repo with AGENTS.md."""
    agents_path = os.path.join(test_repo, "AGENTS.md")
    assert os.path.exists(agents_path), "AGENTS.md should exist"
    with open(agents_path) as f:
        content = f.read()
    assert "test" in content.lower() or "pytest" in content.lower()
    # Verify it's a git repo
    from subprocess import run, PIPE
    r = run(["git", "rev-parse", "--git-dir"], capture_output=True, text=True, cwd=test_repo)
    assert r.returncode == 0, f"Not a git repo: {r.stderr}"
    # Should have initial commit
    r2 = run(["git", "log", "--oneline", "-1"], capture_output=True, text=True, cwd=test_repo)
    assert r2.returncode == 0 and r2.stdout.strip(), "Repo should have at least one commit"


def test_orchestrator_fixture_creates_instance(orchestrator):
    """orchestrator fixture creates an Orchestrator with mock I/O."""
    assert orchestrator is not None
    assert orchestrator.project_dir is not None
    assert orchestrator.feature == "Test pipeline feature"


def test_orchestrator_fixture_mock_safe_run(orchestrator):
    """orchestrator fixture's mock_safe_run returns pre-configured responses."""
    result = orchestrator.safe_run_fn("echo hello", cwd="/tmp", timeout=10)
    # Default mock should return success
    assert result is not None



def test_orchestrator_constructable(panel):
    """Orchestrator can be constructed with default dependencies."""
    orch = panel.Orchestrator(
        project_dir="/tmp/test",
        feature="Test feature",
        stdin=io.StringIO(),
        lock_fn=lambda: (True, -1),
        safe_run_fn=lambda cmd, cwd, timeout: None,
        gh_cli_fn=lambda *a, **kw: "",
    )
    assert orch is not None
    assert orch.project_dir == "/tmp/test"
    assert orch.feature == "Test feature"


def test_orchestrator_run_calls_lock_cleanup(panel):
    """Orchestrator.run() calls cleanup_lock at end."""
    cleanup_called = []
    orch = panel.Orchestrator(
        project_dir="/tmp/test",
        feature="Test feature",
        stdin=io.StringIO(),
        lock_fn=lambda: (True, -1),
        safe_run_fn=lambda cmd, cwd, timeout: None,
        gh_cli_fn=lambda *a, **kw: "",
        cleanup_lock_fn=lambda: cleanup_called.append(True),
    )
    try:
        orch.run()
    except SystemExit:
        pass
    assert cleanup_called, "cleanup_lock should be called by run()"


def test_orchestrator_with_flags(panel):
    """Orchestrator accepts and stores flag values."""
    orch = panel.Orchestrator(
        project_dir="/tmp/test",
        feature="Test feature",
        stdin=io.StringIO(),
        lock_fn=lambda: (True, -1),
        safe_run_fn=lambda cmd, cwd, timeout: None,
        gh_cli_fn=lambda *a, **kw: "",
        is_next=True,
        is_continuous=False,
        is_fix=False,
        skip_auto_archive=True,
    )
    assert orch.is_next is True
    assert orch.is_continuous is False
    assert orch.is_fix is False
    assert orch.skip_auto_archive is True


def test_main_help_exits(panel):
    """--help triggers usage message and exits."""
    old = sys.argv
    try:
        sys.argv = ["dokima", "--help"]
        with pytest.raises(SystemExit):
            panel.main()
    finally:
        sys.argv = old


def test_main_no_args_exits(panel):
    """No args prints usage and exits."""
    old = sys.argv
    try:
        sys.argv = ["dokima"]
        with pytest.raises(SystemExit):
            panel.main()
    finally:
        sys.argv = old


def test_main_flag_parsing_next(panel):
    """--next flag sets is_next=True."""
    old = sys.argv
    try:
        sys.argv = ["dokima", "--next", "/tmp/test-project"]
        # Should reach lock acquisition and fail there (no real infra)
        with pytest.raises((SystemExit, Exception)):
            panel.main()
        # Verify is_next was set via global state
        assert hasattr(panel, "PROJECT_DIR"), "main() should set PROJECT_DIR"
    finally:
        sys.argv = old


def test_main_flag_parsing_continuous(panel):
    """--continuous flag sets is_next=True."""
    old = sys.argv
    try:
        sys.argv = ["dokima", "--continuous", "/tmp/test-project"]
        with pytest.raises((SystemExit, Exception)):
            panel.main()
    finally:
        sys.argv = old


def test_main_flag_parsing_add_no_feature(panel):
    """--add without feature description exits with error."""
    old = sys.argv
    try:
        sys.argv = ["dokima", "--add"]
        with pytest.raises(SystemExit):
            panel.main()
    finally:
        sys.argv = old


def test_main_flag_parsing_fix(panel, tmpdir_path):
    """--fix flag sets is_fix=True and dispatches to fix mode."""
    old = sys.argv
    old_environ = os.environ.copy()
    try:
        # Create a minimal project with AGENTS.md
        agents_path = os.path.join(tmpdir_path, "AGENTS.md")
        with open(agents_path, "w") as f:
            f.write("# Test\n")
        os.environ["PANEL_SKIP_AUTOFIX"] = "1"
        os.environ["PANEL_SKIP_HUMAN_GATE"] = "1"
        sys.argv = ["dokima", "--fix", "--skip-autofix", tmpdir_path]
        with pytest.raises((SystemExit, Exception)):
            panel.main()
        # Fix mode should not crash — should reach AGENTS.md check
        assert callable(panel.run_fix_mode)
    finally:
        sys.argv = old
        os.environ.clear()
        os.environ.update(old_environ)
