---
name: ponytail-guard
description: YAGNI laziness guard for hermes-panel — stops agents from building things that don't need to exist. Pre-spec check for strategist, post-build review for Tech Lead. Based on the ponytail ladder (DietrichGebert/ponytail, MIT).
version: 1.0.0
---

# Ponytail Guard — Laziness Ladder for hermes-panel

Before building anything, stop at the first rung that holds:

```
1. Does this need to exist?           → no: skip it (YAGNI)
2. Already in this codebase?          → reuse it, don't rewrite
3. Stdlib does it?                    → use it
4. Native platform feature?           → use it (browser API, OS call, etc.)
5. Installed dependency can do it?    → use it (check Cargo.toml / package.json first)
6. One line?                          → one line
7. Only then: the minimum that works
```

This ladder runs AFTER understanding the problem — read the code, trace the flow, then pick a rung. Lazy about the solution, never about reading.

Safety is non-negotiable: trust-boundary validation, data-loss handling, security, and accessibility stay. The code ends up small because it's necessary, not golfed.

## Strategist Usage (Pre-Spec Guard)

Before writing a spec, the strategist runs the ladder against the feature request:

1. **Read the codebase.** Check if this capability already exists (grep for function names, check config, read git log).
2. **Run the ladder.** Which rung does this feature land on?
3. **If rung 1-4:** Don't write a spec. Report what already exists and how to use it.
4. **If rung 5-7:** Write a spec that only covers the gap — not the whole feature surface.

Output format:
```
Ponytail Guard — Pre-Spec Review
Feature: <feature name>
Rung: <1-7> — <justification>
Existing solution: <what already covers this, or "none">
Spec needed: <yes/no>
If yes — spec scope: <what the spec should cover, specifically>
```

**Anti-pattern:** Writing a spec for a feature the codebase already supports. GLD+TLT multi-symbol? Already in config.rs. Date picker component? Browser has `<input type="date">`.

## Tech Lead Usage (Post-Build Laziness Review)

After the adversarial correctness review, run the ladder against the implementation:

1. **Diff the PR.** For each new file or function: does it land on rung 1-4?
2. **Flag overbuilds.** "This 47-line wrapper → 1-line stdlib call" is a SHOULD FIX.
3. **Don't flag minimal code.** If rung 7 is the right answer, don't second-guess it.

Output as part of the TL verdict:
```
### Ponytail Review
- <file:line>: <rung violation> — <simpler alternative>
- <file:line>: ✅ appropriate
Summary: <N> overbuilds found, <M> minimal
```

## Pitfalls

- The ladder is NOT an excuse to skip reading code. Read first, lazy second.
- "Stdlib does it" means the ACTUAL stdlib, not "I could implement this with stdlib." If you'd need 20 lines to wire it up, that's rung 7.
- Don't flag idiomatic patterns. A 12-line error wrapper in Rust is not overbuilding — it's how the language works.
- Safety stays. A one-liner that skips input validation is a regression, not a win.
- The ladder applies to NEW code, not test code. Tests can be verbose. Don't ponytail the test suite.
