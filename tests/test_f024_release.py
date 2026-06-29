"""Tests for F024: Auto-Release — Tagging, Changelog, and GitHub Releases."""
import sys, os

# Ensure the project root is on the path so we can import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils


class TestBumpVersion:
    """Tests for _bump_version() helper."""

    def test_bump_patch_increments_z(self):
        """patch: 1.2.1 → 1.2.2"""
        result = utils._bump_version("1.2.1", "patch")
        assert result == "1.2.2", f"Expected 1.2.2, got {result}"

    def test_bump_minor_increments_y_resets_z(self):
        """minor: 1.2.1 → 1.3.0"""
        result = utils._bump_version("1.2.1", "minor")
        assert result == "1.3.0", f"Expected 1.3.0, got {result}"

    def test_bump_major_increments_x_resets_yz(self):
        """major: 1.2.1 → 2.0.0"""
        result = utils._bump_version("1.2.1", "major")
        assert result == "2.0.0", f"Expected 2.0.0, got {result}"

    def test_bump_patch_from_zero(self):
        """patch: 0.0.1 → 0.0.2"""
        result = utils._bump_version("0.0.1", "patch")
        assert result == "0.0.2", f"Expected 0.0.2, got {result}"

    def test_bump_minor_from_zero(self):
        """minor: 0.0.1 → 0.1.0"""
        result = utils._bump_version("0.0.1", "minor")
        assert result == "0.1.0", f"Expected 0.1.0, got {result}"

    def test_bump_major_from_zero(self):
        """major: 0.0.1 → 1.0.0"""
        result = utils._bump_version("0.0.1", "major")
        assert result == "1.0.0", f"Expected 1.0.0, got {result}"

    def test_patch_at_nine(self):
        """patch: 9.9.9 → 9.9.10 (NOT 10.0.0)"""
        result = utils._bump_version("9.9.9", "patch")
        assert result == "9.9.10", f"Expected 9.9.10, got {result}"

    def test_minor_wraps_z(self):
        """minor: 1.9.5 → 1.10.0"""
        result = utils._bump_version("1.9.5", "minor")
        assert result == "1.10.0", f"Expected 1.10.0, got {result}"

    def test_major_wraps_yz(self):
        """major: 5.9.1 → 6.0.0"""
        result = utils._bump_version("5.9.1", "major")
        assert result == "6.0.0", f"Expected 6.0.0, got {result}"


class TestBumpVersionRejectsInvalid:
    """Tests for _bump_version() rejecting invalid bump types."""

    def test_rejects_nonsense(self):
        """Invalid bump type raises ValueError."""
        try:
            utils._bump_version("1.2.1", "nonsense")
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_rejects_prepatch(self):
        """prepatch is not a valid bump type."""
        try:
            utils._bump_version("1.2.1", "prepatch")
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_rejects_empty_bump(self):
        """Empty bump type raises ValueError."""
        try:
            utils._bump_version("1.2.1", "")
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_rejects_invalid_version(self):
        """Invalid version string raises ValueError."""
        try:
            utils._bump_version("not.a.version", "patch")
            assert False, "Expected ValueError"
        except ValueError:
            pass
