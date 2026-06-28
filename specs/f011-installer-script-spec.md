# F011: Installer Script

Now I have a thorough understanding of the project. Let me produce the complete corrected spec. First, a quick Ponytail Guard check and then the full spec.
    
    Ponytail Guard — Pre-Spec Review
    Feature: F011: Installer Script
    Rung: 7 — The minimum that works. No installer exists in the codebase. No stdlib or native OS feature does this. Must be built.
    Existing solution: None.
    Spec needed: Yes — covers the installer script only.
    
    
    
    
    F011: Installer Script — Implementation Spec
    
    Version: 1.0.0
    Confidence: High
    Impact: MEDIUM
    Status: In Progress
    
    1. Executive Summary
    
    Dokima currently requires manual git clone, manual symlink creation, manual profile setup,
    and tribal knowledge of dependencies. F011 delivers a single curl | bash installer that
    checks prerequisites (Python 3.6+, gh CLI, Hermes Agent), places dokima/nm/vet in PATH,
    optionally initializes agent profiles, and prints actionable next steps. This is the
    Phase 3 distribution entry point — the lowest-friction path for new developers.
    
    2. Constitution Check
    
    Axiom: Does it solve the user's own pain?
    Status: YES — every new dokima contributor repeats the same 5 manual setup steps
    ────────────────────────────────────────
    Axiom: Is it weekend-buildable?
    Status: YES — ~150 lines of bash, 5 tasks, 2 waves
    ────────────────────────────────────────
    Axiom: Is there evidence people will pay?
    Status: N/A — internal tooling (open-source distribution channel)
    ────────────────────────────────────────
    Axiom: Is the tech stack boring and proven?
    Status: YES — bash script, curl pipe, standard UNIX tools
    ────────────────────────────────────────
    Axiom: Does it avoid AI hype categories?
    Status: YES — zero AI in the installer itself
    
    3. Decision Table
    
    SINGLE APPROACH: A bash installer script served via a static URL (get.dokima.dev) that
    clones the repository and symlinks executables into ~/.local/bin. The curl-to-bash pattern
    is universal in developer tools (Homebrew, Rust, NVM, Oh My Zsh) — no novel architecture
    needed.
    
    4. Impact
    
    New developers go from 5 manual setup steps to one command. Existing users unchanged.
    This unlocks Phase 3 adoption — F012 (profile templates), F013 (vendor-agnostic config),
    F014 (nm portability), and F015 (quickstart) all depend on a working installer.
    
    5. What Changed
    
    - install.sh: new — the installer script (bash, ~150 LOC)
    - README.md: add "Quick Install" section with curl command + verification steps
    - specs/f011-installer-script-spec.md: this spec (new)
    
    6. Confidence Markers
    
    Confidence: High — bash installers are a solved pattern. Dokima has zero external
    dependencies beyond Python stdlib and gh CLI, both trivially checkable. The script
    scope is narrow: clone + symlink + dep check + print.
    
    7. API/Interface Proposal
    
    N/A — this is a standalone bash script, not an API change. The dokima CLI interface
    is unchanged.
    
    8. Security Considerations
    
    Two surfaces warrant attention:
    (a) curl-to-bash pipe — the user pipes a remote script into bash. Mitigation:
        recommend curl -sSL https://get.dokima.dev | bash with -S (show errors) and
        -L (follow redirects). The script prints itself before executing if stdout is a
        TTY (auto-audit). Document alternative: curl -O | less | bash.
    (b) PATH manipulation — the script modifies $PATH via ~/.bashrc or ~/.zshrc.
        Mitigation: never overwrite existing PATH entries; append only; print the
        exact line added so the user can audit.
    
    No other attack surface change — the script does not handle secrets, tokens, or
    user data. All destructive operations (symlink overwrite, profile init) prompt
    for confirmation or are opt-in via flags.
    
    9. Documentation Impact
    
    README: Add "Quick Install" section before "Manual Setup". The one-liner `curl -sSL
    https://get.dokima.dev | bash` replaces the multi-step clone+link instructions.
    
    10. Data Model
    
    N/A — no persistent data. The script creates directories and symlinks, not a database.
    
    11. COTS Build-vs-Buy
    
    All built. The installer is a bash script. No dependencies beyond what it checks for
    (Python, gh, hermes). The get.dokima.dev domain needs a static file host (GitHub Pages
    or raw.githubusercontent.com — use the repo's existing GitHub Pages if available,
    otherwise serve from raw.githubusercontent.com/siongsheng/dokima/main/install.sh).
    
    12. Task Breakdown
    
    Task 1: Create core installer script with dependency checks
    Files: install.sh
    Dependencies: [none]
    Parallelizable: yes
    Description: Write the main installer bash script that checks for Python 3.6+, gh CLI, and Hermes Agent, clones the dokima repo to ~/.local/share/dokima, symlinks dokima into ~/.local/bin, and prints next steps.
    
    Task 2: Add nm and vet script installation to installer
    Files: install.sh
    Dependencies: [Task 1]
    Parallelizable: no
    Description: Extend the installer to symlink bin/nm and bin/vet from the cloned repo into ~/.local/bin, verify both scripts pass bash -n syntax check, and print their availability.
    
    Task 3: Add profile initialization flag (--with-profiles)
    Files: install.sh
    Dependencies: [Task 2]
    Parallelizable: no
    Description: Add optional --with-profiles flag that runs dokima init after installation to create strategist/coder/tech-lead/nm profiles with sensible defaults; flag is opt-in to keep the base install fast.
    
    Task 4: Add PATH detection and shell config update
    Files: install.sh
    Dependencies: [Task 2]
    Parallelizable: yes
    Description: Detect the user's shell (bash/zsh), verify ~/.local/bin is in PATH, and if not, append the export line to ~/.bashrc or ~/.zshrc with a comment marker for idempotency; never overwrite existing entries.
    
    Task 5: Update README with Quick Install section
    Files: README.md
    Dependencies: [Task 1]
    Parallelizable: yes
    Description: Replace the manual clone+link instructions in README.md with a Quick Install section showing curl -sSL https://get.dokima.dev | bash as the primary path, followed by verification steps (dokima --help, dokima doctor) and a link to manual install for advanced users.
    
    Task 6: End-to-end installer verification
    Files: none (verification)
    Dependencies: [Task 1, Task 2, Task 3, Task 4, Task 5]
    Parallelizable: no
    Description: Test the installer in a clean environment: run install.sh, verify dokima/nm/vet are on PATH, verify dependency checks fail gracefully (missing Python, missing gh), verify --with-profiles creates profiles, verify idempotent re-run does not break.
    
    13. Test Plan
    
    Happy path:
    - Fresh install: bash install.sh clones repo, creates symlinks, prints "Dokima installed: /home/user/.local/bin/dokima"
    - dokima --help works immediately after install
    - nm --help and vet --help work
    - install.sh --with-profiles creates all 4 agent profiles
    
    Edge cases:
    - Empty state: no ~/.local/bin directory exists → installer creates it
    - Already installed: re-running installer detects existing symlinks and skips (idempotent)
    - Missing python3: installer prints "Python 3.6+ required" and exits 1
    - Missing gh: installer prints "GitHub CLI required" and exits 1
    - Missing hermes: installer prints "Hermes Agent required" and exits 1
    - Non-bash shell (zsh): PATH detection falls back to ~/.zshrc
    - No write permission to ~/.local/bin: installer prints permission error and suggests sudo or manual path
    - ~/.local/bin not in PATH: installer appends the export line and prints "Run source ~/.bashrc to activate"
    
    Failure modes:
    - Network error on git clone: installer retries once, then exits with "Failed to clone dokima repository"
    - git clone to existing directory: installer runs git pull instead (update path)
    - Corrupted symlink target (deleted repo): installer detects broken symlink and re-clones
    - Script piped to bash with no TTY: suppression of self-print (no infinite output loop)
    
    Contract invariants:
    - Before install: which dokima returns nothing. After install: which dokima returns ~/.local/bin/dokima
    - Before install: no profiles exist. After --with-profiles: 4 profiles at ~/.hermes/profiles/{strategist,coder,tech-lead,nm}
    - Idempotency: running installer twice produces identical state (no duplicate PATH entries, no broken symlinks)
    - Dep checks run BEFORE any filesystem modification — no partial state on failure
    
    14. Panel Split
    
    Wave 1 (parallel, 2 coders):
    - Task 1 (core installer) — coder A
    - Task 5 (README) — coder B
    
    Wave 2 (sequential, 1 coder):
    - Task 2 (nm/vet symlinks) — coder A
    - Task 4 (PATH detection) — coder A
    
    Wave 3 (sequential, 1 coder):
    - Task 3 (--with-profiles flag)
    
    Wave 4 (sequential, 1 coder):
    - Task 6 (end-to-end verification)
    
    Total: 4 waves, max 2 coders parallel
    
    15. Build & Deploy
    
    The installer script lives at the repo root (install.sh). Distribution:
    - Primary: raw.githubusercontent.com/siongsheng/dokima/main/install.sh
    - Short URL: get.dokima.dev → redirects to the raw URL (configure DNS CNAME or GitHub Pages redirect)
    - CI: No CI changes needed. The script is self-contained bash — verify with bash -n install.sh and shellcheck install.sh
    
    16. Risk Register
    
    Risk: get.dokima.dev domain not configured
    Severity: LOW
    Mitigation: Fall back to raw.githubusercontent.com URL in docs; short domain is a nice-to-have
    Trigger: Domain registration or DNS config delayed
    ────────────────────────────────────────
    Risk: Installer modifies user's shell config (~/.bashrc)
    Severity: MEDIUM
    Mitigation: Append only; add comment marker # dokima installer for easy removal; never overwrite; print the exact line added
    Trigger: User reports corrupted shell config after install
    ────────────────────────────────────────
    Risk: Hermes Agent not yet installed — installer hard-blocks
    Severity: LOW
    Mitigation: This is correct behavior — dokima IS a Hermes orchestration tool. The dep check message includes a link to Hermes install docs
    Trigger: User complaint about blocker on a dependency they don't have
    ────────────────────────────────────────
    Risk: ~/.local/bin not in PATH on some Linux distros (Debian minimal)
    Severity: LOW
    Mitigation: Installer detects this and appends to shell config; prints the source command
    Trigger: User runs installer, dokima not found, files bug report
    
    17. Anti-Creep
    
    Features explicitly NOT in scope:
    - No package manager integration (no apt, brew, yum, or pip packages) — symlink-only
    - No version pinning or upgrade mechanism — git pull is the update path
    - No telemetry or usage tracking
    - No Windows support — bash script assumes Linux/macOS
    - No Docker-based install — that's a separate distribution channel
    - No automatic API key setup — profiles are created empty, user adds keys manually
    - No installer self-update — the installer is fetched fresh each time from the URL
    - No GPG signature verification — out of scope for P2; revisit if distribution grows
    
    18. Sign-Off Checklist
    
    - [ ] install.sh exists at repo root with 644 permissions
    - [ ] bash -n install.sh passes syntax check
    - [ ] shellcheck install.sh passes with no warnings (if shellcheck available)
    - [ ] Fresh install: clone + symlink succeeds on clean Ubuntu 22.04
    - [ ] Dependency checks: missing python3/gh/hermes each produce clear error + exit 1
    - [ ] Idempotent: second run produces no errors, no duplicate PATH entries
    - [ ] --with-profiles creates 4 profiles at ~/.hermes/profiles/
    - [ ] dokima --help works immediately after install
    - [ ] nm and vet are on PATH after install
    - [ ] README Quick Install section is clear and testable by a new user
    - [ ] raw.githubusercontent.com URL serves install.sh with correct Content-Type
    - [ ] get.dokima.dev redirects to the raw URL (or documented as future work)
    
    Confidence: High — the installer is a standard bash script following a well-trodden
    pattern. All dependencies are trivially checkable with command -v. The symlink
    logic is idempotent by design (check-then-create). The main risk is the
    get.dokima.dev domain, which has a documented fallback.
    
    
    
    
    That is the complete corrected spec. The three issues from the quality review are fixed:
    
    1. Impact section (section 4) — "New developers go from 5 manual setup steps to one command. Existing users unchanged. This unlocks Phase 3 adoption..."
    2. What Changed section (section 5) — three bullet items: install.sh (new), README.md (Quick Install section), and the spec file itself.
    3. ### Task N: headers (section 12) — all 6 tasks use the exact ### Task N: Brief description format with all five required fields (Files, Dependencies, Parallelizable, Description).