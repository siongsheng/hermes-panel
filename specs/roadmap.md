# Dokima Roadmap

## Phase 1: Core Stability

### F001: Security Hardening
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** As a panel operator, I trust that shell injection, hardcoded secrets, and agent prompt injection are systematically blocked.

### F002: Panel Self-Tests + CI
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** As a contributor, I can run `pytest` and see 257+ tests pass. CI catches regressions before merge.

### F003: Error Recovery & Resume
**Priority:** P1
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** As a panel operator, if a pipeline crashes mid-run, I can resume from the last completed phase instead of restarting from scratch.

### F004: Model Family Fallback
**Priority:** P1
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** As a panel operator, if the primary model provider is down, the panel auto-falls-back to a configured alternative (e.g. deepseek → openrouter → anthropic).

---

## Phase 2: Pipeline Intelligence

### F005: Strategist Read the Actual Product
**Priority:** P0
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a panel operator, the strategist reads the AGENTS.md header for GitHub links to the product being documented, finds the local repo, and treats its AGENTS.md as truth — never deriving architecture from the docs site itself.

### F006: Strategist Respects Existing Specs
**Priority:** P0
**Dependencies:** None
**Status:** [x] Done
**User Story:** As a panel operator, if I write a spec at `specs/<feature>-spec.md` before running the panel, the strategist uses it as the authoritative source — validating and enhancing, not rewriting from scratch.

### F007: Depth Gating Tuning
**Priority:** P1
**Dependencies:** F005, F006
**Status:** [ ] Pending
**User Story:** As a panel operator, the confidence × impact matrix reliably selects the right depth — docs changes don't run full nm+TL, novel features get full vetting.

### F008: Parallel Coder Robustness
**Priority:** P1
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** As a panel operator, parallel coders never conflict on the same file, worktree cleanup is reliable, and timeout/dead agents don't block the wave.

---

## Phase 3: Distribution & Portability

### F009: Installer Script
**Priority:** P2
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** As a new developer, I run `curl -sSL https://get.dokima.dev | bash` and get a working Dokima installation — script symlinks into PATH, checks dependencies (Python 3.6+, gh CLI, Hermes Agent), and prints next steps.

### F010: Profile Templates
**Priority:** P2
**Dependencies:** F009
**Status:** [ ] Pending
**User Story:** As a new developer, `dokima init` creates agent profiles (`strategist`, `coder`, `tech-lead`, `nm`) with sensible defaults — I only need to add my API keys.

### F011: Vendor-Agnostic Model Config
**Priority:** P2
**Dependencies:** F004, F010
**Status:** [ ] Pending
**User Story:** As a developer using Anthropic, I configure `ANTHROPIC_API_KEY` and the panel maps strategist→claude-sonnet, coder→claude-haiku, TL→claude-opus — no deepseek dependency.

### F012: nm Script Portability
**Priority:** P2
**Dependencies:** F009
**Status:** [ ] Pending
**User Story:** As a new developer, the adversarial review script (`nm`) is installed with the panel — same behavior, same model diversity requirement, no manual `~/bin/nm` symlink needed.

### F013: README & Quickstart Guide
**Priority:** P2
**Dependencies:** F009, F010, F011, F012
**Status:** [ ] Pending
**User Story:** As a new developer, I clone dokima, follow a 5-minute quickstart, and run my first pipeline on a demo repo — no tribal knowledge required.

### F014: Config Validation
**Priority:** P2
**Dependencies:** F010
**Status:** [ ] Pending
**User Story:** As a developer, `dokima doctor` checks: Hermes Agent running, profiles configured, API keys valid, gh CLI authenticated, nm script present — and tells me exactly what to fix.

---

## Icebox (Post-Stable)

### F015: Dokima-as-Service
**Priority:** P3
**Dependencies:** Full Phase 3
**Status:** [ ] Pending
**User Story:** As a team lead, I point Dokima at a GitHub webhook and it auto-reviews every PR — no CLI needed, no local machine dependency.

### F016: Multi-Repo Orchestration
**Priority:** P3
**Dependencies:** F015
**Status:** [ ] Pending
**User Story:** As a platform team, Dokima manages features across a monorepo with cross-cutting specs, shared ADRs, and parallel pipelines per sub-project.
