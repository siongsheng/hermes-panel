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
                panel._safe_run = lambda cmd, **kw: ("", "", 0)
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
                panel._safe_run = lambda cmd, **kw: ("", "", 0)
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
                panel._safe_run = lambda cmd, **kw: ("", "not a branch", 1)
                is_valid = panel.validate_checkpoint(slug)
                assert is_valid is False
            finally:
                panel._safe_run = original_run
        finally:
            panel.delete_checkpoint(slug)
            if os.path.exists(saved_spec_path):
                os.remove(saved_spec_path)
