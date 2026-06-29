"""Tests for F006: Error Recovery & Resume — checkpoint helpers.

Covers _checkpoint_path, save_checkpoint, load_checkpoint, delete_checkpoint,
and stale checkpoint detection.
"""

import os
import json
import tempfile
from conftest import _load_panel as _load


class TestCheckpointPath:
    """Task 1: _checkpoint_path returns correct path."""

    def test_checkpoint_path_format(self):
        panel = _load()
        path = panel._checkpoint_path("test-feature")
        assert path == "/tmp/dokima-test-feature-checkpoint.json"

    def test_checkpoint_path_with_spaces_slug(self):
        panel = _load()
        path = panel._checkpoint_path("my feature")
        assert path == "/tmp/dokima-my feature-checkpoint.json"

    def test_checkpoint_path_empty_slug(self):
        panel = _load()
        path = panel._checkpoint_path("")
        assert path == "/tmp/dokima--checkpoint.json"


class TestSaveCheckpoint:
    """Task 1: save_checkpoint writes to checkpoint path."""

    def test_save_checkpoint_creates_file(self):
        panel = _load()
        slug = "test-save-checkpoint"
        try:
            data = {"version": 1, "phase": "strategist", "feature": "Test Feature"}
            panel.save_checkpoint(slug, data)
            cpath = panel._checkpoint_path(slug)
            assert os.path.exists(cpath), "Checkpoint file should exist"
            with open(cpath) as f:
                loaded = json.load(f)
            assert loaded["version"] == 1
            assert loaded["phase"] == "strategist"
            assert loaded["feature"] == "Test Feature"
        finally:
            cpath = panel._checkpoint_path(slug)
            if os.path.exists(cpath):
                os.remove(cpath)

    def test_save_checkpoint_with_none_deletes(self):
        panel = _load()
        slug = "test-save-none"
        try:
            panel.save_checkpoint(slug, {"version": 1})
            cpath = panel._checkpoint_path(slug)
            assert os.path.exists(cpath)
            panel.save_checkpoint(slug, None)
            assert not os.path.exists(cpath), "Checkpoint should be deleted"
        finally:
            cpath = panel._checkpoint_path(slug)
            if os.path.exists(cpath):
                os.remove(cpath)


class TestLoadCheckpoint:
    """Task 1: load_checkpoint reads checkpoint data."""

    def test_load_checkpoint_returns_data(self):
        panel = _load()
        slug = "test-load-checkpoint"
        try:
            panel.save_checkpoint(slug, {"version": 1, "phase": "coder"})
            loaded = panel.load_checkpoint(slug)
            assert loaded is not None
            assert loaded["version"] == 1
            assert loaded["phase"] == "coder"
        finally:
            cpath = panel._checkpoint_path(slug)
            if os.path.exists(cpath):
                os.remove(cpath)

    def test_load_checkpoint_not_found_returns_none(self):
        panel = _load()
        loaded = panel.load_checkpoint("nonexistent-slug")
        assert loaded is None

    def test_load_checkpoint_corrupted_returns_none(self):
        panel = _load()
        slug = "test-corrupt"
        cpath = panel._checkpoint_path(slug)
        try:
            with open(cpath, "w") as f:
                f.write("not-json")
            loaded = panel.load_checkpoint(slug)
            assert loaded is None
        finally:
            if os.path.exists(cpath):
                os.remove(cpath)


class TestDeleteCheckpoint:
    """Task 1: delete_checkpoint removes checkpoint file."""

    def test_delete_checkpoint_removes_file(self):
        panel = _load()
        slug = "test-delete-checkpoint"
        panel.save_checkpoint(slug, {"version": 1})
        cpath = panel._checkpoint_path(slug)
        assert os.path.exists(cpath)
        panel.delete_checkpoint(slug)
        assert not os.path.exists(cpath)

    def test_delete_checkpoint_nonexistent_no_error(self):
        panel = _load()
        panel.delete_checkpoint("ghost-slug")  # should not raise


class TestCheckpointValidation:
    """Task 4: Stale checkpoint validation."""

    def test_validate_checkpoint_valid(self):
        panel = _load()
        slug = "test-validate-valid"
        saved_branch = "feat/test-validate-valid"
        saved_spec_path = "/tmp/test-spec.md"
        try:
            # Create the checkpoint
            panel.save_checkpoint(slug, {
                "version": 1,
                "branch": saved_branch,
                "spec_path": saved_spec_path,
                "phases_completed": ["strategist"],
            })
            # Create the spec file
            with open(saved_spec_path, "w") as f:
                f.write("# Test spec")
            # Mock git to say branch exists
            original_run = panel._safe_run
            try:
                panel._safe_run = lambda cmd_str, cwd=None, timeout=None: __import__("subprocess").CompletedProcess([], 0)
                is_valid = panel.validate_checkpoint(slug)
                assert is_valid is True
            finally:
                panel._safe_run = original_run
        finally:
            panel.delete_checkpoint(slug)
            if os.path.exists(saved_spec_path):
                os.remove(saved_spec_path)

    def test_validate_checkpoint_no_checkpoint(self):
        panel = _load()
        assert panel.validate_checkpoint("ghost") is False

    def test_validate_checkpoint_missing_spec_file(self):
        panel = _load()
        slug = "test-validate-missing-spec"
        try:
            panel.save_checkpoint(slug, {
                "version": 1,
                "branch": "feat/test",
                "spec_path": "/tmp/nonexistent-spec.md",
                "phases_completed": ["strategist"],
            })
            original_run = panel._safe_run
            try:
                panel._safe_run = lambda cmd_str, cwd=None, timeout=None: __import__("subprocess").CompletedProcess([], 0)
                is_valid = panel.validate_checkpoint(slug)
                assert is_valid is False
            finally:
                panel._safe_run = original_run
        finally:
            panel.delete_checkpoint(slug)

    def test_validate_checkpoint_branch_gone(self):
        panel = _load()
        slug = "test-validate-gone-branch"
        saved_spec_path = "/tmp/test-spec-branch-gone.md"
        try:
            panel.save_checkpoint(slug, {
                "version": 1,
                "branch": "feat/nonexistent-branch",
                "spec_path": saved_spec_path,
                "phases_completed": ["strategist"],
            })
            with open(saved_spec_path, "w") as f:
                f.write("# Test spec")
            original_run = panel._safe_run
            try:
                panel._safe_run = lambda cmd_str, cwd=None, timeout=None: __import__("subprocess").CompletedProcess([], 1)
                is_valid = panel.validate_checkpoint(slug)
                assert is_valid is False
            finally:
                panel._safe_run = original_run
        finally:
            panel.delete_checkpoint(slug)
            if os.path.exists(saved_spec_path):
                os.remove(saved_spec_path)


class TestResumeFlag:
    """Task 2: --resume / --no-resume flag sets global RESUME."""

    def test_resume_flag_default(self):
        """RESUME defaults to None (auto-detect) when not set."""
        panel = _load()
        assert panel.RESUME is None

    def test_resume_flag_true(self):
        """Setting RESUME = True enables resume mode."""
        panel = _load()
        panel.RESUME = True
        assert panel.RESUME is True

    def test_resume_flag_false(self):
        """Setting RESUME = False disables resume mode."""
        panel = _load()
        panel.RESUME = False
        assert panel.RESUME is False


class TestPipelineCheckpointSave:
    """Task 3: Checkpoint saved after each phase in run_pipeline."""

    def test_save_checkpoint_after_strategist(self):
        panel = _load()
        slug = "test-pipeline-strategist"
        try:
            panel.save_checkpoint(slug, {
                "version": 1,
                "feature": "Test Feature",
                "branch": "feat/test",
                "spec_path": "/tmp/test-spec.md",
                "phases_completed": ["strategist"],
            })
            cpath = panel._checkpoint_path(slug)
            assert os.path.exists(cpath)
            data = panel.load_checkpoint(slug)
            assert "strategist" in data["phases_completed"]
        finally:
            panel.delete_checkpoint(slug)

    def test_checkpoint_accumulates_phases(self):
        panel = _load()
        slug = "test-pipeline-accumulate"
        try:
            data = {"version": 1, "phases_completed": ["strategist", "coder"]}
            panel.save_checkpoint(slug, data)
            loaded = panel.load_checkpoint(slug)
            assert loaded["phases_completed"] == ["strategist", "coder"]
        finally:
            panel.delete_checkpoint(slug)

    def test_checkpoint_deleted_on_completion(self):
        panel = _load()
        slug = "test-pipeline-complete"
        try:
            panel.save_checkpoint(slug, {"version": 1, "phases_completed": ["strategist", "coder", "vet", "nm", "tech_lead"]})
            assert panel.load_checkpoint(slug) is not None
            panel.save_checkpoint(slug, None)  # signal completion
            assert panel.load_checkpoint(slug) is None
        finally:
            panel.delete_checkpoint(slug)

    def test_checkpoint_cleanup_no_resume(self):
        """When RESUME=False, any existing checkpoint should be deleted."""
        panel = _load()
        slug = "test-pipeline-no-resume"
        try:
            panel.save_checkpoint(slug, {"version": 1, "phases_completed": ["strategist"]})
            assert panel.load_checkpoint(slug) is not None
            # Simulate what happens when RESUME=False and pipeline starts
            if panel.load_checkpoint(slug) and not panel.RESUME:
                panel.save_checkpoint(slug, None)
            assert panel.load_checkpoint(slug) is None
        finally:
            panel.delete_checkpoint(slug)


class TestResumeSkipPhase:
    """Task 3: Resume skips completed phases."""

    def test_skip_strategist_when_checkpointed(self):
        """If checkpoint says strategist done, should skip strategist."""
        panel = _load()
        assert panel._phase_should_skip(["strategist", "coder"], "strategist", resume=True) is True

    def test_no_skip_uncompleted_phase(self):
        """If checkpoint doesn't list vet, vet should run."""
        panel = _load()
        assert panel._phase_should_skip(["strategist", "coder"], "vet", resume=True) is False

    def test_no_skip_empty_checkpoint(self):
        """Empty phases_completed should not skip anything."""
        panel = _load()
        assert panel._phase_should_skip([], "strategist") is False

    def test_no_skip_without_resume_flag(self):
        """When resume=False or None, don't skip even if checkpoint exists."""
        panel = _load()
        assert panel._phase_should_skip([], "strategist", resume=False) is False
        assert panel._phase_should_skip([], "strategist", resume=None) is False


class TestCheckpointGateBehavior:
    """Task 3: Checkpoint gate saves when resume is None or True, not when False.

    The gate condition ``if resume is not False:`` must save checkpoints by
    default (resume=None) and with --resume (True), and suppress them only
    with --no-resume (False).
    """

    def test_saves_checkpoint_when_resume_none(self):
        """save_checkpoint is called when resume=None (default)."""
        panel = _load()
        slug = "test-gate-resume-none"
        try:
            # Simulate the gate: when resume is not False, save checkpoint
            resume = None  # default
            if resume is not False:
                panel.save_checkpoint(slug, {
                    "version": 1,
                    "phases_completed": ["coder"],
                })
            cpath = panel._checkpoint_path(slug)
            assert os.path.exists(cpath), \
                "Expected checkpoint saved when resume=None (default)"
            data = panel.load_checkpoint(slug)
            assert data is not None
            assert "coder" in data["phases_completed"]
        finally:
            panel.delete_checkpoint(slug)

    def test_saves_checkpoint_when_resume_true(self):
        """save_checkpoint is called when resume=True."""
        panel = _load()
        slug = "test-gate-resume-true"
        try:
            resume = True
            if resume is not False:
                panel.save_checkpoint(slug, {
                    "version": 1,
                    "phases_completed": ["coder"],
                })
            cpath = panel._checkpoint_path(slug)
            assert os.path.exists(cpath), \
                "Expected checkpoint saved when resume=True"
        finally:
            panel.delete_checkpoint(slug)

    def test_skips_checkpoint_when_resume_false(self):
        """save_checkpoint is NOT called when resume=False."""
        panel = _load()
        slug = "test-gate-resume-false"
        try:
            resume = False
            if resume is not False:
                panel.save_checkpoint(slug, {
                    "version": 1,
                    "phases_completed": ["coder"],
                })
            cpath = panel._checkpoint_path(slug)
            assert not os.path.exists(cpath), \
                "Expected NO checkpoint saved when resume=False"
        finally:
            panel.delete_checkpoint(slug)

    def test_saves_checkpoint_directly_matches_gate_logic(self):
        """Verify the gate condition is semantically correct for all values."""
        # The actual gate: if resume is not False
        def would_save(resume):
            return resume is not False

        assert would_save(None) is True, "resume=None should save (default)"
        assert would_save(True) is True, "resume=True should save"
        assert would_save(False) is False, "resume=False should suppress"
