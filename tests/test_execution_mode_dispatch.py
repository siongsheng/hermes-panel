"""Tests for execution-mode-driven dispatch in run_pipeline.

Verifies that the pipeline routes to run_phase2_coder (single_session)
or run_parallel_coders (per_task_spawn) based on compute_execution_mode().
"""
import os
import sys
import json
import pytest
from unittest.mock import patch

from conftest import _load_panel as _load

os.environ.setdefault("PANEL_MAX_RETRIES", "0")
os.environ.setdefault("PANEL_SKIP_HUMAN_GATE", "1")
os.environ.setdefault("PANEL_SKIP_ORCHESTRATOR_REVIEW", "1")
os.environ.setdefault("PANEL_PARALLEL", "0")


_called = {}  # type: ignore[var-annotated]
_captured_depth = None  # type: ignore[var-annotated]


def _reset_called():
    _called.clear()
    global _captured_depth
    _captured_depth = None


def _mock_run_phase2_coder(feature, spec, spec_path, tasks_extract_path,
                            pr_sections, branch, depth, mode, is_next):
    _called["phase2_coder"] = True
    return {"coder_failed": False, "pr_url": "http://pr/2", "verdict": "APPROVED"}


def _mock_run_phase2_coder_capture(feature, spec, spec_path, tasks_extract_path,
                                    pr_sections, branch, depth, mode, is_next):
    global _captured_depth
    _captured_depth = depth
    _called["phase2_coder"] = True
    return {"coder_failed": False, "pr_url": "http://pr/2", "verdict": "APPROVED"}


def _mock_run_parallel_coders(tasks, waves, project_dir, spec_path, tasks_extract_path):
    _called["parallel_coders"] = True
    return True


def _mock_halt_and_revert(msg, phase, branch):
    raise RuntimeError(f"halt_and_revert called: {msg}")


def _mock_merge_worktree_branches(branch, tasks, wtm, project_dir):
    return True



# ── Fixtures ──

@pytest.fixture
def panel():
    p = _load()
    # Disable env override so compute_execution_mode() drives the decision
    os.environ.pop("PANEL_FORCE_EXECUTION_MODE", None)
    return p


def _make_strat_result(panel, parallel_enabled=True, spec_has_tasks=True):
    """Create a realistic strategist output dict with a 3-task DAG."""
    if spec_has_tasks:
        spec = """# Test Feature

## Impact
Test impact.

## What Changed
- Nothing.

### Confidence: High
### Impact: LOW

## Task Breakdown

### Task 1: First task
**Files:** a.py
**Dependencies:** [none]
**Parallelizable:** yes
**Description:** Do thing A.

### Task 2: Second task
**Files:** b.py
**Dependencies:** [none]
**Parallelizable:** yes
**Description:** Do thing B.

### Task 3: Third task
**Files:** a.py
**Dependencies:** [none]
**Parallelizable:** yes
**Description:** Do thing C.
"""
    else:
        spec = "# Empty spec\n\nNo tasks.\n"

    return {
        "spec": spec,
        "spec_path": "/tmp/test-spec.md",
        "pr_sections": "## Impact\nTest.\n## What Changed\n- Stuff\n",
        "tasks_extract_path": "/tmp/test-tasks.md",
        "depth": "full",
        "branch": "feat/test-feature",
        "confidence": "High",
        "impact": "LOW",
        "mode": "feature",
        "strat_output": spec,
        "parallel_enabled": parallel_enabled,
    }


# ── Integration tests ──

class TestExecutionModeDispatch:
    """Verify the pipeline routes to the correct coder path based on execution mode."""

    def test_single_session_routes_to_phase2_coder(self, panel):
        """3 parallel tasks on 2 files → single_session → run_phase2_coder called."""
        _reset_called()
        panel.run_phase2_coder = _mock_run_phase2_coder
        panel.run_parallel_coders = _mock_run_parallel_coders
        panel.halt_and_revert = _mock_halt_and_revert
        panel.merge_worktree_branches = _mock_merge_worktree_branches

        strat = _make_strat_result(panel, parallel_enabled=True, spec_has_tasks=True)
        with patch.object(panel, "run_phase1_strategist", return_value=strat), \
             patch.object(panel, "git", return_value=("", "", 0)), \
             patch.object(panel, "gh", return_value=("", "", 0)), \
             patch.object(panel, "call_agent", return_value={"content": "M", "tokens": 1}), \
             patch.object(panel, "load_key", return_value="fk"), \
             patch.object(panel, "load_github_token", return_value="ft"), \
             patch.object(panel, "detect_repo", return_value="t/t"), \
             patch.object(panel, "_set_gh_token"), \
             patch.object(panel, "acquire_lock", return_value=(True, None)), \
             patch.object(panel, "_cleanup_lock"), \
             patch.object(panel, "_safe_run", return_value=__import__("subprocess").CompletedProcess([], 0)), \
             patch.object(panel, "WorktreeManager"), \
             patch.object(panel, "spawn_agent", return_value="mock"), \
             patch("time.sleep"):
            panel.PROJECT_DIR = "/tmp"
            panel.REPO = "t/t"
            panel.DEFAULT_BRANCH = "main"
            try:
                panel.run_pipeline("Test Feature", False, False, None)
            except SystemExit:
                pass

        assert _called.get("phase2_coder"), \
            "single_session DAG should route to run_phase2_coder"
        assert not _called.get("parallel_coders"), \
            "single_session DAG should NOT route to run_parallel_coders"

    def test_per_task_spawn_routes_to_parallel_coders(self, panel):
        """4 parallelizable tasks, 4 distinct files (>3) → per_task_spawn → run_parallel_coders."""
        _reset_called()
        panel.run_phase2_coder = _mock_run_phase2_coder
        panel.run_parallel_coders = _mock_run_parallel_coders
        panel.halt_and_revert = _mock_halt_and_revert
        panel.merge_worktree_branches = _mock_merge_worktree_branches

        # All parallelizable, 4 distinct files (>3 threshold) → per_task_spawn
        spec = """# Test Feature

## Impact
Test impact.

## What Changed
- Nothing.

### Confidence: High
### Impact: LOW

## Task Breakdown

### Task 1: Module A
**Files:** a.py
**Dependencies:** [none]
**Parallelizable:** yes
**Description:** Touch module A.

### Task 2: Module B
**Files:** b.py
**Dependencies:** [none]
**Parallelizable:** yes
**Description:** Touch module B.

### Task 3: Module C
**Files:** c.py
**Dependencies:** [none]
**Parallelizable:** yes
**Description:** Touch module C.

### Task 4: Module D
**Files:** d.py
**Dependencies:** [none]
**Parallelizable:** yes
**Description:** Touch module D.
"""
        strat = _make_strat_result(panel, parallel_enabled=True, spec_has_tasks=True)
        strat["spec"] = spec

        with patch.object(panel, "run_phase1_strategist", return_value=strat), \
             patch.object(panel, "git", return_value=("", "", 0)), \
             patch.object(panel, "gh", return_value=("", "", 0)), \
             patch.object(panel, "call_agent", return_value={"content": "M", "tokens": 1}), \
             patch.object(panel, "load_key", return_value="fk"), \
             patch.object(panel, "load_github_token", return_value="ft"), \
             patch.object(panel, "detect_repo", return_value="t/t"), \
             patch.object(panel, "_set_gh_token"), \
             patch.object(panel, "acquire_lock", return_value=(True, None)), \
             patch.object(panel, "_cleanup_lock"), \
             patch.object(panel, "_safe_run", return_value=__import__("subprocess").CompletedProcess([], 0)), \
             patch.object(panel, "WorktreeManager"), \
             patch.object(panel, "spawn_agent", return_value="mock"), \
             patch("time.sleep"):
            panel.PROJECT_DIR = "/tmp"
            panel.REPO = "t/t"
            panel.DEFAULT_BRANCH = "main"
            try:
                panel.run_pipeline("Test Feature", False, False, None)
            except SystemExit:
                pass

        assert _called.get("parallel_coders"), \
            "per_task_spawn DAG should route to run_parallel_coders"
        assert not _called.get("phase2_coder"), \
            "per_task_spawn DAG should NOT route to run_phase2_coder"

    def test_parallel_enabled_false_downgrades_to_sequential(self, panel):
        """parallel_enabled=False → sequential even for per_task_spawn DAG."""
        _reset_called()
        panel.run_phase2_coder = _mock_run_phase2_coder
        panel.run_parallel_coders = _mock_run_parallel_coders
        panel.halt_and_revert = _mock_halt_and_revert
        panel.merge_worktree_branches = _mock_merge_worktree_branches

        # Non-parallelizable task → would be per_task_spawn, but disabled
        spec = """# Test Feature

## Impact
Test impact.

## What Changed
- Nothing.

### Confidence: High
### Impact: LOW

## Task Breakdown

### Task 1: Refactor
**Files:** core.py
**Dependencies:** [none]
**Parallelizable:** no
**Description:** Refactor core module.
"""
        strat = _make_strat_result(panel, parallel_enabled=False, spec_has_tasks=True)
        strat["spec"] = spec

        with patch.object(panel, "run_phase1_strategist", return_value=strat), \
             patch.object(panel, "git", return_value=("", "", 0)), \
             patch.object(panel, "gh", return_value=("", "", 0)), \
             patch.object(panel, "call_agent", return_value={"content": "M", "tokens": 1}), \
             patch.object(panel, "load_key", return_value="fk"), \
             patch.object(panel, "load_github_token", return_value="ft"), \
             patch.object(panel, "detect_repo", return_value="t/t"), \
             patch.object(panel, "_set_gh_token"), \
             patch.object(panel, "acquire_lock", return_value=(True, None)), \
             patch.object(panel, "_cleanup_lock"), \
             patch.object(panel, "_safe_run", return_value=__import__("subprocess").CompletedProcess([], 0)), \
             patch.object(panel, "WorktreeManager"), \
             patch.object(panel, "spawn_agent", return_value="mock"), \
             patch("time.sleep"):
            panel.PROJECT_DIR = "/tmp"
            panel.REPO = "t/t"
            panel.DEFAULT_BRANCH = "main"
            try:
                panel.run_pipeline("Test Feature", False, False, None)
            except SystemExit:
                pass

        assert _called.get("phase2_coder"), \
            "parallel_enabled=False should route to run_phase2_coder (downgrade)"
        assert not _called.get("parallel_coders"), \
            "parallel_enabled=False should NOT route to run_parallel_coders"

    def test_force_execution_mode_override(self, panel):
        """PANEL_FORCE_EXECUTION_MODE=single_session overrides per_task_spawn DAG."""
        _reset_called()
        panel.run_phase2_coder = _mock_run_phase2_coder
        panel.run_parallel_coders = _mock_run_parallel_coders
        panel.halt_and_revert = _mock_halt_and_revert
        panel.merge_worktree_branches = _mock_merge_worktree_branches

        # Non-parallelizable task → per_task_spawn, but overridden
        spec = """# Test Feature

## Impact
Test impact.

## What Changed
- Nothing.

### Confidence: High
### Impact: LOW

## Task Breakdown

### Task 1: Refactor
**Files:** core.py
**Dependencies:** [none]
**Parallelizable:** no
**Description:** Refactor core module.
"""
        strat = _make_strat_result(panel, parallel_enabled=True, spec_has_tasks=True)
        strat["spec"] = spec

        with patch.object(panel, "run_phase1_strategist", return_value=strat), \
             patch.object(panel, "git", return_value=("", "", 0)), \
             patch.object(panel, "gh", return_value=("", "", 0)), \
             patch.object(panel, "call_agent", return_value={"content": "M", "tokens": 1}), \
             patch.object(panel, "load_key", return_value="fk"), \
             patch.object(panel, "load_github_token", return_value="ft"), \
             patch.object(panel, "detect_repo", return_value="t/t"), \
             patch.object(panel, "_set_gh_token"), \
             patch.object(panel, "acquire_lock", return_value=(True, None)), \
             patch.object(panel, "_cleanup_lock"), \
             patch.object(panel, "_safe_run", return_value=__import__("subprocess").CompletedProcess([], 0)), \
             patch.object(panel, "WorktreeManager"), \
             patch.object(panel, "spawn_agent", return_value="mock"), \
             patch("time.sleep"):
            panel.PROJECT_DIR = "/tmp"
            panel.REPO = "t/t"
            panel.DEFAULT_BRANCH = "main"
            os.environ["PANEL_FORCE_EXECUTION_MODE"] = "single_session"
            try:
                panel.run_pipeline("Test Feature", False, False, None)
            except SystemExit:
                pass
            finally:
                os.environ.pop("PANEL_FORCE_EXECUTION_MODE", None)

        assert _called.get("phase2_coder"), \
            "PANEL_FORCE_EXECUTION_MODE=single_session should route to run_phase2_coder"
        assert not _called.get("parallel_coders"), \
            "Override should prevent run_parallel_coders"

    def test_empty_dag_routes_to_sequential(self, panel):
        """No tasks in DAG → fallback to sequential coder."""
        _reset_called()
        panel.run_phase2_coder = _mock_run_phase2_coder
        panel.run_parallel_coders = _mock_run_parallel_coders
        panel.halt_and_revert = _mock_halt_and_revert
        panel.merge_worktree_branches = _mock_merge_worktree_branches

        strat = _make_strat_result(panel, parallel_enabled=True, spec_has_tasks=False)

        with patch.object(panel, "run_phase1_strategist", return_value=strat), \
             patch.object(panel, "git", return_value=("", "", 0)), \
             patch.object(panel, "gh", return_value=("", "", 0)), \
             patch.object(panel, "call_agent", return_value={"content": "M", "tokens": 1}), \
             patch.object(panel, "load_key", return_value="fk"), \
             patch.object(panel, "load_github_token", return_value="ft"), \
             patch.object(panel, "detect_repo", return_value="t/t"), \
             patch.object(panel, "_set_gh_token"), \
             patch.object(panel, "acquire_lock", return_value=(True, None)), \
             patch.object(panel, "_cleanup_lock"), \
             patch.object(panel, "_safe_run", return_value=__import__("subprocess").CompletedProcess([], 0)), \
             patch.object(panel, "WorktreeManager"), \
             patch.object(panel, "spawn_agent", return_value="mock"), \
             patch("time.sleep"):
            panel.PROJECT_DIR = "/tmp"
            panel.REPO = "t/t"
            panel.DEFAULT_BRANCH = "main"
            try:
                panel.run_pipeline("Test Feature", False, False, None)
            except SystemExit:
                pass

        assert _called.get("phase2_coder"), \
            "Empty DAG should fallback to sequential coder"
        assert not _called.get("parallel_coders"), \
            "Empty DAG should NOT route to parallel coders"


# ── Depth matrix cell tests ──


def _make_spec_with_confidence_impact(confidence, impact):
    """Build a spec string with the given Confidence and Impact markers."""
    return f"""# Test Feature

## Impact
Test impact.

## What Changed
- Nothing.

### Confidence: {confidence}
### Impact: {impact}

## Task Breakdown

### Task 1: Single task
**Files:** a.py
**Dependencies:** [none]
**Parallelizable:** no
**Description:** Do thing.
"""


class TestDepthMatrixCells:
    """Verify all 9 (confidence × impact) combinations produce correct depth.
    Tests exercise the actual depth computation inside run_phase1_strategist
    by mocking spawn_agent instead of the entire strategist phase.
    """

    def _run_and_get_depth(self, panel, spec_text):
        """Run the pipeline with a given spec text and return the computed depth."""
        _reset_called()
        panel.run_phase2_coder = _mock_run_phase2_coder_capture
        panel.run_parallel_coders = _mock_run_parallel_coders
        panel.halt_and_revert = _mock_halt_and_revert
        panel.merge_worktree_branches = _mock_merge_worktree_branches
        # DO NOT mock run_phase1_strategist — let it execute so
        # the orchestration gate computes depth from the spec.

        with patch.object(panel, "spawn_agent", return_value=spec_text), \
             patch.object(panel, "git", return_value=("", "", 0)), \
             patch.object(panel, "call_agent", return_value={"content": "M", "tokens": 1}), \
             patch.object(panel, "load_key", return_value="fk"), \
             patch.object(panel, "load_github_token", return_value="ft"), \
             patch.object(panel, "detect_repo", return_value="t/t"), \
             patch.object(panel, "_set_gh_token"), \
             patch.object(panel, "acquire_lock", return_value=(True, None)), \
             patch.object(panel, "_cleanup_lock"), \
             patch.object(panel, "_safe_run", return_value=__import__("subprocess").CompletedProcess([], 0)), \
             patch.object(panel, "WorktreeManager"), \
             patch("time.sleep"):
            panel.PROJECT_DIR = "/tmp"
            panel.REPO = "t/t"
            panel.DEFAULT_BRANCH = "main"
            try:
                panel.run_pipeline("Test Feature", False, False, None)
            except SystemExit:
                pass
        return _captured_depth

    def test_high_conf_low_impact_produces_vet(self, panel):
        """(High, LOW) → vet — docs/config changes skip adversarial review."""
        depth = self._run_and_get_depth(panel, _make_spec_with_confidence_impact("High", "LOW"))
        assert depth == "vet", f"Expected 'vet', got '{depth}'"

    def test_high_conf_medium_impact_produces_vet_nm(self, panel):
        """(High, MEDIUM) → vet+nm — normal changes get build+nm."""
        depth = self._run_and_get_depth(panel, _make_spec_with_confidence_impact("High", "MEDIUM"))
        assert depth == "vet+nm", f"Expected 'vet+nm', got '{depth}'"

    def test_high_conf_high_impact_produces_full(self, panel):
        """(High, HIGH) → full — high-impact changes get full pipeline."""
        depth = self._run_and_get_depth(panel, _make_spec_with_confidence_impact("High", "HIGH"))
        assert depth == "full", f"Expected 'full', got '{depth}'"

    def test_medium_conf_low_impact_produces_vet_nm(self, panel):
        """(Medium, LOW) → vet+nm — medium confidence+low impact gets vet+nm."""
        depth = self._run_and_get_depth(panel, _make_spec_with_confidence_impact("Medium", "LOW"))
        assert depth == "vet+nm", f"Expected 'vet+nm', got '{depth}'"

    def test_medium_conf_medium_impact_produces_full(self, panel):
        """(Medium, MEDIUM) → full."""
        depth = self._run_and_get_depth(panel, _make_spec_with_confidence_impact("Medium", "MEDIUM"))
        assert depth == "full", f"Expected 'full', got '{depth}'"

    def test_medium_conf_high_impact_produces_full(self, panel):
        """(Medium, HIGH) → full."""
        depth = self._run_and_get_depth(panel, _make_spec_with_confidence_impact("Medium", "HIGH"))
        assert depth == "full", f"Expected 'full', got '{depth}'"

    def test_low_conf_low_impact_produces_vet(self, panel):
        """(Low, LOW) → vet — low-risk changes skip adversarial review."""
        depth = self._run_and_get_depth(panel, _make_spec_with_confidence_impact("Low", "LOW"))
        assert depth == "vet", f"Expected 'vet', got '{depth}'"

    def test_low_conf_medium_impact_produces_vet_nm(self, panel):
        """(Low, MEDIUM) → vet+nm."""
        depth = self._run_and_get_depth(panel, _make_spec_with_confidence_impact("Low", "MEDIUM"))
        assert depth == "vet+nm", f"Expected 'vet+nm', got '{depth}'"

    def test_low_conf_high_impact_produces_full(self, panel):
        """(Low, HIGH) → full — low confidence but high impact gets full pipeline."""
        depth = self._run_and_get_depth(panel, _make_spec_with_confidence_impact("Low", "HIGH"))
        assert depth == "full", f"Expected 'full', got '{depth}'"

    def test_confidence_parser_rejects_substring_false_positive(self, panel):
        """Confidence 'Higher' must NOT match marker 'High' — defaults to Medium."""
        spec = _make_spec_with_confidence_impact("Higher", "MEDIUM")
        # "Confidence: Higher" should NOT match "High";
        # default is "Medium" → (Medium, MEDIUM) = "full"
        depth = self._run_and_get_depth(panel, spec)
        assert depth == "full", f"Expected 'full' (default Medium), got '{depth}'"

    def test_impact_parser_defaults_to_medium_not_high(self, panel):
        """No Impact marker → defaults to MEDIUM (not HIGH)."""
        spec = """# Test Feature

## Impact
Test impact.

## What Changed
- Nothing.

### Confidence: High

## Task Breakdown

### Task 1: Single task
**Files:** a.py
**Dependencies:** [none]
**Parallelizable:** no
**Description:** Do thing.
"""
        # No Impact marker → impact="MEDIUM" → (High, MEDIUM) = "vet+nm"
        depth = self._run_and_get_depth(panel, spec)
        assert depth == "vet+nm", f"Expected 'vet+nm' (default MEDIUM), got '{depth}'"

    def test_impact_parser_rejects_substring_false_positive(self, panel):
        """'HIGHER' must NOT match marker 'HIGH' — defaults to MEDIUM."""
        spec = _make_spec_with_confidence_impact("High", "HIGHER")
        # "Impact: HIGHER" should NOT match "HIGH";
        # default is "MEDIUM" → (High, MEDIUM) = "vet+nm"
        depth = self._run_and_get_depth(panel, spec)
        assert depth == "vet+nm", f"Expected 'vet+nm' (default MEDIUM), got '{depth}'"
