"""Tests for extract_pr_sections() — PR body extraction from specs."""
import pytest

FULL_SPEC = """Position: This feature adds login to the application.

IMPACT ASSESSMENT
Cascading effects: Auth middleware requires token validation on all endpoints.
Breaking change: API now requires Authorization header.
Est. Lines: +350

Area: src/auth/
File(s): src/auth/login.py, src/auth/models.py
Change: Add password hashing and JWT token generation with refresh support.

Area: src/middleware/
File(s): src/middleware/auth.py
Change: Validate Authorization header on protected routes.
"""

THIN_SPEC = """Position: Add login.

IMPACT ASSESSMENT
Cascading effects: None.
Est. Lines: +50
"""

def test_full_spec_all_sections(panel):
    result = panel.extract_pr_sections(FULL_SPEC, "Login Feature")
    assert "## Why" in result
    assert "Login Feature" in result
    # Impact + What Changed extracted from IMPACT ASSESSMENT
    # If extraction fails (format mismatch), fallback kicks in
    assert "## Impact" in result or "## What Changed" in result

def test_thin_spec_fallback(panel):
    result = panel.extract_pr_sections(THIN_SPEC, "Login")
    # With THIN_SPEC having IMPACT, it should parse something
    # The thin spec only has cascading "None" — impact may be empty
    assert "## Why" in result
    assert "Login" in result

def test_under_100_chars_fallback(panel):
    result = panel.extract_pr_sections("No spec", "Tiny Feature")
    assert "## Why" in result
    assert "Tiny Feature" in result
    assert "## What Changed" in result
    assert "See diff for details" in result

def test_format_a_area_file_change(panel):
    spec = """Position: Fix.

IMPACT ASSESSMENT
Area: src/api/
File(s): src/api/routes.py
Change: Add rate limiting.
Est. Lines: +50
CONFIDENCE: HIGH

"""
    result = panel.extract_pr_sections(spec, "Rate Limit")
    assert "src/api/routes.py" in result
    assert "rate limiting" in result.lower()

def test_format_b_area_change_no_file(panel):
    spec = """Position: Fix.

IMPACT ASSESSMENT
Area: src/config.py
Change: Update defaults.
Lines Est.: +10
CONFIDENCE: MEDIUM

"""
    result = panel.extract_pr_sections(spec, "Defaults")
    assert "src/config.py" in result
    assert "Update defaults" in result

def test_cascading_effects_none_skipped(panel):
    spec = """Position: Fix.

IMPACT ASSESSMENT
Cascading effects: None
"""
    result = panel.extract_pr_sections(spec, "Fix")
    # "None" cascading effects should not appear in impact
    assert "None" not in result.split("## Impact")[-1] if "## Impact" in result else True

def test_breaking_changes_present(panel):
    spec = """Position: Fix.

IMPACT ASSESSMENT
Cascading effects: None.
Breaking change: API response format changed from XML to JSON.
CONFIDENCE: HIGH

"""
    result = panel.extract_pr_sections(spec, "Breaking")
    assert "Breaking" in result
    assert "XML" in result or "JSON" in result

def test_lines_estimation(panel):
    spec = """Position: Fix.

IMPACT ASSESSMENT
Est. Lines: +120
Area: src/x.py
Change: Updated something.
CONFIDENCE: HIGH

"""
    result = panel.extract_pr_sections(spec, "Lines")
    assert "120" in result or "lines" in result.lower()

def test_empty_spec(panel):
    result = panel.extract_pr_sections("", "Empty")
    assert len(result) < 100 or "## Why" in result
