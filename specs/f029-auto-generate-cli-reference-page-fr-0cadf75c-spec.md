# F029: Auto-generate CLI reference page from cli-help.json during Vercel build instead of hand-written MDX. New flags and commands appear in docs automatically on every release.

Now I have complete understanding. Here is the corrected spec:
    
    
    
    F029: Auto-Generate CLI Reference Page from cli-help.json
    
    Version: 1.0.0
    Status: Awaiting Sign-Off
    Confidence: High
    Date: 2026-07-02
    
    
    
    0. Executive Summary
    
    The generate-cli-ref.ts script and prebuild hook already auto-generate page.mdx from cli-help.json during Vercel build. F026 already pushes updated cli-help.json to the docs repo on release. The remaining gap: the test file cli-reference.test.ts still uses hardcoded manifests written for the old hand-authored page — it fails 14 of 30 assertions. F029 rewrites the test to validate against cli-help.json as the single source of truth. New flags and commands then appear in docs AND pass tests automatically on every release — zero manual sync.
    
    
    
    1. Constitution Check
    
    Axiom: Solves user's own pain?
    Verdict: YES — manual MDX edits for CLI changes are a recurring
      maintenance tax
    ────────────────────────────────────────
    Axiom: Weekend-buildable?
    Verdict: YES — one test file rewrite, ~120 LOC change
    ────────────────────────────────────────
    Axiom: Evidence people will pay?
    Verdict: N/A (internal tooling)
    ────────────────────────────────────────
    Axiom: Tech stack boring and proven?
    Verdict: YES — Vitest + fs.readFileSync + JSON.parse. No new deps
    ────────────────────────────────────────
    Axiom: Avoids AI hype?
    Verdict: YES — pure build-time scripting, No new deps, no ML
    
    No misalignments. All checks pass.
    
    
    
    2. Impact
    
    For maintainers: Running dokima --release pushes updated cli-help.json to the docs repo. Vercel auto-deploys, prebuild regenerates page.mdx, and tests validate the output against the same cli-help.json. A new flag added in utils.py automatically appears in docs with zero manual steps — the test gates correctness, not content freshness.
    
    For users: CLI reference page always matches the latest release. No stale docs. Every command, flag, and env var is present and accurate.
    
    For CI: The prebuild step is hermetic — generate-cli-ref.ts uses cli-help.json cache on Vercel (no dokima binary needed). Test runs against same cache. Build fails if cli-help.json is missing or malformed.
    
    Current state: 14/30 test failures because the test was written for hand-authored hermes panel-style page that no longer exists. The auto-generated page uses dokima commands, different heading levels, no YAML frontmatter, no Workflow Examples section.
    
    
    
    3. What Changed
    
    Artifact: src/tests/guides/cli-reference.test.ts
    Action: Rewrite
    Reasoning: Replace hardcoded manifests with cli-help.json-driven
      validation
    ────────────────────────────────────────
    Artifact: scripts/cli-help.json
    Action: No change
    Reasoning: Already maintained by F026. Read by test as source of truth
    ────────────────────────────────────────
    Artifact: scripts/generate-cli-ref.ts
    Action: No change
    Reasoning: Already generates page.mdx during prebuild
    ────────────────────────────────────────
    Artifact: package.json (prebuild)
    Action: No change
    Reasoning: Already runs npx tsx scripts/generate-cli-ref.ts
    ────────────────────────────────────────
    Artifact: src/app/(docs)/guides/cli/page.mdx
    Action: No change
    Reasoning: Already auto-generated, never manually edited
    
    Dropped assertions:
    - YAML frontmatter check — auto-generated page has no frontmatter (handled by layout.tsx metadata)
    - hermes panel command names — CLI is now dokima, not hermes panel
    - Workflow Examples section — not in auto-generated page scope (belongs in Get Started guide)
    - PANEL_INTERACTIVE and PANEL_ANSWERS — don't exist in cli-help.json (old manifest cruft)
    
    Added assertions:
    - Every command from cli-help.json exists in page.mdx with correct heading level
    - Every flag and its associated env var from cli-help.json appear in page.mdx
    - Page version matches cli-help.json version
    - cli-help.json exists and is valid JSON with required keys
    
    
    
    4. Feature Breakdown
    
    Task 1: Rewrite cli-reference.test.ts — dynamic CLI manifest validation
    - Files: src/tests/guides/cli-reference.test.ts
    - Dependencies: [none]
    - Parallelizable: yes
    - Description: Replace all three hardcoded manifests (COMMAND_MANIFEST, FLAG_MANIFEST, ENV_VAR_MANIFEST) with dynamic extraction from scripts/cli-help.json. Read the JSON at test time, derive expected command names/syntaxes, flag names, and env var names. Drop frontmatter test (auto-generated page has no frontmatter). Drop workflow examples tests (section doesn't exist in auto-generated output). Keep the code block policy test (no $ prefix). Add version match test (page heading version === cli-help.json version). All 30 tests pass after rewrite.
    
    Task 2: Verify prebuild integration and hermetic build
    - Files: scripts/generate-cli-ref.ts (read-only verification), package.json (read-only verification)
    - Dependencies: [Task 1]
    - Parallelizable: no
    - Description: Confirm generate-cli-ref.ts runs correctly by executing npx tsx scripts/generate-cli-ref.ts and verifying output page.mdx contains all 13 commands, 11 flags, and 12 env vars from cli-help.json. Verify the generated page.mdx imports CodeBlock and Callout components. Confirm prebuild script in package.json is wired correctly. No code changes — this is a verification gate.
    
    Task 3: Update README to reflect auto-generated CLI page
    - Files: README.md
    - Dependencies: [Task 2]
    - Parallelizable: no
    - Description: Update the project structure section in README.md to note that cli/page.mdx is auto-generated by scripts/generate-cli-ref.ts during prebuild, not manually edited. Add a note that scripts/cli-help.json is the source of truth, pushed by F026 on release. ~5 lines changed.
    
    
    
    5. Data Model
    
    Source of truth: scripts/cli-help.json
    
    {
      tool: string,          // "dokima"
      version: string,       // e.g. "1.2.5"
      commands: [{ name, syntax, description }],
      flags: [{ flag, args: string|null, env_var: string|null, description }],
      env_vars: [{ name, description, related_flag: string|null }]
    }
    
    
    Consumed by:
    - scripts/generate-cli-ref.ts — reads JSON, writes page.mdx
    - src/tests/guides/cli-reference.test.ts — reads JSON, validates page.mdx
    
    No new entities. The JSON schema is already defined (F020).
    
    
    
    6. API Routes
    
    N/A — no API surface change. All work is build-time scripting and test validation.
    
    
    
    7. Component Tree
    
    N/A — no React component changes. The CLI page uses existing MDX components (CodeBlock, Callout) already registered in src/mdx-components.tsx.
    
    
    
    8. COTS Build-vs-Buy
    
    Dependency: Vitest
    Buy/Build: Buy (already installed)
    Justification: Test framework. v4.1.9 in devDependencies
    ────────────────────────────────────────
    Dependency: fs (Node)
    Buy/Build: Platform (stdlib)
    Justification: File reading. No npm package needed
    ────────────────────────────────────────
    Dependency: tsx
    Buy/Build: Buy (already installed)
    Justification: TypeScript execution for generate-cli-ref.ts prebuild
      script. v4 in devDependencies
    ────────────────────────────────────────
    Dependency: Next.js prebuild hook
    Buy/Build: Platform (built-in)
    Justification: npm lifecycle script. Already wired in package.json
    
    Fully bought/built. No new dependencies required.
    
    
    
    9. Test Plan
    
    Feature Area: CLI Reference Page Validation
    
    Happy path:
    - cli-help.json exists with valid JSON → test reads it → derives command/flag/env-var lists → asserts each appears in page.mdx → all 30 tests pass
    
    Edge cases:
    - cli-help.json missing → test fails with clear "cli-help.json not found at scripts/cli-help.json" error (not a cryptic JSON parse error)
    - cli-help.json has empty commands array → test passes (page.mdx should show "0 commands")
    - cli-help.json has extra keys (forward-compat) → test ignores unknown keys, validates known shape
    - page.mdx is stale (version mismatch vs cli-help.json) → version test fails
    - Command syntax contains MDX-breaking characters (<, >, |) → test reads raw page.mdx content, doesn't parse MDX — raw string matching unaffected
    - Flag has null env_var → "Flag" column shows "null" (as designed by generate-cli-ref.ts)
    
    Failure modes:
    - cli-help.json is invalid JSON → test fails with JSON parse error including file path
    - cli-help.json missing required key (commands, flags, or env_vars) → test fails with specific assertion about missing key
    - generate-cli-ref.ts crashes during prebuild → Vercel build fails, no deploy
    - page.mdx is missing entirely → test fails on "exists and is non-empty" assertion
    - Vercel build runs without dokima binary → generate-cli-ref.ts falls back to cli-help.json cache (existing behavior, verified in Task 2)
    
    Contract invariants:
    - page.mdx command count === cli-help.json.commands.length
    - page.mdx flag count === cli-help.json.flags.length
    - page.mdx env var count === cli-help.json.env_vars.length
    - Page version in h1 === cli-help.json.version
    - Every command name from JSON appears as #### \name\ in page.mdx
    - Every flag from JSON appears in page body (backtick-wrapped)
    - Every env var from JSON appears in page body
    - No shell code block uses $ prefix
    
    
    
    10. Panel Split
    
    Wave: Wave 1
    Tasks: Task 1
    Coders: 1 coder
    Justification: Test rewrite — no file overlap with others
    ────────────────────────────────────────
    Wave: Wave 2
    Tasks: Task 2, Task 3
    Coders: 2 coders (parallel)
    Justification: Task 2 touches generate-cli-ref.ts (read-only), Task 3
      touches README.md — no file overlap
    
    Total: 3 tasks, 2 waves, max 2 parallel coders.
    
    
    
    11. Build & Deploy
    
    Build: npm run build triggers prebuild → npx tsx scripts/generate-cli-ref.ts → generates page.mdx → Next.js build compiles MDX → SSG output.
    
    Deploy: Vercel auto-deploys on push to main. prebuild runs in Vercel build environment (uses cli-help.json cache since dokima binary unavailable).
    
    Env vars needed: None. cli-help.json is committed to the repo.
    
    CI: npm test runs Vitest. Test reads cli-help.json and validates page.mdx.
    
    
    
    12. Risk Register
    
    #: R1
    Risk: cli-help.json shape changes (F020 schema evolution) → test breaks on
      unknown keys
    Severity: MEDIUM
    Mitigation: Test validates known keys but ignores unknown ones. Schema
      change requires coordinated F020+F029 update
    Trigger: F020 PR changes --help-json output shape
    ────────────────────────────────────────
    #: R2
    Risk: generate-cli-ref.ts fails silently (writes empty page.mdx)
    Severity: LOW
    Mitigation: Existing prebuild failure halts Vercel build. Test catches
      empty page via "exists and is non-empty" assertion
    Trigger: cli-help.json is empty or valid JSON with zero-length arrays
    ────────────────────────────────────────
    #: R3
    Risk: Vercel build environment loses tsx → prebuild fails
    Severity: LOW
    Mitigation: tsx is in devDependencies, installed during npm install.
      Vercel runs npm install before npm run build
    Trigger: Vercel changes default build image
    ────────────────────────────────────────
    #: R4
    Risk: Test and page.mdx both read stale cli-help.json → passes but docs
      are wrong
    Severity: LOW
    Mitigation: F026 pushes updated cache on release. If F026 fails, the
      release itself has issues — not F029's domain
    Trigger: F026 release push fails silently
    
    
    
    13. Anti-Creep
    
    - Do NOT modify generate-cli-ref.ts — it works correctly and is already wired to prebuild
    - Do NOT add a "Workflow Examples" section to the auto-generated page — that's Get Started content, not CLI reference
    - Do NOT add YAML frontmatter support to generate-cli-ref.ts — metadata is handled by layout.tsx
    - Do NOT add a new npm script — prebuild is already wired
    - Do NOT add a generate-cli-ref.test.ts — the page test IS the generation test (validates output)
    - Do NOT change the page.mdx file — it's auto-generated and will be overwritten on next build
    - Do NOT add new dependencies — fs, path, vitest are already available
    - Do NOT add CI-specific steps — everything runs through existing npm test + npm run build
    
    
    
    14. Sign-Off Checklist
    
    - [ ] Test rewrites: 14 failing assertions → 30 passing, all driven by cli-help.json
    - [ ] Hardcoded COMMAND_MANIFEST, FLAG_MANIFEST, ENV_VAR_MANIFEST removed from test
    - [ ] Version match test: page.mdx h1 version === cli-help.json version
    - [ ] Schema validation: test fails clearly if cli-help.json is missing or malformed
    - [ ] npm test passes with 0 failures
    - [ ] npm run build succeeds (prebuild → page.mdx generated → Next.js SSG)
    - [ ] npm run dev serves the generated CLI page correctly
    - [ ] README updated to note auto-generated CLI page
    - [ ] No new dependencies added
    - [ ] No changes to generate-cli-ref.ts
    - [ ] No changes to page.mdx (auto-generated)
    - [ ] F029 merged → F026's next release push produces updated docs that pass tests automatically