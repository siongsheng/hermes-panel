"""Tests for extract_pr_sections() — PR body extraction from specs."""
import pytest

FULL_SPEC = """# Login Feature — Spec

**Status: In Progress** | **Confidence: High** | **Impact: HIGH**

## 1. Constitution Check

| Axiom | Verdict |
|--------|---------|
| Solves user pain? | YES |

## 2. Decision Table

SINGLE APPROACH: Standard JWT auth with refresh tokens.

## 3. Impact

Auth middleware requires token validation on all endpoints. API now requires Authorization header. Estimated +350 lines.

## 4. What Changed

- `src/auth/login.py` **(NEW)**: Add password hashing and JWT token generation with refresh support
- `src/auth/models.py` **(NEW)**: User and session models
- `src/middleware/auth.py` **(NEW)**: Validate Authorization header on protected routes

## 5. API/Interface Proposal

```
POST /api/auth/login
POST /api/auth/refresh
GET /api/auth/me
```

## 6. Security Considerations

Passwords hashed with bcrypt. JWTs signed with RS256. Refresh tokens rotated on use.

## 8. Task Breakdown

### Task 1: Create auth models
**Files:** src/auth/models.py
**Dependencies:** [none]
**Parallelizable:** no
**Description:** Define User and Session models with bcrypt password hashing.

### Task 2: Implement login endpoint
**Files:** src/auth/login.py
**Dependencies:** [Task 1]
**Parallelizable:** no
**Description:** POST /api/auth/login with JWT token generation.
"""

THIN_SPEC = """# Add Login — Spec

**Confidence: High** | **Impact: LOW**

## 3. Impact

Add login to the application. Estimated +50 lines.

## 4. What Changed

- `src/auth/login.py` **(NEW)**: Basic login endpoint
"""


def test_full_spec_all_sections(panel):
    result = panel.extract_pr_sections(FULL_SPEC, "Login Feature")
    assert "## Why" in result
    assert "Login Feature" in result
    assert "## Impact" in result
    assert "## What Changed" in result
    # Modern format: extracts Impact paragraph and What Changed bullets
    assert "Authorization header" in result
    assert "src/auth/login.py" in result


def test_thin_spec_fallback(panel):
    result = panel.extract_pr_sections(THIN_SPEC, "Login")
    assert "## Why" in result
    assert "Login" in result
    assert "## Impact" in result
    assert "## What Changed" in result


def test_under_100_chars_fallback(panel):
    result = panel.extract_pr_sections("No spec", "Tiny Feature")
    assert "## Why" in result
    assert "Tiny Feature" in result
    assert "## What Changed" in result
    assert "See diff for details" in result


def test_format_a_area_file_change(panel):
    """Modern format: Impact paragraph + What Changed bullet list are extracted."""
    spec = """# Rate Limit — Spec

**Confidence: HIGH** | **Impact: MEDIUM**

## 3. Impact

Add rate limiting to the API to prevent abuse.

## 4. What Changed

- `src/api/routes.py` **(MODIFIED)**: Add rate limiting middleware
"""
    result = panel.extract_pr_sections(spec, "Rate Limit")
    assert "src/api/routes.py" in result
    assert "rate limiting" in result.lower()


def test_format_b_area_change_no_file(panel):
    """Modern format: Impact paragraph is extracted even without file paths."""
    spec = """# Defaults — Spec

**Confidence: MEDIUM** | **Impact: LOW**

## 3. Impact

Update defaults in config.

## 4. What Changed

- `src/config.py` **(MODIFIED)**: Update defaults
"""
    result = panel.extract_pr_sections(spec, "Defaults")
    assert "src/config.py" in result
    assert "Update defaults" in result


def test_cascading_effects_none_skipped(panel):
    """Impact section with 'None' content is still included (it's what the spec says)."""
    spec = """# Fix — Spec

**Confidence: HIGH** | **Impact: LOW**

## 3. Impact

None. No user-facing changes.
"""
    result = panel.extract_pr_sections(spec, "Fix")
    # "None" impact is genuine spec content — it should appear in Impact
    assert "## Impact" in result


def test_breaking_changes_present(panel):
    """Modern format: breaking change info in Impact section is extracted."""
    spec = """# Breaking — Spec

**Confidence: HIGH** | **Impact: HIGH**

## 3. Impact

API response format changed from XML to JSON. All consumers must update.

## 4. What Changed

- `src/api/format.py` **(MODIFIED)**: Switch from XML to JSON serialization
"""
    result = panel.extract_pr_sections(spec, "Breaking")
    assert "Breaking" in result
    assert "XML" in result or "JSON" in result


def test_lines_estimation(panel):
    """Modern format: line count in Impact is preserved."""
    spec = """# Lines — Spec

**Confidence: HIGH** | **Impact: LOW**

## 3. Impact

Updated something. Estimated +120 lines.

## 4. What Changed

- `src/x.py` **(MODIFIED)**: Updated something
"""
    result = panel.extract_pr_sections(spec, "Lines")
    assert "120" in result or "lines" in result.lower()


def test_empty_spec(panel):
    result = panel.extract_pr_sections("", "Empty")
    assert len(result) < 100 or "## Why" in result


# ── PR Impact Alignment verification ──────────────────────────

def test_verify_pr_impact_alignment_missing_impact(panel):
    """Returns BLOCKER when PR body has no Impact section."""
    spec = "## 3. Impact\n\nFaster pipelines via modular architecture."
    pr_body = "## Why\n\nTest.\n## What Changed\n\n- stuff"
    result = panel._verify_pr_impact_alignment(pr_body, spec)
    assert result is not None
    assert "BLOCKER" in result

def test_verify_pr_impact_alignment_passes_when_aligned(panel):
    """Returns None when PR body Impact matches spec."""
    spec = "## 3. Impact\n\nFaster pipelines via modular architecture."
    pr_body = "## Impact\n\nFaster pipelines via modular architecture."
    result = panel._verify_pr_impact_alignment(pr_body, spec)
    assert result is None

def test_verify_pr_impact_alignment_detects_mismatch(panel):
    """Returns BLOCKER when PR body Impact text differs significantly from spec."""
    spec = "## 3. Impact\n\nFaster pipelines via modular architecture."
    pr_body = "## Impact\n\nPurely internal refactor."
    result = panel._verify_pr_impact_alignment(pr_body, spec)
    assert result is not None
    assert "BLOCKER" in result

def test_verify_pr_impact_alignment_no_spec_impact_skips(panel):
    """When spec has no Impact section, verification is skipped (returns None)."""
    spec = "## 4. What Changed\n\n- stuff"
    pr_body = "## Why\n\nTest."
    result = panel._verify_pr_impact_alignment(pr_body, spec)
    assert result is None

def test_verify_pr_impact_alignment_none_impact_matches(panel):
    """When spec says Impact is None, PR body saying None is aligned."""
    spec = "## 3. Impact\n\nNone. No user-facing changes."
    pr_body = "## Impact\n\nNo user-facing changes."
    result = panel._verify_pr_impact_alignment(pr_body, spec)
    assert result is None
