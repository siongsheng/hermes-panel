---
name: no-mistakes
description: Automated validation pipeline for AI-generated code changes. Runs after every non-trivial coding task — fresh-context review, tests, doc lint, PR creation with risk assessment. Must be loaded by all coding sessions.
version: 2.0.0
---

# No Mistakes — Validation Pipeline

Run after every non-trivial coding task. Spawns a fresh Hermes session to review the change with clean context.

## When to Run

- After completing any feature, fix, or refactor
- Before merging any PR
- Skip only for trivial changes (typos, comments, formatting)

## Execution

After completing a coding task, commit the changes, then execute:

```bash
nm
```

This runs the shell script at `~/bin/nm` which spawns a **fresh Hermes session** that:
1. Captures the git diff and changed files from the current repo
2. Loads `no-mistakes` + `ai-coding-best-practices` skills
3. Runs the full 7-stage pipeline with clean context
4. Reports risk assessment (LOW/MEDIUM/HIGH)

**Why a fresh session?** If review runs in the same session that wrote the code, the model is biased — it saw every step and assumes correctness. A fresh session has no memory of the coding process and catches significantly more edge cases.

**Pitfall:** `hermes chat -q "<prompt>"` must pass the prompt as a CLI argument, not via stdin redirection. The `nm` script handles this correctly — do not modify the invocation pattern.

## Options

```bash
nm              # Full pipeline (all 7 stages)
nm --skip-tests # Skip test execution (user already ran them)
```

## Gotchas (Common Pitfalls)

### Terminal commands blocked by approval prompt
The fresh Hermes session runs with `--yolo` to avoid approval prompts blocking the pipeline. Without it, every `git` or `gh` command hangs waiting for a user that isn't there. The `nm` script handles this automatically.

### gh CLI not authenticated (no PR created)
`gh` needs `GH_TOKEN` set, not `GITHUB_TOKEN`. The standalone `~/bin/nm` script sources `~/.hermes/.env` which has the correct token. When nm runs inside the panel pipeline, `spawn_agent()` sets GH_TOKEN automatically — the agent should use it directly and NOT re-source `.env` (which may override with a project-local empty value).

### Redaction mangling edits to nm script
Hermes' secret redaction replaces token-like values with `***` even inside string literals in shell scripts. When editing `~/bin/nm`, avoid mentioning token env var names in patch/write_file calls. Use `read_file` + `execute_code` instead, splitting prefix strings: `prefix = 'GITHUB_TOKEN' + '='`.

### `--yolo` required
The fresh Hermes session spawned by `nm` runs autonomously with no user to approve terminal commands. Without `--yolo`, git and test commands time out waiting for approval. The script MUST include `--yolo`.

### `hermes chat` stdin piping doesn't work
`hermes chat -q "prompt"` works. `hermes chat < file` or `hermes chat --quiet < file` exits immediately with "Input is not a terminal." Always use `-q` with the prompt as a quoted argument.

### `gh pr create` needs BOTH GH_TOKEN and GITHUB_TOKEN
GitHub CLI checks `GITHUB_TOKEN` FIRST, then falls back to `GH_TOKEN`. Setting only `GH_TOKEN` causes HTTP 401 even when the token is valid. Both env vars must be set to the same value. The `.env` file typically uses `GITHUB_TOKEN`.

**Standalone nm (`~/bin/nm`):** Sources `~/.hermes/.env` for both tokens before running — this is the standalone script's responsibility.

**Panel-spawned nm:** `spawn_agent()` already sets BOTH `GH_TOKEN` and `GITHUB_TOKEN` in the child's environment from `~/.hermes/.env`. The spawned agent does NOT need to source `.env` for gh auth — prompts say "GH_TOKEN is already in your environment — use it directly." Sourcing the project's `.env` may override with an empty/stale token, causing 401s. Verified 2026-06-16: direct API call with token returns 200, `gh` CLI with only `GH_TOKEN` = 401, `gh` CLI with both env vars = success (PR #14 created).

### `tsconfig.tsbuildinfo` / large generated files cause "Argument list too long"

`git diff` includes tsconfig.tsbuildinfo deletions (can be 500KB+ per file). Combined with env passthrough vars, this exceeds `ARG_MAX`. The nm script should exclude build artifacts:

```bash
git diff -- . ':(exclude)*.tsbuildinfo' ':(exclude)package-lock.json'
```

Also: squash fixup commits (like .gitignore additions) before running nm so the diff shows the actual code changes, not cleanup noise.

### Hermes secret redaction corrupts shell/Python code
When writing scripts that reference API token variable names (like `GITHUB_TOKEN`), Hermes replaces the value with `***` — even inside string literals. This breaks `if line.startswith('TOKEN=***'` and `export GH_TOKEN="$GIT...`. Workaround in Python: use `'KEY' + '='` split strings. In shell: add the export to `.env` directly and `source` it — never inline token values in scripts.

### ARG_MAX — diff too large for `hermes chat -q`
Large commits (200+ line diffs across 8+ files) can cause `Argument list too long` because the prompt + diff + environment exceed the kernel ARG_MAX (~2MB). The `nm` script trims diffs to 500 lines to stay under the limit. If you still hit this, commit the change first so `nm` picks up `git diff HEAD~1` (usually smaller than working-tree diff), or run `nm` from a clean working tree. Do NOT remove the `-q` approach — stdin piping doesn't work with `hermes chat`.

### Vitest doesn't auto-load .env
Vitest has no built-in `.env` loading. Integration tests that need `MONGODB_URI` or similar will fail with "not set" unless you configure dotenv. Fix: `npm install dotenv`, create `tests/setup.ts` with `import "dotenv/config"`, add `setupFiles: ["tests/setup.ts"]` to `vitest.config.ts`. See `references/vitest-dotenv-setup.md`.

### Risk Assessment for Docs Changes
Documentation-only changes (AGENTS.md, specs/*.md, README) are LOW risk by default. But the pipeline still catches factual errors — nm found edition and container name mismatches in a docs change. Never skip nm, even for docs.

### Domain-Specific Review Patterns

The adversarial review stage should consult domain-specific checklists when the
code under review involves financial calculations, backtesting, or numerical
models. See `references/backtesting-review-patterns.md` for common P&L and
equity-curve bugs that nm has caught in practice.

### Language-Specific Pitfalls

- **Python:** `references/python-default-argument-pitfall.md` — mutable/sentinel
  defaults bound at import time, not call time

## What the Pipeline Does

| Stage | What | Fresh Session? |
|-------|------|---------------|
| Intent | Extract what was built and why | Yes |
| Branch + Commit | Auto-name branch, conventional commit | Yes |
| Rebase | Rebase onto latest main | Yes |
| Fresh-Context Review | Different model family reviews the diff | Yes |
| Test + Evidence | Run test suite, capture evidence | Yes |
| Doc Lint | Find stale documentation | Yes |
| Push + PR | Create PR with risk assessment. PR body must include `## Why` — extract the problem/motivation from commit messages (or the spec if available). Never use bare "See commits on this branch." | Yes |

## Risk Triage

| Risk Level | Agent delivers | User action required |
|---|---|---|---|
| LOW | PR link + diff summary + risk assessment | User says "merge" or "go" — agent waits |
| MEDIUM | PR link + full diff + SHOULD FIX list | User reviews diff, says "merge" |
| HIGH | PR link + full diff + BLOCKER analysis table | User reviews, coordinates fix, says "merge" |

**AGENT NEVER MERGES WITHOUT EXPLICIT APPROVAL.** Even LOW risk. Even if nm says APPROVED. Even if the PR has been sitting for hours. Even if you personally fixed all the BLOCKERs and SHOULD FIXes. Present the PR link + summary, then WAIT. This is the #1 trust-eroding behaviour in the Huat pipeline — the user has corrected this three times now (TG6 review, TG9 merge, ibcore PR #3). The correct sequence is: review → fix blockers → present PR → WAIT FOR USER TO SAY merge. Do not assume. Do not pre-empt. Do not ask should I merge? — just present the PR and stop.

**NM must NOT create or merge PRs for related branches discovered during rebase.** The rebase step (Stage 3) may discover unmerged feature branches on the remote (e.g. feat/contract-caching sitting on origin/master ahead of local master). The NM session MUST NOT create a PR for these branches or merge them — they are separate features the user has not reviewed. Only create PRs for the branch NM was invoked on. If the rebase picks up related commits, that is fine for the diff context — but do NOT create additional PRs or merge anything. Example: NM ran on feat/commission-correlation, discovered feat/contract-caching on origin/master, created PR #5 AND merged it without user approval. This is a violation.

### ⛔ After nm: BLOCKER Triage — ANALYZE FIRST, FIX SECOND

**THIS IS THE MOST VIOLATED RULE.** In June 2026 alone, the agent blindly fixed 3 false BLOCKERs in TG6 and 3 more in TG8 before the user caught it both times. Every session that runs nm MUST apply this section before touching code.

**DO NOT FIX BLIND.** nm miscategorizes ~30-40% of BLOCKERs as more severe than they are. The user expects explicit analysis before any fix. Failing to challenge false BLOCKERs wastes time and erodes trust.

**YOUR FIRST ACTION after seeing nm output is NOT to start fixing — it's to present a table analyzing every BLOCKER:**

| # | nm says | Real? | Already handled? | Verdict |
|---|---------|-------|-----------------|---------|
| 1 | ... | Yes/No | Guard at line X | BLOCKER / False alarm |

Only after the user sees this table do you fix the REAL BLOCKERs. Miscategorized ones get challenged and deferred.

For every BLOCKER, answer three questions:

1. **Is it a real defect?** Would it actually cause wrong results, crashes, or data loss?
2. **Is it already handled?** Does an upstream guard, existing fallback, or code pattern already cover this?
3. **Does the fix add complexity for no real gain?** Some nm findings propose belt-and-suspenders that add code with zero safety improvement.

State explicitly for each: "Valid BLOCKER — fixing because X" or "False alarm — Y already handles this because Z."

**Concrete false-BLOCKER examples (these happen frequently):**

| nm says | Reality | Why it's not a BLOCKER |
|---------|---------|------------------------|
| "Silent error — no error_code field" | Code already falls back to default gracefully | Error produces correct behavior; only downside is a worse log message. SHOULD FIX at most. |
| "Stale Python default — bound at import time" | Default only affects cosmetic dollar display, not computed metrics | DD% is unchanged; nobody overrides starting capital in practice. SHOULD FIX at most. |
| "Subprocess missing CLI flag" | Only matters in a workflow the user never uses | Normal flow: run backtester separately, pass CSV to validator. Edge case. SHOULD FIX at most. |
| "CSV partial file on write error" | `?` operator already propagates; csv crate `Drop` handles cleanup | Adding delete-on-error guard is 10 lines for zero real improvement. Not a BLOCKER. |
### Deferred SHOULD FIX → GitHub Issues

SHOULD FIX items that are **deferred** to a future task group (rather than fixed immediately) MUST be logged as GitHub issues — never left in the PR body to rot. This prevents lost findings (e.g., TG5 SF4-7 were in the delegate_task output and unrecoverable).

```bash
source ~/.hermes/.env && gh issue create \
  --title "TG<N> — <summary>" \
  --body "## Source
nm review — finding <ID>. Deferred to <target TG>.

## What's missing
...

## Where
\`src/path/to/file.rs\`

## Acceptance
- [ ] criterion 1
- [ ] criterion 2"
```

Repo has no labels configured — omit `--label` to avoid 422 errors.

The `nm` script auto-detects the project from the git repo root:

| Project | Repo | Test Command |
|---------|------|-------------|
| Atlas | ~/atlas/ | `npx vitest run` |
| Huat | ~/huat/ | `cargo test --lib` |
