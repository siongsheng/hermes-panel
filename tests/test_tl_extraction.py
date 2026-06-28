"""Tests for _extract_tl_blockers — filters TL monologue from structured findings."""

import pytest
from conftest import _load_panel as _load


@pytest.fixture(scope="module")
def panel():
    return _load()


# ── Sample TL outputs for testing ──

# Clean output: follows adversarial-review-lite format
CLEAN_TL = """### BLOCKERS (2 — must fix before merge)

**1. Fallback failure discards original error**
dokima line 276: Unconditionally replaces output.

**2. Missing stderr collection**
dokima line 264: Fallback path never reads stderr.

### SHOULD FIX (1)

- conventions.md line 65 documents wrong behavior

VERDICT: BLOCKED
RISK: HIGH"""

# Noisy output: TL monologue with BLOCKERs buried in prose
NOISY_TL = """Now let me read the spawn_agent function in full context to verify the previous reviewer's BLOCKER findings.

Now let me check what the TL review fix commit actually added.

    Severity: BLOCKER
    Finding: Fallback failure doesn't match spec.

    Severity: BLOCKER
    Finding: Missing stderr collection in fallback path.

However, 3 BLOCKERs remain from the previous review, unfixed.

### BLOCKERS (3 — same as previous review)

**1. Fallback discards original error**
dokima:276: result = "".join(fb_output)

**2. Missing stderr collection**
dokima:264: No stderr read in fallback

**3. Missing double-failure test**
tests: No coverage for fallback-fails-too path

VERDICT: BLOCKED
RISK: HIGH"""

# Output with multiple verdicts (early false APPROVED, then BLOCKED)
MULTI_VERDICT_TL = """VERDICT: APPROVED
Risk: LOW

Wait, let me look deeper.

Now let me check the spawn_agent error handling.

Severity: BLOCKER
Finding: Fallback discards error output.

### BLOCKERS (3)

**1. Fallback discards error output**
dokima:276

VERDICT: BLOCKED
Risk: HIGH
RELEASE: NO"""

# No blockers — approved
APPROVED_TL = """### Spec Compliance
All tasks completed.

### Code Quality
Clean implementation.

VERDICT: APPROVED
RISK: LOW
RELEASE: YES (patch)"""


class TestExtractTlBlockers:
    """_extract_tl_blockers should filter noise and return structured findings."""

    def test_clean_output_extracts_blockers(self, panel):
        blockers = panel._extract_tl_blockers(CLEAN_TL)
        assert len(blockers) == 2
        assert "Fallback failure discards" in blockers[0]
        assert "Missing stderr" in blockers[1]

    def test_noisy_output_filters_monologue(self, panel):
        """Lines like 'Now let me...' and 'However, N BLOCKERs remain' must be filtered."""
        blockers = panel._extract_tl_blockers(NOISY_TL)
        assert len(blockers) >= 2  # at least the structured ones
        for b in blockers:
            assert not b.startswith("Now let me")
            assert not b.startswith("However,")
            assert "previous reviewer" not in b.lower()

    def test_noisy_output_still_gets_structured_blockers(self, panel):
        blockers = panel._extract_tl_blockers(NOISY_TL)
        structured = [b for b in blockers if b.startswith("**")]
        assert len(structured) >= 2

    def test_multiple_verdicts_extracts_last_verdict(self, panel):
        """The function should still work — verdict extraction is separate but
        we verify the blockers aren't polluted by the false APPROVED section."""
        blockers = panel._extract_tl_blockers(MULTI_VERDICT_TL)
        assert len(blockers) >= 1
        assert "APPROVED" not in "\n".join(blockers)

    def test_approved_output_returns_empty(self, panel):
        blockers = panel._extract_tl_blockers(APPROVED_TL)
        assert blockers == []

    def test_should_fix_not_included_in_blockers(self, panel):
        """SHOULD FIX items are extracted separately — not in blockers list."""
        blockers = panel._extract_tl_blockers(CLEAN_TL)
        should_fix_in_blockers = [b for b in blockers if "SHOULD FIX" in b.upper()]
        assert len(should_fix_in_blockers) == 0

    def test_empty_output_returns_empty(self, panel):
        assert panel._extract_tl_blockers("") == []
        assert panel._extract_tl_blockers("   \n  ") == []


class TestExtractTlVerdict:
    """VERDICT extraction: should always use the LAST verdict line."""

    def test_single_verdict_approved(self, panel):
        v = panel._extract_tl_verdict(APPROVED_TL)
        assert v == "APPROVED"

    def test_multiple_verdicts_picks_last(self, panel):
        v = panel._extract_tl_verdict(MULTI_VERDICT_TL)
        assert v == "BLOCKED"

    def test_clean_blocked(self, panel):
        v = panel._extract_tl_verdict(CLEAN_TL)
        assert v == "BLOCKED"

    def test_timed_out_with_no_verdict(self, panel):
        v = panel._extract_tl_verdict("[TIMEOUT: 600s]")
        assert v == "TIMED_OUT"

    def test_unknown_for_missing_verdict(self, panel):
        v = panel._extract_tl_verdict("Just some text\nNo verdict here.")
        assert v == "UNKNOWN"
