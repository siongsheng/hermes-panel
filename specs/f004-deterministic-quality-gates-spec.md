# F004: Deterministic Quality Gates

I now have a complete picture. Let me write the F004 spec.
    
    Position: Deterministic quality gates that programmatically validate spec output — not just prompt guidance. The panel already asks for quality but doesn't enforce it. F004 adds the enforcement: struct validation, brevity gate, PR body quality check, and CI regression tests. (High confidence)
    
    
    
    Ponytail Guard — Pre-Spec Review
    Feature: F004: Deterministic Quality Gates
    Rung: 6 — existing quality infrastructure (DAG enforcement, garbage detection) provides the pattern but doesn't cover spec structure, brevity, or PR body quality
    Existing solution: DAG re-prompt loop (lines 3806-3840), garbage detection (lines 3964-4007), spec char reporting (line 3962). None enforce spec quality programmatically.
    Spec needed: Yes
    Spec scope: Add verify_spec_quality() gate function, integrate into strategist phase (re-prompt once → warn if still degraded), CI regression tests asserting quality thresholds.
    
    
    
    F004: Deterministic Quality Gates — Spec
    
    Confidence: High | Impact: MEDIUM
    
    1. Constitution Check
    
    Axiom: Solves user's own pain?
    Verdict: YES — Shaun observed F002 producing 14K-char specs and thin PR
      bodies
    ────────────────────────────────────────
    Axiom: Weekend-buildable?
    Verdict: YES — ~200 lines of gate logic + ~100 lines of tests
    ────────────────────────────────────────
    Axiom: Evidence people will pay?
    Verdict: N/A — internal panel quality, not a SaaS feature
    ────────────────────────────────────────
    Axiom: Tech stack boring and proven?
    Verdict: YES — pure Python regex, no new dependencies
    ────────────────────────────────────────
    Axiom: Avoids AI hype categories?
    Verdict: YES — deterministic code, not AI
    
    2. Decision Table
    
    Option: A
    Approach: Hard-fail on quality breach (exit 1)
    Latency: 0s
    Enforceability: Strong
    Recoverability: None — pipeline stops
    Verdict: Reject
    ────────────────────────────────────────
    Option: B
    Approach: Soft-warn only (print + continue)
    Latency: 0s
    Enforceability: Weak — ignored in CI
    Recoverability: Full
    Verdict: Reject
    ────────────────────────────────────────
    Option: C
    Approach: Re-prompt loop (retry until pass)
    Latency: Variable
    Enforceability: Medium
    Recoverability: Good but unbounded cost
    Verdict: Reject
    ────────────────────────────────────────
    Option: D
    Approach: Re-prompt once + warn if still degraded
    Latency: +60s worst case
    Enforceability: Medium
    Recoverability: Good — mirrors DAG pattern
    Verdict: Accept
    
    Rationale: Option D mirrors the existing DAG re-prompt pattern (lines 3806-3840). One re-prompt gives the strategist a second chance with explicit feedback; if it still fails, we proceed with a warning — the pipeline isn't blocked, but operators know quality degraded.
    
    3. Impact
    
    Panel operators get consistent, measurable spec quality. CI catches regressions when panel changes degrade strategist output. PR bodies no longer contain placeholder text ("See diff for details") when real Impact/What Changed sections exist.
    
    4. What Changed
    
    - dokima (MODIFIED): Add verify_spec_quality() function + integrate into run_phase1_strategist after spec extraction, before save. Re-prompt once on quality breach.
    - tests/test_spec_quality_gates.py (NEW): Unit tests for each quality gate (structure, brevity, PR body) + integration test that verifies re-prompt fires on degraded spec.
    - dokima (MODIFIED): PR body quality check — if extract_pr_sections produces fallback text but spec has real Impact/What Changed, flag and re-extract.
    
    5. API/Interface Proposal
    
    N/A — internal panel functions only.
    
    6. Security Considerations
    
    N/A — no attack surface change.
    
    7. Documentation Impact
    
    docs/pipeline.md: Add "Quality Gates" subsection documenting the 4 deterministic checks and their failure modes.
    
    
    
    8. Task Breakdown
    
    Task 1: Create spec quality gate function skeleton
    Files: dokima
    Dependencies: [none]
    Parallelizable: yes
    Description: Add verify_spec_quality(spec_text, confidence) function returning (passed: bool, failures: list[str]) with placeholder checks — no logic yet, just the call site integration in run_phase1_strategist at line 3961 (after clean_spec_content).
    
    Task 2: Implement spec structure gate
    Files: dokima
    Dependencies: [Task 1]
    Parallelizable: no
    Description: Check that spec has required section headers: Impact (## N. Impact), What Changed (## N. What Changed), Task Breakdown (### Task N: headers). Each check yields a specific failure message like "Missing: What Changed section".
    
    Task 3: Implement task field completeness gate
    Files: dokima
    Dependencies: [Task 2]
    Parallelizable: no
    Description: For each task block parsed by TaskDAG, verify all 5 required fields (Files, Dependencies, Parallelizable, Description) are non-empty. Tasks with empty fields → failure message like "Task 3: missing Dependencies field".
    
    Task 4: Implement PR body quality gate
    Files: dokima
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: After extract_pr_sections(), detect if result is the thin fallback (<100 chars and contains "See diff for details") while the spec itself has ≥200 chars of Impact + What Changed content. If so, flag as failure: "PR body degraded to fallback despite spec having real content."
    
    Task 5: Implement brevity warning gate
    Files: dokima
    Dependencies: [Task 2]
    Parallelizable: yes
    Description: After spec extraction, check if HIGH confidence spec exceeds 5,000 chars or MEDIUM exceeds 7,000 chars. Warn (not block) with message: "Spec is N chars — exceeds brevity target of T chars. Review for verbosity." Does NOT trigger re-prompt — it's a soft warning.
    
    Task 6: Integrate quality gate into strategist phase with re-prompt
    Files: dokima
    Dependencies: [Task 2, Task 3, Task 4]
    Parallelizable: no
    Description: After spec extraction + cleaning (line 3961), call verify_spec_quality(). If it fails, trigger one re-prompt with the failure list as feedback. If re-prompt still fails, print warning and proceed. Use existing spawn_agent pattern (like DAG re-prompt at lines 3834-3835).
    
    Task 7: Write unit tests for each quality gate
    Files: tests/test_spec_quality_gates.py
    Dependencies: [Task 2, Task 3, Task 4, Task 5]
    Parallelizable: yes
    Description: Test each gate independently: structure gate detects missing sections, field completeness gate catches empty fields, PR body gate flags fallback text, brevity gate warns on long specs. Use static spec strings — no agent spawning needed.
    
    Task 8: Write CI regression test for spec quality end-to-end
    Files: tests/test_spec_quality_gates.py
    Dependencies: [Task 6, Task 7]
    Parallelizable: no
    Description: Integration test: feed a known feature description through strategist (mock spawn), verify output passes all quality gates. Regression: if a panel change removes a section header from the prompt, the test fails. Use conftest._mock_spawn pattern from existing integration tests.
    
    
    
    9. Risk Register
    
    #: R1
    Risk: Re-prompt loop causes token cost spike
    Severity: Medium
    Mitigation: Max 1 re-prompt (same as DAG enforcement)
    Trigger: Strategist repeatedly produces low-quality specs
    ────────────────────────────────────────
    #: R2
    Risk: Brevity gate rejects a valid 4,500-char HIGH-conf spec
    Severity: Low
    Mitigation: 5,000-char soft limit (not the 4,000-char prompt target) —
      warns, never blocks
    Trigger: Specs naturally grow with feature complexity
    ────────────────────────────────────────
    #: R3
    Risk: Structure gate rejects a spec that uses non-standard section naming
    Severity: Low
    Mitigation: Gate checks for known patterns + falls back to leniency if ≥3
      sections found
    Trigger: Strategist renames sections
    ────────────────────────────────────────
    #: R4
    Risk: PR body gate falsely flags a genuinely thin feature
    Severity: Low
    Mitigation: Only flags if spec itself has ≥200 chars of Impact+What
      Changed content — thin specs with thin PR bodies are valid
    Trigger: Feature has real impact but extract_pr_sections fails to parse
    
    10. Anti-Creep
    
    - NO model-tuning or prompt engineering changes — this is deterministic programmatic gating, not prompt optimization
    - NO spec re-writing or spec normalization — only validation
    - NO new agent roles or profile changes
    - NO changes to the vet or nm scripts
    - NO blocking the pipeline on quality failures — always warn-and-proceed after single re-prompt
    - NO checking subjective quality (task description specificity, file path accuracy) — only structural/mechanical checks
    
    11. Sign-Off Checklist
    
    - [ ] Quality gate runs after spec extraction, before spec save
    - [ ] Max 1 re-prompt on quality failure (not infinite loop)
    - [ ] Each failure message is human-readable (e.g., "Task 3: missing Dependencies field")
    - [ ] Brevity gate is soft-warn only — never blocks the pipeline
    - [ ] PR body gate detects thin fallback when spec has real content
    - [ ] Unit tests cover each gate independently (no agent spawning)
    - [ ] CI regression test fails if quality gates are removed or broken
    - [ ] Existing pipeline tests still pass (no regressions)
    - [ ] docs/pipeline.md updated with Quality Gates section
    - [ ] Tested with a real strategist output (not just synthetic strings)