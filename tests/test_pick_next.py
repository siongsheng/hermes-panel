"""Tests for pick_next_feature() — topological sort + priority ordering."""
import pytest

def make_feat(panel, fid, priority="P1", deps=None, status="pending", section=""):
    return panel.RoadmapFeature(fid=fid, title=f"Feature {fid}",
                                 priority=priority, dependencies=deps or [],
                                 status=status, story="", section=section)

def test_empty_list(panel):
    assert panel.pick_next_feature([]) is None

def test_all_done(panel):
    feats = [
        make_feat(panel, "F001", status="done"),
        make_feat(panel, "F002", status="done"),
    ]
    assert panel.pick_next_feature(feats) is None

def test_single_pending_no_deps(panel):
    feats = [make_feat(panel, "F001")]
    result = panel.pick_next_feature(feats)
    assert result is not None
    assert result.id == "F001"

def test_p0_beats_p1(panel):
    feats = [
        make_feat(panel, "F001", priority="P1"),
        make_feat(panel, "F002", priority="P0"),
    ]
    result = panel.pick_next_feature(feats)
    assert result.id == "F002"

def test_blocked_by_dependency(panel):
    feats = [
        make_feat(panel, "F001", priority="P1"),
        make_feat(panel, "F002", priority="P0", deps=["F001"]),
    ]
    result = panel.pick_next_feature(feats)
    assert result.id == "F001"  # F002 blocked, F001 is open

def test_dependency_done_unblocks(panel):
    feats = [
        make_feat(panel, "F001", status="done"),
        make_feat(panel, "F002", deps=["F001"]),
    ]
    result = panel.pick_next_feature(feats)
    assert result.id == "F002"

def test_same_priority_file_order(panel):
    feats = [
        make_feat(panel, "F003", priority="P1"),
        make_feat(panel, "F001", priority="P1"),
        make_feat(panel, "F002", priority="P1"),
    ]
    result = panel.pick_next_feature(feats)
    assert result.id == "F003"  # first in list (roadmap order) wins

def test_all_blocked(panel):
    feats = [
        make_feat(panel, "F001", deps=["F002"]),
        make_feat(panel, "F002", deps=["F003"]),
        make_feat(panel, "F003", deps=["F001"]),
    ]
    # Should not raise — circular dep exits, but all blocked = None
    # Actually circular will sys.exit(1). We test that separately.
    # For all-blocked without circular: chain where none done
    feats2 = [
        make_feat(panel, "F001", deps=["F002"]),
        make_feat(panel, "F002", status="pending"),
    ]
    # F001 depends on F002 which is pending — both blocked? No, F002 has no deps.
    # Actually F002 has no deps, is pending, so it's unblocked.
    result = panel.pick_next_feature(feats2)
    assert result.id == "F002"

def test_circular_dependency_exits(panel):
    feats = [
        make_feat(panel, "F001", deps=["F002"]),
        make_feat(panel, "F002", deps=["F001"]),
    ]
    with pytest.raises(SystemExit):
        panel.pick_next_feature(feats)

def test_self_dependency_exits(panel):
    feats = [
        make_feat(panel, "F001", deps=["F001"]),
    ]
    with pytest.raises(SystemExit):
        panel.pick_next_feature(feats)

def test_nonexistent_dependency(panel):
    feats = [
        make_feat(panel, "F001", deps=["F999"]),
    ]
    result = panel.pick_next_feature(feats)
    # F001 blocked because F999 is never in done_ids
    assert result is None

def test_mixed_priority_with_deps(panel):
    feats = [
        make_feat(panel, "F001", priority="P0", status="done"),
        make_feat(panel, "F002", priority="P2", deps=["F001"]),
        make_feat(panel, "F003", priority="P1"),
    ]
    result = panel.pick_next_feature(feats)
    # F002 is unblocked (F001 done) but P2. F003 is P1, unblocked. F003 wins.
    assert result.id == "F003"
