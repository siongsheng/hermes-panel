# Dokima — Maintainer's Reference

> Everything you need to remember about Dokima's internals. Update this doc when you discover new gotchas.

Last updated: 2026-06-29

---

## Architecture at a Glance

Dokima is a single Python script (`dokima`, ~5,450 lines, zero dependencies) that orchestrates a 5-phase AI agent pipeline:

```
Strategist → Coder → Vet → nm → Tech Lead
   (spec)    (code)  (build+test) (adversarial) (final gate)
```

Each phase spawns a separate `hermes --profile <role>` process via `spawn_agent()`. The orchestrator (this script) routes data between phases, enforces quality gates, and manages git branches/PRs.

---

## Key Functions by Phase

### Phase 1: Strategist (`run_phase1_strategist`, line 4198)
- Spawns `hermes --profile strategist` with `spec-strategist-lite` skill
- Produces a spec + task breakdown in DAG format
- Quality gate: `verify_spec_quality()` checks for Impact, What Changed, Task headers
- DAG re-prompt: if no `### Task N:` headers found, re-runs strategist once
- Interview mode: if `DECISION: INTERVIEW MODE`, saves `/tmp/dokima-interview.json`, exits 2
- Output: `specs/<feature>-spec.md`, `specs/<feature>-tasks.md`

### Phase 2: Coder (`run_phase2_coder`, line 3406)
- Spawns `hermes --profile coder` with `ai-coding-best-practices-lite`
- Constructs prompt with: codebase map, target file hints, line-range code context
- Enforces TDD: RED commit (failing test) → GREEN commit (passing code)
- Two execution paths: `single_session` (batch) or `per_task_spawn` (parallel worktrees)
- Model upgrade: uses `deepseek-v4-pro` for fix mode or ≥8 tasks

### Phase 3: Vet (`run_phase3_vet`, line 3664)
- Checks out feature branch, runs `BUILD_CMD` + `TEST_CMD` + `LINT_CMD`
- Re-runs project detection (AGENTS.md may have changed on branch)
- Reports pass/fail — pipeline halts on failure

### Phase 4: nm / Adversarial Review (`run_phase4_nm`, line 3822)
- Runs `~/bin/nm` script — cross-family adversarial review
- nm profile MUST use different model family from coder (currently Qwen, fallback Gemini)
- Risk extraction from nm output; fallback to strategist's Impact assessment

### Phase 5: Tech Lead (`run_phase5_tech_lead`, line 4019)
- Spawns `hermes --profile tech-lead` for final review
- Verdict extraction: `_extract_tl_verdict()` takes LAST `VERDICT:` line (TL may change mind mid-review)
- Blocker extraction: `_extract_tl_blockers()` filters out monologue noise
- Updates PR body with Review section

---

## Data Structures

| Class | Line | Purpose |
|-------|------|---------|
| `Task` | 807 | One unit of work: name, files, deps, parallelizable, status, output |
| `TaskDAG` | 834 | Parses strategist output into tasks + waves; `compute_execution_mode()` auto-selects single_session vs per_task_spawn |
| `RoadmapFeature` | 821 | Parsed roadmap entry: id, priority, status, deps |
| `WorktreeManager` | 686 | Creates/destroys git worktrees for parallel coder isolation |
| `TaskLock` | 772 | Per-task file lock for parallel safety |

### Execution Mode Selection (`TaskDAG.compute_execution_mode()`)
```python
all_parallelizable AND (tasks > 10 OR distinct_files > 3) → per_task_spawn
otherwise → single_session
```
**Critical rule:** Only spawn per-task when ALL tasks are parallelizable (no shared files). Non-parallelizable tasks in per_task_spawn = guaranteed merge conflicts (Bug 14).

---

## Model Profiles

| Profile | Primary Model | Provider | Family |
|---------|---------------|----------|--------|
| Strategist | deepseek-v4-pro | DeepSeek | DeepSeek |
| Coder | deepseek-v4-pro | DeepSeek | DeepSeek |
| nm | qwen/qwen3-coder-next | OpenRouter | Qwen |
| nm (fallback) | gemini-2.5-flash | Google | Google |
| Tech Lead | deepseek-v4-pro | DeepSeek | DeepSeek |

**Cross-family rule:** nm MUST be different model family from coder. Both primary AND fallback are cross-family — same-family review never happens.

Config: `~/.hermes/profiles/<role>/config.yaml`
Profile `.env` files REPLACE (don't merge with) `~/.hermes/shared.env` — copy all needed keys.

---

## DeepSeek Model Quirks

DeepSeek models (v4-pro) have consistent output quirks that the parser handles:

| Quirk | Expected | DeepSeek Output | Parsed As |
|-------|----------|-----------------|-----------|
| Task headers | `### Task 1:` | `    Task 1:` (4-space indent, no `###`) | Fine — regex accepts both |
| Bold markers | `**Files:**` | `    Files:` (no bold) | Fine — regex accepts both |
| Parallelizable field | `**Parallelizable:** yes` | Often omitted entirely | Fine — defaults to `True` |
| Wave format | `### Task N:` | `- Wave 1: Task 1, 2, 3` | Caught — DAG re-prompt fires |
| Thinking blocks | N/A | `<thinking>### Task 1:</thinking>` | Caught — `extract_agent_messages()` strips thinking |

**Key insight:** Never require `###` or `**bold**` in regex. Always use `(?:###\s*)?` and `(?:\*\*)?` prefixes. Default Parallelizable to `True`.

---

## Regex Gotchas (Critical)

### 1. `^##` matching own header in roadmap parsing
Searching from `abs_start + 1` after `### F003:` gives a string starting with `## F003:` — `^##\s` matches at position 0 with `re.MULTILINE`. **Fix:** start search at `abs_start + 4`.

### 2. `DECISION: INTERVIEW MODE` substring match
`if "DECISION: INTERVIEW MODE" in text` triggers on spec prose that mentions interview mode. **Fix:** suppress when `### Task N:` headers are present (real spec, not interview request).

### 3. `CLARIFICATION N:` in spec prose
Unanchored regex matches spec prose describing interview mode behavior. **Fix:** anchor to line start with `^` and `re.MULTILINE`.

### 4. Verdict extraction — last wins
TL may produce `VERDICT: APPROVED` then change to `VERDICT: BLOCKED`. **Fix:** `re.findall` all verdicts, take `[-1]`.

---

## Pipeline Cleanup (When Things Go Wrong)

> **F023 Self-Healing (Jun 2026):** Dokima now includes automatic lock-age cleanup
> (stale locks >12h auto-removed even with live PID), fix-loop hash cycle detection
> (identical test+build output after coder fix → skip to BLOCKED), and coder output
> truncation detection (retries once if output appears incomplete).

```bash
# Kill a running pipeline
kill <pid>

# Full cleanup
cd ~/dokima
rm -f /tmp/dokima-dokima.lock /tmp/dokima-dokima.stop
rm -rf .dokima/worktrees/ .dokima/locks/
rm -f /tmp/dokima-*.json /tmp/dokima-*.lock
git checkout main
git branch -D feat/<feature-slug> 2>/dev/null
git branch -D feat/<feature-slug>-t* 2>/dev/null
git push origin --delete feat/<feature-slug> 2>/dev/null

# Re-run
PANEL_SKIP_ORCHESTRATOR_REVIEW=1 python3 dokima --next .
```

---

## Key Files

| Path | Purpose |
|------|---------|
| `dokima` | The entire panel — single script |
| `specs/roadmap.md` | Feature backlog with status markers |
| `specs/codebase-map.md` | Auto-generated directory tree + file descriptions |
| `specs/conventions.md` | Coding conventions and anti-patterns |
| `specs/<feature>-spec.md` | Strategist output for a feature |
| `specs/<feature>-tasks.md` | Task breakdown (DAG format) |
| `tests/` | 495+ tests (pytest) |
| `~/.hermes/profiles/coder/config.yaml` | Coder model config |
| `~/.hermes/profiles/nm/config.yaml` | Adversarial reviewer model config |
| `~/.hermes/skills/software-development/dokima-panel/SKILL.md` | Full skill doc with bug registry |
| `~/.hermes/sprints/12-week-plan.md` | Sprint plan |

---

## Test Suite Map

| Test File | What It Covers |
|-----------|---------------|
| `test_add_to_roadmap.py` | `--add` command: auto-priority, deps, section placement |
| `test_roadmap_parse.py` | Roadmap parsing + feature extraction |
| `test_pick_next_feature.py` | Feature ordering: priority sort, deps, in_progress inclusion |
| `test_root_cause_regressions.py` | Bug 1-8 regression tests (DAG thinking, verdict, anti-creep, etc.) |
| `test_tl_extraction.py` | TL output parsing: verdict + blocker extraction |
| `test_task_dag.py` | TaskDAG parsing + execution mode dispatch |
| `test_f001_security.py` | Prompt sanitization, token redaction, file permissions |
| `test_f003_robustness.py` | Edge cases: RED-only, empty coder, timeouts, locks, slugify |
| `test_f006_recovery.py` | Checkpoint save/load, resume gating |
| `test_extract_file_paths.py` | File path extraction from specs/tasks |
| `test_spec_quality_gates.py` | Spec structure validation (Impact, What Changed, Tasks) |
| `test_pipeline_integration.py` | Full pipeline with mocked agents |
| `conftest.py` | `panel` + `test_repo` fixtures |

**Running tests:**
```bash
python3 -m pytest tests/ -q                          # full suite
python3 -m pytest tests/ -q -x                       # stop on first failure
python3 -m pytest tests/test_f003_robustness.py -v   # single file verbose
```

---

## Common Commands

```bash
# Run next pending feature
PANEL_SKIP_ORCHESTRATOR_REVIEW=1 python3 dokima --next .

# Add feature to roadmap
python3 dokima --add "Feature description"

# Fix a BLOCKED PR
PANEL_SKIP_ORCHESTRATOR_REVIEW=1 python3 dokima --fix --fix-all .

# Show pipeline state
python3 dokima --status .

# Full sprint loop (runs continuously)
PANEL_SKIP_ORCHESTRATOR_REVIEW=1 python3 dokima --continuous .

# Force full pipeline (ignore depth gating)
python3 dokima --next --force-full .
```

---

## Depth Gating Matrix (F009)

```
Confidence × Impact → Pipeline Depth
─────────────────────────────────────
(High,   LOW)     → vet        (build+test only)
(High,   MEDIUM)  → vet+nm     (build+test + adversarial review)
(High,   HIGH)    → full       (all 5 phases)
(Medium, LOW)     → vet+nm
(Medium, MEDIUM)  → full
(Medium, HIGH)    → full
(Low,    LOW)     → vet
(Low,    MEDIUM)  → vet+nm
(Low,    HIGH)    → full
```

`--force-full` overrides to `full` regardless.

---

## PR Conventions

PR body must have sections in order: `## Why` → `## Impact` → `## What Changed` → `## Validation`

- **Never merge without TL review** — nm approval alone is insufficient
- **Squash-merge pitfall:** Rebase feature branch onto main before squash-merging, or main-only files get deleted (Bug: squash merge treats feature branch tree as authoritative)
- **Scope creep:** TL will block PRs with roadmap commits from other features — cherry-pick only feature-specific commits to a clean branch

---

## Known Bugs (Unfixed)

| Bug | Severity | Description |
|-----|----------|-------------|
| 1c | LOW | Strategist uses wave format despite prompt prohibition — DAG re-prompt recovers |
| 11 | MEDIUM | Merge assembly fails on same-file task branches — fixed by Bug 14 (execution mode) but still possible if tasks incorrectly marked parallelizable |
| 19 | MEDIUM | Coder reads full codebase despite file hints — mitigated by `_extract_code_context()` (Jun 29) |
| Strategist scope creep | LOW | Strategist adds tasks beyond spec scope — >20% more tasks is suspect |
| spawn_agent blocking | LOW | `proc.stdout` blocking read can hang — use `_safe_run` pattern |

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `PANEL_SKIP_ORCHESTRATOR_REVIEW` | Skip human gate (set to `1` for automated runs) |
| `PANEL_FORCE_FULL` | Force full pipeline depth regardless of confidence/impact |
| `PANEL_MAX_PARALLEL` | Max concurrent coder worktrees (default from profile config) |
