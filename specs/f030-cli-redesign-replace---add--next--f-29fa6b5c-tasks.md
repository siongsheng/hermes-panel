# Task Breakdown: F030: CLI redesign: replace --add/--next/--fix/--status/--stop/--kill/--list-crons/--version/--upgrade/--release with proper subcommands (dokima add, dokima next, etc). Flags (--force-full, --max-parallel) keep -- prefix. Update all tests, scripts, AGENTS.md, roadmap, and docs.

### Task 1: Replace flag-scanning loop with argparse subparsers in dokima entry point
**Files:** dokima
**Dependencies:** [none]
**Description:** Replace flag-scanning loop with argparse subparsers in dokima entry point

### Task 2: Update HELP_TEXT in utils.py to reflect subcommand syntax
**Files:** utils.py
**Dependencies:** 1
**Description:** Update HELP_TEXT in utils.py to reflect subcommand syntax

### Task 3: Update CLI_METADATA in utils.py for --help-json
**Files:** utils.py
**Dependencies:** 1
**Description:** Update CLI_METADATA in utils.py for --help-json

### Task 4: Update test_f021_version.py for subcommand dispatch
**Files:** tests/test_f021_version.py
**Dependencies:** 1
**Description:** Update test_f021_version.py for subcommand dispatch

### Task 5: Update test_f020_help_json.py for subcommand names
**Files:** tests/test_f020_help_json.py
**Dependencies:** 3
**Description:** Update test_f020_help_json.py for subcommand names

### Task 6: Update test_control_panel.py for subcommand handler names
**Files:** tests/test_control_panel.py
**Dependencies:** 1
**Description:** Update test_control_panel.py for subcommand handler names

### Task 7: Update test_f024_release.py for dokima release subcommand
**Files:** tests/test_f024_release.py
**Dependencies:** 1
**Description:** Update test_f024_release.py for dokima release subcommand

### Task 8: Update test_main_integration.py for dokima next subcommand
**Files:** tests/test_main_integration.py
**Dependencies:** 1
**Description:** Update test_main_integration.py for dokima next subcommand

### Task 9: Update test_fix_mode.py for dokima fix subcommand
**Files:** tests/test_fix_mode.py
**Dependencies:** 1
**Description:** Update test_fix_mode.py for dokima fix subcommand

### Task 10: Update remaining test files for CLI invocation changes
**Files:** tests/test_edge_cases.py, tests/test_final_edge.py, tests/test_final_coverage.py, tests/test_rich_pipeline.py, tests/test_pipeline_integration.py, tests/test_f023_self_healing.py, tests/test_unit_helpers.py, tests/test_sandbox_fixes.py, tests/test_triple_bug_fix.py, tests/test_installer.py
**Dependencies:** 1
**Description:** Update remaining test files for CLI invocation changes

### Task 11: Update README.md examples
**Files:** README.md
**Dependencies:** 1
**Description:** Update README.md examples

### Task 12: Update MAINTAINERS.md command references
**Files:** MAINTAINERS.md
**Dependencies:** 1
**Description:** Update MAINTAINERS.md command references

### Task 13: Update AGENTS.md (if needed)
**Files:** AGENTS.md
**Dependencies:** 1
**Description:** Update AGENTS.md (if needed)

### Task 14: Update install.sh references
**Files:** install.sh
**Dependencies:** 1
**Description:** Update install.sh references

### Task 15: Run full test suite and fix failures
**Files:** (any failing test file)
**Dependencies:** 1, 14
**Description:** Run full test suite and fix failures
