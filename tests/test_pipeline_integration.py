"""Integration tests for Phase 1→2 pipeline handoff (Strategist → Coder).

Tests that the strategist produces a valid spec and the coder receives it
with the spec context in the prompt. Uses the same _patch_and_run / _setup_test_project
pattern as test_main_integration.py.
"""
import os
import sys
import pytest
from unittest.mock import patch

from conftest import _load_panel as _load

os.environ.setdefault("PANEL_MAX_RETRIES", "0")
os.environ.setdefault("PANEL_SKIP_HUMAN_GATE", "1")
os.environ.setdefault("PANEL_SKIP_ORCHESTRATOR_REVIEW", "1")
os.environ.setdefault("PANEL_PARALLEL", "0")


def _setup_test_project(panel, tmpdir):
    """Create a test git repo with AGENTS.md and roadmap.

    Pattern copied from test_main_integration.py to keep tests isolated.
    """
    import subprocess
    project_dir = os.path.join(str(tmpdir), "test-project")
    os.makedirs(os.path.join(project_dir, "specs"), exist_ok=True)
    with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
        f.write("# Test Project\n\n## Commands\n- Test: `echo tests-pass`\n- Build: `echo build-ok`\n")
    with open(os.path.join(project_dir, "specs", "roadmap.md"), "w") as f:
        f.write("""# Roadmap

## Phase 1

### F001: Test Feature
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** Pipeline verification.
""")
    subprocess.run(["git", "init", project_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "config", "user.email", "test@test.com"])
    subprocess.run(["git", "-C", project_dir, "config", "user.name", "Test"])
    subprocess.run(["git", "-C", project_dir, "add", "-A"])
    subprocess.run(["git", "-C", project_dir, "commit", "-m", "init"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "remote", "add", "origin",
                    "https://github.com/test-owner/test-repo.git"])
    panel.PROJECT_DIR = project_dir
    panel.REPO = "test-owner/test-repo"
    panel.DEFAULT_BRANCH = "master"
    return project_dir


# Realistic strategist output matching the format the panel parses.
# Includes all required sections: Decision Table, Impact, What Changed,
# Confidence/Impact markers, Task Breakdown with ### Task N: headers.
STRAT_SPEC = """# Test Feature

## Decision Table

SINGLE APPROACH: Test approach.

## Impact

Test impact description for verification.

## What Changed

- test.py: added tests

### Confidence: High
### Impact: LOW

## API/Interface Proposal

N/A — test change only.

## Security Considerations

N/A — no attack surface change.

## Documentation Impact

README: No change needed.

## Task Breakdown

### Task 1: Write test
**Files:** test_file.py
**Dependencies:** [none]
**Parallelizable:** yes
**Description:** Write the test.
"""


_spawn_calls = []  # type: ignore[var-annotated]


def _mock_capturing_spawn(profile, skills, prompt, timeout=600, cwd=None, model=None):
    """Record all spawn_agent calls and return realistic strategist output."""
    _spawn_calls.append({"profile": profile, "skills": skills,
                         "prompt": prompt, "timeout": timeout, "cwd": cwd})
    return STRAT_SPEC


def _patch_and_run(panel, mock_lock=True):
    """Run panel.main() with all standard patches applied.

    Pattern copied from test_main_integration.py.
    """
    patches = [
        patch.object(panel, "call_agent", return_value={"content": "M", "tokens": 1}),
        patch.object(panel, "_set_gh_token"),
        patch.object(panel, "git", return_value=("", "", 0)),
        patch.object(panel, "gh", return_value=("", "", 0)),
        patch.object(panel, "load_key", return_value="fk"),
        patch.object(panel, "load_github_token", return_value="ft"),
        patch.object(panel, "detect_repo", return_value="t/t"),
        patch("time.sleep"),
    ]
    if mock_lock:
        patches.append(patch.object(panel, "acquire_lock", return_value=(True, None)))
        patches.append(patch.object(panel, "_cleanup_lock"))

    from contextlib import ExitStack
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        try:
            panel.main()
        except SystemExit:
            pass


@pytest.mark.skip(reason="Hangs: panel.main() blocks in coder phase — needs deeper mocking")
class TestStrategistCoderHandoff:

    def test_strategist_output_flows_to_coder(self, tmpdir):
        """Strategist produces spec → spec is written to disk → coder prompt references it.

        Verifies the Phase 1→2 handoff:
        1. spawn_agent called with 'strategist' profile first
        2. Spec file is created at specs/<slug>-spec.md with expected content
        3. spawn_agent called with 'coder' profile
        4. Coder prompt contains reference to the spec
        5. Pipeline completes without error (no SystemExit with non-zero code)
        """
        panel = _load()
        project_dir = _setup_test_project(panel, str(tmpdir))
        old = sys.argv
        try:
            _spawn_calls.clear()
            sys.argv = ["dokima", "--next", project_dir]
            panel.spawn_agent = _mock_capturing_spawn
            _patch_and_run(panel)

            # 1. Phases were called in the right order
            assert len(_spawn_calls) >= 2, \
                f"Expected at least 2 spawn_agent calls, got {len(_spawn_calls)}"
            profiles = [c["profile"] for c in _spawn_calls]
            assert profiles[0] == "strategist", \
                f"First call should be strategist, got {profiles}"

            # 2. Spec file was created (slugified from "F001: Test Feature")
            spec_path = os.path.join(project_dir, "specs", "f001-test-feature-spec.md")
            assert os.path.exists(spec_path), \
                f"Spec file not found at {spec_path}"
            with open(spec_path) as f:
                spec_content = f.read()
            assert "Test Feature" in spec_content, \
                "Spec should contain the feature title"
            assert "### Task 1:" in spec_content, \
                "Spec should contain task breakdown headers"

            # 3. Coder was called
            coder_calls = [c for c in _spawn_calls if c["profile"] == "coder"]
            assert len(coder_calls) >= 1, \
                f"Coder should be called, profiles seen: {profiles}"

            # 4. Coder prompt references the spec
            coder_prompt = coder_calls[0]["prompt"]
            assert "task breakdown" in coder_prompt.lower() \
                or "spec" in coder_prompt.lower(), \
                "Coder prompt should reference spec or task breakdown"

            # 5. Task extract file was created alongside the spec
            task_extract = os.path.join(project_dir, "specs", "f001-test-feature-tasks.md")
            assert os.path.exists(task_extract), \
                f"Task extract not found at {task_extract}"

        finally:
            sys.argv = old

    def test_coder_prompt_includes_tdd_instructions(self, tmpdir):
        """Coder prompt includes TDD enforcement from ai-coding-best-practices-lite.

        Verifies the coder receives TDD instructions:
        - RED/GREEN commit pattern
        - Two separate commits requirement
        - Test command reference
        """
        panel = _load()
        project_dir = _setup_test_project(panel, str(tmpdir))
        old = sys.argv
        try:
            _spawn_calls.clear()
            sys.argv = ["dokima", "--next", project_dir]
            panel.spawn_agent = _mock_capturing_spawn
            _patch_and_run(panel)

            coder_calls = [c for c in _spawn_calls if c["profile"] == "coder"]
            assert len(coder_calls) >= 1, "Coder should be called"
            prompt = coder_calls[0]["prompt"]

            # TDD instructions present
            assert "RED" in prompt and "GREEN" in prompt, \
                "Coder prompt should contain RED/GREEN TDD instructions"
            assert "two separate commits" in prompt.lower() or "TWO SEPARATE COMMITS" in prompt, \
                "Coder prompt should require two separate commits"
            assert "test:" in prompt, \
                "Coder prompt should reference 'test:' commit prefix"
            assert "feat:" in prompt, \
                "Coder prompt should reference 'feat:' commit prefix"

        finally:
            sys.argv = old
