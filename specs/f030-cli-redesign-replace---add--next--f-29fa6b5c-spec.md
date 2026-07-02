# F030: CLI redesign: replace --add/--next/--fix/--status/--stop/--kill/--list-crons/--version/--upgrade/--release with proper subcommands (dokima add, dokima next, etc). Flags (--force-full, --max-parallel) keep -- prefix. Update all tests, scripts, AGENTS.md, roadmap, and docs.

Now I have a complete picture. Let me produce the full corrected spec.
    
    
    
    Position: Complete F030 CLI redesign spec with all required sections. (High confidence)
    
    SPEC: F030 — CLI Subcommand Redesign
    
    Version: 1.1.0 (corrected — added Impact, What Changed, proper Task headers)
    Status: Awaiting Sign-Off
    Confidence: High
    
    
    
    1. Executive Summary
    
    Replace Dokima's flat --flag CLI interface with proper argparse subcommands (dokima add, dokima next, dokima fix, dokima status, dokima stop, dokima kill, dokima list-crons, dokima version, dokima upgrade, dokima release). Boolean flags that modify subcommand behaviour (--force-full, --max-parallel, --interactive, --skip-autofix, etc.) retain their -- prefix. dokima "Feature description" (no subcommand) remains the default pipeline trigger. This is a P2 quality-of-life change — no new functionality, just ergonomic CLI restructuring. Impacts ~2,500 LOC across 20+ files.
    
    2. Constitution Check
    
    Axiom: Solves user's own pain?
    Status: YES
    Notes: Shaun has complained about --flag confusion vs proper subcommands
    ────────────────────────────────────────
    Axiom: Weekend-buildable?
    Status: YES
    Notes: Pure refactor — no new logic, ~2,500 LOC touched (most mechanical)
    ────────────────────────────────────────
    Axiom: Evidence people will pay?
    Status: N/A
    Notes: Internal tool — user is the beneficiary
    ────────────────────────────────────────
    Axiom: Tech stack boring and proven?
    Status: YES
    Notes: Python argparse — stdlib, zero dependencies
    ────────────────────────────────────────
    Axiom: Avoids AI hype categories?
    Status: YES
    Notes: Pure CLI ergonomics
    ────────────────────────────────────────
    Axiom: Existing assets reused?
    Status: YES
    Notes: All handler functions (handle_status, do_release, etc.) stay — only
      dispatch path changes
    
    3. Impact Assessment
    
    Grounded in actual file analysis:
    
    
    dokima              +120/-80  (replace flag-scanning loop with argparse subparsers)
    utils.py             +60/-30  (update HELP_TEXT and CLI_METADATA)
    tests/test_f021_version.py    +40/-30  (--version → version subcommand, --upgrade → upgrade)
    tests/test_f020_help_json.py  +30/-20  (command name changes in assertions)
    tests/test_control_panel.py   +20/-15  (--status/--stop/--kill → subcommands)
    tests/test_f024_release.py    +40/-30  (--release → release subcommand)
    tests/test_main_integration.py +15/-10  (--next → next subcommand)
    tests/test_help_text.py        +5/-3   (PANEL_MAX_PARALLEL ref still valid)
    tests/test_fix_mode.py         +10/-5  (--fix → fix subcommand)
    tests/test_installer.py        +5/-3   (if references --version/--help)
    tests/test_edge_cases.py       +5/-3   (--next → next)
    tests/test_final_edge.py       +5/-3
    tests/test_final_coverage.py   +5/-3
    tests/test_rich_pipeline.py    +5/-3
    tests/test_pipeline_integration.py +5/-3
    tests/test_f023_self_healing.py    +5/-3
    tests/test_unit_helpers.py         +5/-3
    tests/test_sandbox_fixes.py        +5/-3
    tests/test_triple_bug_fix.py       +5/-3
    README.md              +30/-20  (all examples)
    MAINTAINERS.md         +20/-15  (Common Commands section + test suite map)
    docs/setup.md           +5/-5   (prereq checks reference --version not our CLI)
    docs/pipeline.md         +0/-0  (no dokima CLI references found via rg)
    AGENTS.md                +0/-0  (no CLI flag references)
    specs/roadmap.md          +2/-2  (update F030 description to reflect subcommands)
    
    
    Total affected: ~2 files (core) + 16 test files + 3 doc files = ~21 files, ~500 LOC changed.
    
    4. What Changed (from current behavior)
    
    Before (F029): dokima --add "Feature"
    After (F030): dokima add "Feature"
    ────────────────────────────────────────
    Before (F029): dokima --next [dir]
    After (F030): dokima next [dir]
    ────────────────────────────────────────
    Before (F029): dokima --continuous [dir]
    After (F030): dokima continuous [dir] or dokima next --continuous
    ────────────────────────────────────────
    Before (F029): dokima --fix [dir]
    After (F030): dokima fix [dir]
    ────────────────────────────────────────
    Before (F029): dokima --status [dir]
    After (F030): dokima status [dir]
    ────────────────────────────────────────
    Before (F029): dokima --stop [dir]
    After (F030): dokima stop [dir]
    ────────────────────────────────────────
    Before (F029): dokima --kill [dir]
    After (F030): dokima kill [dir]
    ────────────────────────────────────────
    Before (F029): dokima --list-crons
    After (F030): dokima list-crons
    ────────────────────────────────────────
    Before (F029): dokima --version
    After (F030): dokima version
    ────────────────────────────────────────
    Before (F029): dokima --upgrade
    After (F030): dokima upgrade
    ────────────────────────────────────────
    Before (F029): dokima --release patch
    After (F030): dokima release patch
    ────────────────────────────────────────
    Before (F029): dokima "Feature" [dir]
    After (F030): dokima "Feature" [dir] (unchanged)
    ────────────────────────────────────────
    Before (F029): dokima init "desc" [dir]
    After (F030): dokima init "desc" [dir] (unchanged)
    ────────────────────────────────────────
    Before (F029): dokima --help / -h
    After (F030): dokima --help / dokima -h (unchanged)
    ────────────────────────────────────────
    Before (F029): dokima --help-json
    After (F030): dokima --help-json (unchanged)
    ────────────────────────────────────────
    Before (F029): dokima --map [dir]
    After (F030): dokima --map [dir] (unchanged — not in scope)
    
    Key design decision: --continuous becomes a flag on dokima next (dokima next --continuous) rather than a separate subcommand, since it's a mode modifier, not a distinct operation. The bare dokima continuous is accepted as shorthand via argparse alias.
    
    Backward compatibility: NOT provided. This is a clean break. Users update their muscle memory. The dokima "Feature" default path is unchanged — that's the 95% case.
    
    5. Feature Breakdown
    
    Task 1: Replace flag-scanning loop with argparse subparsers in dokima entry point
    Files: dokima
    Dependencies: none
    Parallelizable: no (touches the central dispatch — must go first)
    Description: Replace the manual for arg in sys.argv[1:] flag-scanning loop (lines 87-231 of dokima) with argparse subparsers. Each former --flag becomes a subcommand: add, next, fix, status, stop, kill, list-crons, version, upgrade, release. Boolean flags (--force-full, --max-parallel, --interactive, --skip-autofix, --skip-auto-archive, --skip-human-gate, --resume, --no-resume, --fix-all, --dry-run) attach to their respective subcommands as optional args. The default positional "Feature" [dir] remains the no-subcommand path. --continuous becomes --continuous flag on the next subcommand. --priority becomes --priority flag on add. --map stays as --map flag on the default path (not subcommand-ized in this feature). --help-json stays as top-level flag. The --answers flag stays on default and fix subcommands.
    
    Task 2: Update HELP_TEXT in utils.py to reflect subcommand syntax
    Files: utils.py
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Rewrite HELP_TEXT (lines 54-95) to show subcommand syntax instead of --flag syntax. The COMMANDS section becomes: dokima add, dokima next, dokima fix, dokima status, dokima stop, dokima kill, dokima list-crons, dokima version, dokima upgrade, dokima release. Keep dokima "Feature" [dir] and dokima init "desc" [dir] as-is. Add a MODIFIER FLAGS section for flags that apply across subcommands.
    
    Task 3: Update CLI_METADATA in utils.py for --help-json
    Files: utils.py
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Update CLI_METADATA dict (lines 97-142) to rename command entries: "--add" → "add", "--next" → "next", etc. Update syntax strings: "dokima --add" → "dokima add", "dokima --next" → "dokima next", etc. Keep flag and env_var entries unchanged (they stay with -- prefix).
    
    Task 4: Update test_f021_version.py for subcommand dispatch
    Files: tests/test_f021_version.py
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Change all _run("--version") calls to _run("version"). Change _run("--upgrade") to _run("upgrade"). Change _run("-v") to also accept version. Update assertion messages referencing flag names. The function behavior is unchanged — only the CLI invocation changes.
    
    Task 5: Update test_f020_help_json.py for subcommand names
    Files: tests/test_f020_help_json.py
    Dependencies: [Task 3]
    Parallelizable: yes
    Description: Update assertions that check command names: "name": "--version" → "name": "version", "name": "--upgrade" → "name": "upgrade", etc. The run_help_json() helper stays — --help-json is not subcommand-ized. Assertions about flag/env_var entries remain unchanged.
    
    Task 6: Update test_control_panel.py for subcommand handler names
    Files: tests/test_control_panel.py
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: The handler functions (show_help, handle_status, handle_stop, handle_kill, handle_list_crons) are NOT renamed — only their dispatch path changes. Tests that call these directly via panel.show_help() etc. require no changes. Tests that run the full script with subprocess need updating: any _run("--status") → _run("status"), etc. Review the file — most tests here call handlers directly; confirm no subprocess invocations need updating.
    
    Task 7: Update test_f024_release.py for dokima release subcommand
    Files: tests/test_f024_release.py
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Change _run("--release", "patch") to _run("release", "patch"). Change _run("--release", "invalid") to _run("release", "invalid"). Change _run("--release", "patch", "--dry-run") to _run("release", "patch", "--dry-run"). The do_release() function itself is unchanged. Update help-text assertions: "--release" → "release" in help output checks (or check for the new subcommand format).
    
    Task 8: Update test_main_integration.py for dokima next subcommand
    Files: tests/test_main_integration.py
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Change sys.argv = ["dokima", "--next", project_dir] to sys.argv = ["dokima", "next", project_dir]. All 4 occurrences. The run_next_setup() function is unchanged — only the argv dispatch changes.
    
    Task 9: Update test_fix_mode.py for dokima fix subcommand
    Files: tests/test_fix_mode.py
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Review for any --fix flag references in subprocess calls or sys.argv manipulation. Change to fix subcommand. If tests only call internal functions directly, no changes needed.
    
    Task 10: Update remaining test files for CLI invocation changes
    Files: tests/test_edge_cases.py, tests/test_final_edge.py, tests/test_final_coverage.py, tests/test_rich_pipeline.py, tests/test_pipeline_integration.py, tests/test_f023_self_healing.py, tests/test_unit_helpers.py, tests/test_sandbox_fixes.py, tests/test_triple_bug_fix.py, tests/test_installer.py
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Mechanical search-and-replace in any remaining test files: "--next" → "next", "--fix" → "fix", etc. where they appear in subprocess argv or sys.argv. Functions called directly (not via subprocess) need no changes. Run rg '"--next"|"--fix"|"--add"|"--status"|"--stop"|"--kill"' tests/ to find all occurrences.
    
    Task 11: Update README.md examples
    Files: README.md
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Update all CLI examples: dokima --help stays, dokima --fix → dokima fix, dokima --answers stays (it's a flag on the default path). The --fix mode documentation paragraph updates to fix mode.
    
    Task 12: Update MAINTAINERS.md command references
    Files: MAINTAINERS.md
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Update Common Commands section: python3 dokima --next . → python3 dokima next ., python3 dokima --add "..." → python3 dokima add "...", python3 dokima --fix --fix-all . → python3 dokima fix --fix-all ., python3 dokima --status . → python3 dokima status ., python3 dokima --continuous . → python3 dokima next --continuous ., python3 dokima --next --force-full . → python3 dokima next --force-full .. Update Test Suite Map entry for test_add_to_roadmap.py from --add to add.
    
    Task 13: Update AGENTS.md (if needed)
    Files: AGENTS.md
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Review AGENTS.md — the current version has no CLI flag references. Verify and skip if clean.
    
    Task 14: Update install.sh references
    Files: install.sh
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: The dokima --help reference on line 121 stays (--help is not subcommand-ized). No other CLI flags found. Verify and skip if clean.
    
    Task 15: Run full test suite and fix failures
    Files: (any failing test file)
    Dependencies: [Tasks 1-14]
    Parallelizable: no (serial — must run after all changes)
    Description: Run python3 -m pytest tests/ -q and fix any remaining assertion failures. Expected pattern: tests that do string-matching on help output or CLI metadata may fail on subcommand name format. All handler logic is unchanged — only dispatch path and help text changes.
    
    6. Data Model
    
    No new entities. No schema changes. The argparse Namespace object replaces the manual boolean flags, but this is transient — no persistence change.
    
    Affected global variables in dokima (NOT removed, only their assignment path changes):
    - FORCE_FULL — now set from args.force_full instead of flag scan
    - SKIP_AUTOFIX — now set from args.skip_autofix
    - SKIP_HUMAN_GATE — now set from args.skip_human_gate
    - RESUME — now set from args.resume
    - max_parallel_override — now set from args.max_parallel
    - DEFAULT_BRANCH — unchanged (set from env)
    
    7. API Routes
    
    N/A — this is a CLI tool, not a web service.
    
    8. Component Tree
    
    
    dokima (entry point)
    ├── argparse.ArgumentParser
    │   ├── Default path (no subcommand): positional "feature" + optional "dir" + flags
    │   ├── Subparser: init  → run_init()
    │   ├── Subparser: add   → run_add_to_roadmap()
    │   ├── Subparser: next  → run_next_setup() [+ --continuous flag]
    │   ├── Subparser: fix   → run_fix_mode() [+ flags]
    │   ├── Subparser: status → handle_status()
    │   ├── Subparser: stop   → handle_stop()
    │   ├── Subparser: kill   → handle_kill()
    │   ├── Subparser: list-crons → handle_list_crons()
    │   ├── Subparser: version   → print(VERSION); sys.exit(0)
    │   ├── Subparser: upgrade   → check_upgrade()
    │   └── Subparser: release   → do_release()
    ├── Top-level flags: --help, -h, --help-json, --map, --map-full
    └── Handler functions (unchanged, in utils.py/roadmap.py/pipeline.py)
    
    
    9. COTS Build-vs-Buy
    
    Component: argparse
    Decision: Buy (stdlib)
    Justification: Python 3.6+ stdlib — already available, zero deps
    ────────────────────────────────────────
    Component: click/typer
    Decision: Reject
    Justification: Adds dependency; argparse is sufficient for this CLI
      complexity
    ────────────────────────────────────────
    Component: docopt
    Decision: Reject
    Justification: Unmaintained; argparse is the standard
    
    10. Test Plan (MANDATORY)
    
    Happy Path
    - dokima version prints dokima vX.Y.Z and exits 0
    - dokima status /path/to/repo shows pipeline state and exits 0
    - dokima add "Feature desc" adds to roadmap and exits 0
    - dokima next /path/to/repo starts pipeline and runs
    - dokima next --continuous /path/to/repo starts continuous loop
    - dokima fix /path/to/repo detects blocked PR and fixes
    - dokima release patch --dry-run prints plan without committing
    - dokima --help-json outputs valid JSON with subcommand names
    
    Edge Cases
    - dokima with no args: prints usage (same as before)
    - dokima --help: prints help text with subcommand syntax
    - dokima -h: same as --help
    - dokima next --max-parallel=3 /path: flag on subcommand works
    - dokima version --help: shows version subcommand help
    - dokima version extra-arg: should ignore or error clearly (argparse default: error)
    - dokima release: missing bump type → argparse error message
    - dokima --help-json version: --help-json wins (same behavior as before)
    - Hyphenated subcommand: dokima list-crons — argparse handles this naturally
    - dokima "Feature with --add in the name": positional, not parsed as subcommand
    - dokima unknown-subcommand: argparse error with "invalid choice" message
    
    Failure Modes
    - argparse parse failure: exits 2 with usage message (argparse default)
    - Subcommand handler raises exception: crash is identical to before — handlers are unchanged
    - dokima next without AGENTS.md: same error as before
    - dokima release in non-git dir: same error as before
    - Ctrl-C during subcommand: SIGINT handling unchanged
    
    Contract Invariants
    - All handler functions (handle_status, handle_stop, handle_kill, handle_list_crons, show_help, show_help_json, check_upgrade, do_release, run_add_to_roadmap, run_next_setup, run_fix_mode, run_init) retain identical signatures and behavior
    - FORCE_FULL, SKIP_AUTOFIX, SKIP_HUMAN_GATE, RESUME, max_parallel_override globals are set identically — only the assignment source changes
    - --help-json output format: same structure, only command name and syntax fields change
    - dokima "Feature" [dir] default path: completely unchanged behavior
    - Test count: 679 tests must still pass (same number, adjusted assertions)
    
    11. Panel Split
    
    Wave 1 (Task 1 only — must land first):
    - Task 1: argparse refactor in dokima (sequential bottleneck)
    
    Wave 2 (all parallel — no shared files):
    - Task 2: HELP_TEXT update (utils.py)
    - Task 3: CLI_METADATA update (utils.py) — shares utils.py with Task 2, so this MUST be sequential after Task 2 if the same file is touched, OR they can be merged into one task.
    - Tasks 4-14: all test/doc updates — each touches different files
    
    Correction: Tasks 2 and 3 both touch utils.py. Merge them into a single task OR run sequentially.
    
    Revised waves:
    - Wave 1: Task 1 (dokima — alone, serial)
    - Wave 2: Tasks 2+3 merged (utils.py), Tasks 4-14 (all parallel — different files)
    - Wave 3: Task 15 (test suite verification — serial)
    
    Coder agents needed: 2-3 (Wave 1: 1 agent, Wave 2: up to 5 parallel agents for test/doc files, Wave 3: 1 agent)
    
    12. Build & Deploy
    
    - Deploy: No deployment — dokima is a local script. install.sh unchanged.
    - CI: python3 -m pytest tests/ -q must pass with 679 tests
    - Env vars: No new env vars. All existing PANEL_* vars continue to work as env fallbacks.
    - Release: dokima release patch (the new invocation) must still work for releasing this change.
    
    13. Risk Register
    
    #: 1
    Risk: argparse changes argv parsing order — --help-json before subcommand
      may break
    Severity: MEDIUM
    Mitigation: Test dokima --help-json version explicitly; argparse parent
      parser handles this
    Trigger: Test failure
    ────────────────────────────────────────
    #: 2
    Risk: Hyphenated subcommand list-crons may confuse argparse dest naming
    Severity: LOW
    Mitigation: Argparse converts list-crons → list_crons dest; verify with
      explicit dest=
    Trigger: Test failure
    ────────────────────────────────────────
    #: 3
    Risk: dokima "Feature with --flags" positional overlapping subcommand
      parsing
    Severity: LOW
    Mitigation: Argparse stops at first positional or subcommand; test
      confirms
    Trigger: User report
    ────────────────────────────────────────
    #: 4
    Risk: CI scripts / cron jobs using old --flag syntax break silently
    Severity: HIGH
    Mitigation: Search all cron jobs, CI configs, and scripts BEFORE merge;
      document migration
    Trigger: Cron job failure
    ────────────────────────────────────────
    #: 5
    Risk: dokima --continuous as separate flag breaks — now dokima next
      --continuous
    Severity: MEDIUM
    Mitigation: Document migration prominently; consider alias/backcompat for
      1 release cycle
    Trigger: User confusion
    ────────────────────────────────────────
    #: 6
    Risk: Test assertions about help text format fail on subcommand syntax
    Severity: LOW
    Mitigation: All test updates included in tasks 4-10; final test run
      catches stragglers
    Trigger: Test failure
    
    14. Anti-Creep
    
    Features explicitly NOT in scope:
    - NO backward compatibility shims (--add aliases). Clean break.
    - NO new subcommands beyond the 10 listed. --map stays a flag, not a subcommand.
    - NO plugin system or dynamic subcommand discovery.
    - NO shell completion generation (that's a separate feature).
    - NO changes to handler function internals — pure dispatch refactor.
    - NO changes to install.sh beyond updating --help references (if any).
    - NO changes to dokima init — it's already a positional argument, stays that way.
    - NO nested subcommands (dokima release create vs dokima release). Flat structure only.
    - NO dokima --map → dokima map — map stays as a flag per scope.
    
    15. Sign-Off Checklist
    
    - [ ] argparse subparser design reviewed — all 10 subcommands accounted for
    - [ ] --continuous decision confirmed: flag on next subcommand, not standalone
    - [ ] --help-json confirmed as top-level flag (not subcommand)
    - [ ] --map confirmed staying as flag (not subcommand-ized)
    - [ ] ALL cron job references searched and migration plan ready
    - [ ] CI scripts (GitHub Actions, if any) searched for old flag syntax
    - [ ] Backward compatibility decision: CLEAN BREAK, no aliases — confirmed
    - [ ] Test plan reviewed — 679 tests must pass after changes
    - [ ] README/MAINTAINERS.md update scope confirmed
    - [ ] Release plan: this feature itself will be released with dokima release patch (new syntax)
    - [ ] No shell injection risk from argparse (stdlib, proven safe)
    - [ ] All handler function signatures confirmed unchanged