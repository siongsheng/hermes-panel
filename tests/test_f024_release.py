"""Tests for F024: Auto-Release — Tagging, Changelog, and GitHub Releases."""
import os
import sys
import subprocess
import json
import tempfile
import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dokima")


def _run(*args, cwd=None, timeout=15):
    """Run dokima with given args and return (returncode, stdout, stderr)."""
    p = subprocess.run(
        [sys.executable, SCRIPT] + list(args),
        capture_output=True, text=True, timeout=timeout, cwd=cwd
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


class TestReleaseFlagScanning:
    """Task 4: --release flag scanning and bump type validation."""

    def test_release_patch_exits_zero(self):
        """--release patch exits 0 (recognised, does not demand feature desc)."""
        rc, stdout, stderr = _run("--release", "patch")
        assert rc == 0, (
            f"Expected exit 0, got {rc}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )

    def test_release_minor_exits_zero(self):
        """--release minor is a valid bump type."""
        rc, stdout, stderr = _run("--release", "minor")
        assert rc == 0, (
            f"Expected exit 0, got {rc}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )

    def test_release_major_exits_zero(self):
        """--release major is a valid bump type."""
        rc, stdout, stderr = _run("--release", "major")
        assert rc == 0, (
            f"Expected exit 0, got {rc}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )

    def test_release_invalid_bump_exits_one(self):
        """--release with invalid bump type (prepatch) exits 1 with error."""
        rc, stdout, stderr = _run("--release", "prepatch")
        assert rc == 1, f"Expected exit 1, got {rc}"
        combined = stdout + stderr
        assert "Invalid release bump type" in combined, (
            f"Expected 'Invalid release bump type' in output, got: {combined}"
        )

    def test_release_invalid_bump_exits_one_foo(self):
        """--release with invalid bump type (foo) exits 1 with error."""
        rc, stdout, stderr = _run("--release", "foo")
        assert rc == 1, f"Expected exit 1, got {rc}"
        combined = stdout + stderr
        assert "Invalid release bump type" in combined, (
            f"Expected 'Invalid release bump type' in output, got: {combined}"
        )

    def test_release_invalid_bump_shows_valid_types(self):
        """--release invalid mentions valid bump types in error."""
        rc, out, err = _run("--release", "invalid")
        assert rc == 1, f"Expected exit 1, got {rc}. stdout={out!r} stderr={err!r}"
        combined = (out + err).lower()
        assert any(
            word in combined for word in ("patch", "minor", "major")
        ), f"Expected mention of valid bump types, got: out={out!r} err={err!r}"

    def test_release_missing_bump_exits_one(self):
        """--release without a bump type exits 1 with error message."""
        rc, stdout, stderr = _run("--release")
        assert rc == 1, f"Expected exit 1, got {rc}"
        combined = stdout + stderr
        assert "requires a bump type" in combined, (
            f"Expected 'requires a bump type' in output, got: {combined}"
        )

    def test_release_missing_bump_shows_usage_words(self):
        """--release without bump type mentions patch/minor/major."""
        rc, out, err = _run("--release")
        assert rc == 1, f"Expected exit 1, got {rc}. stdout={out!r} stderr={err!r}"
        combined = (out + err).lower()
        assert any(
            word in combined for word in ("bump", "patch", "minor", "major")
        ), f"Expected error about missing bump type, got: out={out!r} err={err!r}"

    def test_release_flag_does_not_break_help(self):
        """--release patch --help: --help wins (checked first)."""
        rc, stdout, stderr = _run("--help", "--release", "patch")
        assert rc == 0, f"Expected exit 0, got {rc}"
        assert "COMMANDS:" in stdout, (
            f"Expected 'COMMANDS:' in help output, got: {stdout[:200]}"
        )

    def test_release_flag_with_extra_arg_exits_zero(self):
        """--release patch with project_dir arg exits 0."""
        rc, stdout, stderr = _run("--release", "patch", "/tmp")
        assert rc == 0, (
            f"Expected exit 0, got {rc}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )


class TestReleaseDispatch:
    """Task 5: --release dispatch — flag parsing and early-exit dispatch."""

    def test_release_flag_is_recognized(self):
        """dokima --release patch is recognized as a flag, not a feature description."""
        with tempfile.TemporaryDirectory() as td:
            rc, out, err = _run("--release", "patch", cwd=td)
            combined = out + err
            assert "is not a valid git repository" not in combined, \
                f"--release should be recognized as a flag. Got: {combined!r}"

    def test_release_flag_no_bump_shows_error(self):
        """dokima --release (no bump type) produces a bump-type-specific error."""
        with tempfile.TemporaryDirectory() as td:
            rc, out, err = _run("--release", cwd=td)
            combined = (out + err).lower()
            bump_mentioned = "patch" in combined or "minor" in combined or "major" in combined
            is_git_error = "not a valid git repository" in combined
            assert bump_mentioned and not is_git_error, \
                f"Expected bump-type error, got out={out!r} err={err!r}"

    def test_release_flag_invalid_bump_shows_error(self):
        """dokima --release invalid exits non-zero with bump type error."""
        with tempfile.TemporaryDirectory() as td:
            rc, out, err = _run("--release", "prepatch", cwd=td)
            assert rc != 0, f"Expected non-zero exit, got {rc}. out={out!r} err={err!r}"
            combined = (out + err).lower()
            assert "patch" in combined, f"Expected 'patch' in error, got out={out!r} err={err!r}"
            assert "minor" in combined, f"Expected 'minor' in error, got out={out!r} err={err!r}"
            assert "major" in combined, f"Expected 'major' in error, got out={out!r} err={err!r}"
            assert "not a valid git repository" not in combined, \
                f"Should be a bump-type error, not git-repo error. Got: {combined!r}"

    def test_release_flag_accepts_minor(self):
        """dokima --release minor is recognized and dispatched."""
        with tempfile.TemporaryDirectory() as td:
            rc, out, err = _run("--release", "minor", cwd=td)
            combined = out + err
            assert "is not a valid git repository" not in combined, \
                f"--release minor should be recognized as a flag. Got: {combined!r}"

    def test_release_flag_accepts_major(self):
        """dokima --release major is recognized and dispatched."""
        with tempfile.TemporaryDirectory() as td:
            rc, out, err = _run("--release", "major", cwd=td)
            combined = out + err
            assert "is not a valid git repository" not in combined, \
                f"--release major should be recognized as a flag. Got: {combined!r}"

    def test_release_flag_with_project_dir(self):
        """dokima --release patch with a project dir dispatches."""
        with tempfile.TemporaryDirectory() as td:
            rc, out, err = _run("--release", "patch", td, cwd=td)
            combined = out + err
            assert "Feature description required" not in combined, \
                f"--release should be a flag. Got: {combined!r}"
            assert "is not a valid git repository" not in combined, \
                f"--release should dispatch before project validation. Got: {combined!r}"


class TestDryRun:
    """Task 6: --dry-run flag with --release."""

    def test_release_patch_dry_run_exits_zero(self):
        """--release patch --dry-run exits 0 (dry run completes successfully)."""
        rc, stdout, stderr = _run("--release", "patch", "--dry-run")
        assert rc == 0, (
            f"Expected exit 0, got {rc}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )

    def test_release_patch_dry_run_prints_dry_run_header(self):
        """--release patch --dry-run prints '[DRY RUN]' indicator."""
        rc, stdout, stderr = _run("--release", "patch", "--dry-run")
        combined = stdout + stderr
        assert "[DRY RUN]" in combined, (
            f"Expected '[DRY RUN]' in output, got: {combined!r}"
        )

    def test_release_patch_dry_run_shows_planned_version(self):
        """--release patch --dry-run shows the planned new version."""
        rc, stdout, stderr = _run("--release", "patch", "--dry-run")
        combined = stdout + stderr
        assert "Would release" in combined, (
            f"Expected 'Would release' in output, got: {combined!r}"
        )

    def test_release_patch_dry_run_no_git_error(self):
        """--release patch --dry-run does NOT produce a git-repo error."""
        rc, stdout, stderr = _run("--release", "patch", "--dry-run")
        combined = stdout + stderr
        assert "is not a valid git repository" not in combined, (
            f"--dry-run should be recognized as a flag. Got: {combined!r}"
        )

    def test_release_major_dry_run_exits_zero(self):
        """--release major --dry-run exits 0."""
        rc, stdout, stderr = _run("--release", "major", "--dry-run")
        assert rc == 0, (
            f"Expected exit 0, got {rc}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )

    def test_release_minor_dry_run_exits_zero(self):
        """--release minor --dry-run exits 0."""
        rc, stdout, stderr = _run("--release", "minor", "--dry-run")
        assert rc == 0, (
            f"Expected exit 0, got {rc}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )

    def test_release_dry_run_with_project_dir(self):
        """--release patch --dry-run with project_dir arg works."""
        rc, stdout, stderr = _run("--release", "patch", "--dry-run", "/tmp")
        assert rc == 0, (
            f"Expected exit 0, got {rc}\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )

    def test_dry_run_before_release(self):
        """--dry-run --release patch (flag order swap) is recognized."""
        rc, stdout, stderr = _run("--dry-run", "--release", "patch")
        combined = stdout + stderr
        assert "is not a valid git repository" not in combined, (
            f"--dry-run should be recognized before --release. Got: {combined!r}"
        )

