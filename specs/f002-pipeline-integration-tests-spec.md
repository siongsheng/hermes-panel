# F002: Pipeline Integration Tests

14 tasks with proper ### Task N: headers confirmed. Here is the complete spec:
    
    F002: Pipeline Integration Tests
    
    Status: [~] In Progress
    Priority: P0
    Dependencies: None
    Confidence: High Impact: HIGH
    
    Decision Table
    
    SINGLE APPROACH: Extract main() into a testable Orchestrator class with injectable I/O dependencies (stdin, select, lock, gh CLI), then write integration tests for all 5 pipeline phases against a fixture test repo. This is the standard "humble object" pattern — no alternatives needed.
    
    Impact
    
    Every future Dokima change is verified against a real pipeline run. Contributors get a single pytest command that proves all 5 phases work end-to-end. The 4 currently-skipped tests become active. Regressions in flag parsing, lock behavior, stdin handling, and phase transitions are caught automatically.
    
    What Changed
    
    - dokima: Extract main() into Orchestrator class (~100 lines refactored, ~50 lines net new for driver). Add read_stdin_with_timeout() helper. Make select, sys.stdin, acquire_lock, and _safe_run injectable.
    - tests/conftest.py: Add test_repo fixture — a minimal git repo with AGENTS.md, a Python file, and a test. Add orchestrator fixture with mocked I/O.
    - tests/test_pipeline_integration.py (NEW): End-to-end tests for all 5 phases — strategist, coder, vet, nm, TL.
    - tests/test_main.py (NEW): Flag parsing, lock behavior, stdin timeout, signal handling.
    - tests/test_edge_cases.py: Unskip tests at lines 253, 369 by injecting mock stdin.
    - tests/test_final_coverage.py: Unskip test at line 116 by injecting mock stdin.
    - tests/test_main_integration.py: Unskip tests at lines 153, 173 by injecting mock lock + retry.
    - tests/test_unit_helpers.py: Add test_no_agents_md now expects project-type defaults (post-#7 fix), update assertion.
    
    API/Interface Proposal
    
    N/A — internal refactor only. No CLI change. No new flags. No breaking changes.
    
    Security Considerations
    
    N/A — no attack surface change. This is test infrastructure.
    
    Documentation Impact
    
    README: No change needed.
    
    
    
    Task Breakdown
    
    Task 1: Extract read_stdin_with_timeout() helper
    Files: dokima
    Dependencies: [none]
    Parallelizable: yes
    Description: Extract the select.select([sys.stdin], [], [], 60.0) + sys.stdin.readline() pattern (used at lines 3055 and 3840) into a standalone _read_stdin_with_timeout(prompt="", timeout=60, stdin=None) function. Two call sites replace their inline code with this helper. This is the smallest safe cut — no behavior change, pure extraction.
    
    Task 2: Create Orchestrator class with injectable dependencies
    Files: dokima
    Dependencies: [Task 1]
    Parallelizable: no
    Description: Extract the core pipeline dispatch logic from main() (lines 4530–4630) into an Orchestrator class. Constructor accepts: stdin, lock_fn, safe_run_fn, gh_cli_fn, project_dir, feature, flags (is_next, is_continuous, is_fix, etc.). main() becomes a thin shell: parse argv → construct Orchestrator with real dependencies → call orchestrator.run(). No behavior change — verified by running python3 dokima --help producing identical output.
    
    Task 3: Add test_repo fixture to conftest
    Files: tests/conftest.py
    Dependencies: [none]
    Parallelizable: yes
    Description: Create a test_repo pytest fixture that builds a minimal git repo in a temp directory with: AGENTS.md (with test/build/lint commands), a .py file with a function + test, git init, and an initial commit. Returns the path. Used by all integration tests. Covers the case where detect_commands() finds AGENTS.md and also the case where it falls back to project-type detection.
    
    Task 4: Add orchestrator fixture with mock I/O
    Files: tests/conftest.py
    Dependencies: [Task 2, Task 3]
    Parallelizable: yes
    Description: Create an orchestrator pytest fixture that constructs Orchestrator with: stdin=StringIO(...), lock_fn=lambda: (True, mock_fd), safe_run_fn=mock_safe_run, gh_cli_fn=mock_gh. The mock_safe_run returns pre-configured (stdout, stderr, returncode) tuples from a dict keyed by command prefix. The mock_gh returns pre-configured JSON for gh pr list/create/view. Tests configure responses via fixture parameters.
    
    Task 5: Phase 1-2 integration test — Strategist → Coder
    Files: tests/test_pipeline_integration.py
    Dependencies: [Task 4]
    Parallelizable: no
    Description: Test that Orchestrator.run() with a mock strategist that returns a valid spec (with DAG tasks) correctly: extracts tasks, spawns a coder agent (mocked), creates a feature branch, and commits spec files. Verify: branch name format, spec file exists on mock filesystem, correct number of tasks extracted from DAG. Mock all external Hermes spawns — this is pipeline logic testing, not live agent testing.
    
    Task 6: Phase 3-5 integration test — Vet → nm → TL
    Files: tests/test_pipeline_integration.py
    Dependencies: [Task 5]
    Parallelizable: no
    Description: Test that after coder completes, Orchestrator correctly: runs vet phase (mock _safe_run returns pass), triggers nm review (mock spawn returns APPROVED), and produces TL verdict. Verify: vet output parsed correctly, nm verdict recognized, TL verdict emitted. Test BLOCKED verdict path: TL detects blocker → auto-fix loop triggers → fix is applied → re-review passes.
    
    Task 7: Flag parsing tests
    Files: tests/test_main.py
    Dependencies: [Task 2]
    Parallelizable: yes
    Description: Test that main() correctly parses all flag combinations: --next, --continuous, --fix, --fix-all, --skip-autofix, --force-full, --skip-human-gate, --max-parallel=N, --interactive, --answers, --add, positional feature + dir. Verify: correct global flags set, correct dispatch to run_next/run_continuous/run_fix/run_init/run_add. Edge case: --fix + --skip-autofix together, empty feature string, missing directory.
    
    Task 8: Lock and signal tests
    Files: tests/test_main.py
    Dependencies: [Task 4]
    Parallelizable: yes
    Description: Test lock acquisition: first call succeeds, second call (concurrent) exits with code 2. Test stale lock removal (dead PID). Test signal handler: SIGINT triggers cleanup, unlocks. Test lock with garbage content (non-numeric PID). These tests already exist in test_detect_commands.py (misnamed — actually tests acquire_lock) — move them into their own file and verify they pass.
    
    Task 9: Stdin timeout and interview mode tests
    Files: tests/test_main.py
    Dependencies: [Task 1, Task 4]
    Parallelizable: yes
    Description: Test _read_stdin_with_timeout(): returns input when available, returns empty string on timeout, handles empty input (user presses Enter), handles EOF. Test interview mode integration: strategist returns exit code 2 with clarification questions → orchestrator prompts user → user provides answers (via mock stdin) → answers injected into re-prompt.
    
    Task 10: Unskip existing blocked tests
    Files: tests/test_edge_cases.py, tests/test_final_coverage.py, tests/test_main_integration.py
    Dependencies: [Task 2, Task 4]
    Parallelizable: yes
    Description: Unskip the 4 main()-blocked tests by injecting mock stdin/lock where needed. test_edge_cases.py:253 and :369 — inject StringIO stdin via Orchestrator constructor. test_final_coverage.py:116 — same. test_main_integration.py:153 and :173 — construct Orchestrator with mock lock that doesn't block + mock retry that doesn't loop. Verify all 4 previously-skipped tests now pass. Update test_functions_unit.py:23 description to mark as intentionally skip-only (documentation of removed behavior).
    
    Task 11: Edge case — strategist DAG format failure
    Files: tests/test_pipeline_integration.py
    Dependencies: [Task 5]
    Parallelizable: yes
    Description: Test that when strategist returns a spec with NO ### Task N: headers (wave-format or plain text), the DAG re-prompt mechanism fires: orchestrator detects missing format, feeds spec back to strategist with "FORMAT CORRECTION REQUIRED", extracts corrected DAG from re-prompt output. Verify: re-prompt fires exactly once, corrected spec has ### Task N: headers, pipeline proceeds normally after correction. Also test garbage detection: strategist returns "Done. Spec saved" → orchestrator falls back to pre-re-prompt spec.
    
    Task 12: Edge case — coder failure modes
    Files: tests/test_pipeline_integration.py
    Dependencies: [Task 5]
    Parallelizable: yes
    Description: Test coder failure paths: (a) coder produces only RED commits (vet catches — test failure reported, BLOCKED verdict), (b) coder times out (partial results captured, partial spec committed), (c) coder produces zero commits (empty branch — orchestrator detects and reports). Verify each path produces correct verdict and does not crash the pipeline.
    
    Task 13: Edge case — nm/TL failure modes
    Files: tests/test_pipeline_integration.py
    Dependencies: [Task 6]
    Parallelizable: yes
    Description: Test nm failure: nm model provider down → fallback fires → review completes with fallback model. Test TL BLOCKED: TL returns BLOCKED with specific blockers → auto-fix loop extracts blockers → feeds back to coder → coder produces fix commit → re-review passes. Test TL edge: TL returns NIT-only verdict → treated as APPROVED with warnings.
    
    Task 14: Run full suite, update STATUS.md, close F002
    Files: specs/roadmap.md, specs/STATUS.md
    Dependencies: [Task 10, Task 11, Task 12, Task 13]
    Parallelizable: no
    Description: Run python3 -m pytest tests/ -q. Verify 0 failures, 0 skipped (or all skips documented). Update specs/roadmap.md — mark F002 [x] Done. Update specs/STATUS.md — add F002 entry with test counts. Commit with message: feat: F002 pipeline integration tests — 14 tasks, injectable Orchestrator, 6 unskipped tests.
    
    
    
    Risk Register
    
    Risk: Orchestrator extraction breaks panel behavior
    Severity: HIGH
    Mitigation: Task 2 verified by --help output identity + existing 262 tests
      still pass
    Trigger: Any existing test fails after refactor
    ────────────────────────────────────────
    Risk: Mock fidelity gaps hide real pipeline bugs
    Severity: MEDIUM
    Mitigation: Integration test fixtures mirror real AGENTS.md + git repo
      structure
    Trigger: Phase tests pass with mocks but fail with real agents
    ────────────────────────────────────────
    Risk: 4 unskipped tests expose undiscovered bugs
    Severity: LOW
    Mitigation: Each unskip verified individually before batch run
    Trigger: Previously-passing code now fails under injection
    ────────────────────────────────────────
    Risk: DAG re-prompt test fragile to prompt changes
    Severity: MEDIUM
    Mitigation: Test checks behavior (re-prompt fires, format corrected), not
      exact prompt text
    Trigger: Strategist prompt updated without updating test expectations
    ────────────────────────────────────────
    Risk: Task 10 line numbers stale after Task 2 refactor
    Severity: MEDIUM
    Mitigation: Confirm line numbers post-refactor; tasks 2+10 are sequential
    Trigger: test_main() refactor shifts line offsets
    
    Anti-Creep
    
    - No live agent testing — all Hermes spawns are mocked. This is pipeline logic testing, not AI agent testing.
    - No new CLI flags — the Orchestrator is an internal refactor. dokima --help output unchanged.
    - No refactoring beyond what's needed for testability — only main() extraction and read_stdin_with_timeout(). No module split, no dependency injection framework, no ABCs.
    - No E2E test with real models — those live in test_main_integration.py (remains skipped), not in F002 scope.
    - No test coverage targets — don't add --cov or coverage enforcement. The goal is pipeline coverage, not line coverage.
    - No mocking of spawn_agent internals — mock at the Orchestrator level, not the subprocess level.
    
    Sign-Off Checklist
    
    - [ ] Task 1: read_stdin_with_timeout() extracted, both call sites use it, tests pass
    - [ ] Task 2: Orchestrator class exists, main() is a thin shell, --help output identical
    - [ ] Task 3: test_repo fixture creates valid git repo with AGENTS.md + code + tests
    - [ ] Task 4: orchestrator fixture constructs injectable Orchestrator with mock I/O
    - [ ] Task 5-6: Phase transition tests pass — strategist→coder→vet→nm→TL
    - [ ] Task 7-9: Flag parsing, lock, signal, and stdin tests pass
    - [ ] Task 10: 4 previously-skipped tests now pass; 1 intentionally-skipped test documented
    - [ ] Task 11-13: DAG re-prompt, coder failure, nm/TL failure edge cases pass
    - [ ] Task 14: Full suite python3 -m pytest tests/ -q — 0 failures, skips documented
    - [ ] No existing tests regressed (262 pass → 262+ pass)
    - [ ] specs/roadmap.md updated with [x] Done
    - [ ] specs/STATUS.md updated with F002 entry