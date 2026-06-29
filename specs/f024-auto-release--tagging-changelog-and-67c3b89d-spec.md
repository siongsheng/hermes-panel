# F024: Auto-Release — Tagging, Changelog, and GitHub Releases

Here is the complete corrected spec for F024:
    
    
    F024: Auto-Release — Tagging, Changelog, and GitHub Releases
    
    Version: 1.0
    Status: Ready for Implementation
    Confidence: High
    Impact: MEDIUM
    Feature ID: F024
    Dependencies: F021 (done — VERSION file, check_upgrade, _version_newer exist)
    
    ────────────────────────────────────────────────────────
    
    1. Executive Summary
    
    dokima --release [patch|minor|major] automates the full release workflow:
    bump the VERSION file, auto-generate a changelog from merged PRs grouped
    by conventional commit prefix (feat/fix/chore/docs), create a git tag,
    publish a GitHub Release via gh release create, prune old tags to keep
    the repo clean, and push everything to origin. Validates clean tree,
    default branch, and upstream sync before releasing. Replaces the manual
    three-step dance (bump file → tag → gh release create) with one command.
    Confidence is High — the pattern is identical to F021's flag dispatch,
    and gh release create --generate-notes is a solved CLI problem.
    
    ────────────────────────────────────────────────────────
    
    2. Constitution Check
    
    Axiom: Solves user's own pain?
    Status: Yes
    Notes: Roadmap user story: "As a maintainer, dokima --release [patch|minor|major]
    bumps the version, auto-generates a changelog... all in one command."
    Currently releasing dokima requires 4+ manual steps — bump VERSION, write
    changelog, git tag, gh release create. Error-prone and inconsistent.
    
    Axiom: Weekend-buildable?
    Status: Yes
    Notes: ~180 LOC across 10 tasks, ~2 hours. One new function in utils.py,
    one flag dispatch in dokima, one new test file. No new dependencies.
    
    Axiom: Boring and proven?
    Status: Yes
    Notes: VERSION file is the oldest versioning pattern. gh CLI is GitHub's
    own tool. git tag is git. Conventional commits for changelog grouping
    is a widely-adopted standard (Angular, Commitlint). No new frameworks.
    
    Axiom: Avoids AI hype?
    Status: Yes
    Notes: Zero AI. Pure CLI plumbing on existing git/gh tooling.
    
    Verdict: PASS. No misalignments.
    
    ────────────────────────────────────────────────────────
    
    3. Ponytail Guard — Pre-Spec Review
    
    Rung 1: Does this need to exist?
    Check: grep -rl "release|gh release" dokima utils.py — no release automation
    exists. Users must manually bump VERSION, write changelog, tag, and
    run gh release create. Multiple steps, easy to forget one.
    Result: Yes
    
    Rung 2: Already in codebase?
    Check: VERSION file exists (F021). check_upgrade() and _version_newer()
    exist in utils.py. _detect_default_branch() exists. gh() wrapper exists.
    No release automation code.
    Result: No
    
    Rung 3: Stdlib does it?
    Check: subprocess (git/gh calls), os.open (VERSION read/write), re (semver
    parsing, PR title prefix grouping), datetime (changelog date). All stdlib.
    Result: Rung 3
    
    Rung 4: Native platform feature?
    Check: gh release create --generate-notes auto-generates changelog from PRs.
    git tag manages tags. git push pushes. Rung 4 for the heavy lifting.
    Result: Rung 4
    
    Verdict: Rung 3-4 — stdlib + git + gh CLI. Feature is justified, no overbuilding.
    
    ────────────────────────────────────────────────────────
    
    4. Decision Table
    
    Option: gh release create --generate-notes
      Simplicity: Medium — relies on gh's built-in PR-based changelog
      Quality: Good — groups by label, links PR authors
      Flexibility: Low — can't customize grouping or format
      Verdict: Accept for MVP
    
    Option: Manual changelog from git log since last tag
      Simplicity: Medium — parse git log --oneline
      Quality: Poor — commit messages are inconsistent quality
      Flexibility: Medium — full control
      Verdict: Reject — PR titles are better curated than commit messages
    
    Option: Conventional Commits parser from PR titles
      Simplicity: Medium — regex on gh pr list output
      Quality: High — groups by feat/fix/chore/docs
      Flexibility: High — full control over changelog format
      Verdict: Accept as enhancement — use for section grouping,
               keep gh --generate-notes as base
    
    Option: Release Please / semantic-release bot
      Simplicity: Low — adds external dependency, CI config, token management
      Quality: High — battle-tested
      Flexibility: Low — opinionated workflow
      Verdict: Reject — overkill for a single-script CLI tool; YAGNI
    
    DECISION: gh release create --generate-notes as the primary changelog
    generator (zero code needed — gh handles it). Supplement with
    conventional-commit PR title scanning for a cleaner grouped changelog
    if --generate-notes output is insufficient. The release command itself
    uses gh release create vX.Y.Z --generate-notes --title "vX.Y.Z".
    
    ────────────────────────────────────────────────────────
    
    5. Impact
    
    Maintainers save 3-5 minutes per release and eliminate mistakes: no more
    forgotten tag pushes, no more mismatched VERSION vs tag, no more manual
    changelog writing. The release becomes a single command after PRs are
    merged. Users see consistent, well-formed GitHub Releases with auto-generated
    changelogs instead of ad-hoc release notes. No pipeline behavior changes —
    --release exits before pipeline init, same as --version and --upgrade.
    
    ────────────────────────────────────────────────────────
    
    6. What Changed
    
    - utils.py: New do_release(bump) function — validates preconditions,
      bumps VERSION, commits, tags, prunes old tags, pushes, creates
      GitHub Release (~110 LOC)
    - utils.py: New _bump_version(current, bump) helper — semver arithmetic (~15 LOC)
    - utils.py: New _prune_old_tags(keep_count) helper — keeps last N tags (~15 LOC)
    - dokima: New --release flag dispatch + arg validation (~20 LOC)
    - dokima: New is_release flag in main() flag scanning loop (~3 LOC)
    - dokima: Add do_release import to utils imports (~1 LOC)
    - dokima: Add --release to HELP_TEXT COMMANDS section (~3 LOC)
    - dokima: Add --release to CLI_METADATA commands array (~5 LOC)
    - tests/test_f024_release.py: New test file — verify --release with each
      bump type, precondition failures, edge cases (~60 LOC)
    - VERSION: Gets bumped by do_release (existing file, modified)
    
    ────────────────────────────────────────────────────────
    
    7. API / Interface Proposal
    
    New flag: --release <patch|minor|major>
    
    Syntax: dokima --release patch [project_dir]
            dokima --release minor [project_dir]
            dokima --release major [project_dir]
            dokima --release patch --dry-run [project_dir]
    
    dokima --release <bump>:
      1. Validate bump is patch/minor/major (else error + usage)
      2. Validate PROJECT_DIR is a git repo
      3. Detect default branch via _detect_default_branch()
      4. Validate: on default branch (else error)
      5. Validate: clean working tree (git diff-index --quiet HEAD, else error)
      6. Validate: up to date with origin (git fetch origin, git rev-list HEAD..origin/$branch
         is empty, else error)
      7. Read current VERSION, compute new version via _bump_version(current, bump)
      8. Write new VERSION to VERSION file
      9. git add VERSION
      10. git commit -m "chore: bump version to vX.Y.Z"
      11. git tag -a vX.Y.Z -m "Release vX.Y.Z"
      12. Prune old tags: keep last 10 release tags (vX.Y.Z), delete older ones
          via git push origin --delete <old-tag> (warn if any exist)
      13. git push origin $default_branch
      14. git push origin vX.Y.Z
      15. gh release create vX.Y.Z --generate-notes --title "vX.Y.Z" --target $default_branch
      16. Print summary: "Released dokima vX.Y.Z — <url>"
    
    --dry-run flag:
      Skips steps 8-15. Prints what WOULD happen: new version, commit message,
      tag name, gh release create command. Exits 0.
    
    Error exits:
      - Invalid bump type → exit 1, print usage
      - Not on default branch → exit 1, print current branch + expected
      - Dirty tree → exit 1, print git status
      - Behind origin → exit 1, print how many commits behind
      - gh CLI not found → exit 1, print install instructions
      - gh not authenticated → exit 1 (gh release create will fail with clear error)
      - VERSION file missing → exit 1, print path
      - Network failure during push → exit 1, print error
    
    Backward compatibility:
      Fully additive. No existing flags changed. --release exits before pipeline init.
    
    ────────────────────────────────────────────────────────
    
    8. Security Considerations
    
    --release: MEDIUM risk — writes to VERSION file, commits, pushes, creates
    GitHub Release. All subprocess calls use list-based args (per conventions.md
    line 67-79). No shell=True, no os.system(). No user input flows into shell
    commands — bump type is validated against a fixed set (patch/minor/major)
    before use. GH_TOKEN is set via _set_gh_token() (same as existing gh() calls)
    and redacted from logs via _redact_secrets().
    
    VERSION file write: Uses atomic write pattern (write to temp file, rename)
    to prevent corruption on interrupt. Same process as the VERSION file read
    in F021 — no elevated permissions needed.
    
    Tag pruning: Only deletes tags matching vX.Y.Z pattern. The keep_count=10
    floor prevents catastrophic tag deletion. Push --delete lists tags explicitly
    (one per call), avoiding glob injection.
    
    --dry-run: Zero side effects — reads only, no writes, no network (except
    git fetch to check sync). Safe to run in any state.
    
    Attack surface: Requires filesystem write (VERSION), git push (authenticated
    via gh), and gh release create (authenticated). All same permissions as
    manual release workflow. No new attack vectors.
    
    ────────────────────────────────────────────────────────
    
    9. Documentation Impact
    
    README: --release added to HELP_TEXT COMMANDS section (done as part of Task 9).
    docs/pipeline.md: No change — --release exits before pipeline.
    docs/setup.md: No change — no new install dependencies (uses same gh CLI).
    docs/releasing.md: New doc (optional P3 follow-up) documenting the release
    workflow for maintainers.
    
    ────────────────────────────────────────────────────────
    
    10. Task Breakdown
    
    Task 1: Add _bump_version() helper to utils.py
    Files: utils.py
    Dependencies: none
    Parallelizable: yes
    Description: Add _bump_version(current, bump) function adjacent to _version_newer (around line 957): takes current X.Y.Z string and bump type, returns new X.Y.Z string — patch increments Z, minor increments Y and resets Z to 0, major increments X and resets Y and Z to 0.
    
    Task 2: Add _prune_old_tags() helper to utils.py
    Files: utils.py
    Dependencies: none
    Parallelizable: yes
    Description: Add _prune_old_tags(keep_count=10) function: runs git tag --sort=-v:refname, filters to vX.Y.Z pattern, keeps the first keep_count, deletes the rest via git push origin --delete. Warns for each deleted tag. If no tags to prune, silent no-op.
    
    Task 3: Add do_release() function to utils.py
    Files: utils.py
    Dependencies: Task 1, Task 2
    Parallelizable: no
    Description: Add do_release(bump, project_dir, dry_run=False) function: validates preconditions (git repo, default branch, clean tree, up to date with origin), computes new version via _bump_version, if dry_run prints plan and exits, else bumps VERSION, commits, tags, prunes old tags, pushes branch + tag, runs gh release create --generate-notes. Exits on any failure with clear message.
    
    Task 4: Add --release flag scanning to dokima main()
    Files: dokima
    Dependencies: none (flag scanning is mechanical — no function dependency)
    Parallelizable: yes
    Description: Add is_release = False and release_bump = None to flag init block (around line 101), add arg parsing: if arg == "--release": is_release = True; skip_next arg (the bump type) logic. Validate bump type is patch/minor/major. Import do_release in utils import block.
    
    Task 5: Add --release early-exit dispatch to dokima main()
    Files: dokima
    Dependencies: Task 3, Task 4
    Parallelizable: no
    Description: Add if is_release: do_release(release_bump, project_dir_or_cwd) in the early-exit block (after --upgrade handler around line 306). Use PROJECT_DIR resolution from existing logic — --release respects the same project_dir arg.
    
    Task 6: Add --dry-run support to --release
    Files: dokima, utils.py
    Dependencies: Task 4, Task 5
    Parallelizable: no
    Description: Add is_dry_run = False flag to main() arg scanning. Pass dry_run=is_dry_run to do_release(). do_release() skips write/commit/tag/push/release steps when dry_run=True, printing the planned actions instead.
    
    Task 7: Add --release import to dokima header
    Files: dokima
    Dependencies: Task 3
    Parallelizable: no (but trivially small — combined with Task 5)
    Description: Add do_release to the utils import line (line 27-28 of dokima). Add do_release next to check_upgrade and _version_newer in the multi-line import block.
    
    Task 8: Add --release to HELP_TEXT in utils.py
    Files: utils.py
    Dependencies: none (mechanical text change)
    Parallelizable: yes
    Description: Add dokima --release [patch|minor|major] [--dry-run] [project_dir] entry to HELP_TEXT string COMMANDS section, after --upgrade entry. Document the bump types: patch (bug fixes), minor (new features), major (breaking changes).
    
    Task 9: Add --release to CLI_METADATA in utils.py
    Files: utils.py
    Dependencies: none (mechanical)
    Parallelizable: yes
    Description: Add {"name": "--release", "syntax": "dokima --release <patch|minor|major> [--dry-run] [project_dir]", "description": "Bump version, generate changelog, tag, and publish GitHub Release"} to CLI_METADATA commands array.
    
    Task 10: Create tests for --release
    Files: tests/test_f024_release.py
    Dependencies: Task 5 (needs do_release importable)
    Parallelizable: yes
    Description: Create test file testing: (a) _bump_version correct for patch/minor/major, (b) _bump_version rejects invalid bump, (c) do_release with --dry-run prints expected plan, (d) do_release fails on non-git dir, (e) do_release fails on dirty tree, (f) do_release fails on non-default branch, (g) do_release fails on invalid bump type, (h) _prune_old_tags keeps 10 newest, (i) --release in HELP_TEXT output, (j) --release in --help-json output.
    
    Task 11: Run full test suite and verify
    Files: none (verification only)
    Dependencies: Task 10
    Parallelizable: no
    Description: Run python3 -m pytest tests/ -q to confirm zero regressions from all 11 tasks, run python3 dokima --release patch --dry-run to verify real output in a clean repo, run python3 -c "compile(open('dokima').read(), 'dokima', 'exec')" to verify build.
    
    ────────────────────────────────────────────────────────
    
    11. Test Plan (MANDATORY)
    
    Happy path:
    - dokima --release patch bumps 1.2.1 → 1.2.2, writes VERSION, commits, tags v1.2.2, pushes
    - dokima --release minor bumps 1.2.1 → 1.3.0
    - dokima --release major bumps 1.2.1 → 2.0.0
    - dokima --release patch --dry-run prints plan, makes zero changes, exits 0
    - gh release create vX.Y.Z --generate-notes produces a GitHub Release with PR summary
    - Tag pruning keeps exactly 10 latest vX.Y.Z tags when >10 exist
    - Tag pruning is silent no-op when ≤10 tags
    - After release, git tag --sort=-v:refname shows new tag at top
    
    Edge cases:
    - VERSION file has trailing whitespace — strip() handles it
    - VERSION file has leading "v" prefix — handled by _bump_version if present
    - Current version is "0.0.1" → minor → "0.1.0" (standard semver)
    - Current version is "9.9.9" → patch → "10.0.0" is NOT expected (that's a major)
      — correct: "9.9.9" → patch → "9.9.10"
    - No previous tags exist (first release) — pruning is silent no-op
    - gh release create fails (network) — exit 1, VERSION already committed but
      not pushed (user must push manually or re-run)
    - Interrupted after VERSION write but before commit — dirty tree, re-running
      --release fails with "dirty tree" (safe state, requires manual cleanup)
    - Interrupted after tag creation but before push — tag exists locally only,
      re-running would fail on "tag already exists" (user must manually push
      or delete local tag)
    - Repo has no merged PRs since last tag — gh release create --generate-notes
      produces empty changelog (acceptable)
    
    Failure modes:
    - git fetch origin timeout → exit 1, "Could not reach origin"
    - git push origin fails (no network) → exit 1, "Push failed"
    - gh CLI not installed → exit 1, "gh CLI required for --release"
    - gh not authenticated → exit 1, gh's own "gh auth login" message
    - VERSION file missing → exit 1, "VERSION file not found"
    - Invalid bump type ("prepatch", "prerelease", etc.) → exit 1, usage message
    - Running --release on a detached HEAD → exit 1, "Not on a branch"
    - Running --release when behind origin → exit 1, "Pull latest changes first"
    - Running --release with uncommitted changes → exit 1, git status shown
    - gh release create returns non-zero → exit 1, preserve gh error message
    - Tag pruning push --delete fails for some tags (already deleted) → warn,
      continue with remaining
    
    Contract invariants:
    - VERSION file content and git tag name MUST match (e.g., VERSION="1.2.2" ↔ tag="v1.2.2")
    - --release MUST NOT run if tree is dirty, on wrong branch, or behind origin
    - The release commit MUST have message "chore: bump version to vX.Y.Z"
    - Tag pruning MUST keep at least 10 tags — never delete all tags
    - --dry-run MUST make zero changes to filesystem, git state, or remote
    - VERSION file write MUST be atomic (temp + rename) to survive interrupts
    - --release exits before pipeline init — same early-exit priority as --version
    
    ────────────────────────────────────────────────────────
    
    12. Panel Split
    
    Wave 1 (parallel — no shared files):
      Task 1 (_bump_version — new function, bottom of utils.py)
      Task 2 (_prune_old_tags — new function, bottom of utils.py)
      Task 4 (--release flag scanning — mechanical, different file dokima)
      Task 8 (HELP_TEXT addition — different section of utils.py)
      Task 9 (CLI_METADATA addition — different section of utils.py)
      All five are independent. Run in parallel with 2-3 coders touching
      different files or different regions of utils.py.
    
    Wave 2 (sequential — depends on Wave 1 completion):
      Task 3 (do_release — needs Task 1 + 2 in utils.py, needs their placement
      to avoid merge conflicts)
      Task 7 (import addition — trivially combined with Task 5)
    
    Wave 3 (depends on Wave 2):
      Task 5 (--release dispatch — needs do_release importable)
      Task 6 (--dry-run — depends on Task 5 structure)
    
    Wave 4 (depends on Wave 3):
      Task 10 (tests — needs do_release available)
    
    Wave 5:
      Task 11 (verification)
    
    Parallel coder count: 2-3 in Wave 1, 1 in Waves 2-5.
    Total waves: 5. Total tasks: 11.
    
    ────────────────────────────────────────────────────────
    
    13. Build & Deploy
    
    - CI: python3 -m pytest tests/test_f024_release.py -v passes
    - Build: python3 -c "compile(open('dokima').read(), 'dokima', 'exec')" passes
    - Full test suite: python3 -m pytest tests/ -q passes (no regressions)
    - No deployment step — dokima is a CLI script
    - No new env vars needed — uses existing GH_TOKEN/GITHUB_TOKEN setup
    - gh CLI version: requires 2.0+ (--generate-notes added in gh 2.0)
    - Release itself is triggered manually: dokima --release patch
    - Post-F024: dogfood by running dokima --release patch to release F024 itself
    
    ────────────────────────────────────────────────────────
    
    14. Risk Register
    
    1. Risk: Atomicity failure — VERSION written but tag not created
       Severity: Medium
       Mitigation: Precondition checks (clean tree, sync) minimize mid-release
       failures. If interrupted, re-running catches dirty tree and asks user to
       resolve. The release commit is the last local change — user can git reset.
       Trigger: Process killed (SIGKILL) after VERSION write but before commit.
    
    2. Risk: gh release create --generate-notes produces poor changelog
       Severity: Low
       Mitigation: GitHub's --generate-notes groups PRs and links authors.
       If insufficient, F024 can be enhanced later with conventional-commit
       PR title scanning. Acceptable for MVP.
       Trigger: PR titles are vague or non-descriptive.
    
    3. Risk: Tag pruning deletes tags someone else is using
       Severity: Low
       Mitigation: keep_count=10 is generous. Only vX.Y.Z tags are pruned —
       non-release tags (e.g., "experiment", "beta") are untouched. Pruning
       runs AFTER the new tag is pushed, so the new release is preserved.
       Trigger: Repo has >10 release tags (no dokima release ever pruned before).
    
    4. Risk: gh release create requires browser-based OAuth for first auth
       Severity: Low
       Mitigation: Same requirement as existing gh() calls in utils.py. Users
       who run the panel already have gh authenticated. --release will surface
       gh's clear auth error if not.
       Trigger: Fresh machine, gh auth login never run.
    
    5. Risk: --release on a project that is NOT dokima
       Severity: Low
       Mitigation: --release works on any git repo with a VERSION file and
       gh CLI access. The VERSION file check fails fast on non-dokima repos.
       Intended behavior — it's a general release tool.
       Trigger: User runs dokima --release in a non-dokima repo expecting
       different behavior. Not a bug, but could confuse.
    
    6. Risk: Race condition — two maintainers release simultaneously
       Severity: Low
       Mitigation: git push fails for the second one (behind origin after
       first push). User gets clear error to pull first. Same as any
       concurrent git push.
       Trigger: Two maintainers run --release within seconds of each other.
    
    ────────────────────────────────────────────────────────
    
    15. Anti-Creep
    
    NOT in scope:
    - CHANGELOG.md file generation — gh release create --generate-notes
      produces the changelog in the GitHub Release body. No local file needed.
    - Conventional commit enforcement — PR titles are not validated. Grouping
      by prefix is a future enhancement, not MVP.
    - Changelog grouping by feat/fix/chore/docs — gh's --generate-notes groups
      by PR label. Manual grouping is P3.
    - Release draft/pre-release/--prerelease flags — standard full releases only.
    - Automatic release on merge to main — release is manually triggered.
    - Version bump via commit message (e.g., "fix: ... [patch]") — explicit
      --release flag only. No commit message parsing.
    - NPM/PyPI/packaging registry publish — GitHub Releases only.
    - Rollback/revert-release command — use git revert + manual re-release.
    - Multiple version files (e.g., pyproject.toml, package.json) — VERSION
      file is the single source of truth.
    - CI integration or GitHub Actions workflow — CLI command only.
    - Release notes templating or custom formatting — gh defaults only.
    - --release on non-dokima repos without VERSION file — errors cleanly,
      no special handling.
    
    ────────────────────────────────────────────────────────
    
    16. Sign-Off Checklist
    
    - [ ] _bump_version() correctly computes patch/minor/major for 1.2.1
    - [ ] _bump_version() rejects invalid bump types
    - [ ] _prune_old_tags() keeps exactly 10 newest vX.Y.Z tags
    - [ ] do_release() with --dry-run prints plan, makes zero changes
    - [ ] do_release() fails on dirty tree with clear error
    - [ ] do_release() fails on non-default branch with clear error
    - [ ] do_release() fails when behind origin with clear error
    - [ ] do_release() bumps VERSION, commits, tags, pushes, creates release
    - [ ] Tag name matches VERSION (v1.2.2 when VERSION=1.2.2)
    - [ ] gh release create vX.Y.Z --generate-notes produces a GitHub Release
    - [ ] --release patch --dry-run exits 0 with correct plan
    - [ ] --release invalid exits 1 with usage message
    - [ ] Tests pass: python3 -m pytest tests/test_f024_release.py -v
    - [ ] Full test suite passes: python3 -m pytest tests/ -q
    - [ ] Build check passes: python3 -c "compile(open('dokima').read(), 'dokima', 'exec')"
    - [ ] New/changed files: utils.py (+~140 LOC), dokima (+~30 LOC),
      tests/test_f024_release.py (+~60 LOC)
    
    ────────────────────────────────────────────────────────
    
    Confidence: High
    Impact: MEDIUM
    
    All sections present. Impact and What Changed sections included.
    All 11 tasks use ### Task N: headers with all five required fields
    (Files, Dependencies, Parallelizable, Description).