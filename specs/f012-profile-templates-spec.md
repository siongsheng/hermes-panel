# F012: Profile Templates

Now I have full context. Let me produce the complete corrected spec for F012: Profile Templates.
    
    
    
    Ponytail Guard — Pre-Spec Review
    Feature: F012: Profile Templates
    Rung: 7 — install.sh --with-profiles creates bare profiles (no model config, no skills). setup-linux.sh has richer setup but is interactive and not CLI-invocable. Need to build dokima init as a standalone command.
    Existing solution: install.sh creates empty profiles via hermes profile create (no model defaults, no skill deployment). setup-linux.sh deploys skills but requires interactive key entry.
    Spec needed: yes
    Spec scope: dokima init command that creates 4 Hermes profiles with model config, deploys panel skills, idempotent. Resolve naming collision with existing dokima init <description> (project discovery).
    
    
    
    F012: Profile Templates — Implementation Spec
    
    Version: 1.0.0
    Status: Draft — Awaiting Sign-Off
    
    
    
    1. Executive Summary
    
    dokima init creates the 4 Hermes agent profiles (strategist, coder, tech-lead, nm) with sensible defaults — model config, panel skills, and agent settings — so a new developer only needs to add API keys. This replaces the bare hermes profile create loop in install.sh and the interactive wizard in setup-linux.sh with a single idempotent command. Confidence: High — the individual operations (profile create, config set, skill copy) are well-understood; the work is composition and CLI integration.
    
    
    
    2. Constitution Check
    
    Axiom: Solves user's own pain?
    Verdict: ✅ YES
    Evidence: Shaun manually runs setup-linux.sh per machine; dokima init
      automates the exact steps
    ────────────────────────────────────────
    Axiom: Weekend-buildable?
    Verdict: ✅ YES
    Evidence: ~150 LOC of shell + Python glue, no new dependencies
    ────────────────────────────────────────
    Axiom: Evidence people will pay?
    Verdict: N/A
    Evidence: Internal tooling — no direct revenue
    ────────────────────────────────────────
    Axiom: Boring/Proven tech?
    Verdict: ✅ YES
    Evidence: Bash + Python, existing hermes CLI, file copy
    ────────────────────────────────────────
    Axiom: Avoids AI hype?
    Verdict: ✅ YES
    Evidence: No AI integration — pure CLI automation
    
    Flagged: None.
    
    
    
    3. Impact
    
    New developers go from "install Hermes, run interactive setup wizard, manually enter keys" to "install Hermes, set API keys, run dokima init." Existing users on setup-linux.sh get a faster non-interactive path. Profile deployments become reproducible across machines.
    
    
    
    4. What Changed
    
    - dokima (+80/-10): New init_profiles() function + CLI dispatch; rename existing dokima init <desc> → dokima discover <desc>
    - install.sh (+5/-15): Replace bare hermes profile create loop with call to $PANEL_DIR/dokima init
    - scripts/setup-linux.sh (+3/-50): Replace interactive profile/skill setup with call to dokima init
    - tests/test_installer.py (+30/-5): Update --with-profiles tests to verify skills deployed, not just profile dirs exist
    - tests/test_init_profiles.py (NEW, +120): Unit tests for init_profiles() — idempotency, missing hermes, partial state
    - README.md (+10): Document dokima init as primary setup path; mention dokima discover for project init
    
    
    
    5. Confidence & Impact Markers
    
    - Confidence: High — all underlying operations proven in setup-linux.sh
    - Impact: MEDIUM — core onboarding path changes; affects 3 files in dokima repo + installer
    
    
    
    6. Decision Table — Naming Collision Resolution
    
    Existing dokima init <description> runs project discovery (generates specs/mission.md, etc.). F012 also needs dokima init for profile creation.
    
    Option: A: Rename project init to dokima discover, use dokima init for
      profiles
    User Experience: Clean — init = setup, discover = exploration
    Backward Compat: Low risk — init is undocumented, untested
    Code Churn: +10 lines
    Verdict: ACCEPT
    ────────────────────────────────────────
    Option: B: Subcommand dokima init --profiles
    User Experience: Flag overload — dokima init does two unrelated things
    Backward Compat: Fully compat
    Code Churn: +5 lines
    Verdict: Reject — confusing UX
    ────────────────────────────────────────
    Option: C: New command dokima setup
    User Experience: Clean but adds verb
    Backward Compat: Good
    Code Churn: +15 lines
    Verdict: Reject — more commands = more docs
    
    Decision: Option A. dokima init <description> becomes dokima discover <description>. dokima init (no description) creates agent profiles. The existing init code path is untested and undocumented — blast radius is near zero.
    
    
    
    7. API / Interface Proposal
    
    N/A — CLI-only change, no REST endpoints.
    
    
    
    8. Security Considerations
    
    - No credential handling — profiles are created with model/provider names only; API keys remain in user's .env / shared.env
    - File copy from $PANEL_DIR/skills/ → ~/.hermes/profiles/<name>/skills/ — no external sources
    - umask 0o077 applied to profile directories (inherited from dokima's existing umask)
    
    
    
    9. Documentation Impact
    
    README: Update "Quickstart" section to show dokima init as the primary setup command. Add dokima discover <desc> entry in the CLI reference. Deprecation note: dokima init <desc> → use dokima discover <desc>.
    
    
    
    10. Data Model
    
    No persistent data structures. Transient state only — profile directories on disk.
    
    Profile template specification (not stored, embedded in code):
    
    Profile: strategist
    Model Default: deepseek-v4-pro
    Provider Detection: From HERMES_PROVIDER or auto-detect
    Skills Deployed: spec-strategist-lite, ponytail-guard, spec-kit,
      saas-ideation
    Config Overrides: max_turns=150, reasoning_effort=high
    ────────────────────────────────────────
    Profile: coder
    Model Default: deepseek-v4-pro
    Provider Detection: same
    Skills Deployed: ai-coding-best-practices-lite
    Config Overrides: max_turns=150
    ────────────────────────────────────────
    Profile: tech-lead
    Model Default: deepseek-o3
    Provider Detection: same
    Skills Deployed: adversarial-review-lite, ponytail-guard
    Config Overrides: max_turns=150
    ────────────────────────────────────────
    Profile: nm
    Model Default: claude-sonnet-4
    Provider Detection: From NM_PROVIDER or SECONDARY env
    Skills Deployed: (none — nm uses its own skills)
    Config Overrides: max_turns=150
    
    Profile directory layout after dokima init:
    
    
    ~/.hermes/profiles/
    ├── strategist/
    │   ├── config.yaml          ← model.default, model.provider, agent.max_turns, agent.reasoning_effort
    │   └── skills/
    │       └── software-development/
    │           ├── spec-strategist-lite/
    │           ├── ponytail-guard/
    │           ├── spec-kit/
    │           └── saas-ideation/
    ├── coder/
    │   ├── config.yaml
    │   └── skills/
    │       └── software-development/
    │           └── ai-coding-best-practices-lite/
    ├── tech-lead/
    │   ├── config.yaml
    │   └── skills/
    │       └── software-development/
    │           ├── adversarial-review-lite/
    │           └── ponytail-guard/
    └── nm/
        └── config.yaml
    
    
    
    
    11. Feature Breakdown — Task List
    
    Task 1: Rename existing dokima init to dokima discover
    Files: dokima
    Dependencies: none
    Parallelizable: no
    Description: Change the CLI dispatch: dokima init <description> → dokima discover <description>. Rename run_init() → run_discover(). Update all internal references. This is a find-and-replace with no logic changes. Update the feature detection at line 5322 from feature == "init" to feature == "discover".
    
    Task 2: Implement init_profiles() core function in dokima
    Files: dokima
    Dependencies: Task 1
    Parallelizable: no
    Description: Add init_profiles() function that: (1) checks hermes is on PATH, (2) creates 4 profiles via hermes profile create if missing, (3) sets model.default, model.provider, agent.max_turns via hermes --profile X config set, (4) copies skill directories from $PANEL_DIR/skills/ to ~/.hermes/profiles/<name>/skills/software-development/, (5) logs each step. Provider detection: use HERMES_PROVIDER env or hermes config get model.provider to infer. All operations are idempotent — skip if already configured.
    
    Task 3: Wire dokima init (profile mode) into CLI dispatch
    Files: dokima
    Dependencies: Task 2
    Parallelizable: no
    Description: Add dispatch at the top of main(): when feature == "init" and no description argument (or --profiles flag), call init_profiles() and exit. When feature == "init" with a description, print deprecation warning and suggest dokima discover. Add --provider and --nm-provider flags to override auto-detection.
    
    Task 4: Update install.sh to call dokima init
    Files: install.sh
    Dependencies: Task 3
    Parallelizable: yes
    Description: Replace the --with-profiles loop (lines 71-82) with: python3 "$PANEL_DIR/dokima" init (or equivalent). The installer already has hermes on PATH and the repo cloned — dokima init handles the rest. Keep the --with-profiles flag name for backward compatibility.
    
    Task 5: Slim down setup-linux.sh profile section
    Files: scripts/setup-linux.sh
    Dependencies: Task 3
    Parallelizable: yes
    Description: Replace the interactive profile creation + skill deployment sections (lines 248-320) with a call to dokima init --provider=<detected>. Keep the API key collection and verification. The script shrinks by ~70 lines.
    
    Task 6: Write unit tests for init_profiles()
    Files: tests/test_init_profiles.py
    Dependencies: Task 2
    Parallelizable: yes
    Description: Test: (a) creates profiles when none exist, (b) skips existing profiles (idempotent), (c) sets correct model defaults per profile, (d) copies skills to correct directories, (e) handles missing hermes gracefully, (f) handles missing PANEL_DIR/skills/ gracefully, (g) handles partial state (profile exists but no skills — fills gap), (h) respects --provider and --nm-provider overrides.
    
    Task 7: Update installer tests for new profile behavior
    Files: tests/test_installer.py
    Dependencies: Task 4
    Parallelizable: yes
    Description: Update TestWithProfiles class: verify that --with-profiles now creates profile directories AND deploys skill directories. Add test: idempotent re-run with --with-profiles does not break existing profiles. Update the fake hermes to handle hermes --profile X config set subcommands.
    
    Task 8: Update README with new init/discover commands
    Files: README.md
    Dependencies: Task 3
    Parallelizable: yes
    Description: Add dokima init section to quickstart. Show: dokima init creates profiles, dokima init --provider=openrouter overrides. Add dokima discover entry for project initialization. Mention deprecation of dokima init <desc>.
    
    
    
    12. COTS Build-vs-Buy
    
    Component: Profile creation
    Build/Buy: Buy — hermes profile create
    Justification: Hermes CLI provides this; we compose it
    ────────────────────────────────────────
    Component: Config management
    Build/Buy: Buy — hermes config set
    Justification: Hermes CLI provides this; we compose it
    ────────────────────────────────────────
    Component: Skill deployment
    Build/Buy: Build — shutil.copytree
    Justification: Trivial file copy from repo; no COTS needed
    ────────────────────────────────────────
    Component: Provider detection
    Build/Buy: Build — env + hermes config get
    Justification: 15 lines of Python; no dependency
    ────────────────────────────────────────
    Component: Shell orchestration
    Build/Buy: Build — Python subprocess
    Justification: Already in dokima's DNA
    
    
    
    13. Test Plan
    
    Area 1: Profile Creation
    - Happy path: Run dokima init on clean machine → 4 profiles created, config set, skills deployed, exit 0
    - Edge cases: Profiles already exist → skip creation, still deploy skills (gap-fill). Partial state: profile exists but config missing → set config. No hermes on PATH → exit 1 with clear message
    - Failure modes: hermes profile create fails (permissions) → exit 1, report which profile. Disk full during skill copy → exit 1, report which skill. hermes binary broken → exit 1 with stderr
    - Contract invariants: Before: no profiles or partial profiles. After: exactly 4 profiles exist at ~/.hermes/profiles/{strategist,coder,tech-lead,nm}, each with config.yaml and correct skills
    
    Area 2: Config Setting
    - Happy path: Provider auto-detected from HERMES_PROVIDER env → all profiles use it. Model defaults: strategist=deepseek-v4-pro, TL=deepseek-o3, coder=deepseek-v4-pro, nm=claude-sonnet-4
    - Edge cases: HERMES_PROVIDER unset → fallback to hermes config get model.provider output. NM_PROVIDER set → nm uses different provider. --provider flag overrides all
    - Failure modes: hermes config set fails (corrupted config.yaml) → report and continue (non-fatal). Config value contains special chars → properly quoted
    - Contract invariants: config.yaml has model.default and model.provider set for every profile after init
    
    Area 3: Skill Deployment
    - Happy path: Skills copied from $PANEL_DIR/skills/<name>/ → ~/.hermes/profiles/<profile>/skills/software-development/<name>/
    - Edge cases: Skill directory already exists → skip (idempotent). Skill missing from repo → warn, continue. Symlink in skill path → follow, copy target
    - Failure modes: Source directory not found → warn, skip that skill. Destination permission denied → exit 1. Disk full mid-copy → cleanup partial copy on next run
    - Contract invariants: After init, each profile's skill directory contains exactly the skill set defined in the template
    
    Area 4: CLI Dispatch
    - Happy path: dokima init → profiles mode. dokima init --provider=openrouter → profiles mode with override. dokima discover 'my app' → project discovery mode
    - Edge cases: dokima init my description → print deprecation warning, suggest dokima discover. dokima init --help → show profile init help
    - Failure modes: Neither hermes nor PANEL_DIR accessible → exit 1 with clear diagnostic
    - Contract invariants: dokima init (no args) must NOT trigger project discovery. dokima discover <desc> must NOT trigger profile init
    
    
    
    14. Panel Split
    
    Wave 1 (sequential): Task 1 → Task 2 → Task 3 (CLI core — must be sequential)
    Wave 2 (parallel, 4 coders): Task 4, Task 5, Task 6, Task 7, Task 8 (all independent — different files, no shared state)
    
    Total: 1 coder for Wave 1, up to 5 coders for Wave 2.
    
    
    
    15. Build & Deploy
    
    - Where: No separate deployment — this is a CLI command in the existing dokima script
    - CI: python3 -m pytest tests/test_init_profiles.py tests/test_installer.py -q
    - Env vars needed: HERMES_PROVIDER (optional), NM_PROVIDER (optional), PANEL_DIR (auto-detected from script location)
    - Build: python3 -m py_compile dokima
    
    
    
    16. Risk Register
    
    #: 1
    Risk: Rename dokima init breaks undocumented user workflows
    Severity: LOW
    Mitigation: Search codebase + git history for dokima init usage; none
      found outside coverage HTML
    Trigger: User reports "dokima init stopped working"
    ────────────────────────────────────────
    #: 2
    Risk: Skill copy fails silently (partial deployment)
    Severity: MEDIUM
    Mitigation: Verify each copy with os.path.exists; report warnings
      per-skill
    Trigger: os.listdir on destination shows fewer dirs than source
    ────────────────────────────────────────
    #: 3
    Risk: hermes config set format changes across Hermes versions
    Severity: MEDIUM
    Mitigation: Pin to current hermes config set model.default X format; test
      on CI with pinned Hermes version
    Trigger: Hermes release changes config key names
    ────────────────────────────────────────
    #: 4
    Risk: Provider detection fails → wrong model assigned
    Severity: LOW
    Mitigation: Default to "deepseek" if detection fails; print warning
    Trigger: HERMES_PROVIDER unset AND hermes config get fails
    ────────────────────────────────────────
    #: 5
    Risk: dokima init run without hermes installed → cryptic error
    Severity: LOW
    Mitigation: Explicit check: shutil.which('hermes') before any operations
    Trigger: hermes not on PATH
    
    
    
    17. Anti-Creep
    
    Features explicitly NOT in scope:
    - NO API key management — dokima init does not prompt for, store, or validate API keys. That remains in setup-linux.sh / manual .env creation.
    - NO hermes installation — dokima init assumes hermes is already installed. The installer script handles dependency checks.
    - NO dokima doctor — profile validation/diagnostics is F016, not this feature.
    - NO interactive mode — dokima init is non-interactive. Flags for overrides, env vars for detection.
    - NO profile deletion/cleanup — dokima init only creates. dokima reset or profile removal is out of scope.
    - NO custom profile names — hardcoded to strategist/coder/tech-lead/nm. No --profile-names flag.
    - NO model validation — does not check if the configured model actually exists at the provider. Smoke test is out of scope.
    
    
    
    18. Sign-Off Checklist
    
    - [ ] Naming collision resolved: dokima init → profiles, dokima discover → project init
    - [ ] install.sh --with-profiles calls dokima init instead of bare hermes profile create
    - [ ] setup-linux.sh delegates profile/skill setup to dokima init
    - [ ] Skills deployed match setup-linux.sh reference (spec-strategist-lite, ponytail-guard, spec-kit, saas-ideation, ai-coding-best-practices-lite, adversarial-review-lite)
    - [ ] dokima init is fully idempotent — safe to run 3 times in a row
    - [ ] Provider detection fallback chain: --provider flag → HERMES_PROVIDER env → hermes config get → "deepseek" default
    - [ ] nm profile uses different provider when NM_PROVIDER or --nm-provider set
    - [ ] All 7 skills in repo present and copyable (verify with ls skills/*/SKILL.md)
    - [ ] Tests cover: clean install, idempotent re-run, partial state recovery, missing hermes, missing skills
    - [ ] README updated with dokima init → dokima discover migration note
    - [ ] Backward compat: dokima init <desc> prints deprecation warning, suggests dokima discover
    - [ ] CI passes: python3 -m pytest tests/test_init_profiles.py tests/test_installer.py -q