# F021: Semantic Versioning + GitHub Releases

Now I have all the intelligence. Let me produce the complete corrected spec.
    
    F021: Semantic Versioning + GitHub Releases
    
    Version: 1.0
    Status: Ready for Implementation
    Confidence: High
    Impact: MEDIUM
    Feature ID: F021
    Dependencies: F020 (done — CLI_METADATA constant exists)
    
    
    
    1. Executive Summary
    
    dokima --version prints the current version from a VERSION file. dokima --upgrade checks GitHub for newer releases and tells the user whether to upgrade. GitHub Releases are created with auto-generated changelogs via gh release create --generate-notes. Three capabilities, ~120 LOC, all additive — no pipeline interaction, no state mutation. Confidence is High because the pattern is identical to F020's flag + early-exit dispatch, and GitHub release tooling is a solved CLI problem.
    
    
    
    2. Constitution Check
    
    Axiom: Solves user's own pain?
    Status: Yes
    Notes: Roadmap user story: "As a user, dokima --version prints the current version." Currently no way to check version or upgrade — users on stale installs never know.
    
    Axiom: Weekend-buildable?
    Status: Yes
    Notes: ~120 LOC across 7 tasks, ~90 minutes total. Version file + 2 flags + gh release wrapper.
    
    Axiom: Boring and proven?
    Status: Yes
    Notes: VERSION file is the oldest versioning pattern in Unix. gh CLI is GitHub's own tool. No new frameworks, no version databases.
    
    Axiom: Avoids AI hype?
    Status: Yes
    Notes: Zero AI. Pure CLI plumbing.
    
    Verdict: PASS. No misalignments.
    
    
    
    3. Ponytail Guard — Pre-Spec Review
    
    Rung: 1. Does this need to exist?
    Check: No --version or --upgrade exists. Users can't check version or know when to upgrade.
    Result: Yes
    
    Rung: 2. Already in codebase?
    Check: Grepped for version, VERSION, version, semver — zero matches. Tags v1.2.0/v1.2.1 exist but are manual and disconnected from the script.
    Result: No
    
    Rung: 3. Stdlib does it?
    Check: open("VERSION").read() + subprocess for gh/git calls. All stdlib.
    Result: Rung 3
    
    Rung: 4. Native platform feature?
    Check: gh release create is GitHub CLI. git tag is git.
    Result: Rung 4 for tooling, Rung 3 for the version read
    
    Verdict: Rung 3-4 — stdlib file read + existing platform tools (gh, git). Feature is justified, no overbuilding.
    
    
    
    4. Decision Table
    
    Option: VERSION file + gh release create
    Simplicity: High — plain text file
    Automation: Manual (gh release create)
    Maintenance: Low
    Verdict: Accept
    ────────────────────────────────────────
    Option: Git tags as version source
    Simplicity: Medium — parse git describe
    Automation: Auto (git tag)
    Maintenance: Medium — requires git repo context
    Verdict: Reject
    ────────────────────────────────────────
    Option: Python package version (setup.py/pyproject.toml)
    Simplicity: Low — overengineered for single script
    Automation: Medium
    Maintenance: High — adds packaging infra
    Verdict: Reject
    ────────────────────────────────────────
    Option: Version in script header comment
    Simplicity: Medium — parse with regex
    Automation: None
    Maintenance: Low — drift risk
    Verdict: Reject
    
    SINGLE APPROACH: VERSION file at repo root is the single source of truth. dokima reads it for --version. --upgrade fetches tags and compares. Releases use gh release create v$(cat VERSION) --generate-notes.
    
    Rationale: VERSION file is dead-simple, works without git (bundled copies still show version), and requires zero parsing. Tags and VERSION can drift — the release command (manual gh release create) enforces they match by reading VERSION at release time.
    
    
    
    5. Impact
    
    Users and developers get version awareness: dokima --version prints the current version, dokima --upgrade reports whether a newer release exists and how to upgrade. GitHub Releases gain auto-generated changelogs from merged PRs, making each release's changes visible without manual curation. No pipeline behavior changes — both flags exit before pipeline init.
    
    
    
    6. What Changed
    
    - VERSION: New file — single source of truth, e.g. "1.2.1"
    - dokima: Read VERSION at module init, add --version flag + dispatch (~12 lines)
    - dokima: Add --upgrade flag, fetch tags, compare versions, print result (~40 lines)
    - dokima: Add --version/--upgrade to HELP_TEXT and CLI_METADATA (~15 lines)
    - tests/test_f021_version.py: New test file — verify --version, --upgrade, edge cases (~40 lines)
    
    
    
    7. API / Interface Proposal
    
    New flags: --version, --upgrade
    
    --version:
      Reads <script_dir>/VERSION, prints to stdout, exits 0.
      Output: "dokima v1.2.1"
      No network, no git, no project dir needed.
    
    --upgrade:
      Checks ~/.local/share/dokima (install.sh path). If not found, prints "Not installed via install.sh — cannot check for upgrades" and exits 0.
      If found: git fetch --tags origin, reads VERSION from installed copy, finds latest semver tag via git tag --sort=-v:refname | grep '^v[0-9]' | head -1.
      If latest tag > current VERSION: prints "dokima v2.0.0 available (you have v1.2.1) — run: curl -sSL https://get.dokima.dev | bash"
      If current is latest: prints "dokima v1.2.1 is up to date"
      Requires: network access (git fetch), git installed.
      Exits 0 on success, 0 on "already latest", 1 on network failure.
    
    --help-json extension:
      CLI_METADATA gains version field: "version": "<VERSION file contents>"
      commands array gains two entries: --version and --upgrade
    
    Backward compatibility: Fully compatible. Both flags are additive. --help is unchanged.
    
    
    
    8. Security Considerations
    
    --version: N/A — reads a local text file, zero attack surface. No user input, no network, no shell.
    
    --upgrade: LOW risk — one git fetch to GitHub (same as install.sh). Compares semver strings locally, no command injection (uses list-based subprocess args, per conventions). Output is printed, not eval'd. Network failure exits gracefully.
    
    VERSION file: Trivially tamperable (anyone with filesystem access). Acceptable — version is informational, not a security boundary. Same trust model as the script itself.
    
    
    
    9. Documentation Impact
    
    README: Add --version and --upgrade to the COMMANDS section of HELP_TEXT (done as part of Task 4).
    docs/pipeline.md: No change needed — version flags exit before pipeline.
    docs/setup.md: No change needed — install.sh unchanged.
    
    
    
    10. Task Breakdown
    
    Task 1: Create VERSION file at repo root
    Files: VERSION
    Dependencies: none
    Parallelizable: no (prerequisite for all version-reading tasks)
    Description: Create VERSION file containing "1.2.1" (current version matching latest git tag) — single line, no trailing newline, no quotes.
    
    Task 2: Add VERSION reading and --version flag dispatch
    Files: dokima
    Dependencies: Task 1
    Parallelizable: no
    Description: Add VERSION = open(os.path.join(os.path.dirname(os.path.abspath(file)), "VERSION")).read().strip() near the top of the module (after existing constants, around line 26), add is_version = False to main() flag init block, add if arg in ("--version", "-v"): is_version = True; continue to the arg loop, add if is_version: print(f"dokima v{VERSION}"); sys.exit(0) in the early-exit block before is_help_json check.
    
    Task 3: Add --version to HELP_TEXT and CLI_METADATA
    Files: dokima
    Dependencies: Task 2
    Parallelizable: no
    Description: Add dokima --version entry to HELP_TEXT COMMANDS section (after --list-crons), add "version": VERSION field to CLI_METADATA dict, add {"name": "--version", "syntax": "dokima --version", "description": "Print version and exit"} to CLI_METADATA commands array.
    
    Task 4: Implement --upgrade flag and check logic
    Files: dokima
    Dependencies: Task 1 (needs VERSION constant)
    Parallelizable: yes (different function, shares VERSION constant only — no code conflict with Tasks 2-3 if they run first)
    Description: Add is_upgrade = False to main() flag init, add if arg == "--upgrade": is_upgrade = True; continue to arg loop, add early-exit dispatch if is_upgrade: check_upgrade(); sys.exit(0) before is_version check. Implement check_upgrade(): check ~/.local/share/dokima/.git exists, run git -C ~/.local/share/dokima fetch --tags origin (timeout 30s), read installed VERSION file, get latest tag via git -C ~/.local/share/dokima tag --sort=-v:refname, compare semver, print result. If not installed via install.sh, print helpful message and exit 0.
    
    Task 5: Add --upgrade to HELP_TEXT and CLI_METADATA
    Files: dokima
    Dependencies: Task 4
    Parallelizable: no
    Description: Add dokima --upgrade entry to HELP_TEXT COMMANDS section (after --version), add {"name": "--upgrade", "syntax": "dokima --upgrade", "description": "Check for newer version and show upgrade instructions"} to CLI_METADATA commands array.
    
    Task 6: Create tests for --version and --upgrade
    Files: tests/test_f021_version.py
    Dependencies: Task 5
    Parallelizable: yes (new file, no conflicts with dokima edits)
    Description: Create test file with: (a) verify --version prints "dokima vX.Y.Z" format and exits 0, (b) verify --version works in any directory (non-git), (c) verify --version with extra args still exits 0, (d) verify -v shorthand works, (e) verify --upgrade with no install dir exits 0 with helpful message, (f) verify --upgrade handles network failure gracefully (mock subprocess to raise), (g) verify --help still works unchanged, (h) verify --help-json includes version field and both new commands.
    
    Task 7: Run full test suite and verify
    Files: none (verification only)
    Dependencies: Task 6
    Parallelizable: no
    Description: Run python3 -m pytest tests/ -q to confirm zero regressions, run python3 dokima --version to verify real output, run python3 dokima --help-json | python3 -m json.tool to verify version field present, run python3 -c "compile(open('dokima').read(), 'dokima', 'exec')" to verify build.
    
    
    
    11. Test Plan (MANDATORY)
    
    Happy path:
    - dokima --version prints "dokima v1.2.1" to stdout, exits 0
    - dokima -v prints same, exits 0 (shorthand)
    - dokima --upgrade (with install dir present, up to date) prints "dokima v1.2.1 is up to date", exits 0
    - dokima --upgrade (with install dir present, outdated) prints upgrade instructions with URL, exits 0
    - dokima --help-json output includes "version": "1.2.1" top-level field
    - dokima --help-json commands array includes --version and --upgrade entries
    - VERSION file contains exactly "1.2.1" (single line, no whitespace)
    
    Edge cases:
    - Running dokima --version in a non-git directory — should exit 0 (no git dependency)
    - Running dokima --version /some/path — should exit 0, ignoring extra arg
    - Running dokima --version --help — first flag wins (--version prints and exits)
    - Running dokima --upgrade when ~/.local/share/dokima doesn't exist — prints "Not installed via install.sh", exits 0
    - Running dokima --upgrade when ~/.local/share/dokima/.git doesn't exist (corrupted install) — prints error, exits 1
    - VERSION file missing from script directory — --version prints "unknown" or graceful error, exits 0
    - VERSION file has trailing newline — strip() handles it
    - VERSION file has extra content (multiple lines) — only first line matters, strip() handles
    - --upgrade when git is not installed — exits gracefully with "git required for --upgrade"
    - --upgrade when origin is unreachable (no network) — prints "Could not check for updates: network error", exits 1
    - --upgrade with dirty git tree — fetch still works, only reads tags
    
    Failure modes:
    - VERSION file read error (permissions, missing) — catch OSError, print "dokima vunknown", exit 0
    - git fetch timeout (30s) — catch TimeoutExpired, print network error, exit 1
    - git tag returns empty (no tags) — print "No releases found", exit 0
    - semver comparison failure (malformed tag) — skip non-semver tags, compare only vX.Y.Z patterns
    - stdout pipe broken (dokima --version | head) — Python's default SIGPIPE behavior (silent exit)
    
    Contract invariants:
    - dokima --version MUST exit without requiring PROJECT_DIR validation, AGENTS.md, or git
    - dokima --upgrade MUST NOT modify any files (read-only operation)
    - VERSION file and latest git tag SHOULD match — release process enforces this
    - dokima --version output format is stable: "dokima v<semver>"
    - dokima --help behavior is untouched — same output, same exit code
    
    
    
    12. Panel Split
    
    Wave 1: Task 1 → Task 2 → Task 3 (sequential, same file dokima)
    Parallel Coder Count: 1
    
    Wave 2: Task 4 (different function, shares VERSION constant only — if Task 1 complete, can run)
    Note: Task 4 is marked parallelizable=yes with Tasks 2-3 IF Task 1 is done. But since they all touch dokima, safest is sequential after Task 3.
    Parallel Coder Count: 1
    
    Wave 3: Task 5 (depends on Task 4, same file)
    Parallel Coder Count: 1
    
    Wave 4: Task 6 (tests — new file, depends on Task 5 for flag behavior)
    Parallel Coder Count: 1
    
    Wave 5: Task 7 (verification)
    Parallel Coder Count: 1
    
    Only 1 coder needed throughout — sequential chain on same file, then new test file, then verification.
    
    
    
    13. Build & Deploy
    
    - CI: python3 -m pytest tests/ -q passes
    - Build: python3 -c "compile(open('dokima').read(), 'dokima', 'exec')" passes
    - No deployment: dokima is a CLI script, no deployment step
    - No new env vars needed
    - VERSION file must be present in repo root for script to find it
    - GitHub Release: manual or CI step — gh release create v$(cat VERSION) --generate-notes --title "v$(cat VERSION)"
    
    
    
    14. Risk Register
    
    1. Risk: VERSION file and git tag drift apart
       Severity: Medium
       Mitigation: Release process reads VERSION to create tag — single source of truth. Convention: always bump VERSION before tagging.
       Trigger: Manual tag creation without bumping VERSION
    
    2. Risk: --upgrade breaks when GitHub API changes
       Severity: Low
       Mitigation: Uses git fetch (standard protocol), not GitHub REST API. git protocol is stable.
       Trigger: Git protocol deprecation (extremely unlikely)
    
    3. Risk: --upgrade network call blocks terminal for 30s
       Severity: Low
       Mitigation: 30-second timeout on git fetch. User can Ctrl+C.
       Trigger: Slow network or unresponsive GitHub
    
    4. Risk: --version output format change breaks scripts that parse it
       Severity: Low
       Mitigation: Format "dokima v<semver>" documented in this spec and test-enforced.
       Trigger: Format change without test update
    
    5. Risk: VERSION file not included in git bundle transfers (air-gapped migration)
       Severity: Low
       Mitigation: VERSION is a tracked file — git bundle includes all tracked files. Verified by git show.
       Trigger: VERSION added to .gitignore (anti-pattern)
    
    
    
    15. Anti-Creep
    
    NOT in scope:
    - dokima --release command — YAGNI for P2. Use gh release create directly.
    - Auto-bumping VERSION via CI — manual bump is appropriate for a single-script tool
    - Version check on every pipeline run — --version is user-initiated only
    - dokima --upgrade --force to auto-run install.sh — security risk, user must explicitly pipe to bash
    - Parsing CHANGELOG.md — gh release create --generate-notes handles this
    - npm-style version ranges or pre-release suffixes (-alpha, -beta) — standard semver only
    - Version in script docstring — VERSION file is the single source of truth
    - Checking version against PyPI or other registries — GitHub is the distribution channel
    
    
    
    16. Sign-Off Checklist
    
    - [ ] VERSION file exists at repo root with correct current version
    - [ ] dokima --version prints "dokima vX.Y.Z" and exits 0
    - [ ] dokima -v works as shorthand
    - [ ] dokima --upgrade works when installed via install.sh
    - [ ] dokima --upgrade exits gracefully when not installed via install.sh
    - [ ] dokima --upgrade handles network failure gracefully
    - [ ] dokima --help output unchanged (except new command entries)
    - [ ] dokima --help-json includes version field and new commands
    - [ ] Tests pass: python3 -m pytest tests/test_f021_version.py -v
    - [ ] Full test suite passes: python3 -m pytest tests/ -q
    - [ ] Build check passes: python3 -c "compile(open('dokima').read(), 'dokima', 'exec')"
    - [ ] New files: VERSION, tests/test_f021_version.py — no other new files
    
    
    
    Confidence: High
    Impact: MEDIUM
    
    All sections present. All task headers use ### Task N: format. Impact and What Changed sections included. Spec ready for panel parsing.