"""Shared fixtures for dokima tests."""
import os
import sys
import json
import types
import tempfile
import subprocess
import pytest
from unittest.mock import patch

PANEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dokima"))


def _load_panel():
    """Load dokima as a Python module via exec, setting required globals.
    Registers in sys.modules so patch('dokima.X') works across all tests."""
    module_name = "dokima"
    # Remove stale module if present
    if module_name in sys.modules:
        del sys.modules[module_name]
    # F022: Also remove stale sub-modules so fresh imports pick up changes
    for sub in ('tasks', 'utils', 'agent', 'pipeline', 'roadmap'):
        if sub in sys.modules:
            del sys.modules[sub]

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

    # F022: Intercept global assignments to sync to sub-modules.
    def _sync_globals_on_setattr(self, name, value):
        object.__setattr__(self, name, value)
        if name in ('PROJECT_DIR', 'REPO', 'DEFAULT_BRANCH', 'PANEL_FEATURE',
                     'PANEL_DIR', 'API_KEY', 'OUTPUT_LOG', 'HERMES_BIN',
                     'FALLBACK_MODELS', 'SKIP_AUTOFIX', 'FORCE_FULL',
                     'SKIP_HUMAN_GATE', 'max_parallel_override', 'RESUME',
                     'TEST_CMD', 'BUILD_CMD', 'LINT_CMD'):
            for mod_ref in ('_utils', '_agent', '_tasks', '_roadmap', '_pipeline'):
                target = getattr(self, mod_ref, None)
                if target is not None and hasattr(target, name):
                    object.__setattr__(target, name, value)
    module.__class__ = type('DokimaModule', (types.ModuleType,), {'__setattr__': _sync_globals_on_setattr})

    # Execute the script in the module's namespace
    with open(PANEL_PATH) as f:
        code = compile(f.read(), PANEL_PATH, "exec")
    exec(code, module.__dict__)

    # F022b: Link each sub-module back to this panel so override detection
    # uses the correct panel instance (not sys.modules which can be stale).
    for mod_ref in ('_utils', '_agent', '_pipeline', '_tasks', '_roadmap'):
        target = getattr(module, mod_ref, None)
        if target is not None:
            target._IMPORTING_PANEL = module

    # F022: Sync initial globals (set before __setattr__ was active) to sub-modules
    for g_name in ('PROJECT_DIR', 'REPO', 'DEFAULT_BRANCH', 'PANEL_FEATURE',
                   'PANEL_DIR', 'API_KEY', 'OUTPUT_LOG', 'HERMES_BIN',
                   'FALLBACK_MODELS', 'SKIP_AUTOFIX', 'FORCE_FULL',
                   'SKIP_HUMAN_GATE', 'max_parallel_override', 'RESUME',
                   'TEST_CMD', 'BUILD_CMD', 'LINT_CMD'):
        val = getattr(module, g_name, None)
        if val is not None:
            for mod_ref in ('_utils', '_agent', '_tasks', '_roadmap', '_pipeline'):
                target = getattr(module, mod_ref, None)
                if target is not None and hasattr(target, g_name):
                    object.__setattr__(target, g_name, val)

    return module


def _reload_panel():
    """Reload a fresh panel module, clearing any global state pollution.
    Use between tests that modify module-level globals."""
    module_name = "dokima"
    if module_name in sys.modules:
        del sys.modules[module_name]
    return _load_panel()


@pytest.fixture(autouse=True)
def _isolate_panel_modules():
    """Save/restore sys.modules around every test to prevent stale
    references from _load()/_load_panel() calls leaking between tests
    (F022b: Modular Architecture — sys.modules state isolation).

    Tests that call _load() directly (not through the panel fixture)
    leave sys.modules pointing to their panel, breaking override
    detection in other tests that use module-level panel references."""
    _sub_module_names = ('tasks', 'utils', 'agent', 'pipeline', 'roadmap', 'dokima')
    _saved = {k: sys.modules.get(k) for k in _sub_module_names}
    _had = {k: k in sys.modules for k in _sub_module_names}

    yield

    for key in _sub_module_names:
        if _had[key] and _saved[key] is not None:
            sys.modules[key] = _saved[key]
        elif key in sys.modules:
            del sys.modules[key]


@pytest.fixture
def panel():
    """Loaded dokima module with globals set. Fresh per test.
    Saves/restores sys.modules so stale references from module-level
    imports in other test files don't leak into override detection
    (F022b: Modular Architecture — fix stale sys.modules references)."""
    _sub_module_names = ('tasks', 'utils', 'agent', 'pipeline', 'roadmap', 'dokima')
    _saved = {k: sys.modules.get(k) for k in _sub_module_names}
    _had = {k: k in sys.modules for k in _sub_module_names}

    p = _load_panel()
    yield p

    # Restore sys.modules to pre-test state so module-level imports
    # in other test files resolve correctly.
    for key in _sub_module_names:
        if _had[key] and _saved[key] is not None:
            sys.modules[key] = _saved[key]
        elif key in sys.modules:
            del sys.modules[key]


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
def test_repo(panel, tmpdir_path):
    """Create a temporary git repository with AGENTS.md and specs/roadmap.md.
    Sets panel.PROJECT_DIR, panel.REPO, and panel.DEFAULT_BRANCH.
    Yields the project directory path as a string."""
    project_dir = os.path.join(tmpdir_path, "test-project")
    os.makedirs(os.path.join(project_dir, "specs"), exist_ok=True)

    with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
        f.write("# Test Project\n\n## Commands\n- Test: `echo tests-pass`\n- Build: `echo build-ok`\n")

    with open(os.path.join(project_dir, "specs", "roadmap.md"), "w") as f:
        f.write("""# Roadmap\n\n## Phase 1\n\n### F001: Test Feature\n**Priority:** P0\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** Pipeline verification.\n""")

    subprocess.run(["git", "init", project_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "config", "user.email", "test@test.com"])
    subprocess.run(["git", "-C", project_dir, "config", "user.name", "Test"])
    subprocess.run(["git", "-C", project_dir, "add", "-A"])
    subprocess.run(["git", "-C", project_dir, "commit", "-m", "init"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "remote", "add", "origin", "https://github.com/test-owner/test-repo.git"])

    panel.PROJECT_DIR = project_dir
    panel.REPO = "test-owner/test-repo"
    panel.DEFAULT_BRANCH = "master"

    return project_dir


@pytest.fixture
def mock_orchestrator(panel):
    """Replace panel.spawn_agent with a mock and patch common panel functions
    (git, gh, _set_gh_token, load_key, load_github_token, detect_repo,
    acquire_lock, _cleanup_lock, time.sleep).
    Records spawn_agent calls in spawn_calls list.
    Yields dict with: panel, spawn_calls, mock_spawn
    Stops all patches on teardown."""
    spawn_calls = []

    def mock_spawn(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
        spawn_calls.append(profile)
        return "Mock agent output"

    panel.spawn_agent = mock_spawn

    patches = [
        patch.object(panel, "_set_gh_token"),
        patch.object(panel, "git", return_value=("", "", 0)),
        patch.object(panel, "gh", return_value=("", "", 0)),
        patch.object(panel, "load_key", return_value="fk"),
        patch.object(panel, "load_github_token", return_value="ft"),
        patch.object(panel, "detect_repo", return_value="t/t"),
        patch.object(panel, "acquire_lock", return_value=(True, None)),
        patch.object(panel, "_cleanup_lock"),
        patch("time.sleep"),
    ]

    for p in patches:
        p.start()

    yield {
        "panel": panel,
        "spawn_calls": spawn_calls,
        "mock_spawn": mock_spawn,
    }

    for p in patches:
        p.stop()
