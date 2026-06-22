# Hermes Panel

**Multi-agent orchestration engine for Hermes Agent.** Routes feature development through a pipeline of specialist AI agents: **Strategist → Coder → Verification → Tech Lead** — with automated depth-gating, TDD enforcement, and adversarial review.

```
┌─────────────┐     ┌──────────┐     ┌──────────────┐     ┌────────────┐
│ Strategist  │────▶│  Coder   │────▶│ Verification │────▶│ Tech Lead  │
│ Spec + DAG  │     │ TDD impl │     │ test+build+PR│     │ review     │
└─────────────┘     └──────────┘     └──────────────┘     └────────────┘
    5 min              10 min             2 min              10 min
     58%                 8%                0%                 33%

                    Full pipeline: 4 phases | Fast path: ~3 min | Full: ~7 min
```

## Why

Writing specs, implementing TDD, running tests, creating PRs, and reviewing code — for every feature — is mechanical work. AI agents can do this, but one agent alone drifts. The panel chains specialist agents with enforced gates: the strategist designs, the coder implements (RED→GREEN commits), verification checks the build, and the tech lead reviews against the spec.

**Result:** end-to-end features with two-commit TDD discipline, passing tests, passing builds, PR created, and adversarial review completed — for pocket change per feature.

## Quick Start

```bash
# Clone
git clone https://github.com/siongsheng/hermes-panel.git ~/hermes-panel

# Install (symlink to PATH)
ln -sf ~/hermes-panel/hermes-panel ~/bin/hermes-panel

# Run on any project with AGENTS.md + git remote
hermes-panel "Add rate limiting middleware" ~/project

# Force all 4 phases (even for low-risk changes)
PANEL_FORCE_FULL=1 hermes-panel "Add payment webhook" ~/project

# Resume after strategist interview
hermes-panel --answers /tmp/hermes-panel-interview.json "Add API key auth" ~/project
```

> **Full setup guide:** [docs/setup.md](docs/setup.md) — one-time machine setup, per-project config, troubleshooting.

## Pipeline

| Phase | Agent | Model | What it does | Duration |
|-------|-------|-------|-------------|----------|
| 1. Strategist | `strategist` profile | deepseek-v4-pro | Explores codebase, designs spec, produces task DAG. Interview mode if confidence < High. | 5 min |
| 2. Coder | `coder` profile | deepseek-v4-flash | TDD implementation: RED commit → GREEN commit. Lint + test before push. Parallel worktrees. | 10 min |
| 3. Verification | Shell (zero AI) | — | `npm test` + `npm run build` + `gh pr create`. Fail → coder fixes → re-verify (2 retries). | 2 min |
| 4. Tech Lead | `tech-lead` profile | deepseek-v4-pro | Adversarial review: spec compliance, architecture, code quality. Auto-creates Issues for SHOULD FIX. | 10 min |

**Depth gating** auto-selects phases based on confidence × impact:

| Impact ↓ / Confidence → | HIGH | MEDIUM | LOW |
|---|---|---|---|
| **LOW** (tests/docs) | 1+2 | 1+2+3+4 | 1+2+3+4 |
| **MEDIUM** (API/DB/UI) | 1+2+3 | 1+2+3+4 | 1+2+3+4 |
| **HIGH** (auth/payments) | 1+2+3+4 | 1+2+3+4 | 1+2+3+4 |

Only HIGH confidence gets the fast path. Everything else gets adversarial review.

`PANEL_FORCE_FULL=1` overrides → all 4 phases.

## Features

- **Project-agnostic** — takes any repo path. Reads test/build/lint commands from `AGENTS.md`.
- **TDD enforced** — RED→GREEN two-commit discipline verified at each phase. Bundled commits = BLOCKER.
- **Interview pause-and-resume** — non-interactive for Telegram/cron. Strategist exits code 2 with questions; re-run with `--answers` to resume.
- **Parallel coders** — worktree isolation with task claiming. DAG-based wave scheduling.
- **Token optimized** — 54% below unoptimized baseline. Shell verification (zero AI), flash model for coder (3.1× cheaper), lite skills, spec noise extraction.
- **Graceful degradation** — timeouts produce partial results, not failures. Partial review > no review.

## Cost

**54% cheaper than an unoptimized pipeline.** Here's how:

| Optimization | Saving |
|---|---|
| Shell verification | Phase 3 runs with zero AI tokens — 33% of pipeline cost eliminated |
| Flash model for coder | 3.1× cheaper than v4-pro for implementation |
| Spec noise extraction | 45-58% smaller strategist output |
| Task-extract | Coder reads ~800 chars of tasks, not the full 12K spec |
| Lite skills | 2.2K vs 13.8K system tokens for coder + TL |

Cost distribution by phase:

| Phase | % of total |
|---|---|
| Strategist | 58% |
| Coder | 8% |
| Verification | 0% |
| Tech Lead | 33% |

## Requirements

- [Hermes Agent](https://hermes-agent.nousresearch.com) installed
- 3 Hermes profiles: `strategist`, `coder`, `tech-lead` (see [setup guide](docs/setup.md))
- DeepSeek API access
- `gh` CLI (GitHub) installed and authenticated
- `AGENTS.md` at project root with test and build commands
- GitHub remote configured on target project

## Environment Variables

| Variable | Effect |
|----------|--------|
| `PANEL_REASONING=high` | Bump strategist reasoning effort |
| `PANEL_PARALLEL=0` | Force sequential coder mode |
| `PANEL_FORCE_FULL=1` | Run all 4 phases regardless of depth |
| `GH_TOKEN` | GitHub auth (auto-loaded from profile `.env`) |

## Documentation

- **[docs/setup.md](docs/setup.md)** — Deployment guide: one-time machine setup, per-project config, smoke test, cron integration, troubleshooting.
- **[docs/pipeline.md](docs/pipeline.md)** — Full pipeline reference: phases, depth matrix, interview flow, token optimizations, failure handling.

## Files

```
hermes-panel/
├── hermes-panel              # The main script
├── skills/
│   ├── ai-coding-best-practices-lite/   # Coder skill (TDD, gates, anti-patterns)
│   └── adversarial-review-lite/         # Tech Lead skill (review dimensions, severity)
├── docs/
│   ├── setup.md              # Deployment guide
│   └── pipeline.md           # Pipeline reference
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
