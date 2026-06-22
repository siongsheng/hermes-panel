# Hermes Panel

**Multi-agent orchestration engine for Hermes Agent.** Routes feature development through a pipeline of specialist AI agents: **Strategist → Coder → vet → nm → Tech Lead** — with automated depth-gating, TDD enforcement, and adversarial review.

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│Strategist│──▶│  Coder   │──▶│   vet    │──▶│    nm    │──▶│Tech Lead │
│  spec    │   │TDD impl  │   │build+test│   │adversarial│  │  review  │
└──────────┘   └──────────┘   └──────────┘   │ +PR+risk │   │  sign-off │
                                              └──────────┘   └──────────┘
                                                     ↓
                                              fresh session,
                                              different model
```

## Why

Writing specs, implementing TDD, running tests, creating PRs, and reviewing code — for every feature — is mechanical work. AI agents can do this, but one agent alone drifts. The panel chains specialist agents with enforced gates: the strategist designs, the coder implements (RED→GREEN commits), vet checks the build mechanically (no AI), nm runs adversarial review from a fresh session with a different model family, and the tech lead signs off against the spec.

**Result:** end-to-end features with two-commit TDD discipline, passing tests, passing builds, PR created, adversarial review from two independent models, and TL sign-off — all automated.

## Quick Start

```bash
# Clone
git clone https://github.com/siongsheng/hermes-panel.git ~/hermes-panel

# Install (symlink to PATH)
ln -sf ~/hermes-panel/hermes-panel ~/bin/hermes-panel

# Run on any project with AGENTS.md + git remote
hermes-panel "Add rate limiting middleware" ~/project

# Force all 5 phases (even for low-risk changes)
PANEL_FORCE_FULL=1 hermes-panel "Add payment webhook" ~/project

# Resume after strategist interview
hermes-panel --answers /tmp/hermes-panel-interview.json "Add API key auth" ~/project
```

> **Full setup guide:** [docs/setup.md](docs/setup.md) — one-time machine setup, per-project config, troubleshooting.

## Pipeline

| # | Stage | Who | Model | What it does |
|---|-------|-----|-------|-------------|
| 1 | **Strategist** | `strategist` profile | deepseek-v4-pro | Explores codebase, designs spec, produces task DAG. Interview mode if confidence < High. |
| 2 | **Coder** | `coder` profile | deepseek-v4-flash | TDD implementation: RED commit → GREEN commit. Parallel worktrees. Lint before push. |
| 3 | **vet** | Shell (zero AI) | — | `npm test` + `npm run build`. Fail → spawn coder to fix → re-verify (2 retries). Mechanical gate — no AI tokens. |
| 4 | **nm** | Fresh Hermes session | Different model family | Adversarial review from clean context. Creates PR with risk assessment (LOW/MEDIUM/HIGH). No memory of coding process — catches bias-blind spots. |
| 5 | **Tech Lead** | `tech-lead` profile | deepseek-v4-pro | Reviews the PR: spec compliance, architecture, code quality. Appends verdict + release type. Final sign-off. |

**vet is the minimum.** Every change gets build + tests. No skipping.

### Depth Gating

Depth matrix: confidence × impact → how many stages run.

| Impact ↓ / Confidence → | HIGH | MEDIUM | LOW |
|---|---|---|---|
| **LOW** (tests/docs/typos) | **vet** | vet+nm | full |
| **MEDIUM** (API/DB/UI) | vet+nm | full | full |
| **HIGH** (auth/payments) | full | full | full |

**Legend:**

| Depth | Stages | Meaning |
|-------|--------|---------|
| **vet** | 1+2+3 | Strategist + Coder + vet. PR created by panel. No adversarial review. For trivial changes. |
| **vet+nm** | 1+2+3+4 | + nm adversarial review from fresh session. PR + risk assessment. Skip TL only. |
| **full** | 1+2+3+4+5 | All stages. TL reviews the PR and signs off. For anything impactful or uncertain. |

Only HIGH confidence + LOW impact changes skip adversarial review entirely. Everything else gets at least nm's fresh-model review.

`PANEL_FORCE_FULL=1` overrides → all 5 stages.

## Features

- **Project-agnostic** — takes any repo path. Reads test/build/lint commands from `AGENTS.md`.
- **TDD enforced** — RED→GREEN two-commit discipline verified at each phase. Bundled commits = BLOCKER.
- **Interview pause-and-resume** — non-interactive for Telegram/cron. Strategist exits code 2 with questions; re-run with `--answers` to resume.
- **Parallel coders** — worktree isolation with task claiming. DAG-based wave scheduling.
- **Three independent reviews** — vet (mechanical), nm (fresh model, clean context), TL (spec compliance). Two different model families catch different classes of bugs.
- **Token optimized** — 54% below unoptimized baseline. Shell verification (zero AI), flash model for coder, lite skills, spec noise extraction.
- **Graceful degradation** — timeouts produce partial results, not failures. Partial review > no review.

## Cost

**54% cheaper than an unoptimized pipeline.** Here's how:

| Optimization | Saving |
|---|---|
| Shell verification (vet) | Zero AI tokens — runs build+test mechanically |
| Flash model for coder | 3.1× cheaper than v4-pro for implementation |
| Spec noise extraction | 45-58% smaller strategist output |
| Task-extract | Coder reads ~800 chars of tasks, not the full 12K spec |
| Lite skills | 2.2K vs 13.8K system tokens for coder + TL |

## Requirements

- [Hermes Agent](https://hermes-agent.nousresearch.com) installed
- 3 Hermes profiles: `strategist`, `coder`, `tech-lead` (see [setup guide](docs/setup.md))
- DeepSeek API access (strategist/coder/TL) + one additional model family (nm adversarial review)
- `gh` CLI (GitHub) installed and authenticated
- `AGENTS.md` at project root with test and build commands
- GitHub remote configured on target project

## Environment Variables

| Variable | Effect |
|----------|--------|
| `PANEL_REASONING=high` | Bump strategist reasoning effort |
| `PANEL_PARALLEL=0` | Force sequential coder mode |
| `PANEL_FORCE_FULL=1` | Run all 5 stages regardless of depth matrix |
| `GH_TOKEN` | GitHub auth (auto-loaded from profile `.env`) |

## Documentation

- **[docs/setup.md](docs/setup.md)** — Deployment guide: one-time machine setup, per-project config, smoke test, cron integration, troubleshooting.
- **[docs/pipeline.md](docs/pipeline.md)** — Full pipeline reference: phases, depth matrix, interview flow, token optimizations, failure handling.

## Files

```
hermes-panel/
├── hermes-panel                    # The main script
├── skills/
│   ├── spec-strategist-lite/       # Strategist skill (13-section spec format)
│   ├── ai-coding-best-practices-lite/  # Coder skill (TDD, gates, anti-patterns)
│   ├── no-mistakes/                # nm skill (adversarial review + PR + risk)
│   └── adversarial-review-lite/    # Tech Lead skill (review dimensions, severity)
├── docs/
│   ├── setup.md                    # Deployment guide
│   └── pipeline.md                 # Pipeline reference
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
