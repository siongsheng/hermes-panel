# F022b: Modular Architecture — Pipeline, Roadmap, Tasks

Now I have the full picture. Let me produce the corrected F022b spec. The current state: F022 extracted utils.py and agent.py (imports wired, but function bodies remain in dokima as dead code). F022b extracts the remaining 3 modules — tasks.py, roadmap.py, pipeline.py — and finally removes all moved function bodies from the main script.
    
    
    
    Position: F022b extracts the 3 remaining modules (tasks, roadmap, pipeline) and cleans up dokima to ~250 lines. SINGLE APPROACH — mechanical extraction with zero behavioral change, verified by the 640 existing tests. (High confidence)
    
    
    
    F022b: Modular Architecture — Pipeline, Roadmap, Tasks — Implementation Spec
    
    Version: 1.0.0  
    Confidence: High  
    Impact: HIGH  
    Status: Pending  
    Dependencies: F022 (utils.py + agent.py extracted, imports wired)
    
    
    
    1. Executive Summary
    
    Extract the last 3 modules from the 5,721-line dokima monolith: tasks.py (infrastructure classes + parallel execution), roadmap.py (parsing, CLI commands, feature lifecycle), and pipeline.py (all 5 phase functions + fix mode + orchestration). The main dokima script shrinks from 5,721 to ~250 lines — only imports, global declarations, main(), and the if name block. All 640 existing tests must pass identically. Builds on F022's pattern: agent.py and utils.py already prove the module contract works. The primary win is agents loading only the module relevant to their task (~500–2,000 lines) instead of 5,721.
    
    2. Constitution Check
    
    Axiom: Does it solve the user's own pain?
    Status: YES
    Detail: Agents timeout/hallucinate on 5,721-line monolith. F022b drops
      context windows 55–90%
    ────────────────────────────────────────
    Axiom: Is it weekend-buildable?
    Status: YES
    Detail: Mechanical refactoring, 8 tasks, 4 waves
    ────────────────────────────────────────
    Axiom: Is there evidence people will pay?
    Status: N/A
    Detail: Internal tooling improvement
    ────────────────────────────────────────
    Axiom: Is the tech stack boring and proven?
    Status: YES
    Detail: Python 3.6+ imports, zero new dependencies
    ────────────────────────────────────────
    Axiom: Does it avoid AI hype categories?
    Status: YES
    Detail: Pure code organization
    
    3. Impact
    
    Agents loading dokima drop from 5,721 lines to ~250 lines (main entry) + only the module relevant to their task. Coder modifying run_phase2_coder loads pipeline.py (~2,100 lines) instead of the full monolith. Strategist reading infrastructure reads tasks.py (~550 lines). NM agent reviewing a PR reads pipeline.py + utils.py (~3,800 lines instead of 5,721). Context window utilization drops 55–90% for targeted changes. The 640 existing tests serve as the regression safety net — every moved function's behavior is verified.
    
    4. What Changed
    
    - tasks.py — NEW: WorktreeManager, TaskLock, Task, TaskDAG classes and parallel execution functions (spawn_coder_in_worktree, _reap_completed, _poll_until_wave_done, merge_worktree_branches, run_parallel_coders), ~600 lines
    - roadmap.py — NEW: RoadmapFeature class, roadmap parsing (parse_roadmap, pick_next_feature), status management (update_roadmap_status, commit_roadmap_update, auto_repair_status), CLI commands (run_add_to_roadmap, run_next_setup, run_init), ~750 lines
    - pipeline.py — NEW: all 5 phase functions (run_phase1_strategist through run_phase5_tech_lead), run_pipeline, run_fix_mode, run_post_pipeline, halt_and_revert, discover_blocked_pr, extract_blockers_from_pr, archive_specs_for_feature, ~2,100 lines
    - dokima — REDUCED 5,721→~250 lines: imports from all 5 modules, global declarations, main(), if name block; all moved function bodies deleted
    - tests/test_f022_tasks.py — NEW: behavioral tests for tasks.py module exports and class invariants
    - tests/test_f022_roadmap.py — NEW: behavioral tests for roadmap.py module exports and parsing
    
    5. API/Interface Proposal
    
    Each module exports a well-defined public surface. Internal helpers are prefixed with _.
    
    tasks.py public API:
    Task, TaskDAG, TaskLock, WorktreeManager, run_parallel_coders(), spawn_coder_in_worktree(), merge_worktree_branches()
    
    roadmap.py public API:
    RoadmapFeature, parse_roadmap(), pick_next_feature(), update_roadmap_status(), commit_roadmap_update(), auto_repair_status(), run_add_to_roadmap(), run_next_setup(), run_init()
    
    pipeline.py public API:
    run_pipeline(), run_phase1_strategist(), run_phase2_coder(), run_phase3_vet(), run_phase4_nm(), run_phase5_tech_lead(), run_fix_mode(), run_post_pipeline(), halt_and_revert(), archive_specs_for_feature()
    
    6. Security Considerations
    
    No attack surface change. Module boundaries are internal Python imports — same process, same permissions, same os.umask(0o077). Token redaction and prompt sanitization remain in utils.py with identical behavior. No new I/O, no new subprocess calls, no new environment variable reads.
    
    7. Documentation Impact
    
    README: No change needed. MAINTAINERS.md: Update "Key Functions by Phase" to reference module files instead of line numbers in the monolith.
    
    8. COTS Build-vs-Buy
    
    All built. Pure refactoring — zero new dependencies. Python's native import system is the only mechanism.
    
    9. Data Model
    
    No data model changes. All existing data structures (Task, TaskDAG, RoadmapFeature, WorktreeManager, TaskLock) move to tasks.py and roadmap.py with identical field definitions. Checkpoint JSON schema unchanged. Lock file format unchanged. STATUS.md format unchanged.
    
    10. Feature Breakdown
    
    Position: SINGLE APPROACH — extract 3 modules from the monolith into tasks.py, roadmap.py, pipeline.py, then remove all moved function bodies from dokima, leaving only imports + main(). All 640 tests pass. (High confidence)
    
    Task 1: Create tasks.py with infrastructure classes
    Files: tasks.py, dokima
    Dependencies: none
    Parallelizable: yes
    Estimated LOC: ~600 moved + ~20 imports
    Description: Move WorktreeManager, TaskLock, Task, TaskDAG classes from dokima lines 519–809 into tasks.py. Add imports from utils (slugify, git, _safe_run). The classes have no dependencies on other extracted modules — they only use stdlib and utils functions.
    
    Task 2: Add parallel execution functions to tasks.py
    Files: tasks.py, dokima
    Dependencies: Task 1
    Parallelizable: no
    Estimated LOC: ~170 moved + ~10 imports
    Description: Move spawn_coder_in_worktree, _reap_completed, _poll_until_wave_done, merge_worktree_branches, run_parallel_coders from dokima lines 1613–1921 into tasks.py. These depend on the classes moved in Task 1 and on utils functions (git, gh, _safe_run, slugify). Import spawn_agent from agent.py.
    
    Task 3: Create roadmap.py with parsing and feature lifecycle
    Files: roadmap.py, dokima
    Dependencies: Task 1
    Parallelizable: yes
    Estimated LOC: ~500 moved + ~20 imports
    Description: Move RoadmapFeature class (line 691), parse_roadmap, pick_next_feature, update_roadmap_status, commit_roadmap_update, auto_repair_status from dokima lines 691–1501 into roadmap.py. Import RoadmapFeature partial from tasks, and git/gh/slugify/acquire_lock/detect_repo from utils.
    
    Task 4: Add CLI commands to roadmap.py
    Files: roadmap.py, dokima
    Dependencies: Task 3
    Parallelizable: no
    Estimated LOC: ~250 moved + ~15 imports
    Description: Move run_add_to_roadmap, run_next_setup, run_init from dokima lines 2155–2701 into roadmap.py. These depend on the parsing functions moved in Task 3. Import _PROFILE_CONFIGS, _PROFILE_ORDER, ensure_profiles, deploy_profile_skills from utils.
    
    Task 5: Create pipeline.py with phase functions and orchestration
    Files: pipeline.py, dokima
    Dependencies: Task 2, Task 4
    Parallelizable: no
    Estimated LOC: ~2,100 moved + ~35 imports
    Description: Move all pipeline-phase functions from dokima into pipeline.py: halt_and_revert (line 382), archive_specs_for_feature (line 2704), run_post_pipeline (line 2736), discover_blocked_pr (line 2819), extract_blockers_from_pr (line 2869), run_fix_mode (line 3265), run_phase1_strategist (line 4414), run_phase2_coder (line 3547), run_phase3_vet (line 3823), run_phase4_nm (line 4001), run_phase5_tech_lead (line 4224), run_pipeline (line 5033). Import from utils, agent, tasks, roadmap. Global variables (PROJECT_DIR, REPO, DEFAULT_BRANCH, PANEL_PORT, etc.) become module-level variables set by main() after import.
    
    Task 6: Clean up dokima — remove all moved function bodies
    Files: dokima
    Dependencies: Task 1, Task 2, Task 3, Task 4, Task 5
    Parallelizable: no
    Estimated LOC: ~250 (reduced from 5,721)
    Description: Delete all function/class definitions from dokima that now live in modules. Keep only: shebang, module docstring, stdlib imports, module imports (utils, agent, tasks, roadmap, pipeline), all global variable declarations (REAL_HOME, HERMES, HERMES_BIN, PROFILES, PANEL_PORT, OUTPUT_LOG, DEFAULT_BRANCH, SKIP_AUTOFIX, FORCE_FULL, SKIP_HUMAN_GATE, max_parallel_override, FALLBACK_MODELS, RESUME, VERSION), main() function, and if name == 'main' block. main() must set module-level globals on imported modules (e.g., pipeline.PROJECT_DIR = PROJECT_DIR). Verify with python3 -m py_compile dokima.
    
    Task 7: Create behavioral tests for new modules
    Files: tests/test_f022_tasks.py, tests/test_f022_roadmap.py, tests/test_f022_pipeline.py
    Dependencies: Task 6
    Parallelizable: yes
    Estimated LOC: ~200 (3 test files, ~65 lines each)
    Description: Create behavioral tests verifying module exports and class invariants. test_f022_tasks.py: verify Task, TaskDAG, TaskLock, WorktreeManager are importable and behave correctly. test_f022_roadmap.py: verify RoadmapFeature, parse_roadmap, pick_next_feature are importable and parse the real roadmap.md. test_f022_pipeline.py: verify run_pipeline and all 5 phase functions are importable. These are smoke tests — the 640 existing tests cover behavior. Import validation only.
    
    Task 8: Update test imports and verify full test suite
    Files: tests/conftest.py, tests/test_*.py (as needed)
    Dependencies: Task 6, Task 7
    Parallelizable: no
    Estimated LOC: ~30 changes across 2-4 test files
    Description: Tests that import directly from dokima (via import dokima or from dokima import ...) must now import from the correct module. Most tests use fixtures that spawn subprocesses — these are unaffected. Check conftest.py and any test with from dokima import. Run full suite: python3 -m pytest tests/ -q. All 640 tests must pass. Fix any import errors.
    
    11. Test Plan
    
    Happy path:
    - All 640 existing tests pass with zero modifications beyond import path updates
    - Full pipeline runs end-to-end with identical output
    - python3 -m py_compile dokima tasks.py roadmap.py pipeline.py succeeds with no import errors
    
    Edge cases:
    - Circular import detection: verify no module imports another that imports it back. DAG is utils ← agent, utils ← tasks ← roadmap, utils+agent+tasks+roadmap ← pipeline ← dokima
    - Missing function: agent loading pipeline.py must still have access to slugify() via utils import
    - Global variable propagation: PROJECT_DIR, REPO, DEFAULT_BRANCH must be accessible in all modules after main() sets them
    - Duplicate definitions: dokima still has function bodies (dead code) — verify they don't shadow module imports
    - RoadmapFeature class: currently defined at line 691 in dokima between Task (line 677) and TaskDAG (line 704) — verify it moves cleanly to roadmap.py without breaking the import chain
    - halt_and_revert: references WorktreeManager — verify the import from tasks.py resolves after the move
    - run_phase1_strategist: largest single function (~620 lines) — verify it compiles cleanly in pipeline.py
    - What happens when a refactored test file does import dokima and dokima imports pipeline.py which fails? (Cascading failure — all tests break)
    
    Failure modes:
    - ImportError: a moved function references a global that wasn't moved to the same module
    - NameError: a function body references another function that was moved to a different module — fix by adding the import
    - Test import failure: test files doing from dokima import slugify break — update to from utils import slugify
    - DeepSeek model quirk: verify_spec_quality() in utils.py is self-referential (tests itself in spec validation) — must still work
    - Network timeout during integration test: pipeline fails mid-phase — checkpoint resume must still work
    - Concurrent access: two agents trying to import a partially-moved module during the transition
    
    Contract invariants:
    - Before refactoring: python3 -m pytest tests/ -q passes 640 tests. After refactoring: same 640 tests pass
    - dokima --help output must be byte-identical before and after
    - Checkpoint JSON schema unchanged — old checkpoints must load after refactoring
    - _redact_secrets() redacts the same token values before and after
    - _sanitize_prompt() produces identical output for all known injection patterns (F001 test vectors)
    - Lock file behavior unchanged — concurrent pipeline runs still blocked
    
    12. Panel Split
    
    Wave 1 (parallel, 2 coders):
    - Task 1 (tasks.py classes) — coder A
    - Task 3 (roadmap.py parsing) — coder B
    
    Wave 2 (parallel, 2 coders):
    - Task 2 (tasks.py parallel execution) — coder A
    - Task 4 (roadmap.py CLI commands) — coder B
    
    Wave 3 (sequential, 1 coder):
    - Task 5 (pipeline.py — depends on all other modules)
    
    Wave 4 (sequential, 1 coder):
    - Task 6 (dokima cleanup — depends on all modules)
    - Task 8 (test imports — depends on Task 6)
    
    Wave 5 (parallel with Wave 4, 1 coder):
    - Task 7 (behavioral tests — can run alongside Task 8, different files)
    
    Total: 5 waves, max 2 coders parallel
    
    13. Build & Deploy
    
    No deployment change. Dokima remains a single entry-point script at dokima. The 5 module files live alongside it in the project root. No new environment variables. No CI changes.
    
    Build verification:
    bash
    python3 -m py_compile dokima utils.py agent.py tasks.py roadmap.py pipeline.py
    
    
    14. Risk Register
    
    Risk: Circular imports between modules
    Severity: MEDIUM
    Mitigation: Enforce DAG: utils ← agent, utils ← tasks ← roadmap,
      utils+agent+tasks+roadmap ← pipeline ← dokima
    Trigger: Test import fails with circular import error
    ────────────────────────────────────────
    Risk: Missing global variable in moved function
    Severity: HIGH
    Mitigation: Audit all global declarations before moving; grep for global
      in each section
    Trigger: NameError at runtime during pipeline execution
    ────────────────────────────────────────
    Risk: Test suite breaks on direct dokima imports
    Severity: MEDIUM
    Mitigation: Task 8 specifically handles test imports; run tests after
      every module move
    Trigger: Test failure after Task 6
    ────────────────────────────────────────
    Risk: RoadmapFeature positioned between Task and TaskDAG
    Severity: MEDIUM
    Mitigation: Move RoadmapFeature to roadmap.py in Task 3 (same wave as Task
      1 for Task); add explicit import in tasks.py if needed
    Trigger: ImportError: RoadmapFeature referenced in TaskDAG
    ────────────────────────────────────────
    Risk: Coder agent loads wrong module for fix
    Severity: LOW
    Mitigation: File hints in coder prompt include module paths;
      _extract_code_context reads from correct file
    Trigger: Coder modifies moved function in old location
    ────────────────────────────────────────
    Risk: DeepSeek strips module-qualified names
    Severity: LOW
    Mitigation: Module names are simple (no hyphens); from tasks import
      TaskDAG is standard Python
    Trigger: ImportError with mangled module names
    ────────────────────────────────────────
    Risk: halt_and_revert references WorktreeManager
    Severity: MEDIUM
    Mitigation: Add from tasks import WorktreeManager in pipeline.py; verify
      halt_and_revert compiles
    Trigger: NameError at pipeline runtime
    ────────────────────────────────────────
    Risk: 5,721-line count is stale (grows with each commit)
    Severity: LOW
    Mitigation: Re-measured during spec validation; canonical count is wc -l
      dokima at time of execution
    Trigger: Module split produces unexpected line counts
    
    15. Anti-Creep
    
    Features explicitly NOT in scope:
    - No package structure (dokima/ directory with init.py) — flat files in project root
    - No type annotations — keep existing comment style
    - No new abstractions or refactoring beyond moving functions — no "while we're at it" improvements
    - No test restructuring — test files stay where they are, only import paths change
    - No new CLI commands or flags
    - No documentation site updates beyond MAINTAINERS.md
    - No setup.py or pyproject.toml — dokima remains dependency-free
    - No fixing of F022's incomplete cleanup (duplicate function bodies in dokima that shadow utils.py imports) — those are dead code removed by Task 6
    
    16. Sign-Off Checklist
    
    - [ ] All 5 module files exist: utils.py, agent.py, tasks.py, roadmap.py, pipeline.py
    - [ ] dokima script is under 300 lines (imports + globals + main() + if name)
    - [ ] python3 -m py_compile dokima utils.py agent.py tasks.py roadmap.py pipeline.py passes
    - [ ] Full test suite passes: python3 -m pytest tests/ -q — all 640 tests pass
    - [ ] Full pipeline runs end-to-end with a test feature
    - [ ] dokima --help output unchanged
    - [ ] Checkpoint resume works (old checkpoint loads after refactoring)
    - [ ] --fix mode discovers and fixes a BLOCKED PR
    - [ ] No circular imports detected
    - [ ] MAINTAINERS.md updated with new module structure
    - [ ] Behavioral tests for new modules pass: python3 -m pytest tests/test_f022_tasks.py tests/test_f022_roadmap.py tests/test_f022_pipeline.py -v
    - [ ] No behavioral regressions confirmed by TL review
    
    
    
    Confidence: High — F022 proved the module pattern works (utils.py and agent.py imports wired, 640 tests pass). F022b is the same mechanical extraction for the remaining 3 modules. The dependency DAG is well-defined (utils → agent/tasks → roadmap → pipeline → dokima), and this is pure code relocation with zero logic changes. The 640 existing tests serve as the regression safety net.
    
    Impact: HIGH — this is a structural change to the entire codebase. Every remaining function moves, the main script shrinks from 5,721 to ~250 lines, and 3 new module files are created. However, the risk is mitigated by F022's proven pattern, the existing test suite covering all phases, and the fact that behavior is strictly preserved.