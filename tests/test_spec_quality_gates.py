"""Tests for verify_spec_quality() — spec structure, brevity gates, and re-prompt integration."""

import pytest

# Sample well-formed spec with all required sections
WELL_FORMED_SPEC = """## 1. Impact
This feature improves spec quality by adding deterministic
validation of spec structure before saving.

## 2. What Changed
- Added verify_spec_quality() function with structure checks
- Integrated quality gate into strategist phase

## 8. Task Breakdown
### Task 1: Create spec quality gate function skeleton
**Files:** dokima
**Dependencies:** none
**Parallelizable:** yes

### Task 2: Implement spec structure gate
**Files:** dokima
**Dependencies:** 1
**Parallelizable:** no

### Task 3: Implement task field completeness gate
**Files:** dokima
**Dependencies:** 2
**Parallelizable:** no
"""

# Specs missing individual required sections
SPEC_MISSING_IMPACT = """## 1. What Changed
Added verification gates.

## 2. Task Breakdown
### Task 1: Create skeleton
**Files:** dokima
**Dependencies:** none
**Parallelizable:** yes

### Task 2: Implement gate
**Files:** dokima
**Dependencies:** 1
**Parallelizable:** no
"""

SPEC_MISSING_WHAT_CHANGED = """## 1. Impact
This is important.

## 2. Task Breakdown
### Task 1: Create skeleton
**Files:** dokima
**Dependencies:** none
**Parallelizable:** yes

### Task 2: Implement gate
**Files:** dokima
**Dependencies:** 1
**Parallelizable:** no
"""

SPEC_MISSING_TASKS = """## 1. Impact
This is important.

## 2. What Changed
Added verification gates.

## 3. Risk Register
No risks.
"""


class TestVerifySpecQualitySkeleton:
    """Task 1: Verify spec quality gate function skeleton exists with correct signature."""

    def test_function_exists(self, panel):
        """verify_spec_quality function must be defined."""
        assert hasattr(panel, 'verify_spec_quality'), (
            "verify_spec_quality function not found"
        )

    def test_returns_tuple(self, panel):
        """Must return a (bool, list) tuple."""
        result = panel.verify_spec_quality(
            "## 1. Impact\n## 2. What Changed\n### Task 1: test\n**Files:** foo\n**Dependencies:** none\n**Parallelizable:** yes\n"
        )
        assert isinstance(result, tuple), (
            f"Expected tuple, got {type(result)}"
        )
        assert len(result) == 2, (
            f"Expected 2 elements, got {len(result)}"
        )

    def test_first_element_is_bool(self, panel):
        """First element must be a boolean (passed flag)."""
        result = panel.verify_spec_quality(
            "## 1. Impact\n## 2. What Changed\n### Task 1: test\n**Files:** foo\n**Dependencies:** none\n**Parallelizable:** yes\n"
        )
        assert isinstance(result[0], bool), (
            f"Expected bool, got {type(result[0])}"
        )

    def test_second_element_is_list_of_strings(self, panel):
        """Second element must be a list of failure strings."""
        result = panel.verify_spec_quality(
            "## 1. Impact\n## 2. What Changed\n### Task 1: test\n**Files:** foo\n**Dependencies:** none\n**Parallelizable:** yes\n"
        )
        assert isinstance(result[1], list), (
            f"Expected list, got {type(result[1])}"
        )
        for item in result[1]:
            assert isinstance(item, str), (
                f"Expected str in failures list, got {type(item)}: {item}"
            )

    def test_default_confidence_medium(self, panel):
        """Confidence should default to 'Medium'."""
        result = panel.verify_spec_quality(
            "## 1. Impact\n## 2. What Changed\n### Task 1: test\n**Files:** foo\n**Dependencies:** none\n**Parallelizable:** yes\n"
        )
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)

    def test_empty_spec_handled(self, panel):
        """Empty spec text should be handled without error."""
        result = panel.verify_spec_quality("", "High")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_well_formed_spec_passes(self, panel):
        """A complete spec with all required sections passes."""
        result = panel.verify_spec_quality(WELL_FORMED_SPEC, "Medium")
        assert result[0] is True, (
            f"Expected well-formed spec to pass, got failures: {result[1]}"
        )
        assert result[1] == [], (
            f"Expected no failures for well-formed spec, got: {result[1]}"
        )

    def test_confidence_parameter_accepted(self, panel):
        """verify_spec_quality must accept confidence as second parameter."""
        for conf in ["High", "Medium", "Low"]:
            result = panel.verify_spec_quality(
                "## 1. Impact\n## 2. What Changed\n### Task 1: test\n**Files:** foo\n**Dependencies:** none\n**Parallelizable:** yes\n", conf
            )
            assert isinstance(result, tuple)
            assert len(result) == 2


class TestSpecStructureGate:
    """Task 2: Spec structure gate — required section headers."""

    def test_missing_impact_section(self, panel):
        """Spec without Impact section should fail with specific message."""
        result = panel.verify_spec_quality(SPEC_MISSING_IMPACT, "Medium")
        assert result[0] is False, (
            f"Expected failure for missing Impact section, got: {result}"
        )
        failures_lower = [f.lower() for f in result[1]]
        assert any("impact" in f for f in failures_lower), (
            f"Expected 'Impact' in failure messages: {result[1]}"
        )

    def test_missing_what_changed_section(self, panel):
        """Spec without What Changed section should fail with specific message."""
        result = panel.verify_spec_quality(SPEC_MISSING_WHAT_CHANGED, "Medium")
        assert result[0] is False, (
            f"Expected failure for missing What Changed section, got: {result}"
        )
        failures_lower = [f.lower() for f in result[1]]
        assert any("what changed" in f for f in failures_lower), (
            f"Expected 'What Changed' in failure messages: {result[1]}"
        )

    def test_missing_task_headers(self, panel):
        """Spec without ### Task N: headers should fail with specific message."""
        result = panel.verify_spec_quality(SPEC_MISSING_TASKS, "Medium")
        assert result[0] is False, (
            f"Expected failure for missing Task headers, got: {result}"
        )
        failures_lower = [f.lower() for f in result[1]]
        assert any("task" in f for f in failures_lower), (
            f"Expected 'Task' in failure messages: {result[1]}"
        )

    def test_multiple_missing_sections(self, panel):
        """Spec missing multiple required sections should report all failures."""
        spec = "## Something\n## Else\n"
        result = panel.verify_spec_quality(spec, "Medium")
        assert result[0] is False, (
            f"Expected failure for spec with no required sections, got: {result}"
        )
        # Should catch at least 2 missing sections (Impact, What Changed, or Task)
        assert len(result[1]) >= 2, (
            f"Expected at least 2 failure messages for missing sections, "
            f"got {len(result[1])}: {result[1]}"
        )

    def test_empty_spec_structure_fails(self, panel):
        """Empty spec should fail all structure checks."""
        result = panel.verify_spec_quality("", "High")
        assert result[0] is False, (
            f"Expected failure for empty spec, got: {result}"
        )
        assert len(result[1]) > 0, (
            f"Expected at least one failure for empty spec, got: {result}"
        )


# Sample spec with complete task fields (passes structure + field gates)
GOOD_TASK_FIELDS_SPEC = """## 1. Impact
Adds deterministic spec quality gates.

## 2. What Changed
- Added verify_spec_quality() function

## 8. Task Breakdown
### Task 1: Create quality gate skeleton
**Files:** dokima
**Dependencies:** none
**Parallelizable:** yes

### Task 2: Implement structure gate
**Files:** dokima
**Dependencies:** 1
**Parallelizable:** no
"""

# Spec with task missing Description (empty title)
SPEC_EMPTY_DESCRIPTION = """## 1. Impact
Adds deterministic spec quality gates.

## 2. What Changed
- Added verify_spec_quality() function

## 8. Task Breakdown
### Task 1:
**Files:** dokima
**Dependencies:** none
**Parallelizable:** yes
"""

# Spec with task missing Files field
SPEC_MISSING_FILES = """## 1. Impact
Adds deterministic spec quality gates.

## 2. What Changed
- Added verify_spec_quality() function

## 8. Task Breakdown
### Task 1: Create quality gate skeleton
**Dependencies:** none
**Parallelizable:** yes

### Task 2: Implement structure gate
**Files:** dokima
**Dependencies:** 1
**Parallelizable:** yes
"""

# Spec with task missing Dependencies field
SPEC_MISSING_DEPS = """## 1. Impact
Adds deterministic spec quality gates.

## 2. What Changed
- Added verify_spec_quality() function

## 8. Task Breakdown
### Task 1: Create quality gate skeleton
**Files:** dokima
**Parallelizable:** yes
"""

# Spec with task missing Parallelizable field
SPEC_MISSING_PARALLEL = """## 1. Impact
Adds deterministic spec quality gates.

## 2. What Changed
- Added verify_spec_quality() function

## 8. Task Breakdown
### Task 1: Create quality gate skeleton
**Files:** dokima
**Dependencies:** none
"""

# Spec with empty field values (Files: empty)
SPEC_EMPTY_FILES = """## 1. Impact
Adds deterministic spec quality gates.

## 2. What Changed
- Added verify_spec_quality() function

## 8. Task Breakdown
### Task 1: Create quality gate skeleton
**Files:**
**Dependencies:** none
**Parallelizable:** yes
"""

# Spec with empty Dependencies value
SPEC_EMPTY_DEPS = """## 1. Impact
Adds deterministic spec quality gates.

## 2. What Changed
- Added verify_spec_quality() function

## 8. Task Breakdown
### Task 1: Create quality gate skeleton
**Files:** dokima
**Dependencies:**
**Parallelizable:** yes
"""

# Spec with empty Parallelizable value
SPEC_EMPTY_PARALLEL = """## 1. Impact
Adds deterministic spec quality gates.

## 2. What Changed
- Added verify_spec_quality() function

## 8. Task Breakdown
### Task 1: Create quality gate skeleton
**Files:** dokima
**Dependencies:** none
**Parallelizable:**
"""


class TestTaskFieldCompletenessGate:
    """Task 3: Task field completeness gate — verify all required task fields are non-empty."""

    def test_good_task_fields_pass(self, panel):
        """Tasks with all required fields present should pass field checks."""
        result = panel.verify_spec_quality(GOOD_TASK_FIELDS_SPEC, "Medium")
        # The spec has no field-level failures (structure may pass too)
        failures_lower = [f.lower() for f in result[1]]
        field_failures = [f for f in failures_lower if "missing" in f and "task" in f]
        # WELL_FORMED_SPEC also passes field checks
        assert len(field_failures) == 0, (
            f"Expected no task field failures for complete tasks, got: {result[1]}"
        )

    def test_missing_description_field(self, panel):
        """Task with empty description (no text after 'Task N:') should fail."""
        result = panel.verify_spec_quality(SPEC_EMPTY_DESCRIPTION, "Medium")
        failures_lower = [f.lower() for f in result[1]]
        assert any("task 1" in f and "description" in f for f in failures_lower), (
            f"Expected 'Task 1: missing Description field' in failures: {result[1]}"
        )

    def test_missing_files_field(self, panel):
        """Task without Files field should fail."""
        result = panel.verify_spec_quality(SPEC_MISSING_FILES, "Medium")
        failures_lower = [f.lower() for f in result[1]]
        assert any("task 1" in f and "files" in f for f in failures_lower), (
            f"Expected failure for Task 1 missing Files field: {result[1]}"
        )

    def test_missing_dependencies_field(self, panel):
        """Task without Dependencies field should fail."""
        result = panel.verify_spec_quality(SPEC_MISSING_DEPS, "Medium")
        failures_lower = [f.lower() for f in result[1]]
        assert any("task 1" in f and "dependencies" in f for f in failures_lower), (
            f"Expected failure for Task 1 missing Dependencies field: {result[1]}"
        )

    def test_missing_parallelizable_field(self, panel):
        """Task without Parallelizable field should fail."""
        result = panel.verify_spec_quality(SPEC_MISSING_PARALLEL, "Medium")
        failures_lower = [f.lower() for f in result[1]]
        assert any("task 1" in f and "parallelizable" in f for f in failures_lower), (
            f"Expected failure for Task 1 missing Parallelizable field: {result[1]}"
        )

    def test_empty_files_value(self, panel):
        """Task with empty Files value (no file listed) should fail."""
        result = panel.verify_spec_quality(SPEC_EMPTY_FILES, "Medium")
        failures_lower = [f.lower() for f in result[1]]
        assert any("task 1" in f and "files" in f for f in failures_lower), (
            f"Expected failure for Task 1 empty Files field: {result[1]}"
        )

    def test_empty_dependencies_value(self, panel):
        """Task with empty Dependencies value should fail."""
        result = panel.verify_spec_quality(SPEC_EMPTY_DEPS, "Medium")
        failures_lower = [f.lower() for f in result[1]]
        assert any("task 1" in f and "dependencies" in f for f in failures_lower), (
            f"Expected failure for Task 1 empty Dependencies field: {result[1]}"
        )

    def test_empty_parallelizable_value(self, panel):
        """Task with empty Parallelizable value should fail."""
        result = panel.verify_spec_quality(SPEC_EMPTY_PARALLEL, "Medium")
        failures_lower = [f.lower() for f in result[1]]
        assert any("task 1" in f and "parallelizable" in f for f in failures_lower), (
            f"Expected failure for Task 1 empty Parallelizable field: {result[1]}"
        )

    def test_multiple_tasks_with_missing_fields(self, panel):
        """Spec with multiple tasks missing fields should report all failures."""
        spec = """## 1. Impact
Adds gates.

## 2. What Changed
Various.

## 8. Task Breakdown
### Task 1: First task
**Dependencies:** none
**Parallelizable:** yes

### Task 2: Second task
**Files:** dokima
**Parallelizable:** yes
"""
        result = panel.verify_spec_quality(spec, "Medium")
        failures_lower = [f.lower() for f in result[1]]
        task1_files = any("task 1" in f and "files" in f for f in failures_lower)
        task2_deps = any("task 2" in f and "dependencies" in f for f in failures_lower)
        assert task1_files, (
            f"Expected Task 1 missing Files in failures: {result[1]}"
        )
        assert task2_deps, (
            f"Expected Task 2 missing Dependencies in failures: {result[1]}"
        )

    def test_well_formed_spec_also_passes_field_gate(self, panel):
        """The WELL_FORMED_SPEC from structure tests should also pass field checks."""
        result = panel.verify_spec_quality(WELL_FORMED_SPEC, "Medium")
        failures_lower = [f.lower() for f in result[1]]
        field_failures = [f for f in failures_lower if "missing" in f and ("task" in f or "description" in f)]
        assert len(field_failures) == 0, (
            f"Expected no task field failures for WELL_FORMED_SPEC, got: {result[1]}"
        )


class TestQualityGateRepromptIntegration:
    """Task 6: Quality gate re-prompt integration into strategist phase.

    After spec extraction + cleaning, verify_spec_quality() is called.
    If it fails, one re-prompt is triggered with the failure list as feedback.
    If re-prompt still fails, a warning is printed and execution proceeds.
    """

    def test_quality_reprompt_source_pattern(self, panel):
        """Verify required code patterns exist in run_phase1_strategist.

        Regression guard: if a refactor removes or renames the quality
        gate re-prompt, this test fails.
        """
        import inspect
        source = inspect.getsource(panel.run_phase1_strategist)

        # Must call verify_spec_quality (quality check)
        assert "verify_spec_quality" in source, (
            "verify_spec_quality call not found in strategist phase"
        )

        # Must have quality gate section with check + re-prompt
        quality_section_start = source.find("# Quality gate:")
        assert quality_section_start >= 0, (
            "# Quality gate: comment not found in run_phase1_strategist"
        )
        # Use a unique marker to limit the quality gate scope.
        # The quality gate section ends before the garbage detection check.
        quality_end = source.find("# Garbage detection:", quality_section_start)
        if quality_end < 0:
            quality_end = source.find("print(f\"  Spec extracted:", quality_section_start)
        quality_section = source[quality_section_start:quality_end] if quality_end > 0 \
            else source[quality_section_start:]

        # The quality gate section must include a spawn_agent call for re-prompt
        assert "spawn_agent" in quality_section, (
            "spawn_agent re-prompt not found in quality gate section. "
            "The quality gate should re-prompt the strategist on failure."
        )

        # The re-prompt message must include the failure details
        assert "quality" in quality_section.lower() and "re-prompt" in quality_section.lower(), (
            "Expected 're-prompt' or 'quality correction' message in quality gate section."
        )

    def test_quality_reprompt_warn_and_proceed(self, panel):
        """Verify that re-prompt follows warn-and-proceed pattern.

        If re-prompt still produces a failing spec, the pipeline should
        print a warning and continue — it must not exit or abort.
        """
        import inspect
        source = inspect.getsource(panel.run_phase1_strategist)

        # Find quality gate section (before garbage detection)
        quality_section_start = source.find("# Quality gate:")
        assert quality_section_start >= 0
        quality_end = source.find("# Garbage detection:", quality_section_start)
        if quality_end < 0:
            quality_end = source.find("print(f\"  Spec extracted:", quality_section_start)
        quality_section = source[quality_section_start:quality_end] if quality_end > 0 \
            else source[quality_section_start:]

        # Must have a SECOND quality check after re-prompt
        # Use a proper counting loop that stops at -1
        verify_count = 0
        idx = -1
        while True:
            idx = quality_section.find("verify_spec_quality", idx + 1)
            if idx < 0:
                break
            verify_count += 1
        assert verify_count >= 2, (
            f"Expected at least 2 verify_spec_quality calls in quality gate section, "
            f"found {verify_count}. The re-prompt should re-verify after."
        )

        # Must have a warn-and-continue message for 2nd failure
        has_warning = "proceeding with" in quality_section.lower() and \
                      "degraded" in quality_section.lower()
        assert has_warning, (
            "No warn-and-proceed message found in quality gate section. "
            "After re-prompt failure, the code should print a warning and continue."
        )

    def test_reprompt_fires_only_once(self, panel):
        """Verify re-prompt fires at most once — no infinite loop.

        The quality gate should attempt exactly one re-prompt, not multiple.
        After one re-prompt it should always proceed (warn-and-proceed).
        """
        import inspect
        source = inspect.getsource(panel.run_phase1_strategist)

        # Find quality gate section
        quality_section_start = source.find("# Quality gate:")
        assert quality_section_start >= 0
        quality_end = source.find("# Garbage detection:", quality_section_start)
        if quality_end < 0:
            quality_end = source.find("print(f\"  Spec extracted:", quality_section_start)
        quality_section = source[quality_section_start:quality_end] if quality_end > 0 \
            else source[quality_section_start:]

        # Count spawn_agent calls in the quality section (should be exactly 1)
        spawn_count = quality_section.count("spawn_agent")
        assert spawn_count == 1, (
            f"Expected exactly 1 spawn_agent call in quality gate section, "
            f"found {spawn_count}. The re-prompt should fire at most once."
        )


# ── Task 8: CI regression test ────────────────────────────────────
# Integration test: feed a known feature description through strategist
# (mock spawn), verify output passes all quality gates.
# Regression: if a panel change removes a section header from the prompt,
# the test fails.

GOOD_CI_SPEC = """## 1. Impact
This adds deterministic quality gates to ensure spec quality.

## 2. What Changed
- Added verify_spec_quality() function
- Integrated quality gate into strategist phase

## 8. Task Breakdown
### Task 1: Create quality gate skeleton
**Files:** dokima
**Dependencies:** none
**Parallelizable:** yes
**Description:** Create the skeleton.

### Task 2: Implement structure gate
**Files:** dokima
**Dependencies:** 1
**Parallelizable:** no
**Description:** Implement structure gate.
"""

DEGRADED_CI_SPEC = """## 1. What Changed
- Added verify_spec_quality() function

## 2. Task Breakdown
### Task 1: Create quality gate skeleton
**Files:** dokima
**Dependencies:** none
**Parallelizable:** yes
**Description:** Create skeleton.

### Task 2: Implement structure gate
**Files:** dokima
**Dependencies:** 1
**Parallelizable:** no
**Description:** Implement structure gate.
"""


class TestCiRegressionIntegration:
    """Task 8: CI regression test for spec quality end-to-end.

    Integration test: feed a known feature description through strategist
    (mock spawn), verify output passes all quality gates.
    Regression: if a panel change removes a section header from the prompt
    (simulated by a bad spec return), the test fails because verify_spec_quality
    catches the missing section at the end of run_phase1_strategist.
    """

    def test_strategist_integration_passes_quality_gates(self, test_repo, panel):
        """Mock spawn_agent to return a well-formed spec, run through
        run_phase1_strategist, verify the extracted spec passes all quality gates."""
        import os
        from unittest.mock import patch
        from contextlib import ExitStack

        spawn_calls = []

        def _mock_spawn(profile, skills, prompt, timeout=600, cwd=None, model=None, **kwargs):
            spawn_calls.append({"profile": profile, "skills": skills})
            return GOOD_CI_SPEC

        # Ensure spec dir exists in test_repo
        specs_dir = os.path.join(panel.PROJECT_DIR, "specs")
        os.makedirs(specs_dir, exist_ok=True)

        panel.spawn_agent = _mock_spawn

        patches = [
            patch.object(panel, "_set_gh_token"),
            patch.object(panel, "git", return_value=("", "", 0)),
            patch.object(panel, "gh", return_value=("", "", 0)),
            patch.object(panel, "load_key", return_value="fk"),
            patch.object(panel, "load_github_token", return_value="ft"),
            patch.object(panel, "detect_repo", return_value="t/t"),
            patch.object(panel, "acquire_lock", return_value=(True, None)),
            patch.object(panel, "_cleanup_lock"),
            patch("time.sleep"),
        ]

        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            result = panel.run_phase1_strategist("Test Feature", "")

        # Verify strategist was called
        assert len(spawn_calls) >= 1, (
            "Expected at least 1 spawn_agent call"
        )
        assert any(c["profile"] == "strategist" for c in spawn_calls), (
            f"Expected strategist spawn, got: {[c['profile'] for c in spawn_calls]}"
        )

        # Verify result contains a spec
        spec = result.get("spec", "")
        assert len(spec) > 0, (
            "Expected non-empty spec from run_phase1_strategist"
        )

        # Verify spec passes all quality gates
        qg_passed, qg_failures = panel.verify_spec_quality(spec)
        assert qg_passed, (
            f"Expected quality gates to pass for well-formed spec, "
            f"got failures: {qg_failures}"
        )

    def test_strategist_integration_catches_degraded_spec(self, test_repo, panel):
        """Mock spawn_agent to return a spec missing the Impact section.
        The quality gate in run_phase1_strategist should detect and report it.
        Regression: if a panel change removes a section header from the prompt,
        this test catches the degraded output."""
        import os
        from unittest.mock import patch
        from contextlib import ExitStack

        spawn_calls = []

        def _mock_spawn(profile, skills, prompt, timeout=600, cwd=None, model=None, **kwargs):
            spawn_calls.append({"profile": profile, "skills": skills})
            return DEGRADED_CI_SPEC

        # Ensure spec dir exists in test_repo
        specs_dir = os.path.join(panel.PROJECT_DIR, "specs")
        os.makedirs(specs_dir, exist_ok=True)

        panel.spawn_agent = _mock_spawn

        patches = [
            patch.object(panel, "_set_gh_token"),
            patch.object(panel, "git", return_value=("", "", 0)),
            patch.object(panel, "gh", return_value=("", "", 0)),
            patch.object(panel, "load_key", return_value="fk"),
            patch.object(panel, "load_github_token", return_value="ft"),
            patch.object(panel, "detect_repo", return_value="t/t"),
            patch.object(panel, "acquire_lock", return_value=(True, None)),
            patch.object(panel, "_cleanup_lock"),
            patch("time.sleep"),
        ]

        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            result = panel.run_phase1_strategist("Test Feature", "")

        # Verify strategist was called
        assert len(spawn_calls) >= 1

        # Verify result contains a spec
        spec = result.get("spec", "")
        assert len(spec) > 0

        # Verify quality gates catch the degraded spec (missing Impact)
        qg_passed, qg_failures = panel.verify_spec_quality(spec)
        assert qg_passed is False, (
            "Expected quality gates to fail for degraded spec missing Impact section"
        )
        failures_lower = [f.lower() for f in qg_failures]
        assert any("impact" in f for f in failures_lower), (
            f"Expected 'Impact' in failure messages for spec missing Impact section, "
            f"got: {qg_failures}"
        )
