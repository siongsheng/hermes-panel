# F023: Pipeline Self-Healing

Now I know exactly what the quality checker expects. The verify_spec_quality function uses:
    - r'##\s+\d\.?\sImpact' — needs ## level heading for Impact
    - r'##\s+\d\.?\sWhat Changed' — needs ## level heading for What Changed
    - r'###\s+Task\s+\d+:' — needs ### Task N: format
    
    The original spec used ### (level-3) for Impact/What Changed, and the regex looks for ##. That's the bug. Here's the complete corrected spec:
    
    
    
    Position: F023 is well-scoped and largely additive — three targeted self-healing mechanisms on top of existing infrastructure. (High confidence)
    
    
    
    F023: Pipeline Self-Healing — Spec
    
    1. Executive Summary
    
    Dokima already has timeout handling, PID-based stale lock detection, and single-pass auto-fix. But three failure modes still require manual intervention: (a) the pipeline re-triggers the same fix on the same feature in --continuous mode (Bug 13 in MAINTAINERS.md), (b) truncated coder output is indistinguishable from valid but incomplete output, and (c) a SIGKILL'd pipeline leaves a lock file that survives the next startup if the PID gets recycled. F023 adds max-iteration guards, truncation heuristics, and lock-age auto-cleanup so the pipeline self-recovers without operator babysitting.
    
    2. Constitution Check
    
    Axiom: Solves operator pain?
    Verdict: YES — unattended --continuous runs shouldn't need lock file
      cleanup or stale fix loops
    ────────────────────────────────────────
    Axiom: Weekend-buildable?
    Verdict: YES — ~200 LOC of guard clauses in existing functions
    ────────────────────────────────────────
    Axiom: Evidence operators hit this?
    Verdict: YES — Bug 13 (auto-fix infinite loop) is a known MEDIUM-severity
      issue; SIGKILL lock persistence confirmed by MAINTAINERS.md cleanup
      instructions
    ────────────────────────────────────────
    Axiom: Boring tech?
    Verdict: YES — stdlib os.kill(pid, 0), time.time(), hashlib.md5 — no new
      deps
    ────────────────────────────────────────
    Axiom: Avoids AI hype?
    Verdict: YES — no ML/AI, pure guard rails
    
    Verdict: PASS. Aligned with F010 (Parallel Coder Robustness) which F023 depends on. The F010 anti-creep deliberately excluded retry logic — F023 is that retry logic.
    
    3. Ponytail Guard — Pre-Spec Review
    
    
    Ponytail Guard — Pre-Spec Review
    Feature: Pipeline Self-Healing (F023)
    Rung: 7 — minimum that works (stdlib + existing functions can express each mechanism, but none one-line)
    Existing solution: stale PID detection exists in acquire_lock(), _get_lock_state(); timeout markers exist; vet has MAX_VERIFY_RETRIES
    Spec needed: YES — covers three gaps not handled by existing code
    Spec scope: (1) fix-loop iteration caps + output hash cycle detection, (2) coder output truncation heuristics, (3) lock-age auto-cleanup at startup
    
    
    4. Decision Table
    
    Approach: A: Targeted guards
    Description: Add counters + heuristics at 3 specific failure points
    Complexity: Low (~200 LOC)
    Coverage: All 3 failure modes
    Verdict: ACCEPT
    ────────────────────────────────────────
    Approach: B: Pipeline state machine
    Description: Refactor pipeline into explicit states with transitions and
      timeouts
    Complexity: High (~600 LOC, touches every phase)
    Coverage: All + future failures
    Verdict: Reject — overkill for 3 known failures
    ────────────────────────────────────────
    Approach: C: External watchdog
    Description: Separate cron/daemon that monitors pipeline health
    Complexity: Medium (new process)
    Coverage: Only lock files and PID
    Verdict: Reject — adds deployment complexity
    
    SINGLE APPROACH: A — three targeted guard clauses at existing failure points. Each mechanism is independent, testable in isolation, and adds no new abstractions.
    
    Impact
    
    Pipeline operators get unattended --continuous runs without stale lock file cleanup, fix loops that never converge, or truncated coder output silently accepted as valid. No change for interactive users.
    
    What Changed
    
    - dokima (acquire_lock, lines 1040-1090): lock-age check — if lock >12h old, auto-cleanup even if PID alive (PID recycling guard)
    - dokima (run_phase3_vet, lines 3689-3762): fix-output hash comparison — if coder produces identical output 2x in a row, skip to fallback instead of re-looping
    - dokima (run_phase2_coder, lines 3406-3590): truncation heuristic — detect output ending mid-sentence (no closing Report: marker, last line has no terminal punctuation, or char count < 50% of expected)
    - dokima (_get_lock_state, lines 1859-1890): lock-age auto-cleanup for --status command consistency
    - tests/test_f023_self_healing.py (NEW): tests for lock-age auto-cleanup, fix-loop hash detection, truncation heuristics
    - MAINTAINERS.md: remove Bug 13 from Known Bugs, add F023 self-healing note
    
    5. Confidence + Impact Markers
    
    Confidence: High
    Impact: MEDIUM
    
    6. API/Interface Proposal
    
    N/A — internal guard clauses only; no new API surface. acquire_lock() and _get_lock_state() behavior changes are backward-compatible (same return values).
    
    7. Security Considerations
    
    N/A — no auth, permission, or injection surface change. Lock-age check uses existing os.kill(pid, 0) + time.time() which are safe. Hash comparison uses hashlib.md5 on output text only — no data exposure. Truncation heuristic inspects string patterns — no code execution.
    
    8. Documentation Impact
    
    README: No change needed. MAINTAINERS.md: Remove Bug 13 from Known Bugs table, add one sentence under Pipeline Cleanup noting F023 self-healing guards (lock-age auto-cleanup, fix-loop hash detection, truncation detection).
    
    9. Data Model
    
    No new entities. Existing functions affected:
    
    - acquire_lock(): gains lock-age threshold check before PID-based staleness (line 1053 area)
    - _get_lock_state(): gains same lock-age check (line 1869 area)
    - run_phase3_vet(): gains _hash_output() call before/after coder fix retry (line 3735 area)
    - run_phase2_coder(): gains _detect_truncation() call post spawn_agent (line 3580 area)
    
    New helpers:
    - _detect_truncation(text: str) -> bool: checks for missing Report: marker, terminal punctuation, minimum length
    - _hash_output(text: str) -> str: returns md5 hexdigest for cycle detection
    
    10. Risk Register
    
    #: R1
    Risk: Lock-age threshold (12h) too aggressive — kills legit long-running
      pipeline
    Severity: LOW
    Mitigation: Threshold is configurable via env var PANEL_LOCK_MAX_AGE_SECS;
      default 12h far exceeds any single pipeline run (<30 min)
    Trigger: Pipeline somehow runs >12h
    ────────────────────────────────────────
    #: R2
    Risk: Truncation heuristic false positive — flags valid short output
    Severity: LOW
    Mitigation: Heuristic only downgrades to retry; max 1 retry before
      accepting
    Trigger: Coder produces a single-line report
    ────────────────────────────────────────
    #: R3
    Risk: Fix-hash collision — different fixes produce same output
    Severity: LOW
    Mitigation: Hash check only triggers on identical output; different fixes
      always differ
    Trigger: Two different fixes print identical text
    ────────────────────────────────────────
    #: R4
    Risk: PID recycled within 12h to another dokima process
    Severity: LOW
    Mitigation: Lock-age check catches this — if lock >12h old, PID check is
      bypassed
    Trigger: PID recycling within 12h while pipeline is active
    ────────────────────────────────────────
    #: R5
    Risk: Truncation heuristic false negative — truncated output with terminal
      . passes
    Severity: LOW
    Mitigation: Report: marker check is the primary signal; terminal
      punctuation is secondary
    Trigger: Coder output truncated right after a period
    ────────────────────────────────────────
    #: R6
    Risk: Hash check adds latency to vet phase
    Severity: LOW
    Mitigation: md5 is microseconds on text; negligible vs agent spawn time
    Trigger: N/A
    
    11. Anti-Creep
    
    Features explicitly NOT in scope:
    
    - Pipeline state machine refactor (F022 handles modular architecture)
    - External watchdog daemon
    - Circuit breaker patterns (retry with exponential backoff)
    - Auto-merge on fix convergence
    - Monitoring dashboard or metrics
    - Cross-repo lock coordination
    - TL auto-fix loop guards (TL auto-fix runs exactly once — no loop to break; Bug 13 is at vet/continuous level)
    - Per-agent heartbeat or keepalive mechanism
    - Truncation detection for nm or TL agent output (coder only)
    - /tmp/dokima-*.stop file cleanup via age check (separate concern)
    
    12. Sign-Off Checklist
    
    - [ ] Lock-age threshold (12h / PANEL_LOCK_MAX_AGE_SECS) acceptable for operator workflows?
    - [ ] Truncation detection: check for missing Report: marker as primary signal, terminal punctuation + char count as secondary?
    - [ ] Fix-hash cycle detection: hash full test+build output, or just the fix-related section?
    - [ ] Bug 13 confirmed as --continuous vet re-trigger (not single-pass TL loop)?
    - [ ] New test file tests/test_f023_self_healing.py — confirm naming convention?
    - [ ] Should lock-age auto-cleanup also apply to /tmp/dokima-*.stop files? (Decision: NO for this spec — separate concern)
    - [ ] Accept that SIGKILL lock survival is fundamentally unavoidable — best effort via age check at next startup?
    - [ ] MAINTAINERS.md update: remove Bug 13 from Known Bugs?
    - [ ] PANEL_LOCK_MAX_AGE_SECS env var name acceptable?
    - [ ] Max 1 truncation retry acceptable — or should it be configurable?
    
    13. Task Breakdown
    
    Task 1: Add lock-age auto-cleanup in acquire_lock
    Files: dokima
    Dependencies: none
    Parallelizable: yes
    Description: In acquire_lock(), after the existing stale-PID check passes (PID alive + owner verified), add a fallback: if time.time() - os.path.getmtime(lock_path) > LOCK_MAX_AGE (default 43200s = 12h, override via PANEL_LOCK_MAX_AGE_SECS env), remove the lock and retry — handles the SIGKILL + PID-recycled edge case.
    
    Task 2: Add truncation detection after coder output
    Files: dokima
    Dependencies: none
    Parallelizable: yes
    Description: After spawn_agent("coder", ...) returns in run_phase2_coder(), call a new _detect_truncation(coder_output) helper: if output lacks a Report: line AND (ends mid-sentence without ., !, ? or is <50% of expected length based on task count), flag as [TRUNCATED], trigger one retry (max 1) before accepting partial output.
    
    Task 3: Add fix-output hash cycle detection to vet phase
    Files: dokima
    Dependencies: none
    Parallelizable: yes
    Description: In run_phase3_vet(), before spawning coder to fix failures in the retry loop, hash the current test+build output. After the coder fix, hash again. If hashes match (coder produced no change), print warning, skip further retries, and fall through to BLOCKED — prevents the infinite fix-retry cycle documented as Bug 13.
    
    Task 4: Lock-age auto-cleanup also for _get_lock_state (--status)
    Files: dokima
    Dependencies: Task 1
    Parallelizable: no
    Description: In _get_lock_state(), add the same lock-age check as acquire_lock() — if the lock file is older than threshold, remove it even if PID is alive. Ensures dokima --status reports clean state after a SIGKILL'd run.
    
    Task 5: Tests for lock-age auto-cleanup
    Files: tests/test_f023_self_healing.py
    Dependencies: Task 1
    Parallelizable: yes
    Description: Test that acquire_lock() removes a lock file older than threshold even when PID is alive + owner verified (simulated recycled PID edge case), then successfully acquires lock on retry. Also test that fresh locks are preserved.
    
    Task 6: Tests for truncation detection
    Files: tests/test_f023_self_healing.py
    Dependencies: Task 2
    Parallelizable: yes
    Description: Test _detect_truncation(): output ending mid-sentence without terminal punctuation returns True; output with Report: line returns False; output with proper closing returns False. Test that run_phase2_coder retries once on truncated output and accepts after max retry.
    
    Task 7: Tests for fix-hash cycle detection
    Files: tests/test_f023_self_healing.py
    Dependencies: Task 3
    Parallelizable: yes
    Description: Test that run_phase3_vet() detects identical test+build output before and after coder fix attempt, prints warning, and falls through to BLOCKED instead of looping. Test that different output (actual fix) proceeds normally through the retry loop.
    
    Task 8: Update MAINTAINERS.md — remove Bug 13, add F023 self-healing note
    Files: MAINTAINERS.md
    Dependencies: Task 3, Task 7
    Parallelizable: no
    Description: Remove Bug 13 (auto-fix infinite loop) from the Known Bugs table. Add one sentence under Pipeline Cleanup section noting F023 self-healing guards: max-iteration caps on vet fix loop via output hash comparison, lock-age auto-cleanup, and coder output truncation detection.
    
    14. Impact Assessment (Grounded)
    
    Files affected by this feature:
    
    
    $ grep -n "acquire_lock\|_get_lock_state\|run_phase2_coder\|run_phase3_vet\|_detect_truncation\|_hash_output" dokima | head -20
    1033:def acquire_lock(project_dir, agent_id="main"):
    1859:def _get_lock_state(project_dir):
    3407:def run_phase2_coder(feature, spec, ...):
    3664:def run_phase3_vet(feature, branch, ...):
    
    
    Affected code: dokima lines 1033-1092 (acquire_lock), 1859-1890 (_get_lock_state), 3407-3590 (run_phase2_coder), 3664-3762 (run_phase3_vet). New test file: tests/test_f023_self_healing.py. Documentation: MAINTAINERS.md line 252 (Bug 13 row).
    
    15. Panel Split
    
    
    Wave 1 (parallel — no shared files, all touch different functions in dokima):
      Task 1: lock-age auto-cleanup in acquire_lock
      Task 2: truncation detection helper + integration
      Task 3: hash cycle detection in vet phase
    
    Wave 2 (sequential — depends on Task 1):
      Task 4: lock-age in _get_lock_state
    
    Wave 3 (parallel — depends on respective implementations):
      Task 5: lock-age tests
      Task 6: truncation tests
      Task 7: hash cycle tests
    
    Wave 4 (sequential — depends on Task 3 + Task 7):
      Task 8: MAINTAINERS.md update
    
    
    2 coder agents. Waves 1 and 3 are the parallel opportunities — Tasks 1/2/3 touch different functions with no line-range overlap. Tasks 5/6/7 are in the same test file but test different features — sequential within the test file but marking as same-file makes the panel run them sequentially anyway.
    
    16. Build & Deploy
    
    - Deploy: git push origin feat/f023-pipeline-self-healing → PR merge to main
    - CI: python3 -m pytest tests/ -q must pass (495+ tests including new test_f023_self_healing.py)
    - Env vars: PANEL_LOCK_MAX_AGE_SECS (new, optional, default 43200)
    - No new dependencies
    
    17. Test Plan (MANDATORY)
    
    Feature Area: Lock-Age Auto-Cleanup
    
    Happy path: Lock file is <12h old, PID alive + owner verified → lock preserved. Lock file >12h old, PID alive → lock removed, re-acquired.
    
    Edge cases: Lock file age is exactly threshold. Lock file mtime is in future (clock skew). Multiple lock files for different projects.
    
    Failure modes: os.path.getmtime() raises OSError (file deleted between check and stat). Permission denied on lock file read. Corrupt lock file (can't read PID). os.remove() fails (disk full, permissions).
    
    Contract invariants: After acquire_lock() returns True, exactly one valid lock file exists. After _get_lock_state() returns, stale locks are removed.
    
    Feature Area: Truncation Detection
    
    Happy path: Coder output has Report: line → not truncated. Coder output ends mid-sentence without . ! ? → flagged truncated. Short output (<50% expected) without Report: → flagged truncated.
    
    Edge cases: Empty output (coder crashed). Output is exactly Report: done (minimal valid). Output has Report: embedded in code block (false negative). Output is 1000 chars of newlines then truncated sentence.
    
    Failure modes: _detect_truncation() raises on None input. Expected length calculation fails (zero tasks). Hash computation on empty string.
    
    Contract invariants: Truncation flag triggers exactly one retry. After max retries, partial output is accepted.
    
    Feature Area: Fix-Hash Cycle Detection
    
    Happy path: Coder fix changes test+build output → different hash → proceed with retry loop. Coder fix produces identical output → same hash → skip to BLOCKED.
    
    Edge cases: First retry attempt (no prior hash to compare). Coder fix that only changes whitespace in output. Build output contains timestamps that change every run.
    
    Failure modes: md5 of very large output (100KB+). Hash comparison when one output is None.
    
    Contract invariants: Hash check only runs on retry (verify_attempt > 0). BLOCKED fallback preserves existing behavior (halt_and_revert). No more than MAX_VERIFY_RETRIES + 1 total attempts.
    
    
    
    CLARIFICATION: Bug 13 — is the infinite loop at --continuous re-trigger level or within a single --fix pass?
    
    Assumption: Bug 13 occurs when --continuous mode re-processes a BLOCKED feature and auto-fix keeps re-applying the same fix; the fix-hash cycle detection (Task 3) addresses the vet-level loop at lines 3689-3762, and the lock-age cleanup (Task 1) prevents phantom locks from blocking subsequent passes.
    
    Impact if wrong: If Bug 13 is actually a TL auto-fix re-trigger within a single pipeline pass (lines 4062-4124), we'd need to add a counter guard there instead of / in addition to the vet-level hash check. The TL auto-fix currently runs exactly once — no loop — so I believe Bug 13 is at the vet verification retry level.