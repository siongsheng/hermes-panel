# Hermes Panel — Deployment & Setup Guide

Bring the multi-agent panel to a new repository or a fresh machine. One-time setup takes ~5 minutes per machine; per-project setup takes 60 seconds.

---

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌──────────────┐     ┌────────────┐
│ Strategist  │────▶│  Coder   │────▶│ Verification │────▶│ Tech Lead  │
│ (v4-pro)    │     │ (v4-flash)│     │  (shell)     │     │ (v4-pro)   │
│ Spec + DAG  │     │ TDD impl │     │ test+build+PR│     │ adversarial│
│ 5 min       │     │ 10 min   │     │ 2 min        │     │ 10 min     │
└─────────────┘     └──────────┘     └──────────────┘     └────────────┘
     ~$0.007           ~$0.002            $0.000             ~$0.004

                          Total: ~$0.014/run (46% below unoptimized)
```

**Gating:** Depth matrix auto-selects phases based on confidence × impact. `PANEL_FORCE_FULL=1` runs all 4.

---

## 1. Prerequisites

### On every machine

| Requirement | Check |
|-------------|-------|
| Hermes Agent installed | `hermes --version` |
| Python 3.6+ | `python3 --version` |
| `gh` CLI (GitHub) | `gh --version` |
| `git` 2.25+ | `git --version` |
| DeepSeek API access | API key in `~/.hermes/profiles/work/.env` |

### Per-project

| Requirement | Why |
|-------------|-----|
| `AGENTS.md` at repo root | Panel reads test/build/lint commands |
| GitHub remote configured | `git remote get-url origin` returns a GitHub URL |
| Existing test suite | Phase 2 (TDD) needs a test runner |

---

## 2. One-Time Machine Setup

### 2.1 Install the panel script

```bash
# If hermes-config is already cloned:
ln -sf ~/.hermes/scripts/hermes-panel ~/bin/hermes-panel

# Or clone fresh:
git clone https://github.com/siongsheng/hermes-config.git ~/hermes-config
ln -sf ~/hermes-config/scripts/hermes-panel ~/bin/hermes-panel
```

### 2.2 Create the 3 agent profiles

The panel spawns agents by profile name: `strategist`, `coder`, `tech-lead`.

```bash
# Create profiles (if they don't exist)
hermes config profile create strategist
hermes config profile create coder
hermes config profile create tech-lead
```

#### Strategist profile (`~/.hermes/profiles/strategist/config.yaml`)

```yaml
model:
  default: deepseek-v4-pro
  provider: deepseek
agent:
  reasoning_effort: medium
  max_turns: 150
terminal:
  env_passthrough: '[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]'
prompt_caching:
  cache_ttl: 5m
```

#### Coder profile (`~/.hermes/profiles/coder/config.yaml`)

```yaml
model:
  default: deepseek-v4-flash
  provider: deepseek
agent:
  max_turns: 150
terminal:
  env_passthrough: '[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]'
prompt_caching:
  cache_ttl: 30m
```

> **Why v4-flash for coder?** 3.1× cheaper than v4-pro ($0.28/M vs $0.89/M input tokens). The coder does mechanical TDD work — flash handles this reliably.

#### Tech Lead profile (`~/.hermes/profiles/tech-lead/config.yaml`)

```yaml
model:
  default: deepseek-v4-pro
  provider: deepseek
agent:
  max_turns: 150
terminal:
  env_passthrough: '[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]'
prompt_caching:
  cache_ttl: 30m
```

### 2.3 Deploy the lite skills

Two stripped-down skills that replace the full 14K `ai-coding-best-practices` + `adversarial-review`:

```bash
# Create coder skill directory
mkdir -p ~/.hermes/skills/software-development/ai-coding-best-practices-lite

# Create tech-lead skill directory
mkdir -p ~/.hermes/skills/software-development/adversarial-review-lite
```

#### `ai-coding-best-practices-lite/SKILL.md` (coder skill)

```markdown
---
name: ai-coding-best-practices-lite
description: "Stripped coding best practices for coder agents — TDD, task granularity, anti-patterns, verification gates only."
version: 1.0.0
---

# AI Coding Best Practices (Lite — Coder Edition)

## 1. TDD Enforcement (CRITICAL)

Follow TDD: Red → Green → Refactor.
1. Write simplest failing test first
2. Minimum code to pass
3. Refactor only after green
4. NEVER modify or delete tests to pass — fix code, not test

### Two-Commit Requirement

Tests and code MUST be in SEPARATE commits with distinct timestamps.

RED COMMIT (must show FIRST in git log):
  git add <test files only>
  git commit -m "test: <description>"

GREEN COMMIT (must show SECOND, later timestamp):
  git add <impl files only>
  git commit -m "feat: <description>"

## 2. Task Granularity

- One function/component/test-file per task. 5-15 min each.
- After each task: run tests, commit if green.
- Implement ALL tasks from the spec. Do not stop until ALL done.

## 3. No Scope Creep

- NEVER add features not in the spec.
- If you think something is missing, flag CLARIFICATION NEEDED: — do NOT implement.
- If env vars unavailable, create test skeleton with skip + comment.

## 4. Verification Gates

Before marking complete:
1. Tests pass
2. Type check / build passes
3. Lint passes
4. No scope creep

## 5. Anti-Patterns (BLOCKERS)

- Skipping tests
- Deleting failing tests
- Bundling tests + code in one commit
- Adding features not in spec
- Auto-committing without verification
```

#### `adversarial-review-lite/SKILL.md` (tech-lead skill)

```markdown
---
name: adversarial-review-lite
description: "Adversarial review + TDD verification for Tech Lead — review dimensions, severity levels, 2-commit check, output format."
version: 1.0.0
---

# Adversarial Review (Lite — Tech Lead Edition)

## Pre-Review: TDD Verification

Before reading code, verify the two-commit pattern:
git log master..BRANCH --format="%H %ai %s"
- RED commit (test:) must have EARLIER timestamp than GREEN commit (feat:)
- Bundled commits (test + impl in one) = BLOCKER regardless of code quality

## Three Review Dimensions

### 1. Spec Compliance
- Approach matches decision table?
- API/interface matches proposal?
- ALL tasks completed?
- Scope creep?

### 2. Architectural Impact
- New dependencies or coupling?
- Breaking changes?
- Deployment impact?

### 3. Code Quality
- Correctness, security, error handling, performance

## Severity

| Level | When | Action |
|-------|------|--------|
| **BLOCKER** | Spec violation, architecture break, TDD violation, security | Fix before merge |
| **SHOULD FIX** | Conventions, naming, redundant code | File GitHub Issue |
| **NIT** | Formatting, comments, style | Optional |

## Output Format

## Adversarial Review
### Pre-Review: TDD Check
- RED commit: <hash> (<timestamp>)
- GREEN commit: <hash> (<timestamp>)
- Verdict: PASS / BLOCKED

### Spec Compliance | Architectural Impact | Code Quality
(Severity | Finding | Location tables)

### Verdict
VERDICT: APPROVED / CHANGES REQUESTED / BLOCKED
RISK: LOW / MEDIUM / HIGH
```

### 2.4 Set GitHub token

```bash
# Add to work profile's .env
echo 'GH_TOKEN=ghp_yourpersonalaccesstoken' >> ~/.hermes/profiles/work/.env
```

Token needs: `repo` scope (for `gh pr create`, `gh issue create`, `gh pr review`).

### 2.5 Verify profiles start

```bash
# Start all profiles (one terminal each, or as daemons)
hermes --profile strategist &
hermes --profile coder &
hermes --profile tech-lead &
```

---

## 3. Per-Project Setup

### 3.1 AGENTS.md

The panel reads test/build/lint commands from `AGENTS.md` at the project root. Minimum content:

```markdown
# Project Name

Brief description of what this project does.

## Commands

Unit tests: `npm test`
Full build: `npm run build`
Lint: `npm run lint`
```

**Supported patterns** (any will be matched):

| Pattern | Example |
|---------|---------|
| `Unit test: \`cmd\`` | `npx vitest run` |
| `Tests: \`cmd\`` | `cargo test --lib` |
| `Full build: \`cmd\`` | `npx next build` |
| `Lint: \`cmd\`` | `npx eslint .` |

If no pattern matches, defaults to `npm test` / `npm run build` / `npm run lint`.

### 3.2 Project requires specs directory

Panel writes specs to `<project>/specs/`. The directory is auto-created — no setup needed.

### 3.3 Git remote must be GitHub

The panel auto-detects `owner/repo` from `git remote get-url origin`. Supports HTTPS and SSH formats:

```
https://github.com/owner/repo.git     ✓
git@github.com:owner/repo.git         ✓
```

---

## 4. Smoke Test

Verify the pipeline works with a trivial feature:

```bash
cd ~/your-project

# Quick test: add a comment to a file
hermes-panel "Add a JSDoc comment to the main function" .

# Force all 4 phases (for testing)
PANEL_FORCE_FULL=1 hermes-panel "Add a health check endpoint" .
```

**Expected output:**
```
═══ HERMES PANEL — Multi-Agent Orchestration ═══
── Phase 1: Strategist (full session) ──
...
✓ Spec saved: specs/add-a-jsdoc-comment-to-the-main-function-spec.md
── Orchestrator Gate ──
  Confidence: High, Impact: LOW → Depth: CODER
── Phase 2: Coder (feature branch) ──
...
✓ Coder finished
── Phase 3: Verification ──
  ✅ Tests: 42 passed, 0 failed
  ✅ Build: passed
  ✅ PR created: https://github.com/owner/repo/pull/1
✓ Pipeline complete.
```

---

## 5. Advanced: Cron Integration

Run the panel on a schedule for autonomous feature work:

```bash
# Create a cron job that runs panel for a feature each weekday at 2pm
hermes cron create \
  --schedule "0 14 * * 1-5" \
  --prompt "Run the panel for the next feature in the sprint backlog. Read ~/.hermes/sprints/12-week-plan.md to find the next unstarted feature." \
  --name "panel-daily-feature"
```

> When run from cron, the panel uses non-interactive mode. If the strategist needs clarification, panel exits code 2 and saves questions to `/tmp/hermes-panel-interview.json`. The orchestrator must pick these up and re-run with `--answers`.

---

## 6. Environment Variables

| Variable | Effect | Default |
|----------|--------|---------|
| `PANEL_REASONING` | Override strategist reasoning effort | `medium` (config) |
| `PANEL_PARALLEL` | Force sequential (`0`) or parallel (`1`) coders | `1` |
| `PANEL_FORCE_FULL` | Run all 4 phases regardless of depth matrix | off |
| `GH_TOKEN` | GitHub auth for PR/issue creation | from `.env` |

```bash
# High-quality spec for complex features
PANEL_REASONING=high hermes-panel "Add OAuth2 integration" ~/project

# Force adversarial review even for low-risk changes
PANEL_FORCE_FULL=1 hermes-panel "Add unit test for helper" ~/project

# Sequential mode (simpler debugging)
PANEL_PARALLEL=0 hermes-panel "Refactor database layer" ~/project
```

---

## 7. Interview Flow (Non-Interactive)

When the strategist can't proceed with high confidence, it enters interview mode:

```
1. Panel exits with code 2, saves questions to /tmp/hermes-panel-interview.json
2. Orchestrator (you or a cron handler) reads the JSON
3. Presents questions to the user, collects answers
4. Writes answers back to the JSON file
5. Re-runs: hermes-panel --answers /tmp/hermes-panel-interview.json "feature" ~/project
```

**Interview JSON format:**
```json
{
    "feature": "Add API key authentication",
    "project": "/home/user/project",
    "questions": [
        "CLARIFICATION 1: Should API keys be per-user or per-project?",
        "CLARIFICATION 2: Where should keys be stored?"
    ],
    "answers": [
        "Per-user keys",
        "In the users table, hashed"
    ]
}
```

---

## 8. Depth Matrix

| Confidence → / Impact ↓ | HIGH | MEDIUM | LOW |
|---|---|---|---|
| **LOW** (tests/docs) | Phase 1-2 | Phase 1-3 | Phase 1-4 |
| **MEDIUM** (API/DB/UI) | Phase 1-3 | Phase 1-4 | Phase 1-4 |
| **HIGH** (auth/payments) | Phase 1-4 | Phase 1-4 | Phase 1-4 |

- **Phase 1:** Strategist (always runs)
- **Phase 2:** Coder (always runs)
- **Phase 3:** Verification (test + build + PR)
- **Phase 4:** Tech Lead (adversarial review)

`PANEL_FORCE_FULL=1` overrides everything → all 4 phases.

---

## 9. Token Optimization Summary

| Optimization | Savings |
|-------------|---------|
| Spec noise extraction | 45-58% smaller spec |
| Task-extract for coder | Coder reads ~800 chars, not ~12K |
| Coder v4-flash model | 3.1× cheaper than v4-pro |
| Phase 3 pure shell | Zero AI tokens (was ~3K tokens) |
| `adversarial-review-lite` skill | 2.2K vs 13.8K for full skill |

**Result:** ~$0.014/full run → 46% cheaper than unoptimized.

---

## 10. Troubleshooting

### "No AGENTS.md found"
Create one at project root. Minimum:
```markdown
## Commands
Unit tests: `npm test`
Full build: `npm run build`
```

### "Could not detect GitHub repo"
Ensure `git remote get-url origin` returns a valid GitHub URL. The panel supports both HTTPS and SSH formats.

### "gh pr create fails with 401"
`GH_TOKEN` not found or expired. Check `~/.hermes/profiles/work/.env`. Token needs `repo` scope.

### "Strategist produces zero-byte spec"
Interview mode triggered but `--answers` was not provided. Check `/tmp/hermes-panel-interview.json` for questions. Re-run with `--answers`.

### "Coder times out with no branch"
The coder profile may be hitting API rate limits or the feature is too large. Try:
- `PANEL_PARALLEL=0` for sequential mode
- Break the feature into smaller sub-features
- Check `~/.hermes/profiles/coder/config.yaml` for model and provider config

### "Verification fails after 2 retries"
The coder pushed broken code. Check the test/build failure output in the panel log (`/tmp/hermes-panel-output.txt`). Fix manually, then re-run with the same feature description.
