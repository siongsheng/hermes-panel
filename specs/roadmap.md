# Dokima Roadmap

## Phase 1: Core Stability & Test Coverage

### F002: Pipeline Integration Tests
**Priority:** P0
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a contributor, I run one command and a full pipeline executes against a test repo — strategist reads AGENTS.md, produces a spec, coder implements it, vet runs the build, nm reviews, TL delivers verdict. All 5 phases verified end-to-end. Failures at any phase produce clear diagnostics, not silent exits.

### F003: Edge Case & Robustness Tests
**Priority:** P0
**Dependencies:** F002
**Status:** [x] Done
**User Story:** As a panel operator, the pipeline handles every known failure mode gracefully: strategist returns interview mode (exit 2), strategist produces zero ### Task headers (DAG re-prompt fires), coder times out (partial results captured), coder produces only RED commits (vet catches it), nm model provider is down (fallback fires), TL detects BLOCKED verdict (auto-fix loop triggers), concurrent pipelines don't fight over lock files, stop/kill signals clean up worktrees, feature description contains special characters (slugify doesn't crash).

### F004: Deterministic Quality Gates
**Priority:** P1
**Dependencies:** F002
**Status:** [x] Done
**User Story:** As a contributor, running the same feature through the pipeline twice produces comparable output quality — same spec structure, same task granularity (5-15 min each), same DAG format, PR body has real Impact/What Changed (not placeholders). Quality regressions are caught by CI — if a panel change causes the strategist to output 14K-char specs for High-confidence features, the test fails.

### F005: Model Family Fallback
**Priority:** P1
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a panel operator, if the primary model provider is down, the panel auto-falls-back to a configured alternative (e.g. deepseek → openrouter → anthropic).

### F001: Security Hardening
**Priority:** P0
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a panel operator, I trust that shell injection, hardcoded secrets, and agent prompt injection are systematically blocked.

### F006: Error Recovery & Resume
**Priority:** P1
**Dependencies:** F002
**Status:** [x] Done
**User Story:** As a panel operator, if a pipeline crashes mid-run, I can resume from the last completed phase instead of restarting from scratch. Partial state (spec file, task extract, feature branch, open PR) is not lost.

---

## Phase 2: Pipeline Intelligence

### F008: Strategist Respects Existing Specs
**Priority:** P0
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a panel operator, if I write a spec at `specs/<feature>-spec.md` before running the panel, the strategist uses it as the authoritative source — validating and enhancing, not rewriting from scratch.

### F007: Strategist Read the Actual Product
**Priority:** P0
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a panel operator, the strategist reads the AGENTS.md header for GitHub links to the product being documented, finds the local repo, and treats its AGENTS.md as truth — never deriving architecture from the docs site itself.

### F009: Depth Gating Tuning
**Priority:** P1
**Dependencies:** F007, F008
**Status:** [x] Done
**User Story:** As a panel operator, the confidence × impact matrix reliably selects the right depth — docs changes don't run full nm+TL, novel features get full vetting.

### F010: Parallel Coder Robustness
**Priority:** P1
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a panel operator, parallel coders never conflict on the same file, worktree cleanup is reliable, and timeout/dead agents don't block the wave.

### F019: Data-Driven Execution Mode (Orchestrator Computes)
**Priority:** P1
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a panel operator, the orchestrator auto-selects batch coder (single session, no worktrees) for small additive features and per-task spawn for complex/refactor features — derived from existing DAG signals (task count, file count, parallelizability). No strategist changes needed.

### F023: Pipeline Self-Healing
**Priority:** P1
**Dependencies:** F010
**Status:** [x] Done
**User Story:** As a panel operator, the pipeline detects and recovers from common failure patterns without human intervention — auto-fix infinite loops (nm fix already applied), partial coder output (truncated agent), and stale lock files from killed pipelines.

### F022: Modular Architecture
**Priority:** P1
**Dependencies:** F010, F023
**Status:** [x] Done
**User Story:** As a contributor, the 5,400-line monolith is split into modules (agent.py, pipeline.py, roadmap.py, tasks.py, utils.py) with clear interfaces — agents can read and modify one module without loading the entire codebase. Same behavior, same tests, smaller context windows.

### F020: Structured CLI Output (`--help-json`)
**Priority:** P2
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a docs maintainer, `dokima --help-json` outputs all commands, flags, and env vars as structured JSON — consumed by the docs site to auto-generate the CLI reference page. No more manual sync between code and docs.

### F021: Semantic Versioning + GitHub Releases
**Priority:** P2
**Dependencies:** F020
**Status:** [x] Done Progress
**User Story:** As a user, `dokima --version` prints the current version. Releases are tagged and published on GitHub with auto-generated changelogs from merged PRs. `dokima --upgrade` checks for newer versions.

---

## Phase 3: Distribution & Portability

### F011: Installer Script
**Priority:** P2
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a new developer, I run `curl -sSL https://get.dokima.dev | bash` and get a working Dokima installation — script symlinks into PATH, checks dependencies (Python 3.6+, gh CLI, Hermes Agent), and prints next steps.

### F012: Profile Templates
**Priority:** P2
**Dependencies:** F011
**Status:** [x] Done
**User Story:** As a new developer, `dokima init` creates agent profiles (`strategist`, `coder`, `tech-lead`, `nm`) with sensible defaults — I only need to add my API keys.

### F013: Vendor-Agnostic Model Config
**Priority:** P2
**Dependencies:** F005, F012
**Status:** [ ] Pending
**User Story:** As a developer using Anthropic, I configure `ANTHROPIC_API_KEY` and the panel maps strategist→claude-sonnet, coder→claude-haiku, TL→claude-opus — no deepseek dependency.

### F014: nm Script Portability
**Priority:** P2
**Dependencies:** F011
**Status:** [ ] Pending
**User Story:** As a new developer, the adversarial review script (`nm`) is installed with the panel — same behavior, same model diversity requirement, no manual `~/bin/nm` symlink needed.

### F015: README & Quickstart Guide
**Priority:** P2
**Dependencies:** F011, F012, F013, F014
**Status:** [ ] Pending
**User Story:** As a new developer, I clone dokima, follow a 5-minute quickstart, and run my first pipeline on a demo repo — no tribal knowledge required.

### F016: Config Validation (`dokima doctor`)
**Priority:** P2
**Dependencies:** F012
**Status:** [ ] Pending
**User Story:** As a developer, `dokima doctor` checks: Hermes Agent running, profiles configured, API keys valid, gh CLI authenticated, nm script present — and tells me exactly what to fix.

---

## Icebox (Post-Stable)

### F017: Dokima-as-Service
**Priority:** P3
**Dependencies:** Full Phase 3 (F011-F016)
**Status:** [ ] Pending
**User Story:** As a team lead, I point Dokima at a GitHub webhook and it auto-reviews every PR — no CLI needed, no local machine dependency.

### F018: Multi-Repo Orchestration
**Priority:** P3
**Dependencies:** F017
**Status:** [ ] Pending
**User Story:** As a platform team, Dokima manages features across a monorepo with cross-cutting specs, shared ADRs, and parallel pipelines per sub-project.
