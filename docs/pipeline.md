# Hermes Panel — Multi-Agent Orchestration Engine v1.2

`hermes-panel` routes feature development through a specialist panel of AI agents: **Strategist → Coder → Verification → Tech Lead**, with automated depth-gating, interview pause-and-resume, and parallel execution.

> **New here?** Start with [panel-setup.md](panel-setup.md) for deployment instructions.

---

## Quick Start

```bash
# Basic: run on any project with AGENTS.md + git remote
hermes-panel "Add rate limiting middleware" ~/atlas

# Force all 4 phases (even for low-risk changes)
PANEL_FORCE_FULL=1 hermes-panel "Add payment webhook handler" ~/atlas

# High-quality spec for complex features
PANEL_REASONING=high hermes-panel "Design OAuth2 integration" ~/atlas

# Resume after strategist interview
hermes-panel --answers /tmp/hermes-panel-interview.json "Add API key auth" ~/atlas
```

---

## Pipeline Phases

```
Strategist (300s) ──▶ Coder (600s) ──▶ Verification (shell) ──▶ Tech Lead (600s)
   v4-pro               v4-flash           ZERO AI tokens          v4-pro
   ~$0.007              ~$0.002             $0.000                  ~$0.004
```

### Phase 1: Strategist (always runs)
Full Hermes session exploring the codebase. Reads `AGENTS.md`, searches for relevant code, understands existing patterns. Produces:
- Decision table comparing ≥2 approaches
- Impact assessment (files/tables/routes affected)
- Confidence + Impact markers (for depth gating)
- API/interface proposal
- Security considerations
- Numbered task breakdown in DAG format (5-15 min each, TDD-ready)

**Output:** Cleaned spec saved to `specs/<feature>-spec.md`. Session noise (prompt echo, tool calls, init markers) stripped — spec is 45-58% smaller than raw session.

### Orchestrator Gate
Reads confidence × impact from the strategist's spec and decides pipeline depth:

| Confidence → / Impact ↓ | HIGH | MEDIUM | LOW |
|---|---|---|---|
| **LOW** (tests/docs) | 1+2 | 1+2+3+4 | 1+2+3+4 |
| **MEDIUM** (API/DB/UI) | 1+2+3 | 1+2+3+4 | 1+2+3+4 |
| **HIGH** (auth/payments) | 1+2+3+4 | 1+2+3+4 | 1+2+3+4 |

Only HIGH confidence gets the fast path. Everything else gets adversarial review.

**Mode:** High confidence = PASSIVE (auto-pilot). Medium/Low = ACTIVE (orchestrator reviews each phase, may loop back).

`PANEL_FORCE_FULL=1` overrides → all 4 phases.

### Phase 2: Coder
Implements the spec on a `feat/<slug>` branch with TDD (RED→GREEN two-commit discipline):
- Reads task-extract (`specs/<feature>-tasks.md`), not full spec
- Uses `deepseek-v4-flash` (3.1× cheaper than v4-pro) with `ai-coding-best-practices-lite` skill
- Before push: runs lint + full test suite. Fixes failures in-session.
- At `depth=coder`: creates PR directly. Otherwise pushes branch for verification.

**Parallel mode** (default, `PANEL_PARALLEL=1`): Tasks with no file collisions run in parallel worktrees. Waves computed from task DAG. `PANEL_PARALLEL=0` forces sequential.

### Phase 3: Verification (shell — zero AI tokens)
Pure shell script. No AI agent. No tokens. No model.

1. Checkout feature branch
2. Run `npm test` (or project's test command)
3. Run `npm run build` (catches TypeScript errors tests miss)
4. Create PR via `gh pr create`

**Verification retry loop:** On test/build failure → spawn coder with failure output → fix → re-verify (up to 2 retries). BLOCKED if still failing after max retries.

**Risk:** Reuses strategist's impact assessment (LOW/MEDIUM/HIGH). Zero additional tokens.

### Phase 4: Tech Lead (depth=full only)
Three-part adversarial review against the spec using `deepseek-v4-pro` + `adversarial-review-lite` skill (2.2K vs 13.8K for full skill):

1. **Spec Compliance** — Approach matches decision table? API/interface matches? ALL tasks done? Scope creep?
2. **Architectural Impact** — New deps/coupling? Breaking changes? Deployment impact?
3. **Code Quality** — TDD, correctness, security, error handling, performance

**Severity:** BLOCKER (fix before merge) | SHOULD FIX (auto-creates GitHub Issues) | NIT (optional)

**Verdict:** APPROVED / CHANGES REQUESTED / BLOCKED

---

## Interview Flow (Pause-and-Resume)

When the strategist cannot proceed with high confidence, it enters interview mode:

```
1. Panel exits with code 2
2. Saves questions + context to /tmp/hermes-panel-interview.json
3. Orchestrator reads JSON, presents questions to user
4. User answers → orchestrator writes answers back to JSON
5. Re-run: hermes-panel --answers /tmp/hermes-panel-interview.json "feature" ~/project
```

The interview JSON captures full context (assumption, impact if wrong) for each question. This keeps the panel stateless and replayable — perfect for Telegram/cron workflows.

```
┌─ Q1: Should API keys be per-user or per-project?
│  Assumption: Per-project keys (simpler implementation)
│  Impact: If wrong, multi-user projects share keys → security issue
└────────────────────────────────────────
```

---

## Environment Variables

| Variable | Effect | Default |
|----------|--------|---------|
| `PANEL_REASONING` | Override strategist reasoning effort (`high`/`medium`) | `medium` (config) |
| `PANEL_PARALLEL` | Force sequential (`0`) or parallel (`1`) coders | `1` |
| `PANEL_FORCE_FULL` | Run all 4 phases regardless of depth matrix | off |
| `GH_TOKEN` | GitHub auth for PR/issue creation | from `.env` |

---

## Token Optimizations

The panel has been systematically optimized to reduce cost while preserving quality:

| Optimization | Mechanism | Savings |
|-------------|-----------|---------|
| Spec noise extraction | Strip session transcript (prompt echo, tool calls) from strategist output | 45-58% smaller |
| Task-extract for coder | Generate `specs/<feature>-tasks.md` — coder reads ~800 chars, not ~12K | ~93% smaller read |
| Coder flash model | `deepseek-v4-flash` at $0.28/M input vs $0.89/M (v4-pro) | 3.1× cheaper |
| Phase 3 pure shell | No AI agent — `git checkout`, `npm test`, `npm run build`, `gh pr create` | ~3K tokens saved |
| `adversarial-review-lite` | 2.2K vs 13.8K for full `adversarial-review` + `ai-coding-best-practices` | ~11.5K system tokens saved |
| Cache TTL 30m | Extended prompt cache on coder + tech-lead profiles | Cuts repeat-read costs |

**Cost per full run (4 phases): ~$0.014** — 46% below unoptimized baseline (~$0.026).

| Phase | Model | Input tokens | Output tokens | Cost |
|-------|-------|-------------|---------------|------|
| Strategist | v4-pro | ~8,000 | ~3,750 | $0.007 |
| Coder | v4-flash | ~5,000 | ~2,500 | $0.002 |
| Verification | shell | — | — | $0.000 |
| Tech Lead | v4-pro | ~6,000 | ~1,500 | $0.004 |
| **Total** | | **~19,000** | **~7,750** | **~$0.014** |

---

## Project Detection

The panel auto-detects from the project directory:
- **GitHub repo:** parsed from `git remote get-url origin` (supports HTTPS and SSH URLs)
- **Test command:** parsed from `AGENTS.md` matching patterns like `Unit tests: \`npx vitest run\``
- **Build command:** parsed from `AGENTS.md` matching patterns like `Full build: \`npm run build\``
- **Lint command:** parsed from `AGENTS.md` matching patterns like `Lint: \`npx eslint .\``

Falls back to `npm test` / `npm run build` / `npm run lint` if AGENTS.md patterns not found.

---

## Failure Handling

When any phase fails, the panel:
1. Reverts ALL changes (deletes branch, `git checkout master`, clears stash)
2. Prints a `PIPELINE HALTED` summary with phase and reason
3. Prints "Orchestrator Action Required" checklist
4. Exits cleanly — **no automatic retry** without user approval

Per-phase timeout fallbacks:

| Phase | Timeout Response |
|-------|-----------------|
| Strategist | If output < 500 chars → abort pipeline |
| Coder | If branch exists → continue with partial output. If not → abort |
| Verification | Fail → spawn coder to fix → re-verify (up to 2 retries). BLOCKED if still failing |
| Tech Lead | Use partial output for verdict. Partial review > no review |

---

## File Structure

```
~/.hermes/scripts/hermes-panel              → canonical source
<project>/specs/<feature>-spec.md           → cleaned strategist spec
<project>/specs/<feature>-tasks.md          → task-extract for coder
<project>/.hermes-panel/worktrees/          → parallel coder sandboxes
/tmp/hermes-panel-output.txt               → full pipeline log
/tmp/hermes-panel-interview.json           → interview state (exit code 2)
```

---

## Companion Scripts

| Script | Purpose |
|--------|---------|
| `nm` | Standalone no-mistakes validation (manual runs) |
| `daily-cleanup.sh` | Cron-driven cleanup |
| `github-monitor.sh` | GitHub activity monitoring |

---

## Setup & Deployment

See [panel-setup.md](panel-setup.md) for:
- One-time machine setup (profiles, skills, GH token)
- Per-project setup (AGENTS.md, git remote)
- Smoke test instructions
- Cron integration
- Troubleshooting

---

## Requirements

- Python 3.6+ (compatible with Oracle Linux 8 system Python)
- Hermes Agent installed with 3 profiles (strategist, coder, tech-lead)
- `gh` CLI (GitHub) installed and authenticated
- DeepSeek API access (coder + tech-lead profiles configured)
- `AGENTS.md` at project root with test, build, and lint commands
- GitHub remote configured (`git remote get-url origin`)
- `GH_TOKEN` in `~/.hermes/profiles/work/.env`
