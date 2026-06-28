# F022: Modular Architecture

Now I have a thorough understanding of the codebase. Let me produce the complete corrected spec.
    
    Position: This is a mechanical refactoring with well-defined boundaries — SINGLE APPROACH: split the 5,484-line monolith into 5 importable modules with no behavioral changes, verified by the 495+ existing tests. (High confidence)
    
    
    
    
    F022: Modular Architecture — Implementation Spec
    
    Version: 1.0.0
    Confidence: High
    Impact: HIGH
    Status: In Progress
    
    
    
    1. Executive Summary
    
    Split the 5,484-line monolithic dokima script into 5 importable Python modules (agent.py, pipeline.py, roadmap.py, tasks.py, utils.py) with clean import boundaries. The main dokima script becomes a thin orchestration entry point that imports from these modules. Zero behavioral change — all 495+ existing tests must pass identically. The primary win is smaller context windows for AI agents (strategist, coder, TL) who currently must load the full 5,484 lines to modify any function.
    
    2. Constitution Check
    
    Axiom: Does it solve the user's own pain?
    Status: YES — agents timeout/hallucinate on 5,484-line monoliths
    ────────────────────────────────────────
    Axiom: Is it weekend-buildable?
    Status: YES — mechanical refactoring, 8 tasks, ~4 waves
    ────────────────────────────────────────
    Axiom: Is there evidence people will pay?
    Status: N/A — internal tooling improvement
    ────────────────────────────────────────
    Axiom: Is the tech stack boring and proven?
    Status: YES — Python 3.6+ imports, zero new dependencies
    ────────────────────────────────────────
    Axiom: Does it avoid AI hype categories?
    Status: YES — pure code organization
    
    3. Impact
    
    Agents loading dokima drop from 5,484 lines to ~200 lines (main entry) + only the module relevant to their task. Coder modifying run_phase2_coder loads pipeline.py (~900 lines) instead of the full monolith. Strategist reading infrastructure reads tasks.py (~230 lines) instead of 5,484. Context window utilization drops 60–85% for targeted changes.
    
    4. What Changed
    
    - dokima — reduced to ~200 lines: imports, CLI argument parsing, main(), and run_pipeline() orchestration
    - utils.py — security helpers, git/GitHub wrappers, spec extraction/validation, checkpointing, STATUS.md, CLI handlers (~1,750 lines)
    - agent.py — agent spawning, API calls, provider fallback, session extraction (~380 lines)
    - tasks.py — Task, TaskDAG, TaskLock, WorktreeManager, parallel coder execution (~550 lines)
    - roadmap.py — roadmap parsing, feature picking, add/init/repair, RoadmapFeature (~700 lines)
    - pipeline.py — all 5 phase functions, fix mode, post-pipeline, code context extraction (~1,900 lines)
    
    5. API/Interface Proposal
    
    Each module exports a well-defined public surface. Internal helpers are prefixed with _.
    
    utils.py public API: git(), gh(), slugify(), acquire_lock(), _sanitize_prompt(), _validate_project_dir(), _redact_secrets(), extract_pr_sections(), extract_agent_messages(), clean_spec_content(), verify_spec_quality(), detect_repo(), detect_commands(), generate_codebase_map(), extract_file_paths(), _extract_code_context(), save_checkpoint(), load_checkpoint(), validate_checkpoint(), delete_checkpoint(), _phase_should_skip(), try_auto_merge(), handle_status(), handle_stop(), handle_kill(), handle_list_crons(), _extract_tl_verdict(), _extract_tl_blockers(), update_status_md()
    
    agent.py public API: call_agent(), spawn_agent(), _run_agent(), _detect_provider_failure(), _load_fallback_config(), load_key(), load_github_token()
    
    tasks.py public API: Task, TaskDAG, TaskLock, WorktreeManager, run_parallel_coders(), spawn_coder_in_worktree(), merge_worktree_branches()
    
    roadmap.py public API: RoadmapFeature, parse_roadmap(), pick_next_feature(), update_roadmap_status(), commit_roadmap_update(), auto_repair_status(), run_add_to_roadmap(), run_next_setup(), run_init()
    
    pipeline.py public API: run_pipeline(), run_phase1_strategist(), run_phase2_coder(), run_phase3_vet(), run_phase4_nm(), run_phase5_tech_lead(), run_fix_mode(), run_post_pipeline(), archive_specs_for_feature(), halt_and_revert()
    
    6. Security Considerations
    
    No attack surface change. Module boundaries are internal Python imports — same process, same permissions, same os.umask(0o077). Token redaction (_redact_secrets) and prompt sanitization (_sanitize_prompt) remain in utils.py with identical behavior. No new I/O, no new subprocess calls, no new environment variable reads.
    
    7. Documentation Impact
    
    README: No change needed. MAINTAINERS.md: Update "Key Functions by Phase" to reference module files instead of line numbers in the monolith.
    
    8. COTS Build-vs-Buy
    
    All built. This is pure refactoring — zero new dependencies. Python's native import system is the only mechanism.
    
    9. Data Model
    
    No data model changes. All existing data structures (Task, TaskDAG, RoadmapFeature, WorktreeManager, TaskLock) remain in tasks.py and roadmap.py. Checkpoint JSON schema unchanged. Lock file format unchanged. STATUS.md format unchanged.
    
    10. Task Breakdown
    
    Task 1: Create utils.py with all shared utilities and helpers
    Files: utils.py, dokima
    Dependencies: none
    Parallelizable: yes
    Estimated LOC: ~1,750 moved + ~30 imports
    Description: Move all utility functions from dokima into utils.py: security helpers (_sanitize_prompt, _validate_project_dir, _redact_secrets, _write_log_line), git/GitHub wrappers (git, gh, _safe_run), string helpers (slugify), spec extraction/validation (extract_pr_sections, extract_agent_messages, clean_spec_content, verify_spec_quality, _check_pr_body_quality), checkpointing (save_checkpoint, load_checkpoint, delete_checkpoint, validate_checkpoint, _phase_should_skip), STATUS.md helpers (_parse_status_md, _make_status_entry, update_status_md), CLI handlers (handle_status, handle_stop, handle_kill, handle_list_crons, _check_pid, _verify_pid_owner, _get_lock_state), repo detection (detect_repo, detect_commands, _detect_referenced_repo), code context (extract_file_paths, _extract_code_context, generate_codebase_map, _describe_file), TL extraction (_extract_tl_verdict, _extract_tl_blockers), remaining helpers (load_key, load_github_token, _lock_path, _stop_path, _checkpoint_path, acquire_lock, _cleanup_lock, _signal_handler, try_auto_merge, _supplement_pr_sections, _detect_default_branch, _set_gh_token, show_help, halt_and_revert, archive_specs_for_feature). Add necessary imports at module top. The dokima script must keep these functions temporarily until all modules exist (removed in Task 6).
    
    Task 2: Create agent.py with agent spawning and API call logic
    Files: agent.py, dokima
    Dependencies: Task 1 (needs load_key, load_github_token from utils)
    Parallelizable: no
    Estimated LOC: ~380 moved + ~20 imports
    Description: Move agent-related functions from dokima into agent.py: call_agent, _detect_provider_failure, _PROVIDER_FAILURE_PATTERNS, FALLBACK_MODEL_RE, _load_fallback_config, spawn_agent, _run_agent, extract_agent_messages. Import load_key and load_github_token from utils. The call_agent function references global PANEL_PORT and API_KEY — pass these as module-level variables set during init.
    
    Task 3: Create tasks.py with infrastructure classes and parallel execution
    Files: tasks.py, dokima
    Dependencies: Task 1 (needs slugify and git from utils)
    Parallelizable: yes (with Task 2)
    Estimated LOC: ~550 moved + ~25 imports
    Description: Move Task, TaskDAG, TaskLock, WorktreeManager classes plus parallel coder functions (spawn_coder_in_worktree, _reap_completed, _poll_until_wave_done, merge_worktree_branches, run_parallel_coders) into tasks.py. Import slugify, git, _safe_run from utils.
    
    Task 4: Create roadmap.py with roadmap parsing and CLI commands
    Files: roadmap.py, dokima
    Dependencies: Task 1, Task 3 (needs RoadmapFeature from tasks)
    Parallelizable: yes (with Task 2)
    Estimated LOC: ~700 moved + ~25 imports
    Description: Move RoadmapFeature class, parse_roadmap, pick_next_feature, update_roadmap_status, commit_roadmap_update, auto_repair_status, run_add_to_roadmap, run_next_setup, and run_init into roadmap.py. Import RoadmapFeature from tasks, and git/gh/slugify/acquire_lock/detect_repo/etc from utils.
    
    Task 5: Create pipeline.py with all 5 phase functions and fix mode
    Files: pipeline.py, dokima
    Dependencies: Task 1, Task 2, Task 3, Task 4
    Parallelizable: no
    Estimated LOC: ~1,900 moved + ~35 imports
    Description: Move run_phase1_strategist, run_phase2_coder, run_phase3_vet, run_phase4_nm, run_phase5_tech_lead, run_pipeline, run_fix_mode, run_post_pipeline, discover_blocked_pr, extract_blockers_from_pr, and archive_specs_for_feature into pipeline.py. Import from all other modules. The run_pipeline function references globals (PROJECT_DIR, REPO, DEFAULT_BRANCH, PANEL_FEATURE, etc.) — these stay as module-level variables set by main().
    
    Task 6: Refactor main dokima script to import from modules
    Files: dokima
    Dependencies: Task 1, Task 2, Task 3, Task 4, Task 5
    Parallelizable: no
    Estimated LOC: ~200 (reduced from 5,484)
    Description: Replace all moved function/class definitions in dokima with imports from utils, agent, tasks, roadmap, pipeline. Keep only: shebang, module docstring, global variable declarations (REAL_HOME, HERMES, HERMES_BIN, PROFILES, PANEL_PORT, OUTPUT_LOG, DEFAULT_BRANCH, SKIP_AUTOFIX, FORCE_FULL, SKIP_HUMAN_GATE, MAX_CONTINUOUS, max_parallel_override, FALLBACK_MODELS, RESUME, HELP_TEXT), main() function, and the if name == "main" block. main() must set module-level globals on imported modules (e.g., pipeline.PROJECT_DIR = PROJECT_DIR). Remove all moved function bodies. Run python3 -m py_compile dokima to verify.
    
    Task 7: Update test imports and verify test suite
    Files: tests/conftest.py, tests/test_*.py (as needed)
    Dependencies: Task 6
    Parallelizable: no
    Estimated LOC: ~30 changes across 3-5 test files
    Description: Tests that import functions directly from dokima (via import dokima or from dokima import ...) must now import from the correct module. Most tests use fixtures that spawn subprocesses — these are unaffected. Check conftest.py for any direct imports. Run full test suite: python3 -m pytest tests/ -q. All 495+ tests must pass. Fix any import errors.
    
    Task 8: Integration validation — full pipeline end-to-end
    Files: none (verification only)
    Dependencies: Task 7
    Parallelizable: no
    Estimated LOC: 0 (verification)
    Description: Run a full pipeline against a test feature: PANEL_SKIP_ORCHESTRATOR_REVIEW=1 python3 dokima --next . --force-full. Verify: strategist produces spec, coder commits, vet passes, nm runs, TL delivers verdict. Verify checkpoint save/load works. Verify --fix mode discovers and fixes blockers. Verify --status shows correct state. Run MAINTAINERS.md update to reflect new file structure.
    
    11. Test Plan
    
    Happy path:
    - All 495+ existing tests pass with zero modifications beyond import path updates
    - Full pipeline runs end-to-end with identical output
    - python3 -m py_compile dokima succeeds with no import errors
    
    Edge cases:
    - Circular import detection: verify no module imports another that imports it back
    - Missing function: agent loading pipeline.py must still have access to slugify() via utils import
    - Global variable propagation: PROJECT_DIR, REPO, DEFAULT_BRANCH must be accessible in all modules after main() sets them
    - _LOG_FILE_HANDLE and _LOCK_FD globals: must remain in utils.py and be importable by pipeline.py
    
    Failure modes:
    - ImportError: a moved function references a global that wasn't moved to the same module
    - NameError: a function body references another function that was moved to a different module — fix by adding the import
    - Test import failure: test files doing from dokima import slugify break — update to from utils import slugify
    - DeepSeek model quirk: the parser's verify_spec_quality() function must still work after being moved to utils.py (it's self-referential — tests itself in spec validation)
    
    Contract invariants:
    - Before refactoring: python3 -m pytest tests/ -q passes N tests. After refactoring: same N tests pass.
    - dokima --help output must be byte-identical before and after
    - Checkpoint JSON schema unchanged — old checkpoints must load after refactoring
    - _redact_secrets() redacts the same token values before and after
    - _sanitize_prompt() produces identical output for all known injection patterns (F001 test vectors)
    
    12. Panel Split
    
    Wave 1 (parallel, 2 coders):
    - Task 1 (utils.py) — coder A
    - Task 3 (tasks.py) — coder B
    
    Wave 2 (parallel, 2 coders):
    - Task 2 (agent.py) — coder A
    - Task 4 (roadmap.py) — coder B
    
    Wave 3 (sequential, 1 coder):
    - Task 5 (pipeline.py)
    
    Wave 4 (sequential, 1 coder):
    - Task 6 (main dokima refactor)
    
    Wave 5 (sequential, 1 coder):
    - Task 7 (test imports)
    - Task 8 (integration validation)
    
    Total: 5 waves, max 2 coders parallel
    
    13. Build & Deploy
    
    No deployment change. Dokima remains a single entry-point script at dokima. The 5 module files live alongside it in the project root. No new environment variables. No CI changes.
    
    Build verification: python3 -m py_compile dokima utils.py agent.py tasks.py roadmap.py pipeline.py
    
    14. Risk Register
    
    Risk: Circular imports between modules
    Severity: MEDIUM
    Mitigation: Define dependency DAG before coding: utils ← agent, utils ←
      tasks ← roadmap, utils+agent+tasks+roadmap ← pipeline ← dokima
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
    Mitigation: Task 7 specifically handles test imports; run tests after
      every module move
    Trigger: Test failure after Task 6
    ────────────────────────────────────────
    Risk: Coder agent loads wrong module for fix
    Severity: LOW
    Mitigation: File hints in coder prompt include module paths;
      _extract_code_context reads from correct file
    Trigger: Coder modifies moved function in old location
    ────────────────────────────────────────
    Risk: DeepSeek strips module-qualified names
    Severity: LOW
    Mitigation: Module names are simple (no hyphens); from utils import
      slugify is standard Python
    Trigger: ImportError with mangled module names
    
    15. Anti-Creep
    
    Features explicitly NOT in scope:
    - No package structure (dokima/ directory with init.py) — flat files in project root
    - No type annotations — keep existing comment style
    - No new abstractions or refactoring beyond moving functions — no "while we're at it" improvements
    - No test restructuring — test files stay where they are, only import paths change
    - No new CLI commands or flags
    - No documentation site updates beyond MAINTAINERS.md
    - No setup.py or pyproject.toml — dokima remains dependency-free
    
    16. Sign-Off Checklist
    
    - [ ] All 5 module files exist: utils.py, agent.py, tasks.py, roadmap.py, pipeline.py
    - [ ] dokima script is under 250 lines (imports + main + run_pipeline entry)
    - [ ] python3 -m py_compile dokima utils.py agent.py tasks.py roadmap.py pipeline.py passes
    - [ ] Full test suite passes: python3 -m pytest tests/ -q — same test count as pre-refactoring
    - [ ] Full pipeline runs end-to-end with a test feature
    - [ ] dokima --help output unchanged
    - [ ] Checkpoint resume works (old checkpoint loads after refactoring)
    - [ ] --fix mode discovers and fixes a BLOCKED PR
    - [ ] No circular imports detected
    - [ ] MAINTAINERS.md updated with new module structure
    - [ ] No behavioral regressions confirmed by TL review
    
    
    Confidence: High — the function boundaries are clear, the dependency DAG is well-defined (utils → agent/tasks → roadmap → pipeline → dokima), and this is mechanical code relocation with zero logic changes. The 495+ existing tests serve as the regression safety net.
    
    Impact: HIGH — this is a structural change to the entire codebase. Every function moves, every import changes, and the main script is rewritten. However, the risk is mitigated by the fact that behavior is preserved and the test suite covers all phases.