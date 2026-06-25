# Triple Bug Fix — Post-Pipeline Correctness Fixes

**Status:** Draft
**Confidence:** High (root causes confirmed by reading code lines 259-285, 1796-1868, 3895-3932)
**Impact:** MEDIUM
**Version:** 1.0.0
**Feature slug:** triple-bug-fix

---

## 1. Executive Summary

Three correctness bugs exist in dokima's post-pipeline logic, all in code paths that run after a feature pipeline completes. Bug 1 (spec archive never runs on merge) causes merged specs to pile up unarchived. Bug 2 (STATUS.md marked "done" without checking verdict) records BLOCKED/CHANGES_REQUESTED PRs as completed. Bug 3 (detect_commands() caches from main at startup) causes vet to run wrong test/build commands when a feature branch modifies AGENTS.md. All three share the same post-pipeline code path and can be fixed in a single feature without new dependencies or architectural changes.

Confidence: **High** — each bug's root cause was confirmed by reading the exact source lines. The fixes are targeted conditionals, ordering changes, and one re-invocation pattern.

---

## 2. Constitution Check

| Axiom | Status | Detail |
|-------|--------|--------|
| Solves user's own pain? | YES | User has unarchived specs, falsely-marked-done features, and stale test commands. |
| Weekend-buildable? | YES | ~150-200 LOC, no new dependencies, no new functions needed. |
| Evidence people will pay? | N/A | Core correctness fix — not a monetizable feature. |
| Tech stack boring/proven? | YES | Pure Python 3.6+ with existing gh CLI. Same patterns as rest of dokima. |
| Avoids AI hype? | YES | Pure orchestration logic fixes. Zero AI involved. |

No constitutional violations.

---

## 3. Cause Analysis

### Bug 1: Spec archive never runs on merge

**Root cause at lines 3907-3932:**
1. The auto-archive block runs **before** the pipeline (line 3907), not after. So the just-completed feature's spec is never caught until the NEXT `dokima` invocation.
2. Line 3916: `branch_name = f"feat/{entry}"[:80]` uses the raw spec directory name (e.g., `F001-site-shell`), but `gh pr list --head <branch>` requires the actual branch name. The actual branch is `feat/f001-site-shell` (lowercased by `slugify()` during strategist branch creation), but the archive code passes `feat/F001-site-shell` — case mismatch → `gh pr list` returns no match → no archive.

**Fix approach:** Move archive logic into `run_post_pipeline()` (lines 1796-1868). After pipeline completes, check if PR was merged. If yes, archive the spec directory for that feature using the **actual branch name** from the pipeline run, not a guessed one. Also add a follow-up fallback scan at startup to catch any specs missed due to edge cases (e.g., manual merges outside dokima), but this scan should use `gh pr list --search "is:merged"` or check actual branch names from git rather than guessing.

### Bug 2: STATUS.md marked "done" without checking verdict

**Root cause at lines 1843-1860:**
1. **`--continuous` mode (lines 1830-1844):** When `verdict != "APPROVED"` (e.g., BLOCKED, CHANGES_REQUESTED), the `else` at line 1843 sets `continue_loop = True`. Then line 1846 `if continue_loop:` proceeds to mark the feature as "done" in both roadmap and STATUS.md — even though the PR is BLOCKED and was never merged.
2. **`--next` mode (lines 1853-1860):** Marks done unconditionally — no verdict check at all. A BLOCKED/CHANGES_REQUESTED verdict results in the feature being recorded as "[x] Done".

**Fix approach:** Guard all "done" status updates with `verdict == "APPROVED"`. For BLOCKED/CHANGES_REQUESTED verdicts in `--next` mode, leave the status as `in_progress` [~] and print a message explaining why. For `--continuous` mode, do NOT set `continue_loop = True` when verdict is not APPROVED — this ensures the loop stops instead of falsely marking BLOCKED features as done.

### Bug 3: detect_commands() caches from main at startup

**Root cause at line 3895 + lines 259-285:**
1. `detect_commands()` is called **once** at line 3895 during `main()` startup, reading AGENTS.md from `PROJECT_DIR` (which is checked out to the default branch at that point).
2. The results are stored in globals `TEST_CMD`, `BUILD_CMD`, `LINT_CMD`.
3. When the coder phase (Phase 2) modifies AGENTS.md on the feature branch (e.g., adding `Build:` / `Test:` / `Lint:` entries), `run_phase3_vet()` (line 2664) and downstream functions use the **stale** values captured from the default branch's AGENTS.md.
4. Symptom: vet runs `npm test` (default) on a Python project whose AGENTS.md specifies `python3 -m pytest tests/ -q`.

**Fix approach:** Re-run `detect_commands()` after the coder's branch is checked out, before vet runs. The simplest approach is to call `detect_commands()` at the start of `run_phase3_vet()` and update the globals, or change `detect_commands()` to accept a `project_dir` parameter and call it fresh each time.

---

## 4. Feature Breakdown

### Task 1: Move spec archive from pre-pipeline to post-pipeline

- **Files:** dokima
- **Dependencies:** [none]
- **Parallelizable:** no (shared code path with Tasks 2, 5)
- **Estimated LOC:** ~50
- **Description:** Move the auto-archive block (currently lines 3907-3932) from its pre-pipeline position to `run_post_pipeline()`. The new logic:
  1. After pipeline completes, if `pr_url` exists and PR is merged (check via `gh pr view <num> --json merged --jq .merged` or use the `try_auto_merge` result), archive the spec directory at `spec_path` → `specs/archive/<dirname>`. The `branch` parameter from the pipeline run (lowercased by slugify, this is the real branch name) is used — no guessing needed.
  2. Keep a lightweight fallback scan at startup (line 3907 original position) that iterates spec directories and checks for merged PRs, but fix it to use `gh pr list --search "is:merged head:feat/<actual_branch_name>"` or compare against `git branch -r --merged origin/<default>` instead of guessing branch names from directory names. The fallback only fires for specs created outside the pipeline (manual specs).
  3. Print archive count after post-pipeline archive, and separately after fallback scan.

### Task 2: Guard STATUS.md/roadmap "done" update on verdict == "APPROVED"

- **Files:** dokima
- **Dependencies:** [none]
- **Parallelizable:** no
- **Estimated LOC:** ~30
- **Description:** Modify lines 1846-1860 in `run_post_pipeline()`:
  1. **`--continuous` mode (lines 1830-1844):** Change the `else` at line 1843 so that `continue_loop` is NOT set to True when verdict != APPROVED. When verdict is BLOCKED or CHANGES_REQUESTED, set `continue_loop = False` and print `"  ⚠ PR not approved (verdict: {verdict}) — stopping loop"`. Then the `if continue_loop:` guard at line 1846 naturally prevents the "done" marking.
  2. **`--next` mode (lines 1853-1860):** Guard the "done" update with `if verdict == "APPROVED":`. For BLOCKED/CHANGES_REQUESTED verdicts, print `"  ⚠ PR {fid} has verdict: {verdict} — not marking as done. Will retry on next run."` and leave the status as `in_progress` [~].
  3. Also handle `CODER_FAILED`, `TIMED_OUT`, `UNKNOWN` — these already exist at line 1823 and correctly revert to pending. The fix is additive: these cases remain unchanged; the new guard only affects the BLOCKED/CHANGES_REQUESTED gap.

### Task 3: Add `archive_specs_for_feature()` function

- **Files:** dokima
- **Dependencies:** [Task 1]
- **Parallelizable:** yes (independent function)
- **Estimated LOC:** ~25
- **Description:** New helper function extracted from the archive logic:
  ```python
  def archive_specs_for_feature(spec_path: str, branch: str, pr_url: str) -> bool:
      """Move a feature's spec directory to archive/ if PR is merged.
         Returns True if archived, False otherwise."""
  ```
  - Takes `spec_path` (path to the spec directory or file), `branch` (actual branch name from pipeline), `pr_url` (the PR URL to check).
  - Extracts PR number from `pr_url`.
  - Calls `gh pr view <num> --json merged,state` to check merge status.
  - If merged, moves `spec_path` to `specs/archive/<dirname>` and returns True.
  - Called by `run_post_pipeline()` for the just-completed feature.
  - Also used by the startup fallback scan.

### Task 4: Add `refresh_detect_commands()` call in `run_phase3_vet()`

- **Files:** dokima
- **Dependencies:** [none]
- **Parallelizable:** yes (independent function)
- **Estimated LOC:** ~15
- **Description:** At the top of `run_phase3_vet()`, after the branch checkout succeeds (after line 2680 or equivalent), call `detect_commands()` again and update the globals:
  ```python
  global TEST_CMD, BUILD_CMD, LINT_CMD
  TEST_CMD, BUILD_CMD, LINT_CMD = detect_commands()
  ```
  This ensures that AGENTS.md on the feature branch's working tree is read, not the stale copy from startup. If AGENTS.md doesn't exist on the feature branch (unlikely if coder just created it), the function returns defaults (`npm test`, `npm run build`, `npm run lint`), which is the same fallback as before.

### Task 5: Reorder post-pipeline to call archive after verdict check

- **Files:** dokima
- **Dependencies:** [Task 1, Task 2, Task 3]
- **Parallelizable:** no
- **Estimated LOC:** ~20
- **Description:** Within `run_post_pipeline()`, after the verdict-based status update logic (after line 1860), add the archive call:
  ```python
  # After pipeline and status update: archive spec if merged
  if verdict == "APPROVED" and pr_url and spec_path:
      archived = archive_specs_for_feature(spec_path, branch, pr_url)
      if archived:
          print(f"  Spec archived: {os.path.basename(spec_path)} → specs/archive/")
  ```
  This ensures archive only fires for truly completed (APPROVED) features, not blocked ones.

### Task 6: Fix fallback startup archive scan

- **Files:** dokima
- **Dependencies:** [Task 3]
- **Parallelizable:** no
- **Estimated LOC:** ~30
- **Description:** At the original archive position (line 3907), keep the fallback scan but fix the branch name generation approach:
  1. Instead of `f"feat/{entry}"[:80]` (line 3916), use actual branch names from git: run `git branch -r --merged origin/<DEFAULT_BRANCH>` and check if any remote branch matches a pattern derived from the spec directory name. The entry `F001-site-shell` should match `origin/feat/f001-site-shell`.
  2. Alternative: Use `gh pr list --state merged --json headRefName,number --jq '.[] | select(.headRefName | test("'"$(echo "$entry" | tr '[:upper:]' '[:lower:]')"'"))'` to do case-insensitive matching.
  3. Keep the same `shutil.move` logic for archival.
  4. The fallback scan is a second-chance mechanism for specs created outside the pipeline. The primary archive (Task 5) handles pipeline-created specs.

### Task 7: Add tests

- **Files:** tests/test_triple_bug_fix.py (new file)
- **Dependencies:** [Task 2, Task 3, Task 4]
- **Parallelizable:** yes (separate file)
- **Estimated LOC:** ~90
- **Description:** New test file covering all three bugs:

  **Bug 1 tests (archive):**
  - `test_archive_specs_for_feature_merged()` — mock `gh pr view` to return merged=true → archive succeeds → spec dir moved to archive/
  - `test_archive_specs_for_feature_not_merged()` — mock `gh pr view` to return merged=false → no archive
  - `test_archive_specs_for_feature_no_pr_url()` — pass `pr_url=None` → no archive (no crash)

  **Bug 2 tests (verdict guard):**
  - `test_run_post_pipeline_blocked_next()` — pass verdict="BLOCKED", is_next=True → status NOT marked done, remains in_progress
  - `test_run_post_pipeline_blocked_continuous()` — pass verdict="BLOCKED", is_continuous=True → continue_loop=False, status NOT marked done
  - `test_run_post_pipeline_approved_next()` — pass verdict="APPROVED", is_next=True → status IS marked done (regression test)
  - `test_run_post_pipeline_changes_requested()` — pass verdict="CHANGES_REQUESTED" → behaves same as BLOCKED

  **Bug 3 tests (detect_commands refresh):**
  - `test_detect_commands_refreshes_on_vet_start()` — mock `detect_commands()` to return different values on second call (simulating AGENTS.md added on feature branch) → verify vet uses the refreshed values
  - `test_detect_commands_stale_not_used()` — run vet with and without AGENTS.md on feature branch → confirm defaults vs custom commands

---

## 5. Data Model

No new persistent state. All data is transient:

| Entity | Source | Lifetime | Fields |
|--------|--------|----------|--------|
| Archive target | `spec_path` from pipeline | Single invocation | spec directory path, branch name |
| Merge status | `gh pr view --json merged` | Single invocation | boolean |
| Command vars | `detect_commands()` return | Re-invoked per vet run | test_cmd, build_cmd, lint_cmd |
| Verdict seal | `run_post_pipeline()` parameter | Single invocation | "APPROVED" gate condition |

The spec archive already uses `shutil.move` — no new file format needed.

---

## 6. API/Interface Proposal

### New Functions

```python
def archive_specs_for_feature(spec_path: str, branch: str, pr_url: str) -> bool:
    """Move spec directory to archive/ if PR is merged. Returns True if archived."""
    ...
```

### Modified Functions

- `run_post_pipeline()` — adds archive call after verdict-based status update; adds verdict gate on "done" marking.
- `run_phase3_vet()` — adds `detect_commands()` re-invocation after branch checkout.
- `main()` (auto-archive block) — fixes branch name matching to be case-insensitive; moves primary archive to post-pipeline.

### No New CLI Flags

All changes are internal logic fixes. No new command-line arguments.

---

## 7. Security Considerations

- **No new external inputs.** Archive logic uses existing pipeline parameters (`spec_path`, `branch`, `pr_url`). Command refresh reads AGENTS.md which is already read during startup.
- **No new GitHub permissions.** All gh calls (`pr view`, `pr list`) already authorized by existing `GH_TOKEN`.
- **Path safety:** Archive uses `shutil.move` with paths derived from `PROJECT_DIR` and `spec_path` — no user-supplied paths in archive targets.
- **No credential exposure.** Same gh/API key paths as rest of dokima.

---

## 8. Test Plan (MANDATORY)

### Feature Area: Spec Archive (Bug 1)

- **Happy path:** Pipeline completes, PR is merged → `archive_specs_for_feature()` moves spec dir to archive/.
- **Edge case — PR not merged:** `gh pr view` returns `merged=false` → no archive.
- **Edge case — no PR URL:** `pr_url=None` → no archive, no crash.
- **Edge case — fallback scan at startup:** Spec dir exists with no matching pipeline run → fallback scan finds merged PR via case-insensitive branch match → archives.
- **Edge case — archive/ dir doesn't exist yet:** `os.makedirs` creates it.
- **Edge case — spec dir already archived:** `shutil.move` overwrites existing archive path.
- **Failure mode — gh CLI timeout:** `gh pr view` times out → warn and skip archive.
- **Contract invariant:** After archival, the spec dir exists under `specs/archive/` and NOT in `specs/`.

### Feature Area: Verdict Gate on STATUS.md (Bug 2)

- **Happy path — APPROVED + --next:** Verdict="APPROVED", is_next=True → status marked "done" in roadmap + STATUS.md.
- **Happy path — APPROVED + --continuous:** Verdict="APPROVED", is_continuous=True → auto-merge attempted, status marked "done" on success.
- **Edge case — BLOCKED + --next:** Verdict="BLOCKED", is_next=True → status stays "in_progress" [~], message printed.
- **Edge case — CHANGES_REQUESTED + --next:** Same as BLOCKED.
- **Edge case — BLOCKED + --continuous:** Verdict="BLOCKED", is_continuous=True → continue_loop=False, NOT marked done.
- **Edge case — BLOCKED + --next, CODER_FAILED + --next preexisting:** CODER_FAILED at line 1823 already reverts to pending — this logic path is NOT affected by the new guard.
- **Edge case — UNKNOWN verdict:** UNKNOWN at line 1823 already reverts to pending — not affected.
- **Contract invariant:** Only verdict=="APPROVED" triggers "done" status in roadmap and STATUS.md. All other verdicts (BLOCKED, CHANGES_REQUESTED, CODER_FAILED, TIMED_OUT, UNKNOWN) must NOT be recorded as "done".

### Feature Area: detect_commands Refresh (Bug 3)

- **Happy path:** AGENTS.md on feature branch specifies custom commands → vet uses custom commands.
- **Edge case — no AGENTS.md on feature branch:** `detect_commands()` returns defaults (`npm test`, etc.) → vet uses defaults (same behavior as before).
- **Edge case — AGENTS.md unchanged from default branch:** Refresh returns same values → no observable change.
- **Edge case — AGENTS.md has partial entries (e.g., only Test: without Build:):** Refresh picks up Test: from feature branch, Build: falls back to default.
- **Failure mode — can't read AGENTS.md:** `os.path.exists` returns False → defaults used.
- **Contract invariant:** After `detect_commands()` is called at the start of `run_phase3_vet()`, the globals `TEST_CMD`, `BUILD_CMD`, `LINT_CMD` reflect the AGENTS.md on the currently checked-out branch, not the startup branch.

---

## 9. COTS Build-vs-Buy

| Component | Decision | Justification |
|-----------|----------|---------------|
| Spec archive | **Built** — `shutil.move` + `gh pr view` | Already uses these; existing pattern |
| Verdict gate | **Built** — conditional check | Single `if` statement |
| Command refresh | **Built** — re-call `detect_commands()` | Already exists; just call again |
| Branch matching fallback | **Built** — `gh pr list` + case-insensitive query | `gh` is a hard dependency; case-insensitive matching via git/lower |

Nothing to buy. All fixes are pure logic changes in existing Python code.

---

## 10. Panel Split

**Single-threaded editing** — all changes are in `dokima` and share overlapping code paths (post-pipeline function). They must be applied carefully in order.

Recommended implementation order:
- **Wave 1:** Task 3 (new helper function `archive_specs_for_feature()`) + Task 7 (tests, can be written alongside)
- **Wave 2:** Task 4 (detect_commands refresh in vet) — independent of Wave 1
- **Wave 3:** Task 2 (verdict gate) + Task 5 (archive call in post-pipeline) — share `run_post_pipeline()`, must be done together
- **Wave 4:** Task 1 (move archive block) + Task 6 (fix fallback scan) — surgery on main()
- **Wave 5:** Integration testing — run full test suite

---

## 11. Build & Deploy

- **No new dependencies.** Pure Python 3.6+ with existing gh CLI.
- **No build changes.** Single-file script (`dokima`).
- **No new env vars.**
- **Deployment:** Same as current — copy/symlink `dokima` to `~/bin/dokima`.
- **CI:** `python3 -m pytest tests/ -q` already covers all test files. Add the new test file to the test run.

---

## 12. Risk Register

| # | Risk | Severity | Mitigation | Trigger |
|---|------|----------|------------|---------|
| 1 | Verdict gate breaks --continuous mode: loop stops incorrectly | MEDIUM | Existing `is_continuous` logic at lines 1863-1868 already handles `should_stop`. New behavior: BLOCKED verdict stops loop (prints reason). User re-runs `--continuous` to continue. | Loop stops on BLOCKED instead of falsely marking done |
| 2 | detect_commands refresh picks up AGENTS.md from wrong working tree | LOW | `run_phase3_vet()` checks out the branch (line 2674) before calling refresh. The working tree is correctly on the feature branch. | Chdir or subprocess cwd issue |
| 3 | Archive moves spec before it should (false positive merge detection) | LOW | `gh pr view` returns `merged=true` only after actual merge. The pipeline's own `try_auto_merge` already confirmed merge. False positives would require `gh` to misreport. | Race condition between merge check and move |
| 4 | Fallback archive scan misses specs due to branch name mismatch | MEDIUM | The fallback now uses case-insensitive matching (lowercasing both sides). Previous behavior missed 100% of cases. Any improvement is positive. | Edge case with unusual branch naming |
| 5 | Existing tests fail due to behavior change in `run_post_pipeline()` | LOW | Test suite already has `test_roadmap_update.py` (5 tests) and `test_status_md.py` (7 tests). These may need updating if they expected BLOCKED→done behavior. Review and update. | tests/ tests fail |

---

## 13. Anti-Creep

**Explicitly NOT in scope:**

- Adding a new CLI flag or mode
- Changing the pre-pipeline strategist flow
- Refactoring `slugify()` or branch naming conventions
- Adding auto-retry for BLOCKED PRs (loop now stops — user re-runs)
- Adding new environment variables
- Changing `run_phase4_nm()` or `run_phase5_tech_lead()`
- Adding archival of non-spec artifacts (logs, ADRs)
- Changing the `update_roadmap_status()` or `commit_roadmap_update()` functions themselves

---

## 14. Sign-Off Checklist

- [ ] `archive_specs_for_feature()` correctly moves spec dir to archive/ when PR is merged
- [ ] Primary archive fires in `run_post_pipeline()` (after pipeline completes), not before
- [ ] Fallback startup archive scan uses case-insensitive branch matching
- [ ] `--next` mode: BLOCKED verdict leaves status as `in_progress` [~], not "done"
- [ ] `--continuous` mode: BLOCKED verdict sets `continue_loop=False`, doesn't mark "done"
- [ ] `--next` mode: APPROVED verdict still marks "done" (regression check)
- [ ] `--continuous` mode: APPROVED verdict still marks "done" after auto-merge (regression check)
- [ ] CODER_FAILED/TIMED_OUT/UNKNOWN verdicts are unaffected (still revert to pending)
- [ ] `detect_commands()` re-runs in `run_phase3_vet()` after branch checkout
- [ ] Custom commands from feature branch AGENTS.md are used by vet, not startup defaults
- [ ] No AGENTS.md on feature branch → default commands used (no crash)
- [ ] All 9+ new tests pass
- [ ] Existing 196 tests still pass
- [ ] No new CLI flags, no new env vars, no new dependencies

---

## 15. Impact Assessment

**Files changed:**
- `dokima` — main script: ~120-140 LOC (net new + modifications)
- `tests/test_triple_bug_fix.py` — new test file: ~90 LOC

**Files NOT changed:**
- `run_phase2_coder()` — unchanged
- `run_phase4_nm()` — unchanged
- `run_phase5_tech_lead()` — unchanged
- `update_roadmap_status()` — unchanged (only calling code changes)
- `commit_roadmap_update()` — unchanged
- `update_status_md()` — unchanged (only calling code changes)
- `README.md` — no change needed (internal correctness fix)
- Any test file other than the new one — possibly minor fixture adjustments

**Cascading effects:**
- `run_post_pipeline()` signature is unchanged — only internal logic changes
- `run_phase3_vet()` signature is unchanged — only adds a `global` + re-call line at top
- The auto-archive block is removed from pre-pipeline position — `continue_loop` / `should_stop` logic unaffected (it was independent of archive)
- The startup fallback scan uses the same `shutil.move` logic but with case-insensitive branch matching — no new failure modes

**Estimated total LOC:** ~210-230 lines (net new + modifications)

**Risk level:** LOW. All three fixes are additive conditionals or ordering changes. The existing pre-pipeline flow (strategist → human gate → coder → vet → nm → TL) is completely unchanged. Only the post-pipeline bookkeeping and vet's command detection are modified.
