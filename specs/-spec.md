# Hermes Panel — Spec

## Mission

A lightweight, stateless Python script that routes feature development through a pipeline of specialist AI agents — enforcing TDD, adversarial review, and depth-gated execution — while requiring zero non-Python dependencies beyond the agents and tools it orchestrates.

## Tech Stack

- **Runtime:** Python 3.6+ (single script, no pip dependencies, compatible with Oracle Linux 8 system Python)
- **Orchestration:** Hermes Agent (`hermes --profile <role> --yolo -s <skill>`)
- **Version control:** Git + GitHub CLI (`gh`) for branch management and PR creation
- **Verification:** Shell scripts (`~/bin/vet`, `~/bin/nm`) for deterministic build/test/adversarial review
- **ADRs:** `adr-tools` CLI for architectural decision records (optional)
- **Agent provider:** DeepSeek, Anthropic, OpenAI, or OpenRouter (configured per Hermes profile)

## Pipeline Stages

| # | Stage | Agent | What it produces |
|---|-------|-------|-----------------|
| 0 | Human Gate | User | Spec approval before code |
| 1 | Strategist | `strategist` profile | Spec + task list + decision table |
| 1b | TL Spec Pre-Review | `tech-lead` profile | Architecture + test plan review |
| 2 | Coder | `coder` profile | RED→GREEN commits on feature branch |
| 3 | vet | Shell (zero AI) | Build + test verification, PR at depth=vet |
| 4 | nm | `~/bin/nm` | Adversarial review + PR with risk assessment |
| 5 | Tech Lead | `tech-lead` profile | Spec compliance + code quality verdict |

## Feature Set

### Core Pipeline
- [x] Depth-gated execution (vet / vet+nm / full) based on confidence × impact
- [x] Human gate with spec review (interactive: less/vim; non-interactive: auto-skip)
- [x] Strategist codebase exploration → spec generation → interview mode (exit code 2)
- [x] TDD-enforced coder (RED→GREEN two-commit discipline)
- [x] Shell-based verification (vet) with coder fix loopback (up to 2 retries)
- [x] Adversarial review (nm) with risk assessment and PR creation
- [x] Tech Lead spec-compliance and architecture review
- [x] Filtered auto-fix loopbacks (nm→coder, TL→coder) for objective issues only
- [x] Pipeline halt + revert on unrecoverable failures
- [x] Full output log to `/tmp/hermes-panel-output.txt`

### Parallel Execution
- [x] DAG-based task scheduling with dependency resolution
- [x] Parallel coder worktrees (up to 5 via `git worktree`)
- [x] Task claiming with file-collision detection
- [x] Sequential fallback via `PANEL_PARALLEL=0`

### Cost Optimizations
- [x] Spec noise extraction (strip tool calls + prompt echo from agent output: 45-58% smaller)
- [x] Task-extract for coder (~800 chars instead of ~12K full spec)
- [x] Flash model (`deepseek-v4-flash`) for coder phase
- [x] Pure shell verification (zero AI tokens)
- [x] Lite skills (2.2K vs 13.8K system tokens)

### ADR Lifecycle
- [x] Strategist reads existing ADRs before designing
- [x] Panel creates new ADR from decision table after Human Gate
- [x] TL pre-review checks spec against existing ADRs
- [x] Spec↔ADR cross-references

### Spec Archive
- [x] Auto-archive merged PR specs on startup
- [x] `specs/STATUS.md` regeneration
- [x] Manual archive support

### Continuous Mode
- [x] `--next` builds next feature from roadmap
- [x] `--continuous` loop with auto-merge when safe
- [x] `--status` / `--stop` / `--kill` control
- [x] Cron integration with `--list-crons`

## Key Files

| File | Purpose |
|------|---------|
| `hermes-panel` | Main script (single file, ~3300 lines) |
| `~/bin/nm` | Adversarial review companion script |
| `~/bin/vet` | Shell verification companion script |
| `docs/pipeline.md` | Full pipeline reference |
| `docs/setup.md` | Deployment guide |
| `specs/` | Generated specs per feature |

## Conventions

- No hardcoded 'master' branch — detected from `origin/HEAD`
- No hardcoded model names in documentation — provider-agnostic
- State is in the filesystem (specs, branches, worktrees, log files) — not in memory
- Single-entry-point design: all orchestration flows through `hermes-panel`
