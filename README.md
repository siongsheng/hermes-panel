# Hermes Panel

**Multi-agent orchestration engine for Hermes Agent.** Routes feature development through a pipeline of specialist AI agents — with automated depth-gating, TDD enforcement, and adversarial review.

## Why

You asked an AI to add a dark mode toggle.

It installed Tailwind. Refactored your CSS. Wrote 14 components, a theme context, a provider, three hooks, and a README explaining its design philosophy. The toggle doesn't work. The tests pass — it wrote those too.

One agent, zero accountability, unlimited ambition. Give it a button and it builds you a space elevator.

Hermes Panel puts five agents in a room and makes them distrust each other. The strategist writes the spec — because "just code it" is the fastest route to 47 files for a button. The coder tests first (RED commit, GREEN commit, or it didn't happen). vet runs the build with zero AI tokens — shell scripts don't hallucinate, and they certainly don't install Tailwind. nm reviews from a fresh session with a different model, because nobody grades their own homework. The Tech Lead checks the spec, checks the code, and checks for space elevators.

**What comes out:** passing tests, passing build, a PR with two independent reviews, all automated. **What doesn't:** a CSS framework you didn't ask for.

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

```mermaid
stateDiagram-v2
    direction TB

    Plan : 🧠 Strategist + spec‑kit
    Plan : Specs, architecture, tasks
    Implement : 👷 Coder (TDD)
    Implement : RED → GREEN commits
    Validate : 🔧 vet (shell)
    Validate : Build + test
    Verify : 🔍 nm (adversarial)
    Verify : Fresh model, clean context
    Review : 👔 Tech Lead
    Review : Spec compliance, code quality

    [*] --> Plan : feature request
    Plan --> Implement : spec approved (Human Gate)

    Implement --> Validate : code pushed
    Validate --> Implement : build / test fail (2x)
    Validate --> [*] : vet‑only → PR ✓
    Validate --> Verify : vet+nm / full

    Verify --> Implement : auto‑fixable: test · TDD · exception (1x)
    Verify --> [*] : vet+nm → PR + Risk ✓
    Verify --> Review : full

    Review --> Implement : auto‑fixable: test · guard · TDD · exception (1x)
    Review --> [*] : final verdict ✓
```

| # | Stage | Who | What it does |
|---|-------|-----|-------------|
| 0 | **Human Gate** | You | Review the spec before code gets written. Pauses after Strategist finishes — the #1 failure mode defense. |
| 1 | **Strategist** | `strategist` profile | Explores codebase, designs spec, produces task list or DAG. Interview mode if confidence < High. |
| 2 | **Coder** | `coder` profile | TDD implementation: RED commit → GREEN commit. Parallel waves based on task DAG. |
| 3 | **vet** | Shell (zero AI) | Runs test + build commands from `AGENTS.md`. Fail → spawn coder to fix → re-verify (2 retries). |
| 4 | **nm** | Fresh session, different model | Adversarial review from clean context. Creates PR with risk assessment. |
| 5 | **Tech Lead** | `tech-lead` profile | Reviews the PR: spec compliance, architecture, code quality. Final sign-off. |

**Human Gate** is the default in interactive mode. Non-interactive (Telegram/cron) auto-skips. Set `PANEL_SKIP_HUMAN_GATE=1` to bypass. **vet is the minimum** — every change gets build + tests. No skipping.

### Depth Gating

Not every change needs all 5 stages. Confidence × impact → how many stages run:

| Impact ↓ / Confidence → | HIGH | MEDIUM | LOW |
|---|---|---|---|
| **LOW** (tests/docs/typos) | vet | vet+nm | full |
| **MEDIUM** (API/DB/UI) | vet+nm | full | full |
| **HIGH** (auth/payments) | full | full | full |

| Depth | Stages | When |
|-------|--------|------|
| **vet** | Human Gate + Strategist + Coder + vet | Trivial changes. Panel creates PR directly. |
| **vet+nm** | + nm adversarial review | Medium-risk. nm creates PR with risk assessment. |
| **full** | + Tech Lead sign-off | Anything impactful or uncertain. Two independent reviews. |

Only HIGH confidence + LOW impact skips adversarial review. Everything else gets at least nm's fresh-model review. `PANEL_FORCE_FULL=1` overrides → all stages.

### Loopback Rules

Three loopback tiers, all re-vet after fix:

| Loopback | Retries | Auto-fixes | Never auto-fixes |
|----------|---------|-----------|-----------------|
| **Validate → Implement** | 2 | Build failures, test failures | — (all mechanical) |
| **Verify → Implement** | 1 | Missing tests, uncaught exceptions, TDD violations, `unwrap` on Result/Option | Architecture concerns, spec compliance gaps, security findings |
| **Review → Implement** | 1 | Missing tests, uncaught exceptions, TDD violations, missing guards, missing README update | Spec violations, architecture violations, security findings |

Subjective findings halt — human judges the trade-off. `PANEL_SKIP_AUTOFIX=1` disables Verify+Review auto-fix.

## Features

- **Human gate** — pauses after strategist so you can review the spec before code gets written. `[y]` review in less, `[e]` edit in vim, `[Enter]` approve, `[q]` abort. Auto-skipped in non-interactive mode.
- **Project-agnostic** — takes any repo path. Reads test/build/lint commands from `AGENTS.md`.
- **TDD enforced** — RED→GREEN two-commit discipline verified at each phase. Bundled commits = BLOCKER.
- **Parallel coders** — worktree isolation with task claiming. DAG-based wave scheduling.
- **Filtered auto-fix** — nm and TL loop back to Coder for objective issues (missing tests, uncaught exceptions, TDD violations). Architecture and spec findings stay human-only. Re-verified after fix. `PANEL_SKIP_AUTOFIX=1` to disable.
- **Cost-optimized** — 54% below unoptimized baseline. Shell verification (zero AI tokens), flash model for coder, lite skills (2.2K vs 13.8K system tokens), spec noise extraction (45-58% smaller), task-extract (coder reads ~800 chars, not full 12K spec).
- **Two adversarial reviews** — nm (fresh model, different family) + TL (spec compliance). Two independent models catch different classes of bugs.
- **Graceful degradation** — timeouts produce partial results, not failures. Partial review > no review.

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
| `PANEL_SKIP_HUMAN_GATE=1` | Skip the human gate even in interactive mode |
| `PANEL_SKIP_AUTOFIX=1` | Disable nm+TL auto-fix loopbacks |
| `GH_TOKEN` | GitHub auth (auto-loaded from profile `.env`) |

## Standing on Shoulders

The panel doesn't invent methodology. Every stage draws from battle-tested open-source ideas — integrated into a pipeline where each stage reinforces the next.

| Stage | Draws from | What we took | Why |
|-------|-----------|-------------|-----|
| **Strategist** | [Spec Kit](https://github.com/github/spec-kit) (51K ★) | Constitution-first development — mission, tech-stack, roadmap, conventions before any code | Spec-kit proved agents produce better code when they design first |
| | [ponytail](https://github.com/DietrichGebert/ponytail) | YAGNI laziness ladder — "Does this already exist? Can stdlib do it?" before writing a spec | Prevents the #1 waste in agentic coding: building things that don't need to exist |
| **Coder** | [Kent Beck's TDD](https://en.wikipedia.org/wiki/Test-driven_development) | RED → GREEN → REFACTOR cycle, enforced by the coder skill | 25 years of evidence: tests written first produce fewer defects |
| | AI Coding Best Practices | Task granularity (5-15 min), no scope creep, pipeline gates | Agents drift without guardrails. Small tasks keep them focused |
| **vet** | Unix philosophy (McIlroy, 1978) | Mechanical verification — shell script, zero AI tokens | Determinism. `cargo test` passes or fails — no hallucination surface. Every CI system works this way for the same reason |
| **nm** | [no-mistakes](https://github.com/kunchenguid/no-mistakes) | Fresh session, different model family, PR with risk assessment | Research shows adversarial review from independent models catches bias. The coding model can't review its own work |
| **Tech Lead** | GitHub PR review best practices + [Bacchelli & Bird, 2013](https://doi.org/10.1109/icse.2013.6606617) | Multi-dimensional review — spec compliance, architecture, security, test quality, style, drift | Microsoft Research: checklist structure beats reviewer seniority. A rubric catches more than free-form review |
| | [ponytail](https://github.com/DietrichGebert/ponytail) | Post-build laziness lens — "Is there a simpler way?" | Catches overbuilding that passed correctness review. 47-line wrapper → 1 stdlib call |

**The panel integrates proven ideas into a pipeline where each stage reinforces the next.** The strategist's spec gates the coder. The coder's tests gate the vet. The vet gates the review. Two independent models must agree before the TL signs off.

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
