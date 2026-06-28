"""Tests for pick_next_feature — topological sort + priority ordering."""

import pytest
from conftest import _load_panel as _load

# Helper to build RoadmapFeature objects for testing
def _f(fid, priority="P1", status="pending", dependencies=None, title="", story=""):
    panel = _load()
    return panel.RoadmapFeature(
        fid=fid, title=title or fid, priority=priority,
        dependencies=dependencies or [], status=status, story=story
    )


class TestPickNextFeature:
    """Core ordering: P0 before P1, deps block, in_progress + pending pool."""

    def test_returns_none_for_empty_list(self):
        panel = _load()
        assert panel.pick_next_feature([]) is None

    def test_returns_only_pending_feature(self):
        panel = _load()
        f1 = _f("F001", "P0")
        result = panel.pick_next_feature([f1])
        assert result is not None
        assert result.id == "F001"

    def test_p0_before_p1_when_both_unblocked(self):
        """P0 should be picked over P1 regardless of id ordering."""
        panel = _load()
        f1 = _f("F005", "P1")   # lower priority
        f2 = _f("F003", "P0")   # higher priority — should win
        result = panel.pick_next_feature([f1, f2])
        assert result.id == "F003"

    def test_p0_before_p1_regardless_of_list_order(self):
        """P0 wins even when listed after P1."""
        panel = _load()
        f1 = _f("F001", "P0")
        f2 = _f("F004", "P1")
        # List order: P1 first, P0 second
        result = panel.pick_next_feature([f2, f1])
        assert result.id == "F001"

    def test_blocked_by_incomplete_dependency_not_picked(self):
        """Feature with unsatisfied dep is skipped even if higher priority."""
        panel = _load()
        f_blocked = _f("F003", "P0", dependencies=["F002"])  # F002 missing from feature list
        f_ready = _f("F001", "P1")  # lower prio but unblocked
        result = panel.pick_next_feature([f_blocked, f_ready])
        assert result.id == "F001"  # F003 blocked by missing F002, F001 wins

    def test_done_dependency_unblocks(self):
        """Feature with ALL deps done is eligible."""
        panel = _load()
        f_dep = _f("F002", "P0", status="done")
        f_unblocked = _f("F003", "P0", dependencies=["F002"])
        f_p1 = _f("F004", "P1")
        result = panel.pick_next_feature([f_dep, f_unblocked, f_p1])
        assert result.id == "F003"

    def test_tiebreaker_by_position_when_same_priority(self):
        """Same priority + same status → earlier in list (roadmap order) wins."""
        panel = _load()
        f1 = _f("F005", "P1")
        f2 = _f("F001", "P1")
        result = panel.pick_next_feature([f1, f2])
        assert result.id == "F005"  # F005 at position 0, F001 at position 1


class TestInProgressInclusion:
    """BUG FIX: in_progress features must be in the candidate pool with pending."""

    def test_in_progress_p0_beats_pending_p1(self):
        """F003 (P0, in_progress) should beat F005 (P1, pending)."""
        panel = _load()
        f_in_progress = _f("F003", "P0", status="in_progress")
        f_pending = _f("F005", "P1", status="pending")
        result = panel.pick_next_feature([f_in_progress, f_pending])
        assert result.id == "F003"

    def test_in_progress_p1_beats_pending_p1_tiebreaker(self):
        """Same priority → in_progress should be preferred over pending."""
        panel = _load()
        f_in_progress = _f("F006", "P1", status="in_progress")
        f_pending = _f("F005", "P1", status="pending")
        result = panel.pick_next_feature([f_in_progress, f_pending])
        assert result.id == "F006"  # in_progress wins tie

    def test_in_progress_still_respects_deps(self):
        """in_progress feature with unsatisfied dependency is still blocked."""
        panel = _load()
        f_blocked = _f("F003", "P0", status="in_progress", dependencies=["F002"])  # F002 not in list
        f_ready = _f("F001", "P1")
        result = panel.pick_next_feature([f_blocked, f_ready])
        assert result.id == "F001"  # F003 blocked, F001 wins

    def test_done_features_excluded(self):
        """Done features are never picked, even if highest priority."""
        panel = _load()
        f_done = _f("F003", "P0", status="done")
        f_pending = _f("F005", "P1")
        result = panel.pick_next_feature([f_done, f_pending])
        assert result.id == "F005"

    def test_all_in_progress_blocked_by_deps_returns_pending(self):
        """When all in_progress are blocked, fall back to best pending."""
        panel = _load()
        f_blocked = _f("F003", "P0", status="in_progress", dependencies=["F002"])  # F002 not in list
        f_pending = _f("F005", "P1")
        result = panel.pick_next_feature([f_blocked, f_pending])
        assert result.id == "F005"
