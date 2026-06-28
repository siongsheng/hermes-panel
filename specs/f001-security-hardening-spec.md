# F001: Security Hardening

Now I have full understanding of the codebase. Let me produce the complete corrected spec.
    
    Position: This is a P0 security hardening feature for a Python pipeline orchestrator. The primary attack surfaces are prompt injection (user-crafted feature descriptions fed into coder agent prompts), token leakage (GH_TOKEN in subprocess environments), and log file exposure (/tmp/dokima-output.txt). Existing shell injection is already hardened via shlex.split. (High confidence)
    
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    SPEC: F001 — Security Hardening
    Status: In Progress | Priority: P0 | Branch: feat/f001-security-hardening
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    1. Executive Summary
    
    Dokima is a Python script that spawns Hermes Agent subprocesses and executes shell commands on behalf of user-supplied feature descriptions. F001 hardens three threat surfaces: (1) prompt injection — feature descriptions are interpolated into coder prompts without sanitization, potentially injecting malicious directives; (2) token exposure — GH_TOKEN is passed to subprocess environments and could leak through agent output written to /tmp/dokima-output.txt; (3) user-supplied input in /tmp log files — interview answers and feature descriptions may contain secrets persisted in world-readable temp files.
    
    The codebase already has solid shell injection hardening: _safe_run uses shlex.split, no shell=True anywhere, and all subprocess calls use list-based args. This feature closes the remaining gaps without regressing that baseline.
    
    2. Constitution Check
    
    Axiom: Solves user's own pain?
    Status: YES
    Detail: Shaun enforces "never expose credentials" (axiom 3). Token leakage
      is a direct violation of his own rules.
    ────────────────────────────────────────
    Axiom: Weekend-buildable?
    Status: YES
    Detail: ~200 LOC across 4 files. All changes are defensive wrappers and
      validation — no new subsystems.
    ────────────────────────────────────────
    Axiom: Evidence people will pay?
    Status: N/A
    Detail: This is internal infrastructure. Security is table-stakes, not
      revenue-generating.
    ────────────────────────────────────────
    Axiom: Boring/tech-proven?
    Status: YES
    Detail: Standard Python patterns: shlex.quote, re.sub sanitization,
      os.umask, environment filtering. No novel crypto.
    ────────────────────────────────────────
    Axiom: Avoids AI hype?
    Status: YES
    Detail: Zero AI. Pure defensive coding.
    
    Constitution verdict: PASS. All mandatory checks satisfied.
    
    3. Ponytail Guard — Pre-Spec Review
    
    
    Feature: F001 — Security Hardening
    Rung: 7 — minimum that works (new guard code required, no stdlib shortcut for prompt sanitization or env filtering)
    Existing solution: _safe_run already uses shlex.split for shell safety. No prompt sanitization, no token filtering, no log file hardening.
    Spec needed: YES
    Spec scope: Prompt injection sanitization, GH_TOKEN filtering from agent logs, /tmp file permissions, security regression test suite.
    
    
    4. Feature Breakdown
    
    Task 1: Add prompt sanitization utility
    Files: dokima
    Dependencies: none
    Parallelizable: yes
    Estimated LOC: ~25
    Description: Add _sanitize_prompt(text: str) -> str function that strips known injection patterns from user-supplied feature text before it enters agent prompts. Strip backtick-escaped shell commands (\rm -rf /\), markdown code blocks with dangerous commands, and "SYSTEM:" / "OVERRIDE:" prefix injection attempts. Log a warning with the first 80 chars of stripped content. Call this on feature before run_phase1_strategist and run_phase2_coder.
    
    Task 2: Filter GH_TOKEN from agent log output
    Files: dokima
    Dependencies: none
    Parallelizable: yes
    Estimated LOC: ~35
    Description: Add _redact_secrets(text: str) -> str that strips GH_TOKEN and API_SERVER_KEY values from text before writing to OUTPUT_LOG. Redact with [REDACTED]. The redact function must look up token values from the environment at redaction time (not cache them globally), because tokens could rotate. Call this in the OUTPUT_LOG write path and in spawn_agent's line-printer.
    
    Task 3: Harden /tmp file permissions
    Files: dokima
    Dependencies: none
    Parallelizable: yes
    Estimated LOC: ~20
    Description: Set os.umask(0o077) at module init (before any file writes). Apply explicit os.chmod(path, 0o600) to OUTPUT_LOG, lock/stop files, and interview JSON immediately after creation. Verify the lock file already uses fcntl advisory locking (safe) — only add the permission hardening.
    
    Task 4: Validate PROJECT_DIR is a real git repo
    Files: dokima
    Dependencies: none
    Parallelizable: yes
    Estimated LOC: ~15
    Description: After resolving PROJECT_DIR in main(), verify it's a real directory containing .git before proceeding. Reject paths that don't exist, aren't directories, or lack .git. Prevents accidental operations on wrong paths and blocks path-based injection tricks (symlink attacks, /proc paths). Exit with clear error message and exit code 1.
    
    Task 5: Security regression test suite
    Files: tests/test_f001_security.py
    Dependencies: [Task 1, Task 2, Task 3, Task 4]
    Parallelizable: no (depends on all impl tasks)
    Estimated LOC: ~80
    Description: Create comprehensive security tests:
      - test_prompt_sanitizer_removes_backtick_commands
      - test_prompt_sanitizer_removes_override_prefixes
      - test_prompt_sanitizer_preserves_normal_text
      - test_redact_strips_gh_token_from_output
      - test_redact_strips_api_key_from_output
      - test_redact_preserves_non_secret_text
      - test_tmp_files_have_restrictive_permissions
      - test_invalid_project_dir_rejected
      - test_valid_project_dir_accepted
      - test_no_shell_true_anywhere (grep source for shell=True)
      - test_no_os_system_anywhere (grep source for os.system)
      - test_all_subprocess_use_list_args (grep for subprocess.run(cmd, ...) where cmd is a string)
    
    Task 6: Add security section to conventions
    Files: specs/conventions.md
    Dependencies: [Task 1, Task 2]
    Parallelizable: yes
    Estimated LOC: ~15
    Description: Add "Security" section to conventions.md documenting: prompt sanitization rules, token redaction policy (never pass raw tokens in prompts, redact in logs), umask convention (0o077 for all /tmp artifacts), and the rule that all subprocess calls must use list args (never shell=True or string commands). This serves as guardrail reinforcement for future contributors and agent coders.
    
    5. Impact
    
    Panel operators gain defense-in-depth against three threat classes: (a) malicious feature descriptions can no longer inject commands into coder agent prompts; (b) GH_TOKEN can no longer leak through agent output written to /tmp logs; (c) /tmp artifacts (logs, lock files, interview JSON) are no longer world-readable. No behavior change for legitimate workflows.
    
    6. What Changed
    
    - dokima: Added _sanitize_prompt() and _redact_secrets() functions, called at injection points. Added PROJECT_DIR validation at startup. Set umask 0o077 at module init.
    - tests/test_f001_security.py: New file with 11 security regression tests (prompt sanitizer, token redaction, file permissions, path validation, shell safety assertions).
    - specs/conventions.md: New Security section documenting sanitization, redaction, umask, and subprocess rules.
    
    7. API / Interface Proposal
    
    N/A — this is a pure hardening change. No new APIs, routes, or data structures. Two new internal functions (_sanitize_prompt, _redact_secrets) are called at existing injection points; no external interface changes.
    
    8. Security Considerations
    
    Threat model covered by this change:
    Threat: Prompt injection
    Vector: Feature desc → coder prompt via f-string
    Mitigation: _sanitize_prompt() strips injection patterns before
      interpolation
    Residual Risk: Coders could still be tricked by cleverly-phrased feature
      descriptions — this is an inherent LLM risk, not a dokima bug
    ────────────────────────────────────────
    Threat: Token exposure
    Vector: GH_TOKEN in subprocess env → agent outputs to /tmp log
    Mitigation: _redact_secrets() strips token values before log write
    Residual Risk: Token could leak through agent's HERMES_BOX output if
      redaction is bypassed — but we redact at the log-write boundary, not
      per-line
    ────────────────────────────────────────
    Threat: /tmp file snooping
    Vector: World-readable lock/log/interview files
    Mitigation: os.umask(0o077) + explicit chmod 0o600
    Residual Risk: Race condition between file creation and chmod — mitigated
      by umask set before any file I/O
    ────────────────────────────────────────
    Threat: Path traversal
    Vector: User-supplied PROJECT_DIR
    Mitigation: os.path.abspath() + git repo validation
    Residual Risk: Abspath resolves symlinks; git check prevents operations on
      non-repo paths
    
    What this change does NOT cover (out of scope):
    - Hermes Agent API server authentication (api-server already has API_SERVER_KEY)
    - Network-level isolation (localhost-only comms are 127.0.0.1 by design)
    - Subprocess sandboxing (seccomp, cgroups) — dokima trusts the project's build commands
    - Dependency supply-chain attacks (pip/npm packages) — this is the project's responsibility
    
    9. Confidence & Impact
    
    Confidence: High
    Impact: MEDIUM — no behavior change for legitimate use; defense-in-depth that blocks known attack patterns.
    
    10. Documentation Impact
    
    README: No change needed.  
    specs/conventions.md: Add Security section (see Task 6).
    
    11. Test Plan (MANDATORY)
    
    Prompt sanitizer (Tasks 1, 5):
    - Happy path: Normal feature descriptions pass through unchanged
    - Edge cases: Empty string, non-ASCII characters, very long descriptions (10K chars), descriptions containing "SYSTEM" as legitimate word
    - Failure modes: RegexReDoS (pathological patterns like \\\\\\... — tested with 1000 backticks)
    - Contract invariants: _sanitize_prompt(text) must never crash, must return a string, and must not be longer than input
    
    Token redaction (Tasks 2, 5):
    - Happy path: Text containing GH_TOKEN=ghp_xxx gets redacted to GH_TOKEN=[REDACTED]
    - Edge cases: Token appears at start of line, end of line, multiple times, token value contains regex special chars
    - Failure modes: Token is empty/missing (no crash, no redaction), output is 1MB+ (performance test — must complete in < 1s)
    - Contract invariants: Redacted output must never contain the raw token value, must preserve all non-token content byte-for-byte
    
    File permissions (Tasks 3, 5):
    - Happy path: Newly created /tmp/dokima-* files have mode 0o600
    - Edge cases: Files already exist with wrong permissions (auto-fix on open), directory doesn't exist yet
    - Failure modes: Disk full (write fails gracefully), /tmp mounted noexec
    - Contract invariants: No /tmp/dokima-* file ever has world/group readable bits after this change
    
    Path validation (Tasks 4, 5):
    - Happy path: Real git repo directory accepted
    - Edge cases: Symlink to git repo (accepted — abspath resolves), relative paths (resolved), root-owned directory (permission error caught)
    - Failure modes: Non-existent path, file instead of directory, directory without .git
    - Contract invariants: Pipeline never proceeds without a verified git repo at PROJECT_DIR
    
    Shell safety assertions (Task 5):
    - Contract invariants: grep -r 'shell=True' dokima returns zero matches; grep -r 'os\.system(' dokima returns zero matches; no subprocess call passes a bare string as the command argument
    
    12. COTS Build-vs-Buy
    
    Component: Prompt sanitization
    Decision: Build — re.sub patterns
    Justification: No library needed — the injection patterns are
      dokima-specific (feature desc → coder prompt f-string)
    ────────────────────────────────────────
    Component: Secret redaction
    Decision: Build — string replacement
    Justification: Commercial secret scanners (truffleHog, git-secrets) are
      for repos, not live log streams
    ────────────────────────────────────────
    Component: File permissions
    Decision: Buy — os.umask + os.chmod
    Justification: Stdlib. No dependency.
    ────────────────────────────────────────
    Component: Subprocess safety
    Decision: Already built — _safe_run with shlex.split
    Justification: Already implemented and tested. This spec adds assertions
      only.
    
    13. Build & Deploy
    
    - Build: python3 -c "compile(open('dokima').read(), 'dokima', 'exec')" (unchanged)
    - Test: python3 -m pytest tests/test_f001_security.py -v (new test file)
    - CI: Add test_f001_security.py to the existing CI test suite
    - Deploy: Single-file Python script — just replace dokima. No server restart needed.
    
    14. Risk Register
    
    #: 1
    Risk: Prompt sanitizer blocks legitimate feature descriptions
    Severity: MEDIUM
    Mitigation: Sanitizer is conservative — only strips unambiguous injection
      patterns. Log warnings for audit.
    Trigger: User reports "my feature spec got mangled"
    ────────────────────────────────────────
    #: 2
    Risk: Token redaction misses token due to encoding/case mismatch
    Severity: HIGH
    Mitigation: Redact by exact value lookup, not regex pattern. Both
      uppercase and mixed-case forms.
    Trigger: GH_TOKEN appears in /tmp/dokima-output.txt
    ────────────────────────────────────────
    #: 3
    Risk: umask 0o077 breaks a dependency that expects world-readable /tmp
      files
    Severity: LOW
    Mitigation: Only affects dokima-created files in /tmp. No known consumers
      beyond dokima itself.
    Trigger: External tool reads /tmp/dokima-output.txt and fails
    ────────────────────────────────────────
    #: 4
    Risk: PROJECT_DIR validation rejects legitimate edge cases (detached HEAD,
      bare repos)
    Severity: LOW
    Mitigation: Check is .git directory existence only — works for all normal
      git repos. Bare repos unsupported by design.
    Trigger: User reports "valid git repo rejected"
    ────────────────────────────────────────
    #: 5
    Risk: Security test assertions break when dokima is refactored
    Severity: LOW
    Mitigation: Test on shell=True/os.system are grep-based — they catch
      regressions but may false-positive on commented-out code.
    Trigger: CI fails after a rename refactor
    ────────────────────────────────────────
    #: 6
    Risk: RegexReDoS in prompt sanitizer
    Severity: MEDIUM
    Mitigation: Use re.search with fixed strings, not complex backtracking
      regex. Timeout or char-limit on input.
    Trigger: CPU spike during sanitization of crafted input
    
    15. Anti-Creep
    
    Features explicitly NOT in scope for F001:
    - No sandboxing — seccomp, cgroups, Docker, or process isolation. Dokima already runs project-local commands.
    - No network hardening — localhost-only API server and single-machine operation are acceptable for a CLI tool.
    - No secret manager integration — no HashiCorp Vault, AWS Secrets Manager, or similar. .env file is sufficient.
    - No audit logging — no structured security event log. Warnings go to stderr.
    - No CI/CD scanning — no SAST/DAST integration. This is a personal CLI tool.
    - No multi-user hardening — single-user tool, no RBAC or user isolation.
    - No prompt injection defenses for the LLM itself — only for dokima's prompt construction. The LLM's own alignment is out of scope.
    
    16. Panel Split
    
    Wave 1 (parallel — all tasks independent): Task 1, Task 2, Task 3, Task 4  
    Wave 2 (sequential — depends on impl): Task 5  
    Wave 3 (parallel — depends on impl for docs): Task 6
    
    Coder agents: 1 (tasks 1-4 share the same file dokima, so they cannot be parallelized across separate coders. Single agent with all 4 tasks, then Task 5 (tests), then Task 6 (docs).)
    
    17. Sign-Off Checklist
    
    - [ ] Prompt sanitizer doesn't block legitimate feature descriptions (tested with real dokima pipeline inputs)
    - [ ] Token redaction verified: grep $GH_TOKEN /tmp/dokima-output.txt returns empty after pipeline run
    - [ ] All /tmp/dokima-* files have mode 0o600 after creation
    - [ ] Invalid PROJECT_DIR produces clear error, not crash
    - [ ] 11 security tests pass: python3 -m pytest tests/test_f001_security.py -v
    - [ ] No regression: full test suite passes: python3 -m pytest tests/ -q
    - [ ] No shell=True anywhere in dokima: grep -n 'shell=True' dokima returns nothing
    - [ ] No os.system anywhere in dokima: grep -n 'os\.system(' dokima returns nothing
    - [ ] conventions.md Security section written
    - [ ] Pipeline runs end-to-end with security code active (manual test: dokima "F001: test feature")
    - [ ] Code review: all new functions are < 30 lines each
    
    The spec is complete — Impact section (item 5), What Changed (item 6), and ### Task N: headers (items 4.1-4.6) are all present and correctly formatted.