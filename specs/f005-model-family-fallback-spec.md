# F005: Model Family Fallback

Now I have full understanding. Let me produce the complete corrected spec.
    
    Position: F005 adds provider-fallback to spawn_agent so the panel survives primary model outages by auto-retrying with a configured secondary model per role. (High confidence)
    
    
    
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    SPEC: F005 — Model Family Fallback
    Status: In Progress | Priority: P1 | Branch: feat/f005-model-family-fallback
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    1. Executive Summary
    
    Dokima spawns Hermes agents for strategist, coder, and tech-lead phases. When
    the primary model provider suffers an outage (DeepSeek API returns 503s, auth
    expires, rate limits hit), the pipeline halts with an opaque subprocess failure.
    F005 adds a fallback chain to spawn_agent: primary model fails → detect failure
    pattern → retry with secondary model from env vars. The panel continues without
    operator intervention. Cross-family adversarial review (nm) is preserved: its
    fallback model stays in a different family from the coder's fallback.
    
    2. Constitution Check
    
    Axiom: Solves user's own pain?
    Status: YES
    Detail: Pipeline runs that silently fail on provider outages waste operator
      time. Shaun runs Dokima autonomously — fallback eliminates a failure mode
      that currently requires manual intervention.
    ────────────────────────────────────────
    Axiom: Weekend-buildable?
    Status: YES
    Detail: ~150 LOC in dokima + ~80 LOC test file. Single function modification
      (spawn_agent) + env var wiring. No new dependencies.
    ────────────────────────────────────────
    Axiom: Evidence people will pay?
    Status: N/A
    Detail: Internal infrastructure robustness. Not revenue-generating.
    ────────────────────────────────────────
    Axiom: Boring/tech-proven?
    Status: YES
    Detail: Retry-with-fallback is standard distributed-systems pattern. Hermes
      Agent already supports --provider and -m flags we leverage.
    ────────────────────────────────────────
    Axiom: Avoids AI hype?
    Status: YES
    Detail: Zero AI. Pure error-handling plumbing.
    
    Constitution verdict: PASS. All mandatory checks satisfied.
    
    3. Ponytail Guard — Pre-Spec Review
    
    Feature: F005 — Model Family Fallback
    Rung: 7 — minimum that works (new fallback detection + retry logic required; no
      stdlib shortcut for Hermes error-pattern matching or multi-model retry)
    Existing solution: None. spawn_agent has no retry or fallback logic. Primary
      model failure = pipeline halt.
    Spec needed: YES
    Spec scope: Error detection in spawn_agent output, env var config for
      fallback models, single-retry with fallback per agent spawn, test coverage
      for each failure pattern.
    
    4. Decision Table
    
    Option: A: Per-profile secondary config in config.yaml
    Operator UX: Requires profile editing
    Complexity: Medium (YAML parsing)
    Coverage: Silent config
    Verdict: Reject — too coupled to hermES internals, fragile
    ────────────────────────────────────────
    Option: B: Env vars PANEL_FALLBACK_STRATEGIST, etc.
    Operator UX: One-line .env edit
    Complexity: Low
    Coverage: All roles
    Verdict: Accept — same pattern as PANEL_PARALLEL, PANEL_REASONING
    ────────────────────────────────────────
    Option: C: Single PANEL_FALLBACK env var shared by all
    Operator UX: Minimal config
    Complexity: Low
    Coverage: Role-oblivious
    Verdict: Reject — strategist and coder may need different fallback
      families
    
    5. Impact
    
    Pipeline survives primary model provider outages without operator intervention.
    Operators configure one env var per role to enable fallback; unconfigured roles
    halt as before (no silent degradation).
    
    6. What Changed
    
    - dokima: spawn_agent gains _detect_provider_failure() helper and single-retry
      fallback path using PANEL_FALLBACK_<ROLE> env vars
    - dokima: main() loads fallback config from env, validates format, surfaces
      warnings on misconfiguration
    - tests/test_f005_fallback.py: new — covers timeout detection, API error
      patterns, auth failure patterns, fallback success, fallback exhaustion,
      env var parsing edge cases
    - specs/conventions.md: model compatibility table updated with fallback guidance
    - docs/setup.md: fallback configuration section added
    
    7. Confidence: High | Impact: MEDIUM
    
    Confidence is High because:
    - spawn_agent is a well-understood function with 16 call sites (all identical
      shape)
    - Error detection patterns are regex-based on known Hermes error output shapes
    - Env var pattern matches existing PANEL_* conventions
    - No new dependencies or API surface
    
    Impact is MEDIUM because fallback changes the pipeline's operational behavior,
    but only in failure scenarios. Normal-path behavior is unchanged.
    
    8. API/Interface Proposal
    
    N/A — this is purely internal error-handling plumbing. No new APIs, routes, or
    data structures. External interface is env vars only.
    
    9. Security Considerations
    
    New env vars (PANEL_FALLBACK_STRATEGIST, PANEL_FALLBACK_CODER, PANEL_FALLBACK_TL)
    are read from the same .env file as API_SERVER_KEY. Token redaction in logs
    already covers any model provider strings that might leak. No new attack surface.
    The fallback model string is validated against a safe pattern (alphanumeric,
    hyphens, slashes, dots) before being passed to subprocess — prevents injection
    through env var tampering.
    
    10. Documentation Impact
    
    docs/setup.md: Add "Fallback Configuration" subsection under "Model Configuration"
    explaining PANEL_FALLBACK_* env vars with provider-specific examples.
    specs/conventions.md: Add fallback row to model compatibility table.
    
    11. Feature Breakdown
    
    Task 1: Add failure-detection helper to spawn_agent
    Files: dokima
    Dependencies: [none]
    Parallelizable: yes
    Description: Add _detect_provider_failure(output: str, returncode: int) -> bool that regex-matches known Hermes error patterns: timeout markers, API 5xx/429 errors, auth failure (401/403), connection refused, empty response. Returns True when primary provider is definitively down (not when the agent produced a valid-but-wrong answer).
    
    Task 2: Wire fallback env vars into main() config loading
    Files: dokima
    Dependencies: [none]
    Parallelizable: yes
    Description: In main(), after API_KEY load, read PANEL_FALLBACK_STRATEGIST, PANEL_FALLBACK_CODER, PANEL_FALLBACK_TL from os.environ. Validate each with a safe pattern regex ^[a-zA-Z0-9_./-]+$. Store in a FALLBACK_MODELS dict keyed by profile name. Warn on invalid format, skip on absent.
    
    Task 3: Add fallback retry path to spawn_agent
    Files: dokima
    Dependencies: [Task 1, Task 2]
    Parallelizable: no
    Description: Modify spawn_agent to accept an optional fallback_model parameter. After the primary spawn completes, if returncode != 0 or _detect_provider_failure(output) is True, print a warning, then spawn a second agent with the fallback model/provider flags. On fallback success, tag output with [profile:fallback]. On fallback failure, return the original failure output (not the fallback failure). Pass FALLBACK_MODELS[profile] from each call site. Preserve the model=None default behavior for call sites that don't pass fallback.
    
    Task 4: Update all spawn_agent call sites to pass fallback
    Files: dokima
    Dependencies: [Task 3]
    Parallelizable: no
    Description: At each of the 16 spawn_agent call sites, add fallback_model=FALLBACK_MODELS.get(profile). This is a mechanical change — same expression at every site. The default of None (no fallback configured) preserves existing behavior. Exclude the nm phase call site (nm uses its own script, not spawn_agent directly).
    
    Task 5: Preserve cross-family invariant for nm fallback
    Files: dokima
    Dependencies: [Task 2]
    Parallelizable: yes
    Description: Add validation at startup: if both coder and nm fallback models are configured, verify they belong to different model families (different provider prefix). Warn if they're same-family — adversarial review is degraded. This does not block the pipeline — only warns. Also add this check to the nm phase's existing "different model family" print statement.
    
    Task 6: Write test suite for fallback behavior
    Files: tests/test_f005_fallback.py
    Dependencies: [Task 1, Task 3]
    Parallelizable: no
    Description: Create test_f005_fallback.py with test classes:
    - test_detect_timeout_after_kill — spawn_agent output with TIMEOUT marker triggers detection
    - test_detect_api_503_error — stderr contains 503 Service Unavailable
    - test_detect_auth_401_error — stderr contains 401 Unauthorized
    - test_detect_connection_refused — subprocess fails with connection error
    - test_detect_normal_output_passes — valid spec output does not trigger fallback
    - test_fallback_fires_on_primary_failure — mock primary fail, verify fallback spawn called
    - test_fallback_exhaustion_returns_primary_error — both fail, return original error
    - test_no_fallback_when_not_configured — absent env var, no retry
    - test_fallback_model_validation_rejects_injection — env var with shell chars rejected
    - test_cross_family_warning — same-family coder+nm fallback logs warning
    
    12. Risk Register
    
    #: R1
    Risk: Fallback model also down → pipeline halts anyway
    Severity: Medium
    Mitigation: Acceptable — two-provider outage is rare; returns primary
      error for diagnosis
    Trigger: Both providers down simultaneously
    ────────────────────────────────────────
    #: R2
    Risk: Fallback model produces lower-quality specs (different reasoning)
    Severity: Low
    Mitigation: Panel's DAG re-prompt and TL review catch quality issues
      regardless of model
    Trigger: Fallback model is flash-tier or different architecture
    ────────────────────────────────────────
    #: R3
    Risk: nm cross-family invariant broken if operator configures same-family
      fallback
    Severity: Low
    Mitigation: Startup validation warns; does not block
    Trigger: Operator misconfiguration
    ────────────────────────────────────────
    #: R4
    Risk: False positive failure detection → unnecessary fallback (wasted
      tokens)
    Severity: Medium
    Mitigation: Tight regex patterns on known error signatures; normal output
      (even with warnings) passes detection
    Trigger: Hermes stderr contains substrings matching error patterns in
      non-error context
    ────────────────────────────────────────
    #: R5
    Risk: Env var injection via PANEL_FALLBACK_CODER
    Severity: Low
    Mitigation: Pattern validation ^[a-zA-Z0-9_./-]+$ before use; list-based
      subprocess args prevent shell injection
    Trigger: Malicious env file write
    ────────────────────────────────────────
    #: R6
    Risk: Fallback model string format mismatch (hermes --provider parsing)
    Severity: Low
    Mitigation: Validation in main() with clear error; skip invalid config,
      print warning
    Trigger: Provider/model format differs from slash-separated convention
    
    13. Anti-Creep
    
    Features explicitly NOT in scope:
    - Multiple fallback tiers (primary → secondary → tertiary) — single fallback only
    - Circuit breaker or backoff logic — one retry per agent spawn
    - Per-phase timeout tuning based on model family
    - Model family auto-detection from provider name
    - Fallback model health checks or pre-warming
    - Changing nm script internals (nm uses _safe_run, not spawn_agent)
    - Dashboard or metrics for fallback frequency
    - Per-provider API key management (uses existing profile .env)
    
    14. Parallelization
    
    | Wave | Tasks                  | Coder count |
    |------|------------------------|-------------|
    | 1    | T1, T2, T5             | 3 parallel  |
    | 2    | T3 (depends on T1, T2) | 1           |
    | 3    | T4 (depends on T3)     | 1           |
    | 4    | T6 (depends on T1, T3) | 1           |
    
    15. Build & Deploy
    
    - No new dependencies
    - No CI changes
    - Test with: python3 -m pytest tests/test_f005_fallback.py -v
    - Env vars added to docs/setup.md and setup scripts (setup-linux.sh, setup-windows.ps1)
    - This feature deploys as part of the single dokima script — no separate service
    
    16. Sign-Off Checklist
    
    - [ ] PANEL_FALLBACK_* env var naming approved
    - [ ] Error detection regex patterns reviewed against real Hermes error output
    - [ ] Cross-family warning severity confirmed (warn vs. block)
    - [ ] Fallback model validation pattern ^[a-zA-Z0-9_./-]+$ sufficient for all providers
    - [ ] Single-retry policy acceptable (no exponential backoff)
    - [ ] Test plan covers all failure modes in roadmap's user story
    - [ ] No change to nm script (nm continues using _safe_run, not spawn_agent)
    - [ ] Existing 196 tests still pass with fallback wiring
    - [ ] docs/setup.md and specs/conventions.md update scope confirmed
    - [ ] setup-linux.sh and setup-windows.ps1 update scope confirmed
    
    
    That is the complete corrected spec for F005. Every section required by the panel's DAG format is present: Executive Summary, Constitution Check, Ponytail Guard, Decision Table, Impact, What Changed, Confidence/Impact markers, API/Interface, Security, Documentation, Task Breakdown with proper ### Task N: headers, Risk Register, Anti-Creep, Parallelization wave plan, Build & Deploy, and Sign-Off Checklist.