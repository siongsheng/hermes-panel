# F003: Edge Case & Robustness Tests

Here is the complete corrected F003 spec:
    
    
    F003: Edge Case & Robustness Tests
    
    Confidence: High | Impact: LOW
    
    1. Constitution Check
    
    Axiom: Solves user's own pain?
    Verdict: YES — Shaun hit DAG re-prompt bugs, interview false positives, and
      coder timeout silently eating output. F003 proves the pipeline survives
      every known failure mode.
    ────────────────────────────────────────
    Axiom: Weekend-buildable?
    Verdict: YES — ~250 lines of test code in one file. No production code changes.
    ────────────────────────────────────────
    Axiom: Evidence people will pay?
    Verdict: N/A — internal pipeline robustness, not a SaaS feature
    ────────────────────────────────────────
    Axiom: Tech stack boring and proven?
    Verdict: YES — pure pytest with mock patches. No new dependencies.
    ────────────────────────────────────────
    Axiom: Avoids AI hype categories?
    Verdict: YES — deterministic tests, not AI
    
    2. Decision Table
    
    SINGLE APPROACH: Fill the remaining robustness gaps with targeted integration
    tests in a single file (tests/test_f003_robustness.py) using the same
    _patch_and_run pattern from test_main_integration.py. Each test targets one
    failure mode in the user story. No alternative approaches needed — the existing
    372 tests already cover most edge cases via scattered unit/mock tests. F003
    consolidates and fills gaps.
    
    3. Impact
    
    Developers get a single test file that proves every pipeline failure mode
    handles gracefully — no silent exits, no stale locks, no orphaned worktrees.
    Pipeline operators can verify robustness with one command:
    pytest tests/test_f003_robustness.py -v.
    
    4. What Changed
    
    - tests/test_f003_robustness.py (NEW): ~250 lines. Targeted integration tests
      for the 9 failure modes from the roadmap user story, filling gaps the
      existing 372 tests don't cover.
    - No production code changes. No dokima edits. No conftest changes.
    
    5. API/Interface Proposal
    
    N/A — test-only change. No new functions, no CLI flags, no API surface.
    
    6. Security Considerations
    
    N/A — no attack surface change. Test file only.
    
    7. Documentation Impact
    
    README: No change needed. specs/roadmap.md: Already has F003 entry.
    
    8. Feature Breakdown
    
    All existing edge case tests scattered across 37 test files remain intact.
    F003 adds one new test file with targeted gap-filling tests.
    
    ── Covered by existing tests (do not duplicate) ──
    Failure Mode: Interview mode (exit 2)
    Existing Coverage: test_final_coverage.py TestInterviewGate,
      test_root_cause_regressions.py Bug 7
    ────────────────────────────────────────
    Failure Mode: Zero ### Task headers (DAG re-prompt)
    Existing Coverage: test_root_cause_regressions.py Bug 3,
      test_dag_format.py
    ────────────────────────────────────────
    Failure Mode: Coder timeout (partial results)
    Existing Coverage: test_final_coverage.py TestCoderTimeout,
      test_edge_cases.py TestCallAgent
    ────────────────────────────────────────
    Failure Mode: TL BLOCKED verdict (auto-fix)
    Existing Coverage: test_edge_cases.py TestTechLeadPaths
    ────────────────────────────────────────
    Failure Mode: Special characters in slugify
    Existing Coverage: test_slugify.py (7 tests)
    ────────────────────────────────────────
    Failure Mode: Lock acquisition
    Existing Coverage: test_acquire_lock.py, test_lock_paths.py
    ────────────────────────────────────────
    Failure Mode: Stop file halts pipeline
    Existing Coverage: test_main_integration.py
      test_stop_file_exits_before_pipeline
    ────────────────────────────────────────
    Failure Mode: Signal handler cleanup
    Existing Coverage: test_unit_helpers.py TestSignalHandler
    
    ── Gaps F003 fills ──
    | Gap                                      | Status     |
    |------------------------------------------|------------|
    | RED-only commits → vet catch             | NOT tested |
    | nm script timeout/failure                | NOT tested |
    | Feature with special chars full pipeline | NOT tested |
    | Vet verification retry exhaustion        | NOT tested |
    | Coder empty output (no RED, no GREEN)    | NOT tested |
    | Worktree cleanup after crashed run       | NOT tested |
    
    Task 1: RED-only commits — vet phase detects missing GREEN
    Files: tests/test_f003_robustness.py
    Dependencies: none
    Parallelizable: yes
    Description: Test run_phase3_vet() when coder output contains "RED: a1b2c3" but no "GREEN:" — verify coder_failed=True and verdict="VET_FAILED". Mock _safe_run to return pass for TEST_CMD/BUILD_CMD so only the RED detection triggers failure.
    
    Task 2: Coder empty output — no RED and no GREEN
    Files: tests/test_f003_robustness.py
    Dependencies: none
    Parallelizable: yes
    Description: Test run_phase3_vet() when coder output is empty or contains neither RED nor GREEN — verify coder_failed=True. This catches the case where the coder agent crashes silently producing zero output.
    
    Task 3: nm script timeout — pipeline recovers gracefully
    Files: tests/test_f003_robustness.py
    Dependencies: none
    Parallelizable: yes
    Description: Test run_phase4_nm() when _safe_run returns TIMEOUT (returncode 124). Verify the function returns nm_ok=False (or equivalent failure signal) without crashing. Mock _safe_run to return a CompletedProcess with stdout="[TIMEOUT]" and returncode=124.
    
    Task 4: nm script returns non-zero exit — pipeline proceeds with fallback
    Files: tests/test_f003_robustness.py
    Dependencies: none
    Parallelizable: yes
    Description: Test run_phase4_nm() when nm exits with non-zero code and empty stdout. Verify the function returns a dict with pr_url preserved and risk falling back to impact level. Mock _safe_run returncode=1, stdout="".
    
    Task 5: Vet verification retry exhaustion — BLOCKED after max retries
    Files: tests/test_f003_robustness.py
    Dependencies: none
    Parallelizable: yes
    Description: Test run_phase3_vet() with _safe_run always returning failures (test and build both fail across all MAX_VERIFY_RETRIES attempts). Verify the function calls halt_and_revert and returns verdict="VET_FAILED". Mock spawn_agent to simulate coder fix attempts but _safe_run to keep failing.
    
    Task 6: Feature description with special characters — full pipeline survives
    Files: tests/test_f003_robustness.py
    Dependencies: none
    Parallelizable: yes
    Description: Test that slugify("Fix: OAuth2 — login (urgent!!) 🚀") produces a safe branch name, and the pipeline creates a branch with that slug without crashing. Use the _patch_and_run pattern with a strategist mock returning a spec for a feature with emoji/punctuation in the title.
    
    Task 7: Stale worktree cleanup on crashed run recovery
    Files: tests/test_f003_robustness.py
    Dependencies: none
    Parallelizable: yes
    Description: Test WorktreeManager.create() when a stale worktree directory exists from a prior crashed run. Verify it detects the stale worktree (via git worktree list --porcelain) and removes it before creating a fresh one. Mock subprocess.run to simulate a stale worktree listing.
    
    Task 8: Concurrent pipeline lock — second run exits cleanly
    Files: tests/test_f003_robustness.py
    Dependencies: none
    Parallelizable: yes
    Description: Test acquire_lock() when lock is already held by a live process. Verify it calls sys.exit(1) with a clear error message. Mock _check_pid to return True (process alive) and _verify_pid_owner to return True. Assert SystemExit is raised with code 1 and error message contains "Panel already running".
    
    9. Test Plan
    
    Task 1 — RED-only commits
    - Happy path: RED present, GREEN present → coder_failed=False
    - Edge case: RED present, GREEN absent → coder_failed=True, verdict="VET_FAILED"
    - Edge case: RED present in a URL or filename, no actual commit → still coder_failed=True
    - Failure mode: None (pure string detection, no network/IO)
    
    Task 2 — Empty coder output
    - Happy path: Non-empty output with RED+GREEN → coder_failed=False
    - Edge case: Empty string → coder_failed=True
    - Edge case: Whitespace only → coder_failed=True
    - Edge case: Output with no RED/GREEN patterns at all → coder_failed=True
    
    Task 3 — nm script timeout
    - Happy path: nm completes with returncode 0 → nm_ok=True, risk extracted
    - Edge case: returncode 124, stdout="[TIMEOUT]" → function returns without crashing
    - Edge case: returncode 124, empty stdout → risk falls back to impact
    - Failure mode: What if nm times out but pr_url was passed in? Verify pr_url preserved.
    
    Task 4 — nm script non-zero exit
    - Happy path: nm returncode 0, stdout has PR URL → extracted
    - Edge case: returncode 1, stdout empty → pr_url preserved from input, risk=impact
    - Edge case: returncode 1, partial output → risk extraction still attempted
    - Failure mode: What if gh pr list also fails? Verify fallback to None.
    
    Task 5 — Vet retry exhaustion
    - Happy path: First vet passes → verdict set from TL output
    - Edge case: 1 retry, passes on 2nd → proceeds to PR creation
    - Edge case: MAX_VERIFY_RETRIES exhausted → halt_and_revert called, verdict="VET_FAILED"
    - Edge case: Test passes but build fails (or vice versa) → retry
    - Failure mode: spawn_agent for coder fix itself times out → still counts as a retry attempt
    - Contract invariant: halt_and_revert must be called exactly once when retries exhausted
    
    Task 6 — Special characters end-to-end
    - Happy path: ASCII-only feature title → slugify produces clean branch name
    - Edge case: "Fix: OAuth2 — login (urgent!!) 🚀" → slugify produces valid git branch name
    - Edge case: All special characters "!@#$%^&*()" → slugify returns empty string (pipeline handles)
    - Edge case: 100+ char title with emoji → truncated with hash suffix
    - Failure mode: git branch create with special chars in name → should fail gracefully
    - Contract invariant: The branch name passed to git must contain only [a-z0-9-]
    
    Task 7 — Stale worktree cleanup
    - Happy path: No stale worktrees → create fresh
    - Edge case: Stale worktree exists from PID that is dead → removed before create
    - Edge case: Stale worktree exists but git worktree remove fails → rmtree fallback
    - Edge case: Path escapes worktrees_dir (traversal attempt) → ValueError raised
    - Failure mode: git worktree list times out → exception caught, proceeds to create
    - Contract invariant: After create() returns, worktree directory exists and is writable
    
    Task 8 — Concurrent lock
    - Happy path: No lock held → acquire succeeds
    - Edge case: Lock held by live process → SystemExit(1) with message
    - Edge case: Lock held by dead process → stale lock removed, retry succeeds
    - Edge case: Lock held by non-dokima process (PID alive but comm != dokima/python) → stale lock removed
    - Failure mode: lock file exists but unreadable → sys.exit(1)
    - Contract invariant: Only one dokima instance holds the lock at any time
    
    10. Panel Split
    
    All 8 tasks share no files with each other (all write to the same NEW file
    test_f003_robustness.py, but each writes a different test function within it).
    
    Parallelization strategy: Run all 8 tasks in a single coder wave. Each task
    is an independent test function — no dependencies between tests. A single
    coder can implement all 8 in one batch (~250 LOC total) with zero conflicts.
    
    If parallelized: split across 2 coders (Tasks 1-4, Tasks 5-8) to different
    sections of the same file, with a final merge step.
    
    11. Build & Deploy
    
    - Deploy: N/A — test file only. Committed to dokima repo on feat/f003 branch.
    - CI: python3 -m pytest tests/test_f003_robustness.py -v added to vet phase.
    - Env vars: PANEL_MAX_RETRIES=0, PANEL_SKIP_HUMAN_GATE=1 (same as existing tests).
    - No new dependencies. No new Python imports beyond existing test imports.
    
    12. Risk Register
    
    #: 1
    Risk: Test depends on internal function signature that changes
    Severity: LOW
    Mitigation: Tests call public run_phase* functions only
    Trigger: Function signature changes in future refactor
    ────────────────────────────────────────
    #: 2
    Risk: nm timeout test flaky (nm script hangs differently in CI)
    Severity: LOW
    Mitigation: Mock _safe_run — no real nm execution
    Trigger: CI runner has different timeout behavior
    ────────────────────────────────────────
    #: 3
    Risk: Special chars test breaks if slugify behavior changes
    Severity: LOW
    Mitigation: Test documents expected behavior; slugify has its own test
      suite
    Trigger: Slugify algorithm change
    ────────────────────────────────────────
    #: 4
    Risk: Stale worktree test hard to mock (subprocess deep mocking)
    Severity: MEDIUM
    Mitigation: Use targeted subprocess.run patches per test
    Trigger: git worktree CLI changes output format
    ────────────────────────────────────────
    #: 5
    Risk: Concurrent lock test fragile (relies on PID state)
    Severity: LOW
    Mitigation: Mock _check_pid and _verify_pid_owner
    Trigger: Test PID collision on CI
    
    13. Anti-Creep
    
    Features explicitly NOT in scope:
    - Do NOT modify dokima (production code). Tests only.
    - Do NOT add new CLI flags or env vars.
    - Do NOT refactor run_phase3_vet() or run_phase4_nm() — test what exists.
    - Do NOT add integration tests that require real Hermes sessions.
    - Do NOT modify conftest.py or existing fixtures.
    - Do NOT add tests for failure modes already covered by existing 372 tests.
    - Do NOT add a test for "nm model provider down" at the Hermes level — that's
      Hermes Agent's responsibility, not dokima's. Test dokima's reaction to nm
      returning failure, not how nm handles provider failures internally.
    
    14. Sign-Off Checklist
    
    - [ ] No production code changes (dokima untouched)
    - [ ] All 8 tasks produce test functions in test_f003_robustness.py
    - [ ] Each task tests exactly one failure mode from the user story
    - [ ] No duplication of existing test coverage
    - [ ] All mocks use the _patch_and_run pattern from test_main_integration.py
    - [ ] Tests pass with pytest tests/test_f003_robustness.py -v
    - [ ] Full suite still passes: pytest tests/ -q (374→382 tests, 6 skipped)
    - [ ] PANEL_MAX_RETRIES=0 and PANEL_SKIP_HUMAN_GATE=1 set per test class
    - [ ] No real subprocess or network calls — everything mocked
    - [ ] Each test includes docstring explaining which user story edge case it covers
    - [ ] Branch name: feat/f003-edge-case--robustness-tests