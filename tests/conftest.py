"""Shared fixtures for dokima tests."""
import os
import sys
import json
import types
import tempfile
import pytest

PANEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dokima"))


def _load_panel():
    """Load dokima as a Python module via exec, setting required globals.
    Registers in sys.modules so patch('dokima.X') works across all tests."""
    module_name = "dokima"
    # Remove stale module if present
    if module_name in sys.modules:
        del sys.modules[module_name]

    module = types.ModuleType(module_name)
    module.__file__ = PANEL_PATH
    sys.modules[module_name] = module

    # Set required globals BEFORE execution so functions reference them
    module.PROJECT_DIR = "/tmp/test-project"
    module.REPO = "test-owner/test-repo"
    module.API_KEY = "test-key"
    module.PANEL_FEATURE = "Test Feature"
    module.PANEL_DIR = "/tmp/.dokima-test"
    module.DEFAULT_BRANCH = "main"
    module.TEST_CMD = "echo test"
    module.BUILD_CMD = "echo build"
    module.LINT_CMD = "echo lint"

    # Execute the script in the module's namespace
    with open(PANEL_PATH) as f:
        code = compile(f.read(), PANEL_PATH, "exec")
    exec(code, module.__dict__)

    return module


def _reload_panel():
    """Reload a fresh panel module, clearing any global state pollution.
    Use between tests that modify module-level globals."""
    module_name = "dokima"
    if module_name in sys.modules:
        del sys.modules[module_name]
    return _load_panel()


@pytest.fixture
def panel():
    """Loaded dokima module with globals set. Fresh per test."""
    return _load_panel()


@pytest.fixture
def tmpdir_path():
    """Temporary directory as a string path."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def fake_roadmap(tmpdir_path):
    """Create a temporary roadmap.md and return function to create with content."""
    p = os.path.join(tmpdir_path, "roadmap.md")
    def _create(content):
        with open(p, "w") as f:
            f.write(content)
        return p
    return _create


@pytest.fixture
def fake_agents_md(tmpdir_path):
    """Create a temporary AGENTS.md and return function to create with content."""
    p = os.path.join(tmpdir_path, "AGENTS.md")
    def _create(content):
        with open(p, "w") as f:
            f.write(content)
        return p
    return _create


@pytest.fixture
def test_repo(tmpdir_path):
    """Create a minimal git repo with AGENTS.md, a .py file, and an initial commit.

    Returns the path to the repo root.
    """
    import subprocess

    # AGENTS.md with test/build/lint commands
    agents_content = """# Test Project

A minimal test project for pipeline integration tests.

## Commands
- Test: python3 -m pytest -q
- Build: python3 -c "compile(open('main.py').read(), 'main.py', 'exec')"
- Lint: python3 -m py_compile main.py

## Tech
Python 3.10+
"""
    agents_path = os.path.join(tmpdir_path, "AGENTS.md")
    with open(agents_path, "w") as f:
        f.write(agents_content)

    # Python module with a function and test
    main_py = '''"""Main module."""
def add(a, b):
    return a + b


def subtract(a, b):
    return a - b
'''
    main_path = os.path.join(tmpdir_path, "main.py")
    with open(main_path, "w") as f:
        f.write(main_py)

    # Test file
    test_py = '''"""Tests for main module."""
from main import add, subtract


def test_add():
    assert add(1, 2) == 3


def test_subtract():
    assert subtract(5, 3) == 2
'''
    test_path = os.path.join(tmpdir_path, "test_main.py")
    with open(test_path, "w") as f:
        f.write(test_py)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmpdir_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmpdir_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmpdir_path, capture_output=True)

    return tmpdir_path
