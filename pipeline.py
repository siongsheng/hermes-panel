"""Dokima pipeline module — all 5 phase functions, fix mode, post-pipeline.

All functions extracted from dokima monolith (F022: Modular Architecture).
Imports from utils, agent, tasks, and roadmap.
"""
import sys, os, json, re, subprocess, time

# Set by conftest._load_panel() — see utils.py _IMPORTING_PANEL docstring (F022b).
_IMPORTING_PANEL = None

from utils import (slugify, git, gh, detect_repo, acquire_lock, _cleanup_lock,
                   update_status_md, _write_log_line, show_help, check_upgrade,
                   _extract_tl_verdict, _extract_tl_blockers, extract_pr_sections,
                   extract_agent_messages, clean_spec_content, verify_spec_quality,
                   generate_codebase_map, extract_file_paths, load_github_token,
                   save_checkpoint, load_checkpoint, delete_checkpoint,
                   validate_checkpoint, _phase_should_skip, _signal_handler,
                   _safe_run, _redact_secrets, halt_and_revert,
                   archive_specs_for_feature, try_auto_merge, _supplement_pr_sections,
                   _detect_default_branch, _set_gh_token, show_help_json,
                   _check_pr_body_quality, _detect_referenced_repo,
                   detect_commands, _hash_output, _detect_truncation,
                   _extract_code_context, _describe_file,
                   handle_status, handle_stop, handle_kill, handle_list_crons,
                   _check_pid, _verify_pid_owner, _get_lock_state,
                   _sanitize_prompt, _validate_project_dir,
                   _parse_status_md, _make_status_entry,
                   _lock_path, _stop_path, _checkpoint_path,
                   HERMES_BIN, DEFAULT_BRANCH, PROJECT_DIR, REPO, PANEL_FEATURE,
                   PANEL_DIR, PROFILES, OUTPUT_LOG, FALLBACK_MODELS, PANEL_PORT,
                   API_KEY, SKIP_AUTOFIX, FORCE_FULL, SKIP_HUMAN_GATE,
                   max_parallel_override, RESUME, MAX_CONTINUOUS,
                   _LOG_FILE_HANDLE, _LOCK_FD, _LOG_FILE, _STDOUT_ORIG,
                   VERSION, HELP_TEXT, TEST_CMD, BUILD_CMD, LINT_CMD,
                   REAL_HOME, _GH_TOKEN_CACHE)
from agent import (call_agent, spawn_agent, _run_agent,
                   _detect_provider_failure, _load_fallback_config)
from tasks import (Task, TaskDAG, TaskLock, WorktreeManager, RoadmapFeature,
                   spawn_coder_in_worktree, merge_worktree_branches,
                   run_parallel_coders)
from roadmap import (RoadmapFeature, parse_roadmap, pick_next_feature,
                     update_roadmap_status, commit_roadmap_update,
                     auto_repair_status, run_add_to_roadmap,
                     run_next_setup, run_init)

def run_post_pipeline(feature, is_next, is_continuous, continue_loop, pr_url, verdict, impact, branch, spec_path, strat_output, mode):
    """Post-pipeline: report, roadmap update, auto-merge. Returns continue_loop."""
    global PANEL_FEATURE, PROJECT_DIR, REPO, OUTPUT_LOG
    print("\n" + "═" * 55)
    print("  PANEL REPORT")
    print("═" * 55)
    print(f"Feature:    {feature}")
    print(f"Project:    {PROJECT_DIR}")
    print(f"Repo:       {REPO}")
    print(f"Branch:     {branch}")
    print(f"PR:         {pr_url or 'N/A'}")
    print(f"Spec:       {spec_path}")
    print(f"Strategist: {len(strat_output)} chars output")
    print(f"Mode:       {mode.upper()}")
    print(f"Verdict:    {verdict}")
    print(f"Full log:   {OUTPUT_LOG}")
    print("✓ Pipeline complete.")

    # Auto-refresh codebase map after pipeline completes
    generate_codebase_map(PROJECT_DIR)

    if is_next:
        roadmap_path = os.path.join(PROJECT_DIR, "specs", "roadmap.md")
        fid_match = re.match(r'(F\d{3})', PANEL_FEATURE) if PANEL_FEATURE else None
        fid = fid_match.group(1) if fid_match else ""
        title = PANEL_FEATURE.split(": ", 1)[1] if fid and ": " in PANEL_FEATURE else PANEL_FEATURE

        if verdict in ("CODER_FAILED", "TIMED_OUT", "UNKNOWN"):
            continue_loop = False
            if fid and os.path.exists(roadmap_path):
                update_roadmap_status(roadmap_path, fid, "pending")
                commit_roadmap_update(roadmap_path, fid, "revert")
                print(f"  {fid} reverted to [ ] Pending — will retry on next run")

        elif is_continuous:
            if pr_url and verdict == "APPROVED":
                continue_loop = False
                if impact in ("LOW", "MEDIUM"):
                    merge_result = try_auto_merge(pr_url)
                    if merge_result == "merged":
                        continue_loop = True
                    elif merge_result == "queued":
                        print("\n── Continuous: auto-merge queued (CI waiting)")
                    elif merge_result == "failed":
                        print("\n── Continuous: auto-merge failed")
                else:
                    print(f"\n── Continuous: risk HIGH — human review required for {fid}")
            elif verdict in ("BLOCKED", "CHANGES_REQUESTED"):
                continue_loop = False
                print(f"  ⚠ PR not approved (verdict: {verdict}) — stopping loop")
            else:
                continue_loop = False

            if continue_loop:
                if fid and os.path.exists(roadmap_path):
                    update_roadmap_status(roadmap_path, fid, "done")
                    status_path = os.path.join(PROJECT_DIR, "specs", "STATUS.md")
                    update_status_md(status_path, fid, title, "done",
                                     pr_url=pr_url or "", source="panel")
                    commit_roadmap_update(roadmap_path, fid, "done")
        else:
            # --next (non-continuous): only mark done if APPROVED
            if verdict == "APPROVED":
                if fid and os.path.exists(roadmap_path):
                    update_roadmap_status(roadmap_path, fid, "done")
                    status_path = os.path.join(PROJECT_DIR, "specs", "STATUS.md")
                    update_status_md(status_path, fid, title, "done",
                                     pr_url=pr_url or "", source="panel")
                    commit_roadmap_update(roadmap_path, fid, "done")
            else:
                print(f"  ⚠ PR {fid} has verdict: {verdict} — not marking as done. Will retry on next run.")

    # Archive spec if PR was merged (only for approved/merged features)
    if verdict == "APPROVED" and pr_url and spec_path:
        archived = archive_specs_for_feature(spec_path, branch, pr_url)
        if archived:
            print(f"  Spec archived: {os.path.basename(spec_path)} → specs/archive/")

    if not continue_loop:
        print("\n── Continuous: stopping loop")
    return continue_loop


def discover_blocked_pr():
    """Detect most recent BLOCKED PR via gh CLI.
    Returns {number, title, headRefName, body} or None."""
    # Allow test patching via dokima.discover_blocked_pr override (F022 modular refactor)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, 'discover_blocked_pr', None)
        if override is not None and override is not discover_blocked_pr:
            return override()

    global REPO
    stdout, _, rc = gh("pr", "list", "--state", "open",
                       "--repo", REPO,
                       "--json", "number,title,body,headRefName,updatedAt",
                       "--jq", "sort_by(.updatedAt) | reverse")
    if rc != 0 or not stdout.strip():
        print("  No open PRs found.", flush=True)
        return None

    import json as _json
    try:
        pr_list = _json.loads(stdout.strip())
    except _json.JSONDecodeError:
        print("  Failed to parse PR list output.", flush=True)
        return None

    prs = []
    for pr_data in pr_list:
        number = pr_data.get("number")
        title = pr_data.get("title", "")
        body = pr_data.get("body", "")
        head = pr_data.get("headRefName")
        updated = pr_data.get("updatedAt", "")

        is_blocked = (
            "[BLOCKED]" in title
            or re.search(r'VERDICT.*?BLOCKED', body, re.IGNORECASE | re.DOTALL)
            or "### Blockers" in body
        )
        if is_blocked:
            prs.append({
                "number": number,
                "title": title,
                "headRefName": head,
                "body": body,
                "updatedAt": updated,
            })

    if not prs:
        print("  No BLOCKED PRs found.", flush=True)
        return None

    if len(prs) > 1:
        print(f"  Found {len(prs)} BLOCKED PRs. Fixing #{prs[0]['number']} (most recent).", flush=True)
    return prs[0]



def extract_blockers_from_pr(pr_body, pr_number=None):
    """Parse PR body for blocker descriptions under ### Blockers section.
    Returns list of blocker strings with ARCHITECTURAL lines excluded.
    Falls back to PR comments if pr_number provided."""
    global REPO
    blockers = []

    # Primary: ### Blockers section
    blockers_section = re.search(r'### Blockers\s*\n(.*?)(?=\n### |\n## |\Z)', pr_body, re.DOTALL)
    if blockers_section:
        section_text = blockers_section.group(1)
        for line in section_text.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                desc = line[2:].strip()
                if desc:
                    blockers.append(desc)

    # Fallback: look for 🔴 BLOCKER or BLOCKER: lines anywhere
    if not blockers:
        for line in pr_body.split("\n"):
            stripped = line.strip()
            if "🔴 BLOCKER" in stripped or stripped.startswith("BLOCKER:"):
                desc = stripped.replace("🔴", "").replace("BLOCKER:", "").replace("BLOCKER", "").strip()
                if desc:
                    blockers.append(desc)

    # Fallback: PR comments if no blockers found and pr_number given
    if not blockers and pr_number:
        try:
            stdout, _, rc = gh("pr", "view", str(pr_number), "--repo", REPO, "--comments",
                               "--json", "body", "--jq", ".body")
            if rc == 0 and stdout.strip():
                # Recurse with comment body as pr_body
                return extract_blockers_from_pr(stdout)
        except Exception:
            print("  ⚠ Failed to fetch PR comments for blocker extraction", flush=True)

    # Filter out ARCHITECTURAL blockers
    filtered = [b for b in blockers if "ARCHITECTURAL" not in b.upper() and "ARCHITECTURE VIOLATION" not in b.upper()]

    return filtered


def run_fix_mode(project_dir, fix_all=False, skip_human_gate=False):
    """Fix-mode orchestrator: detect BLOCKED PR, extract blockers, run fix pipeline."""
    global PROJECT_DIR, REPO, DEFAULT_BRANCH, TEST_CMD, BUILD_CMD
    PROJECT_DIR = project_dir

    print(f"\n{'═'*60}", flush=True)
    print(f"  FIX MODE — {project_dir}", flush=True)
    print(f"{'═'*60}\n", flush=True)

    # Step 1: Discover BLOCKED PR
    pr = discover_blocked_pr()
    if pr is None:
        print("  No BLOCKED PRs found. Run `dokima --next` for new features.", flush=True)
        return

    pr_num = pr["number"]
    pr_title = pr["title"]
    pr_branch = pr["headRefName"]
    pr_body = pr["body"]
    pr_url = f"https://github.com/{REPO}/pull/{pr_num}"
    print(f"  Found PR #{pr_num}: {pr_title}", flush=True)
    print(f"  Branch: {pr_branch}", flush=True)
    print(f"  URL: {pr_url}\n", flush=True)

    # Step 2: Check PR state (EC8: merged, closed)
    import json as _json
    view_stdout, _, view_rc = gh("pr", "view", str(pr_num), "--repo", REPO,
                                 "--json", "state,merged", "--jq", "{state, merged}")
    if view_rc == 0:
        try:
            pr_state = _json.loads(view_stdout)
            if pr_state.get("merged"):
                print(f"  PR #{pr_num} is already merged. Nothing to fix.", flush=True)
                return
            if pr_state.get("state", "").upper() == "CLOSED":
                print(f"  PR #{pr_num} is closed.", flush=True)
                return
        except _json.JSONDecodeError:
            pass  # Proceed anyway

    # Step 2.5: Check most recent TL review verdict — skip if already APPROVED
    reviews_out, _, reviews_rc = gh("pr", "view", str(pr_num), "--repo", REPO,
                                    "--json", "reviews", "--jq", ".reviews")
    if reviews_rc == 0 and reviews_out.strip():
        try:
            reviews = _json.loads(reviews_out)
            if reviews:
                latest_body = (reviews[-1].get("body") or "").upper()
                # Match: "VERDICT: APPROVED", "**APPROVED**", "VERDICT\n\n**APPROVED**"
                if "VERDICT: APPROVED" in latest_body or "**APPROVED**" in latest_body:
                    print(f"  ✅ PR #{pr_num} already APPROVED in most recent review — nothing to fix.", flush=True)
                    print(f"  {pr_url}", flush=True)
                    return
        except (_json.JSONDecodeError, IndexError, KeyError):
            pass  # Proceed — best-effort check

    # Step 3: Extract blockers (EC13: no TL review fallback)
    blockers = extract_blockers_from_pr(pr_body, pr_number=pr_num)
    if not blockers:
        # EC13: check PR comments via fallback
        blockers = extract_blockers_from_pr("", pr_number=pr_num)
    if not blockers:
        print(f"  Cannot extract blockers automatically. Review PR manually:", flush=True)
        print(f"  {pr_url}", flush=True)
        return

    # Step 4: Filter architectural blockers (EC4)
    code_blockers = [b for b in blockers if "ARCHITECTURAL" not in b.upper()
                     and "ARCHITECTURE VIOLATION" not in b.upper()]
    arch_blockers = [b for b in blockers if b not in code_blockers]

    # Step 4b: Filter out non-blocker prose (lines without explicit BLOCKER markers)
    # The TL review may include commentary, verdicts, and release notes under ### Blockers.
    # Only keep lines that look like actual blockers: contain 🔴 BLOCKER, or start with "BLOCKER",
    # or are in table format with a BLOCKER label.
    code_blockers = [b for b in code_blockers
                     if "🔴 BLOCKER" in b
                     or re.search(r'^\|.*BLOCKER.*\|', b)
                     or b.upper().startswith("BLOCKER")
                     or "BLOCKER:" in b
                     or "BLOCKER detail" in b
                     or re.search(r'\*\*BLOCKER\b', b)]

    if arch_blockers:
        print(f"  ⚠ Architectural blockers (skipped — require human decision):", flush=True)
        for b in arch_blockers:
            print(f"     - {b}", flush=True)

    if not code_blockers:
        print("  All blockers are architectural. Human review required.", flush=True)
        return

    # Step 5: PANEL_FIX_ALL / --fix-all (EC16)
    should_fix_items = []
    if fix_all:
        for line in pr_body.split("\n"):
            if "SHOULD FIX" in line.upper():
                should_fix_items.append(line.strip())
        if should_fix_items:
            print(f"  --fix-all: including {len(should_fix_items)} SHOULD FIX items", flush=True)
    else:
        # Check if any SHOULD FIX exist
        sf_count = sum(1 for line in pr_body.split("\n") if "SHOULD FIX" in line.upper())
        if sf_count:
            print(f"  {sf_count} SHOULD FIX items skipped (use --fix-all to include)", flush=True)

    fix_tasks = code_blockers + should_fix_items

    print(f"\n  Fixing {len(code_blockers)} BLOCKER(s)", flush=True)
    for b in code_blockers:
        print(f"     - {b}", flush=True)

    # Step 6: Abbreviated Human Gate (EC9: non-interactive)
    # Skip if PANEL_SKIP_HUMAN_GATE=1 or non-interactive (no TTY)
    skip_gate = skip_human_gate
    is_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    if not skip_gate and is_tty:
        print(f"\n  ── Human Gate ──", flush=True)
        print(f"  [y] Proceed with fix  [e] Edit blocker list  [q] Abort", flush=True)
        choice = input("  Choice: ").strip().lower()
        if choice == "q":
            print("  Fix aborted by user.", flush=True)
            return
        if choice == "e":
            import tempfile
            content = "\n".join(fix_tasks)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(content)
                tmp_path = f.name
            editor = os.environ.get("EDITOR", "vim")
            subprocess.call([editor, tmp_path])
            with open(tmp_path) as f:
                fix_tasks = [l.strip() for l in f if l.strip()]
            os.unlink(tmp_path)
            print(f"  {len(fix_tasks)} task(s) after edit.", flush=True)

    # Determine spec path (EC14: spec file stale/missing)
    spec_path = None
    specs_dir = os.path.join(project_dir, "specs")
    if os.path.isdir(specs_dir):
        for entry in sorted(os.listdir(specs_dir)):
            entry_path = os.path.join(specs_dir, entry)
            if os.path.isdir(entry_path) and entry != "archive":
                # Try spec.md first, then requirements.md (some projects use different naming)
                for name in ("spec.md", "requirements.md", "plan.md"):
                    spec_file = os.path.join(entry_path, name)
                    if os.path.exists(spec_file):
                        spec_path = spec_file
                        break
                if spec_path:
                    break
        # Fallback: check for loose spec files at specs/ root (e.g., f002-home-page-content-spec.md)
        if not spec_path:
            for entry in sorted(os.listdir(specs_dir)):
                if entry.endswith("-spec.md") or entry.endswith("_spec.md"):
                    spec_path = os.path.join(specs_dir, entry)
                    break

    # Step 7: Coder phase (construct fix-only prompt, spawn coder)
    print(f"\n{'─'*60}", flush=True)
    print("  Phase: Coder (fix only)", flush=True)
    print(f"{'─'*60}", flush=True)

    # Ensure we're on the right branch (EC7: branch divergence)
    git("checkout", pr_branch)
    git("pull", "origin", pr_branch)

    # Construct fix-only coder prompt (Task 6)
    fix_prompt = (
        f"FIX MODE: Fix BLOCKED PR #{pr_num}\n\n"
        f"PR Title: {pr_title}\n"
        f"Branch: {pr_branch}\n\n"
        f"### Blockers to Fix\n"
    )
    for i, task in enumerate(fix_tasks, 1):
        fix_prompt += f"{i}. {task}\n"

    # Step 6b: Extract target file paths from blocker text
    target_files = extract_file_paths("\n".join(fix_tasks))
    if target_files:
        fix_prompt += "\n### Target Files (start here — read these first)\n"
        for f in target_files:
            fix_prompt += f"- {f}\n"
        fix_prompt += "\n"

    fix_prompt += (
        "\n### Constraints\n"
        "- FIX MODE: only fix the listed blockers. Do NOT add features.\n"
        "- Do NOT refactor unrelated code. Do NOT change architecture.\n"
        f"- WORKING DIRECTORY: {project_dir}. Do NOT cd to other directories.\n"
        "- TDD: write failing test first, then fix, then confirm tests pass.\n"
        "- Single commit message: `fix: address TL review blockers`\n"
        "- Run BUILD_CMD + TEST_CMD before pushing.\n"
        "- If unable to fix a blocker, report: ⚠ CODER UNABLE TO FIX: <reason>\n"
        "- ⚡ PERFORMANCE: Read the target files above FIRST. Only explore beyond\n"
        "  them if you need context to understand a blocker. Do NOT read the entire\n"
        "  codebase before starting.\n"
    )

    # Use existing coder invocation pattern
    coder_result = run_phase2_coder(
        feature=pr_title,
        spec=fix_prompt,  # Blockers + constraints inlined — coder uses this directly in fix mode
        spec_path=spec_path or "",
        tasks_extract_path="",  # Fix mode: blockers are inlined in spec
        pr_sections=f"## Why\n\nFix blockers on PR #{pr_num}: {pr_title}",
        branch=pr_branch,
        depth="full",
        mode="fix",
        is_next=False
    )
    coder_failed = coder_result.get("coder_failed", True)
    pr_url = coder_result.get("pr_url", pr_url)

    # Step 8: vet phase
    if not coder_failed:
        print(f"\n{'─'*60}", flush=True)
        print("  Phase: vet (build + test)", flush=True)
        print(f"{'─'*60}", flush=True)
        vet_result = run_phase3_vet(
            feature=pr_title,
            branch=pr_branch,
            pr_sections=f"## What Changed\n\nFixed blockers on PR #{pr_num}",
            impact="MEDIUM",
            spec_path=spec_path or ""
        )
        if vet_result.get("coder_failed"):
            coder_failed = True
            print("  ⚠ vet phase failed. Fix incomplete.", flush=True)

    # Step 9: nm phase
    if not coder_failed:
        print(f"\n{'─'*60}", flush=True)
        print("  Phase: nm (adversarial review)", flush=True)
        print(f"{'─'*60}", flush=True)
        nm_result = run_phase4_nm(
            feature=pr_title,
            branch=pr_branch,
            impact="MEDIUM",
            pr_url_in=pr_url
        )
        pr_url = nm_result.get("pr_url", pr_url)

    # Step 10: TL re-review (scoped — verify blocker resolution only)
    # Not a full architecture audit. Just: are these specific blockers resolved?
    # Did the fix break anything?
    if not coder_failed:
        fix_verdict = "UNKNOWN"
        print(f"\n{'─'*60}", flush=True)
        print("  Phase: TL re-review (blocker verification)", flush=True)
        print(f"{'─'*60}", flush=True)

        blocker_list = "\n".join(f"- {b}" for b in blockers)
        tl_result = run_phase5_tech_lead(
            feature=pr_title,
            pr_url=pr_url,
            branch=pr_branch,
            spec_path=spec_path or "original spec not found — review against PR blockers",
            impact="MEDIUM",
            nm_output=nm_result.get("nm_stdout", "") if nm_result else ""
        )
        fix_verdict = tl_result.get("verdict", "UNKNOWN")
        tl_output = tl_result.get("tl_output", "")

        print(f"\n  TL Verdict: {fix_verdict}", flush=True)
        if fix_verdict == "APPROVED":
            print(f"  ✅ All blockers resolved — PR #{pr_num} APPROVED", flush=True)
        elif fix_verdict == "BLOCKED":
            print(f"  ❌ PR #{pr_num} still has unresolved blockers.", flush=True)
        else:
            print(f"  Verdict: {fix_verdict}. Check PR: {pr_url}", flush=True)
        print(f"  {pr_url}", flush=True)
    else:
        print(f"\n{'═'*60}", flush=True)
        print(f"  ❌ Fix failed — coder could not complete.", flush=True)
        print(f"  {pr_url}", flush=True)

    # Auto-refresh codebase map after fix completes
    if not coder_failed:
        generate_codebase_map(project_dir)


def run_phase2_coder(feature, spec, spec_path, tasks_extract_path, pr_sections, branch, depth, mode, is_next):
    """Phase 2: Coder — spawn coder, retry loop, TDD verification. Returns dict."""
    global PROJECT_DIR, REPO, DEFAULT_BRANCH, TEST_CMD, BUILD_CMD, LINT_CMD
    max_retries = 2
    coder_failed = False
    coder_ok = False
    coder_output = ""
    pr_url = None
    verdict = None
    _truncation_retried = False  # F023: truncation retry guard
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"\n── Phase 2 (Retry {attempt}): Coder ──", flush=True)
        else:
            print("\n── Phase 2: Coder (feature branch) ──", flush=True)

        spec_ref = f"{spec_path} for context" if spec_path else "the PR blocker descriptions above"

        # Codebase map hint — coder reads this INSTEAD of exploring the full codebase
        map_path = os.path.join(PROJECT_DIR, "specs", "codebase-map.md")
        map_hint = ""
        if os.path.exists(map_path):
            map_hint = (
                f"\n\n⚡ CODING STARTUP: Read {map_path} FIRST "
                f"(~{os.path.getsize(map_path)} bytes). "
                "It contains the directory tree, tech stack, file descriptions, "
                "and commands. Use it instead of reading every file to understand "
                "the codebase. Only read individual files when you need implementation details."
            )

        if mode == "fix" and spec:
            # Fix mode: spec IS the fix prompt (blockers + constraints inline)
            coder_prompt = (
                spec + "\n\n"
                f"### Branch Setup\n"
                f"FIRST: Switch to the existing branch — do NOT create a new one:\n"
                f"  git checkout {branch} && git pull origin {branch}\n"
                f"All fixes go on this branch. Do NOT create a new branch.\n"
                + map_hint
            )
        else:
            # Extract target file hints from task extract for faster codebase navigation
            file_hints = ""
            if tasks_extract_path and os.path.exists(tasks_extract_path):
                try:
                    with open(tasks_extract_path) as f:
                        task_text = f.read()
                    target_files = extract_file_paths(task_text)
                    if target_files:
                        file_hints = "\n### Target Files (start here — read these first)\n"
                        for f in target_files[:12]:  # cap at 12 to avoid bloat
                            file_hints += f"- {f}\n"
                        file_hints += (
                            "\n⚡ Read the target files first. Then if needed, explore "
                            "related tests and adjacent files. Do NOT read the entire "
                            "codebase before starting.\n"
                        )
                except Exception:
                    pass  # Best-effort — not critical
            # Fallback: if task extract is empty, parse spec file directly for file hints
            if not file_hints and spec_path and os.path.exists(spec_path):
                try:
                    with open(spec_path) as f:
                        spec_text = f.read()
                    target_files = extract_file_paths(spec_text)
                    if target_files:
                        file_hints = "\n### Target Files (start here — read these first)\n"
                        for f in target_files[:12]:
                            file_hints += f"- {f}\n"
                        file_hints += (
                            "\n⚡ Read the target files first. Then if needed, explore "
                            "related tests and adjacent files. Do NOT read the entire "
                            "codebase before starting.\n"
                        )
                except Exception:
                    pass

            # Extract relevant code snippets from spec line references
            code_context = ""
            try:
                spec_text = ""
                task_text = ""
                if spec_path and os.path.exists(spec_path):
                    with open(spec_path) as f:
                        spec_text = f.read()
                if tasks_extract_path and os.path.exists(tasks_extract_path):
                    with open(tasks_extract_path) as f:
                        task_text = f.read()
                if spec_text or task_text:
                    code_context = _extract_code_context(spec_text, task_text, PROJECT_DIR)
            except Exception:
                pass  # Best-effort — not critical

            coder_prompt = f"""Read the task breakdown at {tasks_extract_path} (full spec: {spec_ref}).{map_hint}{file_hints}{code_context}
FIRST: Create and switch to branch '{branch}':
  git checkout -b {branch} 2>/dev/null || git checkout {branch}
  git push -u origin {branch}

Implement ALL tasks from the spec, ONE AT A TIME. Before each: check if another task remains. Do not stop until ALL tasks done — including trivial ones (docs, imports, config).

For each task, TDD with TWO SEPARATE COMMITS:
RED: Write tests → {TEST_CMD} must FAIL → git add <test files only> && git commit -m "test: <summary>"
GREEN: Write minimum code → {TEST_CMD} must PASS → {BUILD_CMD} must succeed → git add <impl files only> && git commit -m "feat: <summary>"
CRITICAL: Two distinct commits, RED before GREEN, different timestamps. NEVER bundle. No task numbers in commit messages.
BEFORE PUSHING: After ALL tasks done, check if the spec requires a README update. If yes, update README.md and commit as \"docs: update README for <feature>\". Then run lint ({LINT_CMD}) + FULL test suite ({TEST_CMD}). If either fails, fix and retry. Only git push when clean.

CRITICAL RULES:
- YOU ARE THE CODER — your job is to IMPLEMENT working code, not to write specs or planning documents. The strategist already wrote the spec. You must produce actual code changes that pass tests.
- ONLY modify files listed in the current task's **Files:** field. DO NOT delete, rename, or touch any other files — even if they look stale, unused, or mergeable.
- DO NOT archive, delete, or move existing specs/ files. Spec lifecycle is managed by the panel.
- DO NOT refactor code beyond what the task requires. No drive-by cleanups, no "while I'm here" improvements.
- If a pre-existing test fails, report it — do NOT fix it unless the task explicitly says to.
Report: both commit hashes, files changed, test results, lint status, branch name.
"""

        if depth == "vet":
            coder_prompt += (
                f'\nAfter the report, create a PR for this branch:\n'
                f'  Read {spec_path} — extract the problem statement (WHY this was built, what it solves).\n'
                f'  Source .env for gh auth: export $(grep -v "^#" .env | xargs) 2>/dev/null\n'
                f'  Write the PR body to /tmp/pr-body.md with sections:\n'
                f'    ## Why — the problem statement from the spec (what problem does this solve?)\n'
                f'    ## What Changed — bullet summary of what was implemented (use this exact heading)\n'
                f'    ## Impact — who/what is affected (from the spec)\n'
                f'    ## Spec — {spec_path}\n'
                f'  gh pr create --repo {REPO} --base {DEFAULT_BRANCH} --head {branch} --title "{feature}" --body-file /tmp/pr-body.md\n'
                f'Report the PR URL.\n'
            )

        # ── Model selection: upgrade to v4-pro for complex features ──
        coder_model = None  # None = use profile default (v4-pro)
        if mode == "fix":
            coder_model = "deepseek-v4-pro"  # Fix mode always benefits from stronger reasoning
        elif tasks_extract_path and os.path.exists(tasks_extract_path):
            try:
                with open(tasks_extract_path) as f:
                    task_count = len(re.findall(r'^### Task \d+:', f.read(), re.MULTILINE))
                if task_count >= 8:
                    coder_model = "deepseek-v4-pro"
                    print(f"  ⚡ {task_count} tasks → upgrading coder to v4-pro", flush=True)
            except Exception:
                pass

        kwargs = {"cwd": PROJECT_DIR}
        if coder_model:
            kwargs["model"] = coder_model
        coder_output = spawn_agent("coder", ["ai-coding-best-practices-lite"], coder_prompt, **kwargs, fallback_model=FALLBACK_MODELS.get("coder"))
        print(f"\n✓ Coder finished ({len(coder_output)} chars)", flush=True)

        # ── Coder clarification gate ──
        coder_clarify = re.findall(r'(?:⚠\s*)?CLARIFICATION\s*NEEDED\s*[：:]\s*(.+)', coder_output)
        if coder_clarify:
            print(f"\n── Coder has {len(coder_clarify)} clarification(s) ──", flush=True)
            for i, q in enumerate(coder_clarify, 1):
                print(f"  {i}. {q.strip()}", flush=True)

            user_answers = []
            try:
                import select
                for i in range(len(coder_clarify)):
                    print(f"\n  A{i+1}: ", end="", flush=True)
                    ready, _, _ = select.select([sys.stdin], [], [], 60.0)
                    if not ready:
                        print("(timed out — using default assumption)", flush=True)
                        break
                    answer = sys.stdin.readline().strip()
                    if not answer:
                        break
                    user_answers.append(answer)
            except (EOFError, KeyboardInterrupt):
                print("\n  ⚠ No input available — proceeding with assumptions", flush=True)

            if user_answers:
                ans_block = "\n".join(
                    f"Clarification: {q}\nUser's answer: {a}"
                    for q, a in zip(coder_clarify, user_answers) if a
                )
                coder_prompt_refine = (
                    f"{coder_prompt}\n\n"
                    f"── USER CLARIFICATIONS (from the user, treat as authoritative) ──\n"
                    f"{ans_block}\n\n"
                    f"Continue from where you left off. Do NOT restart from scratch."
                )
                print(f"\n  ↻ Re-running coder with {len([a for a in user_answers if a])} answer(s)...", flush=True)
                coder_output = spawn_agent("coder", ["ai-coding-best-practices-lite"],
                                           coder_prompt_refine, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("coder"))
                print(f"  ✓ Coder re-run finished ({len(coder_output)} chars)", flush=True)
            else:
                print("  → No answers provided — proceeding with original output", flush=True)

        # F023: Truncation detection — retry once if output appears truncated
        if not _truncation_retried and _detect_truncation(coder_output):
            print("  ⚠ [TRUNCATED] Coder output appears incomplete — retrying once...", flush=True)
            _truncation_retried = True
            coder_prompt_trunc = (
                f"{coder_prompt}\n\n"
                f"[SYSTEM NOTE: Your previous output was truncated. "
                f"Please ensure your response ends with a Report: section "
                f"summarizing what was done.]"
            )
            coder_output = spawn_agent("coder", ["ai-coding-best-practices-lite"],
                                       coder_prompt_trunc, cwd=PROJECT_DIR,
                                       fallback_model=FALLBACK_MODELS.get("coder"))
            print(f"  ✓ Coder truncation retry finished ({len(coder_output)} chars)", flush=True)
        elif _truncation_retried and _detect_truncation(coder_output):
            print("  ⚠ Output still appears truncated after retry — proceeding anyway", flush=True)

        # Coder contingency: check if branch + commits exist despite timeout
        if "[TIMEOUT:" in coder_output:
            branch_out, _, branch_rc = git("rev-parse", "--verify", branch)
            if branch_rc != 0:
                print("  ❌ Coder timed out with no branch — skipping remaining phases")
                coder_failed = True
                break
            print("  ⚠ Coder timed out but branch exists — continuing with partial output")

        # Post-coder gate (active mode only)
        coder_ok = True
        if mode == "active":
            print("\n── Orchestrator: Reviewing Coder Output ──", flush=True)
            has_red = bool(re.search(r'\bRED\b', coder_output)) or bool(re.search(r'^test:', coder_output, re.MULTILINE))
            has_green = bool(re.search(r'\bGREEN\b', coder_output)) or bool(re.search(r'^feat:', coder_output, re.MULTILINE))
            build_ok = "build" in coder_output.lower() and any(w in coder_output.lower() for w in ["pass", "clean", "succeed", "0 error"])
            tests_ok = "pass" in coder_output.lower() and "0 fail" not in coder_output.lower()

            issues = []
            if not has_red: issues.append("No RED commit found")
            if not has_green: issues.append("No GREEN commit found")
            if not build_ok: issues.append("Build status unclear")
            if not tests_ok: issues.append("Test results unclear or failing")

            if issues:
                print(f"  ❌ Issues: {', '.join(issues)}", flush=True)
                if attempt < max_retries:
                    print(f"  ↻ Looping back to coder (attempt {attempt+1}/{max_retries})...", flush=True)
                    continue
                else:
                    print("  ⚠ Max retries reached — proceeding anyway", flush=True)
                    coder_ok = False
            else:
                print("  ✅ RED/GREEN commits, build, tests — all OK", flush=True)
        break  # exit retry loop if we get here

    if not coder_ok and mode == "active":
        print("\n⚠ Coder phase had unresolved issues. Pipeline continues but results may be affected.", flush=True)

    # On failure: revert all changes, report to orchestrator, stop
    if coder_failed:
        halt_and_revert("Coder timed out with no usable output", "PHASE 2 (Coder)", branch)
        pr_url = None
        verdict = "CODER_FAILED"
        print("\n── Phase 3: vet — SKIPPED (coder failed) ──", flush=True)
        print("── Phase 4+5: nm+TL — SKIPPED (coder failed) ──", flush=True)

    # Extract PR URL from coder output when depth=coder (coder creates own PR)
    if not coder_failed:
        pr_url = None
        if depth == "vet":
            pr_urls = re.findall(r'https://github\.com/[\w.-]+/[\w.-]+/pull/\d+', coder_output)
            if pr_urls:
                pr_url = pr_urls[-1]
                print(f"\n  PR (coder): {pr_url}", flush=True)
            if not pr_url:
                stdout, _, rc = gh("pr", "list", "--repo", REPO, "--head", branch,
                                   "--json", "url", "--jq", ".[0].url")
                if rc == 0 and stdout:
                    pr_url = stdout
                    print(f"\n  PR (coder, found): {pr_url}", flush=True)

    return {
        "coder_output": coder_output,
        "pr_url": pr_url,
        "coder_failed": coder_failed,
        "verdict": verdict,
    }


def run_phase3_vet(feature, branch, pr_sections, impact, spec_path):
    """Phase 3: vet — checkout branch, run tests, run build, create PR, merge worktrees.
    Returns dict with: nm_output, pr_url, coder_failed, verdict."""
    global PROJECT_DIR, REPO, DEFAULT_BRANCH, TEST_CMD, BUILD_CMD
    nm_output = ""
    pr_url = None
    coder_failed = False
    verdict = None

    print("\n── Phase 3: vet (coder claimed clean — let's check) ──", flush=True)

    # 1. Verify branch
    print("  ⏳ Checking out branch...", flush=True)
    co_out, co_err, co_rc = git("checkout", branch)
    if co_rc != 0:
        print(f"  ❌ Checkout failed: {co_err}", flush=True)
        halt_and_revert(f"nm: cannot checkout {branch}", "PHASE 3 (vet)", branch)
        coder_failed = True
        verdict = "VET_FAILED"
        return {"nm_output": "Checkout: FAILED", "pr_url": None, "coder_failed": True, "verdict": "VET_FAILED", "test_pass": False, "build_pass": False}

    # Refresh detect_commands after checkout to use feature branch's AGENTS.md
    global TEST_CMD, BUILD_CMD, LINT_CMD
    TEST_CMD, BUILD_CMD, LINT_CMD = detect_commands()

    # ── Verification loop: fail → coder fixes → re-verify ──
    MAX_VERIFY_RETRIES = 2
    test_pass = build_pass = False
    test_output = build_output = ""
    tests_passed = tests_failed = "?"
    prev_output_hash = None  # F023: cycle detection

    for verify_attempt in range(MAX_VERIFY_RETRIES + 1):
        if verify_attempt > 0:
            print(f"\n  ↻ Verification retry {verify_attempt}/{MAX_VERIFY_RETRIES} — spawning coder to fix...", flush=True)

        git("pull", "origin", branch)

        # Run test suite
        print("  ⏳ Running test suite...", flush=True)
        t0 = time.time()
        test_result = _safe_run(TEST_CMD, cwd=PROJECT_DIR, timeout=300)
        test_output = test_result.stdout or ""
        test_pass = test_result.returncode == 0
        pm = re.search(r'(\d+)\s+passed', test_output)
        fm = re.search(r'(\d+)\s+failed', test_output)
        tests_passed = pm.group(1) if pm else "?"
        tests_failed = fm.group(1) if fm else ("0" if test_pass else "?")
        print(f"  {'✅' if test_pass else '❌'} Tests: {tests_passed} passed, {tests_failed} failed ({time.time()-t0:.0f}s)", flush=True)

        # Run build
        print("  ⏳ Running build...", flush=True)
        t0 = time.time()
        build_result = _safe_run(BUILD_CMD, cwd=PROJECT_DIR, timeout=300)
        build_pass = build_result.returncode == 0
        build_output = build_result.stdout or ""
        print(f"  {'✅' if build_pass else '❌'} Build: {'passed' if build_pass else 'FAILED'} ({time.time()-t0:.0f}s)", flush=True)

        # F023: Hash cycle detection — on retry, check if coder fix changed output
        if verify_attempt > 0 and prev_output_hash is not None:
            current_hash = _hash_output(test_output + build_output)
            if current_hash == prev_output_hash:
                print(f"\n  🔴 BLOCKED — Coder fix produced identical output (hash cycle detected)", flush=True)
                print(f"  Coder is re-applying the same fix. Skipping further retries.", flush=True)
                halt_and_revert("nm: coder fix loop detected (hash cycle)", "PHASE 3 (Verification)", branch)
                nm_output = (
                    f"Tests: {tests_passed} passed, {tests_failed} failed\n"
                    f"Build: {'PASS' if build_pass else 'FAIL'}\n"
                    f"PR: N/A\n"
                    f"Risk: {impact}"
                )
                return {"nm_output": nm_output, "pr_url": None, "coder_failed": True,
                        "verdict": "VET_FAILED", "test_pass": test_pass, "build_pass": build_pass}

        if test_pass and build_pass:
            break  # Clean!

        # Show failures
        if not test_pass:
            print("  Test failures (last 15 lines):", flush=True)
            for line in test_output.split("\n")[-15:]:
                if line.strip():
                    print(f"    {line.strip()}", flush=True)
        if not build_pass:
            for line in build_output.split("\n")[-8:]:
                if line.strip():
                    print(f"    {line.strip()}", flush=True)

        if verify_attempt < MAX_VERIFY_RETRIES:
            # F023: Save pre-fix hash for cycle detection
            prev_output_hash = _hash_output(test_output + build_output)

            # Loop back to coder
            fix_prompt = f"""Verification failed on branch '{branch}'. Fix these failures and push.

TEST FAILURES:
{test_output[-2000:] if not test_pass else 'Tests passed.'}

BUILD FAILURES:
{build_output[-1000:] if not build_pass else 'Build passed.'}

Fix the code so both pass. Then: git add <fixed files> && git commit -m "fix: verification failures" && git push origin {branch}
Do NOT change tests unless they are wrong. Do NOT change code outside this scope.
WORKING DIRECTORY: {PROJECT_DIR}. Do NOT cd to other directories.
Report: what was broken, what you fixed, commit hash."""
            spawn_agent("coder", ["ai-coding-best-practices-lite"],
                        fix_prompt, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("coder"))
            print(f"  ✓ Coder fix attempt finished", flush=True)
        else:
            print(f"\n  🔴 BLOCKED — Verification failed after {MAX_VERIFY_RETRIES} retries", flush=True)
            print(f"  Coder pushed code that doesn't pass. Must be fixed manually.", flush=True)
            halt_and_revert("nm: verification failed after max retries", "PHASE 3 (Verification)", branch)
            nm_output = (
                f"Tests: {tests_passed} passed, {tests_failed} failed\n"
                f"Build: {'PASS' if build_pass else 'FAIL'}\n"
                f"PR: N/A\n"
                f"Risk: {impact}"
            )
            return {"nm_output": nm_output, "pr_url": None, "coder_failed": True, "verdict": "VET_FAILED", "test_pass": test_pass, "build_pass": build_pass}

    # 4. Verify coder produced actual code changes (not just spec/docs)
    print("  ⏳ Checking diff for code changes...", flush=True)
    diff_stat, _, _ = git("diff", "--stat", DEFAULT_BRANCH + "..." + branch)
    source_files = re.findall(r'^\s*[\w/.-]+\.(?:py|sh|js|ts|rs|go)\s*\|', diff_stat, re.MULTILINE)
    spec_only = re.findall(r'^\s*specs/[\w/.-]+\.(?:md)\s*\|', diff_stat, re.MULTILINE)
    if not source_files and (spec_only or not diff_stat.strip()):
        print(f"  🔴 BLOCKED — No source code changes detected in diff.", flush=True)
        print(f"  Coder only produced spec/documentation files:", flush=True)
        for m in spec_only:
            print(f"    {m.strip().rstrip('|')}", flush=True)
        print(f"  This is not a valid feature implementation — coder must produce code.", flush=True)
        halt_and_revert("nm: coder produced no source code changes (spec-only)", "PHASE 3 (Verification)", branch)
        return {"nm_output": f"VET_FAILED: no source code changes\n{diff_stat[:500]}", "pr_url": None,
                "coder_failed": True, "verdict": "VET_FAILED", "test_pass": test_pass, "build_pass": build_pass}

    # 4. Create PR (verification passed)
    print("  ⏳ Creating PR...", flush=True)

    pr_sections_final = _supplement_pr_sections(pr_sections, PROJECT_DIR, branch, DEFAULT_BRANCH)
    try:
        tp = int(tests_passed)
    except (ValueError, TypeError):
        tp = 0
    try:
        tf = int(tests_failed)
    except (ValueError, TypeError):
        tf = 0
    total_tests = tp + tf if (tp + tf) > 0 else "?"
    passed_str = f"{tests_passed}/{total_tests}" if total_tests != "?" else f"{tests_passed} passed"
    pr_body = (
        f"{pr_sections_final}\n\n"
        f"## Validation\n"
        f"- {passed_str} tests\n"
        f"- Build passes\n"
    )
    pr_stdout, pr_stderr, pr_rc = gh("pr", "create", "--repo", REPO,
        "--base", DEFAULT_BRANCH, "--head", branch,
        "--title", f"feat: {feature}",
        "--body", pr_body)
    if pr_rc == 0 and pr_stdout.strip():
        parts = pr_stdout.strip().split()
        if parts:
            pr_url = parts[-1]
            print(f"  ✅ PR created: {pr_url}", flush=True)
        else:
            pr_url = None
    else:
        # Try finding existing PR
        stdout, _, rc = gh("pr", "list", "--repo", REPO, "--head", branch,
                           "--json", "url", "--jq", ".[0].url")
        if rc == 0 and stdout:
            pr_url = stdout
            print(f"  Found existing PR: {pr_url}", flush=True)
        else:
            print(f"  ❌ No PR found — create failed: {pr_stderr[:200]}", flush=True)
            pr_url = None

    # 5. Risk: reuse strategist's impact assessment (zero AI tokens)
    risk = impact  # LOW/MEDIUM/HIGH — already determined in orchestrator gate
    print(f"  Risk: {risk} (from strategist impact={impact})", flush=True)

    # Build nm output for report
    nm_output = (
        f"Tests: {tests_passed} passed, {tests_failed} failed\n"
        f"Build: {'PASS' if build_pass else 'FAIL'}\n"
        f"PR: {pr_url or 'N/A'}\n"
        f"Risk: {risk}"
    )
    print(f"✓ Verification passed ({len(nm_output)} chars)", flush=True)

    return {"nm_output": nm_output, "pr_url": pr_url, "coder_failed": coder_failed, "verdict": verdict, "tests_passed": tests_passed, "tests_failed": tests_failed, "test_pass": test_pass, "build_pass": build_pass}


def run_phase4_nm(feature, branch, impact, pr_url_in):
    """Phase 4: nm — adversarial review, parse PR. Returns dict with nm_ok, pr_url, risk."""
    global PROJECT_DIR, REPO
    print("\n── Phase 4: nm (adversarial review) ──", flush=True)
    print("  ⏳ Spawning fresh Hermes session with different model family...", flush=True)
    nm_cmd = os.path.expanduser("~/bin/nm") + " --skip-tests"
    nm_result = _safe_run(nm_cmd, cwd=PROJECT_DIR, timeout=600)
    nm_stdout = nm_result.stdout or ""
    print(f"  ✓ nm finished ({len(nm_stdout)} chars)", flush=True)

    pr_url = pr_url_in

    # Extract PR URL from nm output (only if we don't already have one)
    if not pr_url:
        pr_match = re.search(r'(https://github\.com/[^/]+/[^/]+/pull/\d+)', nm_stdout)
        if pr_match:
            pr_url = pr_match.group(1)
            print(f"  PR: {pr_url}", flush=True)
    if not pr_url:
        stdout, _, rc = gh("pr", "list", "--repo", REPO, "--head", branch,
                           "--json", "url", "--jq", ".[0].url")
        if rc == 0 and stdout:
            pr_url = stdout
            print(f"  Found existing PR: {pr_url}", flush=True)
        else:
            print("  ⚠ No PR found in nm output", flush=True)

    # Extract risk from nm output
    risk_match = re.search(r'RISK:\s*(LOW|MEDIUM|HIGH)', nm_stdout, re.IGNORECASE)
    risk = risk_match.group(1).upper() if risk_match else impact
    print(f"  Risk: {risk}", flush=True)

    # ── nm AUTO-FIX LOOPBACK ──
    # Auto-fix objective nm findings (missing tests, uncaught exceptions, TDD violations).
    # Skips subjective findings (architecture, spec compliance) — human judges those.
    nm_auto_fix_patterns = [
        (r'(?i)missing\s+test', "missing test"),
        (r'(?i)uncaught\s+(panic|exception)', "uncaught exception"),
        (r'(?i)\bunwrap\b.*\b(result|option)\b', "unwrap on Result/Option"),
        (r'(?i)bundled\s+commit', "TDD violation: bundled commit"),
        (r'(?i)TDD\s+violation', "TDD violation"),
        (r'(?i)unhandled\s+error', "unhandled error"),
    ]
    nm_auto_fixable = []
    for pattern, label in nm_auto_fix_patterns:
        if re.search(pattern, nm_stdout):
            nm_auto_fixable.append(label)

    if nm_auto_fixable and not SKIP_AUTOFIX:
        issues_text = "\n".join(f"  - {i}" for i in nm_auto_fixable)
        print(f"\n  ↻ nm found {len(nm_auto_fixable)} auto-fixable issue(s):", flush=True)
        print(issues_text, flush=True)
        print("  Spawning coder to fix...", flush=True)

        fix_prompt = f"""nm adversarial review found these issues. Fix them and push to branch '{branch}'.

ISSUES TO FIX:
{chr(10).join(f'- {i}' for i in nm_auto_fixable)}

RULES:
- Add missing tests (do NOT change existing tests unless they are wrong).
- Fix uncaught exceptions/panics — use proper error handling (Result, ?).
- Fix TDD violations — split bundled commits into separate RED + GREEN.
- Do NOT change architecture, spec design, or anything not listed above.
- WORKING DIRECTORY: {PROJECT_DIR}. Do NOT cd to other directories.
- After fixing: git add <files> && git commit -m "fix: address nm review findings" && git push origin {branch}
- Run {TEST_CMD} before pushing. Fix if it fails.
Report: what you fixed, commit hash."""
        spawn_agent("coder", ["ai-coding-best-practices-lite"],
                    fix_prompt, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("coder"))
        print(f"  ✓ Coder fix finished", flush=True)

        # Re-vet after fix
        print("  ⏳ Re-verifying after auto-fix...", flush=True)
        test_result = _safe_run(TEST_CMD, cwd=PROJECT_DIR, timeout=300)
        build_result = _safe_run(BUILD_CMD, cwd=PROJECT_DIR, timeout=300)
        if test_result.returncode == 0 and build_result.returncode == 0:
            # Re-run nm to refresh PR with fixes
            print("  ✓ Re-verify passed — re-running nm with fixes...", flush=True)
            nm_result = _safe_run(nm_cmd, cwd=PROJECT_DIR, timeout=600)
            nm_stdout = nm_result.stdout or ""
            pr_match = re.search(r'(https://github\.com/[^/]+/[^/]+/pull/\d+)', nm_stdout)
            if pr_match:
                pr_url = pr_match.group(1)
            print(f"  ✓ nm re-run finished ({len(nm_stdout)} chars)", flush=True)
        else:
            print("  ⚠ Re-verify failed after auto-fix — proceeding with original nm output", flush=True)
    elif nm_auto_fixable:
        print("  ⚠ Auto-fix skipped (--skip-autofix)", flush=True)

    return {"nm_ok": True, "pr_url": pr_url, "risk": risk, "nm_stdout": nm_stdout}


def _verify_pr_impact_alignment(pr_body: str, spec_text: str) -> str | None:
    """Verify PR body's Impact section aligns with the spec's Impact.
    Returns None if aligned, or a BLOCKER description string if mismatched.
    Skips verification if spec has no Impact section (spec may not require one)."""
    # Extract spec Impact
    spec_impact_m = re.search(
        r'^##\s*\d*\.?\s*Impact\s*\n+(.+?)(?=\n##\s|\n###\s|\n\*\*Confidence|\Z)',
        spec_text, re.DOTALL | re.IGNORECASE | re.MULTILINE)
    if not spec_impact_m:
        # Try legacy colon format
        spec_impact_m = re.search(
            r'Impact:\s*(.+?)(?=\n\s*\n|\n(?:What Changed|Confidence|### Task|\Z))',
            spec_text, re.DOTALL | re.IGNORECASE)
    if not spec_impact_m:
        return None  # No Impact in spec — skip verification

    spec_impact = spec_impact_m.group(1).strip()
    if not spec_impact:
        return None

    # Extract PR body Impact
    pr_impact_m = re.search(
        r'^##\s*Impact\s*\n+(.+?)(?=\n##\s|\n\*\*|\Z)',
        pr_body, re.DOTALL | re.IGNORECASE | re.MULTILINE)
    if not pr_impact_m:
        return ("🔴 BLOCKER: PR body is missing '## Impact' section. "
                "The spec defines impact; the PR must include it.")

    pr_impact = pr_impact_m.group(1).strip()

    # Check alignment: spec impact keywords should appear in PR body
    # Normalize: lowercase, strip punctuation for comparison
    import string as _string
    spec_words = set(
        w.lower().rstrip(_string.punctuation)
        for w in spec_impact.split() if len(w) > 1)
    pr_words = set(
        w.lower().rstrip(_string.punctuation)
        for w in pr_impact.split() if len(w) > 1)

    # Require at least 30% word overlap (safe threshold for meaningful alignment)
    if spec_words and pr_words:
        overlap = len(spec_words & pr_words) / len(spec_words)
        if overlap >= 0.30:
            return None  # Aligned

    return ("🔴 BLOCKER: PR body Impact section does not align with spec. "
            "Spec Impact must be reflected in the PR body. "
            "Regenerate PR body from spec or update Impact to match.")


def run_phase5_tech_lead(feature, pr_url, branch, spec_path, impact, nm_output=""):
    """Phase 5: Tech Lead — spawn tech lead, handle BLOCKED/CHANGES_REQUESTED verdicts, auto-fix loop.
    Returns dict with: verdict, tl_output, changes_made."""
    global PROJECT_DIR, REPO, DEFAULT_BRANCH, TEST_CMD, BUILD_CMD
    tl_output = ""

    print("\n── Phase 5: Tech Lead (PR review) ──", flush=True)

    # ── Pre-check: verify PR body Impact aligns with spec ──
    if pr_url and spec_path and os.path.exists(spec_path):
        try:
            with open(spec_path) as f:
                spec_text = f.read()
            # Fetch PR body from GitHub
            pr_body, _, rc = gh("pr", "view", pr_url.split("/")[-1], "--repo", REPO,
                               "--json", "body", "--jq", ".body")
            if rc == 0 and pr_body.strip():
                alignment_issue = _verify_pr_impact_alignment(pr_body, spec_text)
                if alignment_issue:
                    print(f"\n  {alignment_issue}", flush=True)
                    # Don't block the pipeline — flag it, TL will re-check
            else:
                print("  ⚠ Could not fetch PR body for impact alignment check", flush=True)
        except Exception as e:
            print(f"  ⚠ Impact alignment check failed: {e}", flush=True)

    tl_prompt = f"""You are the Tech Lead — your job is a THREE-PART adversarial review against the spec at {spec_path}.

FIRST — read the spec: the chosen approach, API/interface proposal, and task breakdown.

THEN — review the pull request{' at ' + pr_url if pr_url else ' for branch ' + branch}:
1. Source .env: export $(grep -v '^#' .env | xargs) 2>/dev/null
2. Fetch PR: gh pr view --repo {REPO} {'--json body,additions,deletions,files,reviews' if pr_url else ''}
3. Check out branch, review diff: git diff {DEFAULT_BRANCH}...{branch}
4. Verify TDD: git log {DEFAULT_BRANCH}..{branch} --oneline — RED before GREEN
5. Read changed files — understand what was built

THREE DIMENSIONS (every finding: severity + dimension + file:line + rule violated):
1. SPEC COMPLIANCE: Approach matches decision table? API/interface matches? ALL tasks done? README updated if spec required it? Scope creep?
2. ARCHITECTURAL IMPACT: New deps/coupling? Breaking changes? DB schema impact? Deployment impact?
3. CODE QUALITY + DOCUMENTATION: TDD, correctness, security, error handling, performance. Also check documentation freshness — if README, docs/, or specs/perf-tracking.md describe old behavior that changed, flag as SHOULD FIX.

NM FINDINGS (supplementary): The nm pipeline stage already reviewed this diff with a different model family. If nm findings below are relevant and not already addressed, include them in your review:
{nm_output[:2000] if nm_output else '(no nm output available)'}

SEVERITY: BLOCKER (spec violation, architecture violation, TDD violation, missing guards, uncaught exceptions, security, missing tests, missing README update when spec required it) | SHOULD FIX (conventions, naming, AGENTS.md, redundant code, stale docs referencing old behavior) | NIT (formatting, comments, style)

FINAL: export $(grep -v '^#' .env | xargs) 2>/dev/null && gh pr review --repo {REPO} PR_NUMBER --comment --body "Tech Lead Review: <verdict>. <summary>"
Do NOT --approve (self-approval blocked). User merges manually.

CRITICAL — your final output MUST end with this exact format (these lines are parsed):
VERDICT: APPROVED
RISK: LOW
RELEASE: NO
(Use APPROVED / BLOCKED / CHANGES REQUESTED.
 Risk: LOW = isolated, well-tested, no DB/API surface. MEDIUM = DB/API/UI, moderate blast radius. HIGH = auth/payments/security, wide blast radius → human review required.
 Use YES + semver or NO for RELEASE.)
RELEASE determination: Check if this feature introduces new functionality, API changes, or breaking changes visible to users. YES → recommend semver level (patch/minor/major). NO → no release needed."""
    tl_output = spawn_agent("tech-lead", ["adversarial-review-lite", "ponytail-guard"],
                            tl_prompt, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("tech-lead"))
    print(f"\n✓ Tech Lead finished ({len(tl_output)} chars)", flush=True)

    # ── TL AUTO-FIX LOOPBACK ──
    # Auto-fix objective TL BLOCKERs (missing tests, TDD violations, uncaught exceptions).
    # Skips subjective BLOCKERs (spec violation, architecture, security) — human judges.
    if not SKIP_AUTOFIX:
        tl_auto_fix_keywords = {
            "tdd violation": "TDD violation",
            "missing test": "missing test",
            "uncaught exception": "uncaught exception",
            "uncaught panic": "uncaught panic",
            "missing guard": "missing guard (null/error check)",
            "missing readme": "missing README update",
        }
        tl_auto_fixable = []
        for line in tl_output.split("\n"):
            upper = line.upper()
            if "BLOCKER" not in upper:
                continue
            # Skip subjective blockers
            if any(kw in upper for kw in ("SPEC VIOLATION", "ARCHITECTURE VIOLATION", "SECURITY", "ARCHITECTURAL")):
                continue
            for kw, label in tl_auto_fix_keywords.items():
                if kw in line.lower():
                    tl_auto_fixable.append(label)
                    break

        if tl_auto_fixable:
            issues_text = "\n".join(f"  - {i}" for i in tl_auto_fixable)
            print(f"\n  ↻ TL found {len(tl_auto_fixable)} auto-fixable BLOCKER(s):", flush=True)
            print(issues_text, flush=True)
            print("  Spawning coder to fix...", flush=True)

            fix_prompt = f"""Tech Lead review found these BLOCKER issues. Fix them and push to branch '{branch}'.

ISSUES TO FIX:
{chr(10).join(f'- {i}' for i in tl_auto_fixable)}

RULES:
- Add missing tests (do NOT change existing tests unless they are wrong).
- Fix uncaught exceptions/panics — use proper error handling (Result, ?).
- Fix TDD violations — split bundled commits into separate RED + GREEN.
- Add missing guard clauses for null/error conditions.
- Do NOT change architecture, spec design, security posture, or anything not in the list above.
- WORKING DIRECTORY: {PROJECT_DIR}. Do NOT cd to other directories.
- After fixing: git add <files> && git commit -m "fix: address TL review blockers" && git push origin {branch}
- Run {TEST_CMD} + {BUILD_CMD} before pushing. Fix if either fails.
Report: what you fixed, commit hash."""
            spawn_agent("coder", ["ai-coding-best-practices-lite"],
                        fix_prompt, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("coder"))
            print(f"  ✓ Coder fix finished", flush=True)

            # Re-vet + re-TL
            print("  ⏳ Re-verifying after auto-fix...", flush=True)
            test_result = _safe_run(TEST_CMD, cwd=PROJECT_DIR, timeout=300)
            build_result = _safe_run(BUILD_CMD, cwd=PROJECT_DIR, timeout=300)
            if test_result.returncode == 0 and build_result.returncode == 0:
                print("  ✓ Re-verify passed — re-running Tech Lead with fixes...", flush=True)
                tl_output = spawn_agent("tech-lead", ["adversarial-review-lite", "ponytail-guard"],
                                        tl_prompt, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("tech-lead"))
                print(f"  ✓ Tech Lead re-run finished ({len(tl_output)} chars)", flush=True)
            else:
                print("  ⚠ Re-verify failed after auto-fix — proceeding with original TL output", flush=True)
    elif any("BLOCKER" in l.upper() for l in tl_output.split("\n")):
        print("  ⚠ Auto-fix skipped (--skip-autofix) — TL blockers will remain in review", flush=True)

    # Tech Lead contingency: use partial output for verdict if timed out
    if "[TIMEOUT:" in tl_output:
        print("  ⚠ Tech Lead timed out — using partial output for verdict and issues")

    # ── POST-TECH-LEAD GATE ──
    verdict = _extract_tl_verdict(tl_output)

    # ── Inject TL review into PR body ──
    if pr_url and verdict not in ("SKIPPED", "UNKNOWN", "TIMED_OUT"):
        pr_num = pr_url.split("/")[-1]
        # Extract blocker lines using the smart extractor
        blocker_lines = _extract_tl_blockers(tl_output)
        # Extract risk from TL output or use strategist's impact
        risk_match = re.search(r'RISK:\s*(LOW|MEDIUM|HIGH)', tl_output, re.IGNORECASE)
        tl_risk = risk_match.group(1).upper() if risk_match else impact
        # Extract impact from TL output
        impact_match = re.search(r'IMPACT:\s*(.+?)(?=\n(?:VERDICT|RISK|RELEASE|$))', tl_output, re.DOTALL | re.IGNORECASE)
        tl_impact = impact_match.group(1).strip() if impact_match else ""
        # Fetch existing PR body, strip old Review sections
        existing_body, _, _ = gh("pr", "view", pr_num, "--repo", REPO,
                                 "--json", "body", "--jq", ".body")
        existing_body = re.sub(
            r'\n## Review\n\n.*?(?=\n## |\Z)',
            '', existing_body or '', flags=re.DOTALL
        )
        review_section = f"\n\n## Review\n\n**Verdict:** {verdict}  \n**Risk:** {tl_risk}\n"
        if tl_impact:
            review_section += f"\n**Impact:** {tl_impact}\n"
        if blocker_lines:
            review_section += "\n### Blockers\n\n"
            for bl in blocker_lines:
                # Parse "1. Title — detail" where title may contain backticks
                match = re.match(r'(\d+)\.\s*(.+?)\s+[—–-]\s+(.+)$', bl)
                if match:
                    num, title, detail = match.group(1), match.group(2).strip(), match.group(3)
                    review_section += f"{num}. **{title}** — {detail}\n"
                else:
                    # No em-dash separator — just title
                    match2 = re.match(r'(\d+)\.\s*(.+)$', bl)
                    if match2:
                        review_section += f"{match2.group(1)}. **{match2.group(2).strip()}**\n"
                    else:
                        review_section += f"- {bl}\n"
        new_body = (existing_body or "") + review_section
        print(f"  ⏳ Updating PR body with verdict ({verdict}, {len(blocker_lines)} blockers)...", flush=True)
        _, edit_err, edit_rc = gh("api",
            f"repos/{REPO}/pulls/{pr_num}",
            "--method", "PATCH",
            "-f", f"body={new_body}")
        if edit_rc == 0:
            print(f"  ✅ PR updated with Review section", flush=True)
        else:
            print(f"  ⚠ Could not update PR body (gh api rc={edit_rc}): {edit_err[:200]}", flush=True)

    # Create GitHub Issues for SHOULD FIX items
    should_fix_lines = [l for l in tl_output.split("\n") if "SHOULD FIX" in l.upper() and "—" in l]
    if should_fix_lines:
        print(f"\n── Creating GitHub Issues for {len(should_fix_lines)} SHOULD FIX items ──", flush=True)
        for line in should_fix_lines[:5]:
            parts = line.split("—", 1)
            desc = parts[1].strip() if len(parts) > 1 else line.strip()
            title = f"SHOULD FIX: {desc[:80]}"
            body = (
                f"## Tech Lead Review Finding\n\n"
                f"**Feature:** {feature}\n"
                f"**Branch:** {branch}\n"
                f"**PR:** {pr_url or 'N/A'}\n"
                f"**Verdict:** {verdict}\n"
                f"**Spec:** {spec_path}\n\n"
                f"### Finding\n{line.strip()}\n\n"
                f"### Context\nFound during adversarial review of `{branch}` against the spec. "
                f"See the PR for full review details and other findings."
            )
            stdout, stderr, rc = gh("issue", "create", "--repo", REPO,
                                    "--title", title, "--body", body)
            if rc == 0:
                print(f"  Created: {stdout}", flush=True)
            else:
                print(f"  Failed: {stderr}", flush=True)

    return {"verdict": verdict, "tl_output": tl_output}


def run_phase1_strategist(feature, user_answers_prefill):
    """Phase 1: Strategist — spawn strategist, parse output, save spec, handle interview mode, create ADR.
    Returns dict with: spec, spec_path, pr_sections, tasks, tasks_extract_path, depth, branch, confidence, impact, mode, strat_output."""
    global PROJECT_DIR, PROFILES, REAL_HOME
    print("\n── Phase 1: Strategist (full session) ──", flush=True)
    _strat_reasoning = os.environ.get("PANEL_REASONING", "")
    _strat_config = os.path.join(PROFILES, "strategist", "config.yaml")
    _orig_reasoning = None
    if _strat_reasoning and os.path.exists(_strat_config):
        with open(_strat_config) as f:
            _orig_yaml = f.read()
        _orig_m = re.search(r'^(\s+reasoning_effort:\s*)(\S+)', _orig_yaml, re.MULTILINE)
        if _orig_m:
            _orig_reasoning = _orig_m.group(2)
            _new_yaml = _orig_yaml.replace(
                f"{_orig_m.group(1)}{_orig_m.group(2)}",
                f"{_orig_m.group(1)}{_strat_reasoning}")
            with open(_strat_config, "w") as f:
                f.write(_new_yaml)
            print(f"  PANEL_REASONING={_strat_reasoning} (override, was {_orig_reasoning})", flush=True)

    # Check for existing spec at standard path BEFORE spawning strategist.
    # If a human or prior pipeline already wrote a spec, it is the AUTHORITATIVE SOURCE —
    # the strategist must validate and refine it, not replace it.
    _spec_slug = slugify(feature)
    _standard_spec = os.path.join(PROJECT_DIR, "specs", f"{_spec_slug}-spec.md")
    _subdir_spec = os.path.join(PROJECT_DIR, "specs", _spec_slug, "plan.md")
    _refine_note = ""
    # Check both conventions: specs/<slug>-spec.md (panel-generated) and specs/<slug>/plan.md (human-written)
    _found_spec = None
    if os.path.exists(_standard_spec):
        _found_spec = _standard_spec
    elif os.path.exists(_subdir_spec):
        _found_spec = _subdir_spec
    if _found_spec:
        _spec_size = os.path.getsize(_found_spec)
        _refine_note = f"""CRITICAL: A spec already exists at {_found_spec} ({_spec_size} bytes).
This spec was written by a human or a prior pipeline run. IT IS THE AUTHORITATIVE SOURCE.

Your job is to VALIDATE, ENHANCE, and FORMAT — NOT rewrite from scratch:
1. Read the existing spec FIRST — it defines the feature scope, approach, and task breakdown.
2. Verify it against the current codebase state — has anything changed? Are the assumptions still valid?
3. Fill gaps — missing sections, unclear task descriptions, missing dependency declarations.
4. Convert tasks to DAG format (### Task N: headers) if they aren't already.
5. Keep ALL sections from the original spec UNLESS they are factually wrong vs the codebase.
   If a section is correct, preserve it verbatim.
DO NOT: redesign the feature, change scope, add unmentioned features, or rewrite from scratch.
The existing spec is TRUTH unless it contradicts the current codebase state.

"""
    # PANEL_EXISTING_SPEC override (internal, from --fix mode)
    _existing_spec = os.environ.get("PANEL_EXISTING_SPEC", "")
    if _existing_spec and os.path.exists(_existing_spec) and not _refine_note:
        _refine_note = f"""NOTE: A spec already exists at {_existing_spec}. This feature was previously designed.
        Read the existing spec FIRST. REFINE — do not start from scratch. Identify gaps vs the current
        codebase state, address them, improve the design. Keep what's good. The existing spec is
        authoritative context — you are enhancing it, not replacing it.

        """

    # Detect if this project documents an external system (e.g. docs site for the panel itself)
    _ref_context = _detect_referenced_repo(os.path.join(PROJECT_DIR, "AGENTS.md"))
    if _ref_context:
        print(f"  Detected external reference — injecting {len(_ref_context)} chars of context", flush=True)

    strat_prompt = f"""You are the Strategist for a software project at {PROJECT_DIR}.
{_ref_context}
    {_refine_note}FIRST — understand the project's PURPOSE, ARCHITECTURE, and RECENT HISTORY:
    1. Read specs/mission.md, specs/tech-stack.md, specs/roadmap.md, specs/conventions.md (if missing, work from AGENTS.md).
    2. Read AGENTS.md at {PROJECT_DIR}/AGENTS.md — exact commands, non-standard tooling, permission boundaries.
    3. If .specify/ exists, read .specify/memory/constitution.md and .specify/specs/baseline/spec.md. Otherwise skip.
    3b. If {PROJECT_DIR}/docs/adr/ exists, run `adr list` and read the most recent ADRs — they capture past architectural decisions. Respect them.
    4. Run `git log --oneline -20` and `git log origin/{DEFAULT_BRANCH}..HEAD` — recent work and unmerged changes.
    5. Search for relevant code: rg on patterns related to "{feature}" — find existing abstractions and conventions.
    6. Read the key files — understand the architecture before designing.

    SECOND — interview the user when confidence is NOT High:
    - Inventory assumptions. If \u22653 unverified OR confidence is Low → INTERVIEW MODE: output ONLY clarification questions (no spec).
    - Output exactly: DECISION: INTERVIEW MODE, then CLARIFICATION: <question>, Assumption: <...>, Impact if wrong: <...>
    - Medium confidence with \u22642 assumptions: include CLARIFICATION: markers inline. High confidence: skip.
    - Max 3-4 critical clarifications. Skip trivial ones.

    """

    if user_answers_prefill:
        strat_prompt += f"""USER CLARIFICATIONS (from the user, treat as authoritative):
    {user_answers_prefill}

    """

    strat_prompt += """THEN — design the feature. BREVITY IS CORRECTNESS.

    ╔═════════════════════════════════════════════════════════════╗
    ║ TASK FORMAT — THIS IS THE ONLY THING THE PANEL PARSES.    ║
    ║ If your output does not contain ### Task N: headers, the  ║
    ║ feature runs SEQUENTIALLY (3x slower), no model upgrade   ║
    ║ fires, no target file hints, and you will be RE-PROMPTED. ║
    ║ Do NOT use wave groupings, bullet points, numbered lists, ║
    ║ or bold text for tasks. ONLY this format:                 ║
    ║                                                           ║
    ║ ### Task N: Brief description                             ║
    ║ **Files:** path/to/file1, path/to/file2                   ║
    ║ **Dependencies:** [none] or [Task N]                      ║
    ║ **Parallelizable:** yes or no                             ║
    ║ **Description:** One sentence.                            ║
    ║                                                           ║
    ║ ALL FIVE FIELDS REQUIRED. The panel regex is              ║
    ║ ^### Task \\d+: — ONLY that pattern is parsed. Not       ║
    ║ "Wave 1: (T1)", not "- [ ] Task 1", not **Task 1**.       ║
    ║ Before submitting, search your output for ### Task.        ║
    ╚═════════════════════════════════════════════════════════════╝

    1. DECISION TABLE: For novel/complex features, compare ≥2 approaches. For features with an obvious pattern match (visual change, config, docs, standard CRUD), use "SINGLE APPROACH: <one sentence>" — skip the comparison table.

    2. ## N. Impact — a section header (e.g., ## 3. Impact) with a paragraph describing what changes for users/developers. Use a real section header, not "Impact: MEDIUM" inline metadata. Example:
       ## 3. Impact

       Maintainers can release with one command. Auto-generated changelogs grouped by feat/fix/docs. No more manual tagging.

    3. ## N. What Changed — a section header with a bullet list of key files and what they do. Max 6 bullets. Example:
       ## 4. What Changed

       - `dokima`: Add --release flag and dispatch
       - `utils.py`: Add bump_version(), generate_changelog(), do_release()

    4. CONFIDENCE + IMPACT markers (REQUIRED — inline metadata, separate from sections above):
       **Confidence:** (High)/(Medium)/(Low)
       **Impact:** (LOW)/(MEDIUM)/(HIGH)

    5. API/INTERFACE PROPOSAL: Only if this feature adds/changes APIs, routes, or data structures. For visual-only, docs-only, config-only, or CSS-only changes, write EXACTLY: "N/A — visual/docs/config change only." No further text.

    6. SECURITY CONSIDERATIONS: Only if this feature touches auth, permissions, data exposure, injection surfaces, or rate limiting. For visual/docs/config/CSS changes, write EXACTLY: "N/A — no attack surface change." No further text.

    7. DOCUMENTATION IMPACT: "README: No change needed." or a single sentence stating what section changes.

    8. TASK BREAKDOWN — DAG FORMAT MANDATORY:
    ### Task N: Brief description
    **Files:** path/to/file1, path/to/file2
    **Dependencies:** [none] or [Task N]
    **Parallelizable:** yes or no
    **Description:** One sentence.

    BREVITY TARGETS: High confidence → <4,000 chars total. Medium → <6,000 chars. Low → no hard limit. Shorter specs run faster pipelines. Every section you can N/A moves you closer to the target. Count your output before submitting.

    RULES: Every task MUST start with "### Task N:" and have ALL five fields. Non-DAG formats are DISCARDED → feature runs SEQUENTIALLY (3× slower).

    CODER CONSTRAINTS:
    - Each task MUST be completable in 5-10 min by a coder agent (100-200 lines).
    - Break large features into MORE granular tasks, not fewer big ones.
    - 8 small tasks > 4 big tasks. The panel runs coders in parallel.
    - Assign different **Files:** per task so coders run concurrently. Same-file tasks are sequential (3× slower).
    - If a feature genuinely needs 8+ tasks, that's fine — just keep each one small.

    CRITICAL: You are a DESIGNER, not a coder. Write NO implementation code. Describe WHAT and WHY — the coder decides HOW.

    OUTPUT FORMAT: Output the complete spec in your message. Do NOT use write_file to save it to a file — the panel extracts your message as the spec. Do NOT summarize — every section must be present in full."""

    strat_output = spawn_agent("strategist", ["spec-strategist-lite", "ponytail-guard"], strat_prompt, timeout=300, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("strategist"))
    print(f"\n✓ Strategist finished ({len(strat_output)} chars)", flush=True)

    # ── DAG format enforcement ──
    orig_strat_output = strat_output  # save in case re-prompt produces garbage
    # Check DAG on extracted agent messages, not raw output (which has <thinking> blocks)
    agent_text_for_dag = extract_agent_messages(strat_output)
    if not re.search(r'^\s*(?:###\s*)?Task\s*\d+:', agent_text_for_dag, re.MULTILINE):
        print("  ⚠ No DAG-format tasks (### Task N:) found — re-prompting strategist...", flush=True)
        # Truncate first output to keep re-prompt tokens reasonable (first 4K chars)
        truncated = strat_output[:4096] + ("...[truncated]" if len(strat_output) > 4096 else "")
        dag_correction = (
            f"── FORMAT CORRECTION REQUIRED ──\n"
            f"Feature: {feature}\n"
            f"Project: {PROJECT_DIR}\n\n"
            f"Your spec is below. Keep ALL sections (Decision Table, Impact, What Changed,\n"
            f"Confidence, Impact markers, API/Interface, Security, Documentation) EXACTLY\n"
            f"as they are. Rewrite ONLY the task breakdown section as ### Task N: headers.\n\n"
            f"Format:\n"
            f"### Task N: Brief description\n"
            f"**Files:** path/to/file1, path/to/file2\n"
            f"**Dependencies:** [none] or [Task N]\n"
            f"**Parallelizable:** yes or no\n"
            f"**Description:** What this task accomplishes.\n\n"
            f"CRITICAL: Return the COMPLETE spec in your response — every section, every\n"
            f"field, every line. Do NOT output a summary of changes. Do NOT say 'Done'\n"
            f"or 'Format fixes applied'. Output the ENTIRE corrected spec as your message.\n"
            f"Do NOT use write_file — the panel reads your message as the spec.\n\n"
            f"── YOUR EXISTING SPEC (preserve this, only fix task headers) ──\n\n"
            f"{truncated}"
        )
        strat_output = spawn_agent("strategist", ["spec-strategist-lite", "ponytail-guard"],
                                   dag_correction, timeout=600, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("strategist"))
        print(f"  ✓ Strategist re-run finished ({len(strat_output)} chars)", flush=True)
        # Verify re-prompt output
        agent_text_recheck = extract_agent_messages(strat_output)
        if not re.search(r'^\s*(?:###\s*)?Task\s*\d+:', agent_text_recheck, re.MULTILINE):
            print("  ⚠ Re-prompt also lacks DAG format — proceeding with degraded (sequential) mode", flush=True)

    if _orig_reasoning and os.path.exists(_strat_config):
        with open(_strat_config, "w") as f:
            f.write(_orig_yaml)
        print(f"  Restored strategist reasoning_effort \u2192 {_orig_reasoning}", flush=True)

    # ── Interview gate ──
    agent_text_pre = extract_agent_messages(strat_output)
    interview_mode = "DECISION: INTERVIEW MODE" in agent_text_pre
    has_clarifications = bool(re.search(r'^\s*CLARIFICATION\s+\d+:', agent_text_pre, re.MULTILINE))
    # Guard: if output has task headers, it's a full spec, not an interview request.
    # F003 and similar features that TEST interview mode include the string
    # "DECISION: INTERVIEW MODE" in their task descriptions/prose → false positive.
    has_tasks = bool(re.search(r'^\s*(?:###\s*)?Task\s*\d+:', agent_text_pre, re.MULTILINE))
    if has_tasks and interview_mode:
        interview_mode = False  # Spec prose, not a real interview request
    if (interview_mode or has_clarifications) and not user_answers_prefill:
        if not sys.stdin.isatty():
            clarification_blocks = []
            pattern = r'(^\s*CLARIFICATION\s+\d+:.*?)(?=\n\s*CLARIFICATION\s+\d+|\n\s*\n\s*(?:DECISION|IMPACT|CONFIDENCE|### Task|SPEC COMPLETE|Ready for)|\Z)'
            for match in re.finditer(pattern, agent_text_pre, re.DOTALL | re.MULTILINE):
                block = match.group(1).strip()
                if len(block) > 10:
                    clarification_blocks.append(block)
            if not clarification_blocks:
                for line in agent_text_pre.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("CLARIFICATION"):
                        clarification_blocks.append(stripped)
            interview_state = {
                "feature": feature,
                "project_dir": PROJECT_DIR,
                "interview_mode": interview_mode,
                "questions": clarification_blocks,
                "prompt": strat_prompt
            }
            interview_path = "/tmp/dokima-interview.json"
            with open(interview_path, "w") as f:
                json.dump(interview_state, f)
            os.chmod(interview_path, 0o600)
            print(f"\n{'═' * 55}", flush=True)
            print(f"  STRATEGIST NEEDS CLARIFICATION", flush=True)
            print(f"{'═' * 55}", flush=True)
            if interview_mode:
                print(f"\n  ⚠  Interview mode \u2014 spec cannot be written without answers.", flush=True)
            print(f"\n  Questions ({len(clarification_blocks)}):", flush=True)
            for i, q in enumerate(clarification_blocks, 1):
                lines = q.split("\n")
                header = lines[0].replace("CLARIFICATION", "").lstrip(" 0123456789: ").strip()
                print(f"\n  \u250c\u2500 Q{i}: {header}", flush=True)
                for ctx in lines[1:]:
                    if ctx.strip():
                        print(f"  \u2502  {ctx.strip()}", flush=True)
                print(f"  \u2514{'─' * 40}", flush=True)
            print(f"\n  State saved: {interview_path}", flush=True)
            print(f"  Re-run with: dokima --answers {interview_path}", flush=True)
            print(f"{'═' * 55}", flush=True)
            sys.exit(2)

        # Interactive mode
        print("\n" + "=" * 60, flush=True)
        print("  STRATEGIST INTERVIEW \u2014 Clarifications Needed", flush=True)
        print("=" * 60, flush=True)
        if interview_mode:
            print("\n\u26a0\ufe0f  The strategist flagged this as INTERVIEW MODE \u2014 your requirements need refining before a spec can be written.", flush=True)
        else:
            print("\nThe strategist identified ambiguities in your feature request.", flush=True)
        print("Answer these questions to refine the spec. Blank line = accept assumptions.\n", flush=True)
        clarification_lines = []
        for line in strat_output.split("\n"):
            stripped = line.strip()
            if stripped.startswith("CLARIFICATION"):
                clarification_lines.append(stripped)
        for i, c in enumerate(clarification_lines, 1):
            print(f"\n  Q{i}: {c}", flush=True)
        print("\n" + "-" * 60, flush=True)
        print("  Type your answers (one per line). Empty input = accept all assumptions.", flush=True)
        print("-" * 60, flush=True)
        user_answers = []
        try:
            import select
            for i in range(len(clarification_lines)):
                print(f"\n  A{i+1}: ", end="", flush=True)
                ready, _, _ = select.select([sys.stdin], [], [], 60.0)
                if not ready:
                    print("(timed out \u2014 accepting assumptions)", flush=True)
                    break
                answer = sys.stdin.readline().strip()
                if not answer:
                    break
                user_answers.append(answer)
        except (EOFError, KeyboardInterrupt):
            print("\n  \u26a0 No input available \u2014 proceeding with assumptions", flush=True)
        if user_answers:
            print(f"\n  \u2713 Got {len(user_answers)} answer(s). Re-running strategist with your clarifications...", flush=True)
            clarif_context = "\n".join(
                f"Clarification: {c}\nUser's answer: {a}"
                for c, a in zip(clarification_lines, user_answers)
            )
            strat_output = spawn_agent("strategist", ["spec-strategist-lite", "ponytail-guard"],
                                       strat_prompt + f"\n\nUSER CLARIFICATIONS:\n{clarif_context}\n\nTHEN \u2014 design the feature:",
                                       timeout=300, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("strategist"))
            print(f"\n\u2713 Refined spec finished ({len(strat_output)} chars)", flush=True)
        else:
            print("\n  \u2713 No answers provided \u2014 proceeding with assumptions as-is.", flush=True)
            if interview_mode:
                print("\n  \u26a0\ufe0f  WARNING: Strategist entered INTERVIEW MODE but no clarifications were provided.", flush=True)
                print("  The spec below is based on UNVERIFIED ASSUMPTIONS. Review carefully before proceeding.", flush=True)
                print("  To answer later: re-run the panel with the same feature description.", flush=True)
                print("\n  \u26a1 Running strategist with defaults (no user answers)...", flush=True)
                strat_output = spawn_agent("strategist", ["spec-strategist-lite", "ponytail-guard"], strat_prompt, timeout=300, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("strategist"))
                print(f"\n\u2713 Default spec finished ({len(strat_output)} chars)", flush=True)

    # Strategist contingency
    if "[TIMEOUT:" in strat_output and len(strat_output) < 500:
        print("ERROR: Strategist timed out with insufficient output \u2014 aborting pipeline")
        sys.exit(1)

    spec = extract_agent_messages(strat_output, last_only=True)
    if len(spec) < 100 and len(strat_output) > 500:
        spec = strat_output
    spec = clean_spec_content(spec)

    # Quality gate: validate spec quality, re-prompt once on failure
    _qg_passed, _qg_failures = verify_spec_quality(spec)
    if not _qg_passed:
        print(f"  ⚠ Spec quality gate: {len(_qg_failures)} issue(s)", flush=True)
        for _f in _qg_failures:
            print(f"     - {_f}", flush=True)
        print("  ⚡ Re-prompting strategist to fix quality issues...", flush=True)
        truncated = strat_output[:4096] + ("...[truncated]" if len(strat_output) > 4096 else "")
        quality_correction = (
            f"── QUALITY CORRECTION REQUIRED ──\n"
            f"Feature: {feature}\n"
            f"Project: {PROJECT_DIR}\n\n"
            f"Your spec has quality issues that need fixing:\n"
            + "\n".join(f"  - {_f}" for _f in _qg_failures) +
            f"\n\n"
            f"Fix these issues while preserving ALL content and sections.\n"
            f"Output the COMPLETE corrected spec — every section, every line.\n"
            f"Do NOT use write_file. Do NOT summarize.\n\n"
            f"── YOUR EXISTING SPEC (preserve this, fix issues) ──\n\n"
            f"{truncated}"
        )
        strat_output = spawn_agent("strategist", ["spec-strategist-lite", "ponytail-guard"],
                                   quality_correction, timeout=600, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("strategist"))
        print(f"  ✓ Strategist quality re-run finished ({len(strat_output)} chars)", flush=True)
        # Re-extract and re-verify after re-prompt
        spec = extract_agent_messages(strat_output, last_only=True)
        if len(spec) < 100 and len(strat_output) > 500:
            spec = strat_output
        spec = clean_spec_content(spec)
        _qg_passed2, _qg_failures2 = verify_spec_quality(spec)
        if not _qg_passed2:
            print(f"  ⚠ Quality gate still has {len(_qg_failures2)} issue(s) after re-prompt — proceeding with degraded quality", flush=True)
            for _f in _qg_failures2:
                print(f"     - {_f}", flush=True)

    print(f"  Spec extracted: {len(spec)} chars (from {len(strat_output)} raw)", flush=True)

    # Garbage detection: if spec looks like format-fix chatter, not a real spec
    _garbage_markers = [
        r'Done\.\s*Spec\s+saved\s+to', r'Format\s+fixes\s+applied',
        r'Let\s+me\s+verify', r'I\s+found\s+the\s+full\s+spec',
        r'Now\s+I\s+understand\s+the\s+full\s+picture',
    ]
    _looks_like_garbage = any(
        re.search(m, spec, re.IGNORECASE) for m in _garbage_markers
    ) or (len(spec) < 500 and len(strat_output) > 2000)

    # Fallback chain: write_file recovery → original pre-re-prompt spec
    if _looks_like_garbage:
        # 1. Try to recover from write_file paths in transcript
        recovered = False
        wf_matches = re.findall(
            r'(?:write_file|wrote to)\s+(\S+spec\S*\.md)',
            strat_output, re.IGNORECASE)
        for wf_path in wf_matches:
            if os.path.exists(wf_path):
                try:
                    with open(wf_path) as wf:
                        wf_content = wf.read()
                    if len(wf_content) > len(spec):
                        spec = clean_spec_content(wf_content)
                        print(f"  ⚡ Recovered spec from write_file: {wf_path} ({len(spec)} chars)", flush=True)
                        recovered = True
                except Exception:
                    pass
                if recovered:
                    break

        # 2. Fall back to original spec (pre-DAG-re-prompt) if re-prompt happened
        if not recovered and orig_strat_output and orig_strat_output != strat_output:
            orig_spec = extract_agent_messages(orig_strat_output, last_only=True)
            if len(orig_spec) < 100 and len(orig_strat_output) > 500:
                orig_spec = orig_strat_output
            orig_spec = clean_spec_content(orig_spec)
            if len(orig_spec) > len(spec):
                spec = orig_spec
                print(f"  ⚡ Recovered spec from original output ({len(spec)} chars)", flush=True)
                recovered = True

        if not recovered:
            print(f"  ⚠ Spec may be degraded — garbage markers detected", flush=True)

    spec_dir = os.path.join(PROJECT_DIR, "specs")
    os.makedirs(spec_dir, exist_ok=True)
    spec_name = slugify(feature)[:50]
    spec_path = os.path.join(spec_dir, f"{spec_name}-spec.md")
    with open(spec_path, "w") as f:
        f.write(f"# {feature}\n\n{spec}")
    print(f"\n\u2713 Spec saved: {spec_path}", flush=True)

    pr_sections = extract_pr_sections(spec, feature)
    print(f"  PR sections extracted: {len(pr_sections)} chars", flush=True)

    tasks_extract_path = os.path.join(spec_dir, f"{spec_name}-tasks.md")
    try:
        dag_pre = TaskDAG()
        feature_slug = slugify(feature)
        dag_pre.parse(strat_output, feature_slug)  # raw output, not extracted spec (extract_agent_messages strips write_file tool output containing tasks)
        if dag_pre.tasks:
            tasks_extract = []
            for t in sorted(dag_pre.tasks.values(), key=lambda x: int(x.id)):
                tasks_extract.append(f"### Task {t.id}: {t.description}\n"
                    f"**Files:** {', '.join(t.files) if t.files else 'from spec'}\n"
                    f"**Dependencies:** {', '.join(t.dependencies) if t.dependencies else '[none]'}\n"
                    f"**Description:** {t.description}\n")
            with open(tasks_extract_path, "w") as tf:
                tf.write(f"# Task Breakdown: {feature}\n\n" + "\n".join(tasks_extract))
            print(f"  Task extract: {tasks_extract_path} ({len(dag_pre.tasks)} tasks)", flush=True)
        else:
            tasks_extract_path = ""
            print("  \u26a0 No tasks parsed from spec", flush=True)
    except Exception as e:
        tasks_extract_path = ""
        print(f"  \u26a0 Task extraction failed: {e} \u2014 coder will read full spec", flush=True)

    # Tech Lead spec pre-review
    if not os.environ.get("PANEL_SKIP_ORCHESTRATOR_REVIEW"):
        print("\n\u2500\u2500 Tech Lead \u2014 Spec Pre-Review \u2500\u2500", flush=True)
        review_prompt = f"""You are the Tech Lead reviewing a spec BEFORE implementation. Read the spec at {spec_path}.

Your job is NOT to find general gaps \u2014 the Human Gate and nm will catch those. Focus on what ONLY you can assess:

## 1. Architectural Impact
- Does this design introduce coupling where it shouldn't?
- Are there implicit assumptions about service boundaries, data ownership, or API contracts?
- Will this change break existing consumers or require migrations?
- Is the design consistent with the codebase's existing patterns?
- **ADR check:** If {PROJECT_DIR}/docs/adr/ exists, run `adr list` and check: does this spec violate any existing architectural decision? If yes, flag it as CONCERN with the ADR reference.

## 2. Test Plan Verification
- Does the spec's Test Plan section exist and is it complete?
- Are edge cases concrete (not generic "test edge cases")?
- Are failure modes specified (what breaks, how it breaks, what happens)?
- Are contract invariants defined (what must remain true)?
- If the Test Plan is missing or vague, that's a BLOCKER.

Output format:
TEST PLAN: PASS / BLOCKER \u2014 <reason>
ARCHITECTURE: PASS / CONCERN \u2014 <reason>

If BLOCKER: name the missing test plan sections.
If CONCERN: name the specific architectural risk (not generic "consider coupling").
If both PASS: say "Spec pre-review approved \u2014 no architectural concerns, test plan complete."

Output NOTHING ELSE."""
        review_output = spawn_agent("tech-lead", ["adversarial-review-lite", "ponytail-guard"], review_prompt, timeout=120, cwd=PROJECT_DIR, fallback_model=FALLBACK_MODELS.get("tech-lead"))
        review_text = extract_agent_messages(review_output)
        if len(review_text) < 20 and len(review_output) > 100:
            review_text = review_output
        print(f"  Pre-review: {review_text.strip()[:200]}", flush=True)
    else:
        print("\n\u2500\u2500 Tech Lead \u2014 Spec Pre-Review \u2014 SKIPPED (PANEL_SKIP_ORCHESTRATOR_REVIEW=1) \u2500\u2500", flush=True)

    # Orchestra gate
    print("\n\u2500\u2500 Orchestrator Gate \u2500\u2500", flush=True)
    confidence = "Medium"
    for marker in ["High", "Medium", "Low"]:
        if f"({marker}" in spec or re.search(r'confidence:\s*' + re.escape(marker) + r'\b', spec, re.IGNORECASE):
            confidence = marker
            break
    impact = "MEDIUM"
    for marker in ["HIGH", "MEDIUM", "LOW"]:
        if re.search(r'impact:\s*' + re.escape(marker) + r'\b', spec, re.IGNORECASE):
            impact = marker
            break
    depth_matrix = {
        ("High", "LOW"):    "vet",      # Docs/config changes: coder-only, skip adversarial review
        ("High", "MEDIUM"): "vet+nm",
        ("High", "HIGH"):   "full",
        ("Medium", "LOW"):  "vet+nm",
        ("Medium", "MEDIUM"): "full",
        ("Medium", "HIGH"): "full",
        ("Low", "LOW"):     "vet",      # Low-risk changes: coder-only
        ("Low", "MEDIUM"):  "vet+nm",
        ("Low", "HIGH"):    "full",
    }
    depth = depth_matrix.get((confidence, impact), "full")
    if FORCE_FULL:
        depth = "full"
        print("  ⚠ --force-full — forcing full pipeline (all 5 phases)", flush=True)
    mode = "passive" if confidence == "High" else "active"
    print(f"  Confidence: {confidence}, Impact: {impact} \u2192 Depth: {depth.upper()}", flush=True)
    if mode == "passive":
        print("  Auto-pilot \u2014 no gates between phases", flush=True)
    else:
        print("  Review-gate \u2014 orchestrator checks each phase, may loop back", flush=True)
    branch = f"feat/{slugify(feature)}"
    print(f"  Branch: {branch}", flush=True)

    # Human gate
    if sys.stdin.isatty() and not SKIP_HUMAN_GATE:
        print(f"\n{'─' * 55}", flush=True)
        print(f"  HUMAN GATE \u2014 Spec ready for review", flush=True)
        print(f"{'─' * 55}", flush=True)
        print(f"  Feature:  {feature}", flush=True)
        print(f"  Depth:    {depth.upper()} ({confidence} confidence, {impact} impact)", flush=True)
        print(f"  Branch:   {branch}", flush=True)
        print(f"  Spec:     {spec_path}", flush=True)
        print(f"  Tasks:    {tasks_extract_path if tasks_extract_path else 'N/A'}", flush=True)
        print(f"\n  Options:", flush=True)
        print(f"    [y] Review the spec now (opens in less)", flush=True)
        print(f"    [e] Edit the spec (opens in vim)", flush=True)
        print(f"    [Enter] Proceed \u2014 spec looks good", flush=True)
        print(f"    [q] Quit \u2014 spec needs major changes", flush=True)
        print(f"{'─' * 55}", flush=True)
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = "q"
        if choice == "y":
            subprocess.run(["less", spec_path], timeout=300)
            try:
                confirm = input("\n  Proceed with this spec? [Enter=yes / q=quit]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = "q"
            if confirm == "q":
                print("\n  \u270b Pipeline halted by human. Spec saved \u2014 revise and re-run.", flush=True)
                sys.exit(0)
        elif choice == "e":
            subprocess.run(["vim", spec_path], timeout=600)
            try:
                with open(spec_path) as f:
                    spec = f.read()
                pr_sections = extract_pr_sections(spec, feature)
                dag_pre = TaskDAG()
                dag_pre.parse(spec, slugify(feature))
                if dag_pre.tasks:
                    tasks_extract = []
                    for t in sorted(dag_pre.tasks.values(), key=lambda x: int(x.id)):
                        tasks_extract.append(f"### Task {t.id}: {t.description}\n"
                            f"**Files:** {', '.join(t.files) if t.files else 'from spec'}\n"
                            f"**Dependencies:** {', '.join(t.dependencies) if t.dependencies else '[none]'}\n"
                            f"**Description:** {t.description}\n")
                    with open(tasks_extract_path, "w") as tf:
                        tf.write(f"# Task Breakdown: {feature}\n\n" + "\n".join(tasks_extract))
                    print(f"  Task extract regenerated: {tasks_extract_path} ({len(dag_pre.tasks)} tasks)", flush=True)
                print("  \u2713 Spec edited \u2014 proceeding with updated spec.", flush=True)
            except Exception as e:
                print(f"  \u26a0 Failed to re-read spec: {e} \u2014 proceeding with original.", flush=True)
        elif choice == "q":
            print("\n  \u270b Pipeline halted by human. Spec saved \u2014 revise and re-run.", flush=True)
            sys.exit(0)
        print("  \u2713 Human gate passed \u2014 proceeding to implementation.\n", flush=True)
    elif SKIP_HUMAN_GATE:
        print("\n  ⚠ Human gate skipped (--skip-human-gate)", flush=True)
    else:
        print("\n  \u26a0 Human gate skipped (non-interactive \u2014 Telegram/cron mode)", flush=True)

    # ADR creation
    adr_dir = os.path.join(PROJECT_DIR, "docs", "adr")
    adr_bin = os.path.join(REAL_HOME, "adr-tools", "src")
    adr_binary = os.path.join(adr_bin, "adr")
    if os.path.isdir(adr_dir) and os.path.exists(adr_binary):
        try:
            with open(spec_path) as f:
                spec_for_adr = f.read()
        except Exception:
            spec_for_adr = spec
        decision_m = re.search(
            r'(?:DECISION TABLE|Decision Table).*?(?:\n\n(?:IMPACT|CONFIDENCE|###|\Z))',
            spec_for_adr, re.DOTALL | re.IGNORECASE)
        if decision_m:
            title = feature[:80]
            result = subprocess.run(
                [os.path.join(adr_bin, "adr"), "new", f"ADR for: {title}"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=30, cwd=PROJECT_DIR,
                env={**os.environ, "PATH": f"{adr_bin}:{os.environ.get('PATH', '')}"})
            if result.returncode == 0:
                adr_output = result.stdout.strip()
                print(f"  ADR created: {adr_output}", flush=True)
                adr_file_match = re.search(r'(docs/adr/\d+-.+\.md)', adr_output)
                if adr_file_match:
                    adr_rel_path = adr_file_match.group(1)
                    adr_full_path = os.path.join(PROJECT_DIR, adr_rel_path)
                    try:
                        with open(adr_full_path, "a") as af:
                            af.write(f"\n## Source\n\nSpec: {spec_path}\n")
                    except Exception:
                        pass
                    try:
                        with open(spec_path, "a") as sf:
                            sf.write(f"\n\n## ADR\n\nSee: {adr_rel_path}\n")
                    except Exception:
                        pass
            else:
                print(f"  \u26a0 ADR creation skipped: {result.stderr.strip()[:100]}", flush=True)
    else:
        print(f"  \u2139 ADR dir not found ({adr_dir}) \u2014 skipping ADR creation. Run `adr init docs/adr` to enable.", flush=True)

    # Parallel execution gate
    parallel_enabled = os.environ.get("PANEL_PARALLEL", "1") == "1"
    return {
        "spec": spec,
        "spec_path": spec_path,
        "pr_sections": pr_sections,
        "tasks_extract_path": tasks_extract_path,
        "depth": depth,
        "branch": branch,
        "confidence": confidence,
        "impact": impact,
        "mode": mode,
        "strat_output": strat_output,
        "parallel_enabled": parallel_enabled,
    }


def run_pipeline(feature, is_next, is_continuous, user_answers_prefill, resume=None):
    """Run one full pipeline iteration for a single feature. Returns exit code."""
    global PROJECT_DIR, REPO

    # Sanitize feature description before it enters any agent prompt
    feature = _sanitize_prompt(feature)
    feature_slug = slugify(feature)

    # ── Resume / Checkpoint Handling ──
    phases_completed = []
    cp = None
    if resume:
        cp = load_checkpoint(feature_slug)
        if cp and validate_checkpoint(feature_slug):
            phases_completed = cp.get("phases_completed", [])
            print(f"  ✓ Resume: {len(phases_completed)} phase(s) completed: {', '.join(phases_completed)}", flush=True)
        else:
            print("  ⚠ No valid checkpoint found — starting fresh", flush=True)
            resume = False
            cp = None
    else:
        delete_checkpoint(feature_slug)

    # Only run strategist if not completed
    if not _phase_should_skip(phases_completed, "strategist", resume):
        strat_result = run_phase1_strategist(feature, user_answers_prefill)
        spec = strat_result["spec"]
        spec_path = strat_result["spec_path"]
        pr_sections = strat_result["pr_sections"]
        tasks_extract_path = strat_result["tasks_extract_path"]
        depth = strat_result["depth"]
        branch = strat_result["branch"]
        confidence = strat_result["confidence"]
        impact = strat_result["impact"]
        mode = strat_result["mode"]
        strat_output = strat_result["strat_output"]
        parallel_enabled = strat_result["parallel_enabled"]

        # Commit spec to feature branch before coder starts
        print(f"\n── Commit spec to {branch} ──", flush=True)
        try:
            _, _, rc = git("checkout", DEFAULT_BRANCH)
            _, _, rc = git("checkout", "-b", branch, DEFAULT_BRANCH)
            if rc != 0:
                git("checkout", branch)
            git("add", spec_path)
            if tasks_extract_path and os.path.exists(tasks_extract_path):
                git("add", tasks_extract_path)
            git("commit", "-m", f"spec: add {feature} spec")
            git("push", "-u", "origin", branch)
            git("checkout", DEFAULT_BRANCH)
            print(f"  ✓ Spec committed to {branch}", flush=True)
        except Exception as e:
            print(f"  ⚠ Spec commit failed: {e} — coder will handle", flush=True)

        # Save checkpoint after strategist
        save_checkpoint(feature_slug, {
            "version": 1,
            "feature": feature,
            "branch": branch,
            "spec_path": spec_path,
            "tasks_extract_path": tasks_extract_path or "",
            "depth": depth,
            "impact": impact,
            "mode": mode,
            "parallel_enabled": parallel_enabled,
            "phases_completed": phases_completed + ["strategist"],
        })
        phases_completed.append("strategist")
    else:
        # Reconstruct from checkpoint
        spec_path = cp.get("spec_path", "")
        branch = cp.get("branch", "")
        depth = cp.get("depth", "vet")
        impact = cp.get("impact", "LOW")
        mode = cp.get("mode", "")
        parallel_enabled = cp.get("parallel_enabled", False)
        pr_sections = ""
        strat_output = ""
        tasks_extract_path = cp.get("tasks_extract_path", "")
        # Read spec from file
        try:
            with open(spec_path) as f:
                spec = f.read()
        except (IOError, FileNotFoundError):
            print(f"  ⚠ Cannot read spec at {spec_path} — falling back to empty spec", flush=True)
            spec = ""
        # Re-checkout the branch
        git("checkout", branch)
        git("pull", "origin", branch)
        print(f"  ✓ Resumed from strategist: branch={branch}", flush=True)

    coder_failed = False
    pr_url = None
    verdict = None
    nm_output = ""
    tl_output = ""

    # Reconstruct pr_url from checkpoint if coder was completed
    if _phase_should_skip(phases_completed, "coder", resume) and cp:
        pr_url = cp.get("pr_url", "")
        print(f"  ✓ Resuming after coder: PR URL={pr_url}", flush=True)

    # ── DAG parse + execution mode ──
    dag = TaskDAG()
    feature_slug = slugify(feature)
    dag.parse(spec, feature_slug)

    # Determine execution mode from DAG (with env override)
    force_mode = os.environ.get("PANEL_FORCE_EXECUTION_MODE", "")
    if force_mode:
        exec_mode = force_mode
    elif not parallel_enabled:
        exec_mode = "single_session"
    else:
        exec_mode = dag.compute_execution_mode()

    if not dag.tasks:
        print("  ⚠ No tasks found in strategist output — falling back to sequential coder", flush=True)
        exec_mode = "single_session"

    # Parallel coders (per_task_spawn)
    if exec_mode == "per_task_spawn":
        print("\n── Parallel Coders (data-driven) ──", flush=True)
        print(f"  Parsed {len(dag.tasks)} tasks from spec", flush=True)
        waves = dag.compute_waves()
        print(f"  Waves: {' → '.join('[' + ','.join(w) + ']' for w in waves)}", flush=True)
        all_ok = run_parallel_coders(dag.tasks, waves, PROJECT_DIR, spec_path, tasks_extract_path)
        task_ids = list(dag.tasks.keys())
        wt_mgr = WorktreeManager(PROJECT_DIR)
        if not all_ok:
            print("\n  ⚠ Some tasks failed — checking if feature is still viable", flush=True)
            completed = [t for t in dag.tasks.values() if t.status == "completed"]
            if not completed:
                halt_and_revert("All parallel coders failed", "PHASE 2 (Parallel Coders)", branch, task_ids=task_ids, worktrees=wt_mgr)
                coder_failed = True
                pr_url = None
                verdict = "CODER_FAILED"
            else:
                print(f"  {len(completed)}/{len(dag.tasks)} tasks completed — proceeding with partial results", flush=True)
                if not merge_worktree_branches(branch, dag.tasks, WorktreeManager(PROJECT_DIR), PROJECT_DIR):
                    halt_and_revert("Merge assembly failed", "PHASE 2 (Merge)", branch, task_ids=task_ids, worktrees=wt_mgr)
                    coder_failed = True
                    verdict = "CODER_FAILED"
        else:
            if not merge_worktree_branches(branch, dag.tasks, WorktreeManager(PROJECT_DIR), PROJECT_DIR):
                halt_and_revert("Merge assembly failed", "PHASE 2 (Merge)", branch, task_ids=task_ids, worktrees=wt_mgr)
                coder_failed = True
                verdict = "CODER_FAILED"

        if not coder_failed and depth == "vet":
            print("\n── Creating PR (depth=coder) ──", flush=True)
            pr_sections_final = _supplement_pr_sections(pr_sections, PROJECT_DIR, branch, DEFAULT_BRANCH)
            pr_body = f"{pr_sections_final}\n\n## Validation\n- Build passes\n"
            stdout, _, rc = gh("pr", "create", "--repo", REPO,
                               "--base", DEFAULT_BRANCH, "--head", branch,
                               "--title", f"feat: {feature}",
                               "--body", pr_body)
            if rc == 0:
                parts = stdout.strip().split()
                pr_url = parts[-1] if parts else None
                if pr_url:
                    print(f"  PR created: {pr_url}", flush=True)
                else:
                    print("  PR created (no URL returned)", flush=True)
            else:
                print(f"  ⚠ PR creation failed: unknown", flush=True)

        if depth == "vet" and not coder_failed:
            print("\n── Phase 3: vet — SKIPPED (depth=vet, parallel) ──", flush=True)
            print("── Phase 4+5: nm+TL — SKIPPED (depth=vet) ──", flush=True)
            verdict = "APPROVED" if not coder_failed else "CODER_FAILED"
            # Save checkpoint after coder (parallel)
            if resume is not False:
                save_checkpoint(feature_slug, {
                    "version": 1, "feature": feature, "branch": branch,
                    "spec_path": spec_path, "tasks_extract_path": tasks_extract_path or "",
                    "depth": depth, "impact": impact, "mode": mode,
                    "parallel_enabled": parallel_enabled, "pr_url": pr_url or "",
                    "phases_completed": phases_completed + ["coder"],
                })
            continue_loop = run_post_pipeline(feature, is_next, is_continuous, True, pr_url, verdict, impact, branch, spec_path, strat_output, mode)
            if not continue_loop:
                return 0
            return 0

    # Sequential / single_session coder path
    if exec_mode == "single_session" and not coder_failed:
        coder_result = run_phase2_coder(feature, spec, spec_path, tasks_extract_path, pr_sections, branch, depth, mode, is_next)
        coder_failed = coder_result["coder_failed"]
        pr_url = coder_result["pr_url"]
        verdict = coder_result["verdict"]
        # Save checkpoint after coder
        if resume is not False:
            cp_data = {
                "version": 1, "feature": feature, "branch": branch,
                "spec_path": spec_path, "tasks_extract_path": tasks_extract_path or "",
                "depth": depth, "impact": impact, "mode": mode,
                "parallel_enabled": parallel_enabled,
                "pr_url": pr_url or "",
                "phases_completed": phases_completed + ["coder"],
            }
            save_checkpoint(feature_slug, cp_data)

    # Phase 3: vet
    if not coder_failed and depth in ("vet+nm", "full"):
        vet_result = run_phase3_vet(feature, branch, pr_sections, impact, spec_path)
        nm_output = vet_result["nm_output"]
        pr_url = vet_result["pr_url"] or pr_url
        if vet_result["coder_failed"]:
            coder_failed = True
            verdict = "VET_FAILED"
        # Save checkpoint after vet
        if resume is not False:
            cp_data = {
                "version": 1, "feature": feature, "branch": branch,
                "spec_path": spec_path, "tasks_extract_path": tasks_extract_path or "",
                "depth": depth, "impact": impact, "mode": mode,
                "parallel_enabled": parallel_enabled,
                "pr_url": pr_url or "",
                "phases_completed": phases_completed + ["coder", "vet"],
            }
            save_checkpoint(feature_slug, cp_data)
    else:
        print(f"\n── Phase 3: vet — SKIPPED (depth={depth}) ──", flush=True)
        if coder_failed:
            print("── Phase 3: vet — SKIPPED (coder failed) ──", flush=True)

    # Phase 4: nm
    if not coder_failed and depth in ("vet+nm", "full"):
        nm_result = run_phase4_nm(feature, branch, impact, pr_url)
        pr_url = nm_result["pr_url"]
        # Save checkpoint after nm
        if resume is not False:
            cp_data = {
                "version": 1, "feature": feature, "branch": branch,
                "spec_path": spec_path, "tasks_extract_path": tasks_extract_path or "",
                "depth": depth, "impact": impact, "mode": mode,
                "parallel_enabled": parallel_enabled,
                "pr_url": pr_url or "",
                "phases_completed": phases_completed + ["coder", "vet", "nm"],
            }
            save_checkpoint(feature_slug, cp_data)
    else:
        print(f"\n── Phase 4: nm — SKIPPED (depth={depth}) ──", flush=True)
        if coder_failed:
            print("\n── Phase 4: nm — SKIPPED (coder failed) ──", flush=True)

    # Phase 5: Tech Lead
    if not coder_failed and depth == "full":
        tl_result = run_phase5_tech_lead(feature, pr_url, branch, spec_path, impact, nm_output=nm_output)
        verdict = tl_result["verdict"]
        tl_output = tl_result["tl_output"]
    else:
        print(f"\n── Phase 5: Tech Lead — SKIPPED (depth={depth}) ──", flush=True)
        if coder_failed:
            print("\n── Phase 5: Tech Lead — SKIPPED (coder failed) ──", flush=True)
        if verdict is None:
            verdict = "APPROVED" if not coder_failed else "CODER_FAILED"

    # Post pipeline
    continue_loop = True
    continue_loop = run_post_pipeline(feature, is_next, is_continuous, continue_loop, pr_url, verdict, impact, branch, spec_path, strat_output, mode)
    # Delete checkpoint on successful completion
    if not coder_failed:
        delete_checkpoint(feature_slug)
    return 0


# ── main ──

