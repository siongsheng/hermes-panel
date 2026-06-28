# F020: Structured CLI Output (`--help-json`)

Now I have full context on the project. Let me produce the corrected, complete spec.
    
    
    
    Spec: F020 — Structured CLI Output (--help-json)
    
    Version: 1.0  
    Status: Ready for Implementation  
    Confidence: High  
    Impact: LOW  
    Feature ID: F020  
    Dependencies: None
    
    
    
    1. Executive Summary
    
    dokima --help-json outputs the complete CLI surface (commands, flags, env vars) as structured JSON, consumed by the docs site to auto-generate the CLI reference page. No more manual sync between code and docs. This is a single-file change with no external dependencies — add a JSON serialization function, register the flag, and exit. Confidence is High because the feature is purely additive, no state mutation, no pipeline interaction.
    
    
    
    2. Constitution Check
    
    Axiom: Solves user's own pain?
    Status: ✅ Yes
    Notes: Roadmap: "As a docs maintainer… No more manual sync between code
      and docs."
    ────────────────────────────────────────
    Axiom: Weekend-buildable?
    Status: ✅ Yes
    Notes: ~100 LOC, 4 tasks, ~1 hour total
    ────────────────────────────────────────
    Axiom: Boring and proven?
    Status: ✅ Yes
    Notes: Python json.dumps — no new frameworks
    ────────────────────────────────────────
    Axiom: Avoids AI hype?
    Status: ✅ Yes
    Notes: Pure CLI metadata export
    
    Verdict: PASS. No misalignments.
    
    
    
    3. Ponytail Guard — Pre-Spec Review
    
    Rung: 1. Does this need to exist?
    Check: There's no machine-readable CLI reference
    Result: ✅ Yes
    ────────────────────────────────────────
    Rung: 2. Already in codebase?
    Check: show_help() prints text; no JSON output exists
    Result: No
    ────────────────────────────────────────
    Rung: 3. Stdlib does it?
    Check: json.dumps() — yes, stdlib
    Result: Rung 3
    ────────────────────────────────────────
    Rung: 4. Native platform feature?
    Check: Python json module
    Result: Rung 3
    ────────────────────────────────────────
    Rung: 5. Installed dependency?
    Check: Not needed
    Result: N/A
    
    Verdict: Rung 3 — stdlib json output. Feature is justified, no overbuilding.
    
    
    
    4. Impact
    
    Docs site gets a single source of truth for CLI reference — every --help-json call reflects the current code's actual commands and flags, eliminating manual sync drift.
    
    
    
    5. What Changed
    
    - dokima: Add --help-json flag detection in main() flag-scanning loop (~6 lines)
    - dokima: Add show_help_json() function that builds and prints the JSON structure (~70 lines)
    - dokima: Early-exit dispatch: if is_help_json: show_help_json() (~3 lines, right after the existing is_help check at line ~5440)
    - tests/test_f020_help_json.py: New test file — verify JSON output schema, completeness, and --help-json flag not breaking --help (~30 lines)
    
    
    
    6. Decision Table
    
    SINGLE APPROACH: Add --help-json flag to the existing main() flag-scanning loop, call a new show_help_json() that builds a dict from a manually-maintained metadata constant and prints json.dumps().
    
    No comparison table needed — the approach is obvious: same pattern as --help → show_help(), but output JSON via stdlib. No alternative designs exist that would change the trade-off surface.
    
    
    
    7. API / Interface Proposal
    
    New flag: --help-json
    
    Output schema:
    
    json
    {
      "tool": "dokima",
      "commands": [
        {"name": "<name>", "syntax": "<usage string>", "description": "<one-line>"}
      ],
      "flags": [
        {"flag": "--flag-name", "args": "<value-hint or null>", "env_var": "PANEL_... or null", "description": "<one-line>"}
      ],
      "env_vars": [
        {"name": "PANEL_...", "description": "<one-line>", "related_flag": "--flag or null"}
      ]
    }
    
    
    Exit code: 0 on success. Output goes to stdout.
    
    Backward compatibility: Fully compatible. --help is unchanged. --help-json is a new, mutually-exclusive flag.
    
    
    
    8. Security Considerations
    
    N/A — no attack surface change. --help-json reads only hardcoded string constants, no user input beyond the flag presence check. No filesystem access, no network, no secrets.
    
    
    
    9. Documentation Impact
    
    README: Add --help-json to the COMMANDS section of HELP_TEXT (the constant itself gets updated as part of Task 1).
    
    
    
    10. Task Breakdown
    
    Task 1: Define the JSON metadata constant
    Files: dokima
    Dependencies: none
    Parallelizable: no (prerequisite for Task 2)
    Description: Add a CLI_METADATA dict constant containing all commands, flags, and env_vars — deduplicated from HELP_TEXT and the main() flag loop. This is the single source of truth that both show_help_json() and future updates draw from.
    
    Task 2: Implement show_help_json() function
    Files: dokima
    Dependencies: Task 1
    Parallelizable: no
    Description: Implement show_help_json() — prints json.dumps(CLI_METADATA, indent=2) to stdout and calls sys.exit(0). Place it adjacent to show_help() (after line ~1231).
    
    Task 3: Register --help-json flag and dispatch in main()
    Files: dokima
    Dependencies: Task 2
    Parallelizable: no
    Description: Add is_help_json = False to the flag-scanning init block, add if arg == "--help-json": is_help_json = True; continue to the arg loop, and add if is_help_json: show_help_json() in the early-exit block right before if is_help: show_help().
    
    Task 4: Add tests for --help-json
    Files: tests/test_f020_help_json.py
    Dependencies: Task 3
    Parallelizable: yes (parallelizable with nothing — no other file touched)
    Description: Create test file with: (a) verify --help-json produces valid JSON, (b) verify schema has required top-level keys (tool, commands, flags, env_vars), (c) verify every command and flag from HELP_TEXT is represented, (d) verify --help still works unchanged, (e) verify exit code 0.
    
    Task 5: Run full test suite and verify
    Files: none (verification only)
    Dependencies: Task 4
    Parallelizable: no
    Description: Run python3 -m pytest tests/ -q to confirm zero regressions, then run python3 dokima --help-json | python3 -m json.tool to verify real output.
    
    
    
    11. Test Plan (MANDATORY)
    
    Happy path:
    - dokima --help-json outputs valid, parseable JSON to stdout, exits 0
    - All 6 commands from HELP_TEXT COMMANDS section are present in JSON
    - All 11 flags from HELP_TEXT FLAGS section are present in JSON
    - All PANEL_* env vars referenced in the codebase are present in JSON
    
    Edge cases:
    - Running dokima --help-json with no other args — should exit 0 (not demand a feature description)
    - Running dokima --help-json in a non-git directory — should exit 0 (no PROJECT_DIR validation needed for help flags)
    - Running dokima --help-json /some/path — should still exit 0, ignoring the extra arg
    - Running dokima --help-json --help — if both flags present, --help-json should win (first-match priority, consistent with the current flag loop order)
    - JSON output is valid UTF-8, no control characters in description strings
    
    Failure modes:
    - json.dumps() failure (should never happen with a static dict, but verify it doesn't crash)
    - stdout pipe broken (dokima --help-json | head → BrokenPipeError should be caught silently, same as Python's default SIGPIPE behavior)
    - Disk full (shouldn't matter — no file writes)
    
    Contract invariants:
    - dokima --help-json MUST exit without requiring PROJECT_DIR validation or AGENTS.md presence
    - HELP_TEXT and CLI_METADATA MUST stay in sync — any command/flag added to HELP_TEXT MUST also be added to CLI_METADATA
    - --help behavior is untouched — same output, same exit code
    
    
    
    12. Panel Split
    
    Wave: 1
    Tasks: Task 1 → Task 2 → Task 3
    Parallel Coder Count: 1 (sequential chain, same file)
    ────────────────────────────────────────
    Wave: 2
    Tasks: Task 4 (tests)
    Parallel Coder Count: 1 (different file, but depends on Task 3)
    ────────────────────────────────────────
    Wave: 3
    Tasks: Task 5 (verification)
    Parallel Coder Count: 1 (final check)
    
    Only 1 coder needed throughout — tasks touch the same file sequentially.
    
    
    
    13. Build & Deploy
    
    - CI: python3 -m pytest tests/ -q passes
    - Build: python3 -c "compile(open('dokima').read(), 'dokima', 'exec')" passes
    - No deployment: dokima is a CLI script, no deployment step
    - No new env vars needed
    
    
    
    14. Risk Register
    
    #: 1
    Risk: CLI_METADATA drifts from HELP_TEXT over time
    Severity: Medium
    Mitigation: Convention comment in both constants: "KEEP IN SYNC with
      CLI_METADATA / HELP_TEXT"; test verifies coverage
    Trigger: New flag/command added but only one constant updated
    ────────────────────────────────────────
    #: 2
    Risk: --help-json blocks on PROJECT_DIR validation
    Severity: Low
    Mitigation: Early-exit dispatch happens BEFORE project setup in main()
    Trigger: If dispatch order changes in future refactor
    ────────────────────────────────────────
    #: 3
    Risk: JSON schema changes break docs site consumer
    Severity: Low
    Mitigation: Schema documented in this spec; docs site pins to a version
    Trigger: Schema change without docs site update
    ────────────────────────────────────────
    #: 4
    Risk: --help-json flag collides with future flag
    Severity: Low
    Mitigation: Standard flag naming convention; --help-* namespace is small
    Trigger: Adding another --help-* flag
    
    
    
    15. Anti-Creep
    
    NOT in scope:
    - --help-json --pretty / --help-json --compact formatting flags — use | python3 -m json.tool for pretty-print
    - OpenAPI / JSON Schema generation — this is CLI metadata, not an API spec
    - --help-yaml or --help-toml — YAGNI
    - Auto-generating HELP_TEXT from CLI_METADATA — two-way sync is overengineering for P2
    - Outputting version info in --help-json (that's F021's domain)
    - Making HELP_TEXT dynamically generated from CLI_METADATA at runtime
    
    
    
    16. Sign-Off Checklist
    
    - [ ] CLI_METADATA constant covers all 6 COMMANDS, all 11 FLAGS, all PANEL_* env vars
    - [ ] --help-json exits 0 without requiring PROJECT_DIR/AGENTS.md
    - [ ] --help output is unchanged (diff HELP_TEXT before/after)
    - [ ] JSON output validates with python3 -m json.tool
    - [ ] Tests pass: python3 -m pytest tests/test_f020_help_json.py -v
    - [ ] Full test suite passes: python3 -m pytest tests/ -q
    - [ ] Build check passes: python3 -c "compile(open('dokima').read(), 'dokima', 'exec')"
    - [ ] HELP_TEXT updated to include --help-json in COMMANDS section
    - [ ] No new files created (tests/test_f020_help_json.py is the only new file)
    - [ ] Risk #1 mitigation: sync comment present in both HELP_TEXT and CLI_METADATA