"""Dokima roadmap module — roadmap parsing, feature picking, CLI commands.

All functions extracted from dokima monolith (F022: Modular Architecture).
Imports from utils, agent, and tasks.
"""
import sys, os, json, re, subprocess, time

from utils import (load_key, slugify, git, gh, detect_repo, acquire_lock, _cleanup_lock,
                   update_status_md, _write_log_line, show_help, check_upgrade,
                   _extract_tl_verdict, _extract_tl_blockers, extract_pr_sections,
                   clean_spec_content, verify_spec_quality, generate_codebase_map,
                   extract_file_paths, load_github_token, save_checkpoint,
                   delete_checkpoint, _signal_handler, _safe_run, _redact_secrets,
                   HERMES, HERMES_BIN, DEFAULT_BRANCH, PROJECT_DIR, REPO, PANEL_FEATURE,
                   PROFILES, OUTPUT_LOG, FALLBACK_MODELS, PANEL_PORT, API_KEY,
                   SKIP_AUTOFIX, FORCE_FULL, SKIP_HUMAN_GATE, max_parallel_override,
                   RESUME, MAX_CONTINUOUS, _LOG_FILE_HANDLE, _LOCK_FD,
                   VERSION, HELP_TEXT, TEST_CMD, BUILD_CMD, LINT_CMD)
from tasks import RoadmapFeature
from agent import spawn_agent

def parse_roadmap(roadmap_path: str) -> list:
    """Parse specs/roadmap.md into a list of RoadmapFeature. Returns empty list if none found.
    # FIXME: O(n²) for large roadmaps — each feature's section detection scans all preceding lines.
    """
    if not os.path.exists(roadmap_path):
        return []

    with open(roadmap_path) as f:
        content = f.read()

    features = []
    current_section = ""

    # Track which sections features belong to
    for line in content.split("\n"):
        if line.startswith("## ") and not line.startswith("### "):
            current_section = line.strip("# ").strip()

    # Match ### F001: Title blocks
    feature_pattern = re.compile(
        r'^###\s+(F\d{3}):\s*(.+?)$\n'
        r'(.*?)(?=^###\s+F\d{3}:|^##\s|\Z)',
        re.MULTILINE | re.DOTALL
    )

    for m in feature_pattern.finditer(content):
        fid = m.group(1)
        title = m.group(2).strip()
        body = m.group(3)

        # Determine section
        section = ""
        body_start = m.start()
        pre_text = content[:body_start]
        for line in reversed(pre_text.split("\n")):
            if line.startswith("## ") and not line.startswith("### "):
                section = line.strip("# ").strip()
                break

        # Priority
        prio_m = re.search(r'\*\*Priority:\*\*\s*(P[012])', body)
        priority = prio_m.group(1) if prio_m else "P2"

        # Dependencies
        deps_m = re.search(r'\*\*Dependencies:\*\*\s*(.+?)$', body, re.MULTILINE)
        if deps_m:
            dep_text = deps_m.group(1).strip()
            deps = re.findall(r'F\d{3}', dep_text) if dep_text.lower() not in ('none', '') else []
        else:
            deps = []

        # Status
        status_m = re.search(r'\*\*Status:\*\*\s*\[([ x~])\]\s*(\w+)', body)
        if status_m:
            marker = status_m.group(1)
            status = {" ": "pending", "~": "in_progress", "x": "done"}.get(marker, "pending")
        else:
            status = "pending"

        # User Story
        story_m = re.search(r'\*\*User Story:\*\*\s*(.+?)$', body, re.MULTILINE)
        story = story_m.group(1).strip() if story_m else ""

        features.append(RoadmapFeature(
            fid=fid, title=title, priority=priority,
            dependencies=deps, status=status, story=story,
            section=section
        ))

    return features

def pick_next_feature(features: list) -> object:
    """Topological sort + priority ordering. Returns RoadmapFeature or None."""
    if not features:
        return None

    # 1. Detect circular deps (DFS cycle check)
    dep_graph = {f.id: set(f.dependencies) for f in features}
    for fid in dep_graph:
        visited = set()
        stack = [fid]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            for dep in dep_graph.get(node, set()):
                if dep == fid:
                    print(f"ERROR: Circular dependency: {fid} depends on itself via chain. Fix roadmap.md.")
                    sys.exit(1)
                if dep in dep_graph:
                    stack.append(dep)

    # 2. Filter: include pending and in_progress features (exclude done)
    candidates = [f for f in features if f.status in ("pending", "in_progress")]
    if not candidates:
        return None

    # 3. Filter: all dependencies are done
    done_ids = {f.id for f in features if f.status == "done"}

    unblocked = []
    for f in candidates:
        if all(dep in done_ids for dep in f.dependencies):
            unblocked.append(f)
        else:
            missing = [dep for dep in f.dependencies if dep not in done_ids]
            print(f"  {f.id} blocked — waiting on: {', '.join(missing)}")

    if not unblocked:
        print("All pending/in-progress features are blocked by incomplete dependencies.")
        return None

    # 4. Sort: by execution priority (P0 first, then P1, P2, P3).
    #    Within same priority, in_progress beats pending, then by roadmap order
    #    (features earlier in the file — higher phases — take precedence).
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    status_order = {"in_progress": 0, "pending": 1}
    pos_map = {f.id: i for i, f in enumerate(features)}
    unblocked.sort(key=lambda f: (
        priority_order.get(f.priority, 2),
        status_order.get(f.status, 1),
        pos_map.get(f.id, 999)
    ))

    return unblocked[0]

def update_roadmap_status(roadmap_path: str, feature_id: str, new_status: str):
    """Update feature status in roadmap.md inline."""
    if not os.path.exists(roadmap_path):
        return
    marker_map = {
        "pending":     "[ ] Pending",
        "in_progress": "[~] In Progress",
        "done":        "[x] Done",
    }
    new_marker = marker_map.get(new_status, "[ ] Pending")

    with open(roadmap_path) as f:
        content = f.read()

    # Find the feature block and replace its status
    pattern = re.compile(
        rf'(^###\s+{feature_id}:.+?\n\*\*Status:\*\*\s*)\[([ x~])\]\s*\w+',
        re.MULTILINE | re.DOTALL
    )

    new_content = pattern.sub(rf'\g<1>{new_marker}', content)

    if new_content == content:
        print(f"  WARNING: Could not find status for {feature_id} in roadmap")
        return

    with open(roadmap_path, "w") as f:
        f.write(new_content)

def commit_roadmap_update(roadmap_path: str, feature_id: str, action: str):
    """Commit a roadmap status change to the default branch.
    Also commits STATUS.md, codebase-map.md, .map-cache.json, and any untracked
    loose spec files in specs/ (F*-spec.md) — so the working tree is clean
    before the next feature's PR creation."""
    # Ensure we're on default branch
    rel_path = os.path.relpath(roadmap_path, PROJECT_DIR)
    git("checkout", DEFAULT_BRANCH)
    git("pull", "origin", DEFAULT_BRANCH)
    git("add", rel_path)
    # Also stage STATUS.md (written by update_status_md)
    status_rel = "specs/STATUS.md"
    if os.path.exists(os.path.join(PROJECT_DIR, status_rel)):
        git("add", status_rel)
    # Also stage codebase map files (written by generate_codebase_map)
    for map_file in ["specs/codebase-map.md", "specs/.map-cache.json"]:
        if os.path.exists(os.path.join(PROJECT_DIR, map_file)):
            git("add", map_file)
    # Stage any loose spec files the strategist wrote
    specs_dir = os.path.join(PROJECT_DIR, "specs")
    if os.path.isdir(specs_dir):
        for entry in os.listdir(specs_dir):
            if entry.endswith("-spec.md") and not os.path.isdir(os.path.join(specs_dir, entry)):
                git("add", os.path.join("specs", entry))
    if action == "start":
        msg = f"chore: mark {feature_id} as in progress [panel]"
    elif action == "revert":
        msg = f"chore: revert {feature_id} to pending after pipeline failure [panel]"
    else:
        msg = f"chore: mark {feature_id} as done [panel]"
    git("commit", "-m", msg)
    git("push", "origin", DEFAULT_BRANCH)
    print(f"  Roadmap updated: {feature_id} → {action}")

def auto_repair_status(features: list, roadmap_path: str) -> int:
    """Check for features not marked done that have merged PRs → auto-mark [x].
       Returns count of repaired features."""
    repaired = 0

    for f in features:
        if f.status == "done":
            continue
        # Check if a merged PR exists for this feature
        branch_slug = slugify(f.title)[:40]
        branch_patterns = [f"feat/{branch_slug}"]
        # Also try with feature ID
        branch_patterns.append(f"feat/{slugify(f'{f.id}-{f.title}')[:60]}")

        for bp in branch_patterns:
            stdout, _, rc = gh("pr", "list", "--repo", REPO, "--head", bp,
                              "--state", "merged", "--json", "url,number", "--jq", ".[0]")
            if rc != 0 or not stdout.strip():
                continue
            pr_data = json.loads(stdout.strip()) if stdout.strip().startswith("{") else {}
            pr_url = pr_data.get("url", stdout.strip())
            pr_num = pr_data.get("number", "")

            # Guard: require a valid PR number (skip non-JSON / corrupted output)
            if not pr_num:
                continue

            # Guard: only auto-repair if the PR had real code changes (not just specs)
            if pr_num:
                diff_out, _, drc = gh("pr", "diff", str(pr_num), "--repo", REPO, "--stat")
                code_files = [l for l in (diff_out or "").split("\n")
                              if l.strip() and not l.startswith("specs/")
                              and not l.startswith(" .../") and "file changed" not in l
                              and l.strip()]
                if not code_files:
                    print(f"  Auto-repair: SKIPPED {f.id} — merged PR #{pr_num} has no code changes (spec-only)")
                    continue

            update_roadmap_status(roadmap_path, f.id, "done")
            print(f"  Auto-repair: {f.id} → [x] Done (merged PR: {pr_url})")
            # Update STATUS.md
            status_path = os.path.join(PROJECT_DIR, "specs", "STATUS.md")
            update_status_md(status_path, f.id, f.title, "done",
                             pr_url=pr_url, source="auto-repair")
            repaired += 1
            break

    if repaired:
        rel_path = os.path.relpath(roadmap_path, PROJECT_DIR)
        git("checkout", DEFAULT_BRANCH)
        git("pull", "origin", DEFAULT_BRANCH)
        git("add", rel_path)
        # Also stage STATUS.md (modified by update_status_md above)
        status_rel = os.path.join("specs", "STATUS.md")
        if os.path.exists(os.path.join(PROJECT_DIR, status_rel)):
            git("add", status_rel)
        git("commit", "-m", f"chore: auto-repair {repaired} roadmap statuses [panel]")
        git("push", "origin", DEFAULT_BRANCH)

    return repaired

def run_add_to_roadmap(feature_desc, project_dir, priority_hint=None):
    """Add a feature to roadmap.md with auto-determined priority, dependencies,
    and section placement. Orders features by execution priority within each
    section: infrastructure/tests first, then critical bugs, resilience,
    security, features, docs, distribution, icebox."""

    roadmap_path = os.path.join(project_dir, "specs", "roadmap.md")
    if not os.path.exists(roadmap_path):
        print("ERROR: No roadmap.md found. Run 'dokima init' first.")
        sys.exit(1)

    with open(roadmap_path) as f:
        content = f.read()

    # Find highest existing F-number
    existing_ids = re.findall(r'^###\s+(F\d{3}):', content, re.MULTILINE)
    next_num = 1
    if existing_ids:
        nums = [int(fid[1:]) for fid in existing_ids]
        next_num = max(nums) + 1
    new_fid = f"F{next_num:03d}"

    desc_lower = feature_desc.lower()

    # ── Execution priority scoring ──
    # Domain score (lower = execute first): infrastructure (10) < critical bugs (20)
    # < resilience (30) < security (40) < features (50) < docs (60) < distribution
    # (70) < icebox (80). Combined with P-level: score = (P_level * 100) + domain.
    def _execution_score(fdesc: str, fpriority: str) -> int:
        """Compute execution priority score for ordering. Lower = execute sooner."""
        fd = fdesc.lower()
        # Domain classification
        if any(w in fd for w in ("test", "integration test", "edge case", "quality gate",
                                  "deterministic", "ci ", "pipeline test", "spec test")):
            domain = 10  # Infrastructure/tests — needed first
        elif any(w in fd for w in ("broken", "dead code", "cosmetic", "defeated",
                                    "wrong command", "hardcode", "same model", "fake",
                                    "fictional", "crash", "silent fail", "bug")):
            domain = 20  # Critical bugs/blockers — broken today
        elif any(w in fd for w in ("fallback", "recovery", "resume", "retry",
                                    "timeout", "lock file", "error handl")):
            domain = 30  # Resilience — prevents catastrophic failure
        elif any(w in fd for w in ("security", "injection", "vulnerability",
                                    "auth", "secret", "xss", "csrf")):
            domain = 40  # Security
        elif any(w in fd for w in ("docs", "documentation", "readme", "guide",
                                    "tutorial", "changelog")):
            domain = 60  # Documentation
        elif any(w in fd for w in ("installer", "portability", "template", "quickstart",
                                    "doctor", "config valid", "profile templ",
                                    "vendor agnostic", "package")):
            domain = 70  # Distribution/portability
        elif any(w in fd for w in ("someday", "icebox", "future", "post-stable",
                                    "nice to have", "maybe")):
            domain = 80  # Icebox
        else:
            domain = 50  # Features (default)
        p_level = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(fpriority, 1)
        return p_level * 100 + domain

    # Determine priority from keywords (same logic, but now also used for scoring)
    priority = priority_hint or ""
    if not priority:
        p0_words = ["security", "crash", "data loss", "injection", "vulnerability",
                    "critical", "blocker", "broken pipeline", "silent failure"]
        p3_words = ["someday", "icebox", "maybe", "future", "post-stable", "nice to have"]
        p2_words = ["docs", "documentation", "readme", "portability", "installer",
                    "quickstart", "template", "config", "guide"]
        if any(w in desc_lower for w in p0_words):
            priority = "P0"
        elif any(w in desc_lower for w in p3_words):
            priority = "P3"
        elif any(w in desc_lower for w in p2_words):
            priority = "P2"
        else:
            priority = "P1"

    new_score = _execution_score(feature_desc, priority)

    # Determine dependencies from keyword overlap with existing features
    existing_features = {}
    for m in re.finditer(r'^###\s+(F\d{3}):\s*(.+?)$\n(.*?)(?=^###\s+F\d{3}:|^##\s|\Z)',
                         content, re.MULTILINE | re.DOTALL):
        fid = m.group(1)
        ftitle = m.group(2).strip()
        fbody = m.group(3)
        existing_features[fid] = {"title": ftitle, "body": fbody}

    # Find dependencies based on keyword overlap (min 4-char words)
    deps = []
    desc_words = set(re.findall(r'\w{4,}', desc_lower))
    for fid, finfo in existing_features.items():
        ftitle_words = set(re.findall(r'\w{4,}', finfo["title"].lower()))
        overlap = desc_words & ftitle_words
        if len(overlap) >= 2:
            status_m = re.search(r'\*\*Status:\*\*\s*\[x\]', finfo["body"])
            if not status_m:  # Only depend on not-done features
                deps.append(fid)
    deps_str = ", ".join(deps[:3]) if deps else "None"

    # Build feature block
    feature_block = f"""
### {new_fid}: {feature_desc}
**Priority:** {priority}
**Dependencies:** {deps_str}
**Status:** [ ] Pending
**User Story:** As a user, I can {feature_desc.lower().strip('.')}.
"""

    # ── Insert at execution-priority position within correct section ──
    # Find all features in each section with their execution scores
    section_features = {}  # {section_title: [(start_pos, end_pos, fid, score), ...]}
    section_pattern = re.compile(r'^##\s+(.+?)$', re.MULTILINE)
    for sm in section_pattern.finditer(content):
        sec_title = sm.group(1).strip()
        sec_start = sm.start()
        next_sec = section_pattern.search(content, sm.end())
        sec_end = next_sec.start() if next_sec else len(content)
        section_features[sec_title] = []

        # Collect features in this section
        for fm in re.finditer(r'^###\s+(F\d{3}):\s*(.+?)$', content[sec_start:sec_end],
                              re.MULTILINE):
            fid = fm.group(1)
            ftitle = fm.group(2).strip()
            abs_start = sec_start + fm.start()
            # Find end of this feature's block (skip past own header, find next ### or ##)
            # Start search at abs_start+4 to skip past "### " of current feature header
            next_feat = re.search(r'^###\s+F\d{3}:|^##\s',
                                  content[abs_start + 4:sec_end], re.MULTILINE)
            feat_end = (abs_start + 4 + next_feat.start()
                       if next_feat else sec_end)
            # Determine this feature's priority from its body
            feat_body = content[abs_start:feat_end]
            prio_m = re.search(r'\*\*Priority:\*\*\s*(P[0-3])', feat_body)
            feat_priority = prio_m.group(1) if prio_m else "P1"
            score = _execution_score(ftitle, feat_priority)
            section_features[sec_title].append((abs_start, feat_end, fid, score))

    # Decide target section
    target_section = None
    priority_band = {"P0": "Phase 1", "P1": "Phase 2", "P2": "Phase 3", "P3": "Icebox"}
    band_key = priority_band.get(priority, "Phase 2")
    for sec_title in section_features:
        if sec_title.startswith(band_key) or band_key.lower() in sec_title.lower():
            target_section = sec_title
            break
    # Only use fallback if there are sections AND one of them matches band_key.
    # Otherwise trigger new section creation.

    # Insert at execution-priority position
    if target_section and target_section in section_features:
        feats = section_features[target_section]
        # Find insertion point: after the last feature with score <= new_score
        insert_pos = None
        for feat_start, feat_end, fid, score in feats:
            if score > new_score:
                # Insert before this feature (it has lower execution priority)
                insert_pos = feat_start
                break
        if insert_pos is None:
            # Append to end of section
            # Find the end of the section (before next ## or end of file)
            sec_start = None
            for sm in section_pattern.finditer(content):
                if sm.group(1).strip() == target_section:
                    sec_start = sm.start()
                    next_sec = section_pattern.search(content, sm.end())
                    sec_end = next_sec.start() if next_sec else len(content)
                    insert_pos = sec_end
                    break
        new_content = content[:insert_pos] + feature_block + "\n" + content[insert_pos:]
    else:
        # No matching section found — create section header automatically
        phase_names = {"P0": "Phase 1: Core Stability & Test Coverage",
                       "P1": "Phase 2: Pipeline Intelligence",
                       "P2": "Phase 3: Distribution & Portability",
                       "P3": "Icebox (Post-Stable)"}
        section_name = phase_names.get(priority, "Phase 2: Features")
        # If this is the first feature in the file, add a title too
        if not content.strip():
            section_header = f"# Roadmap\n\n## {section_name}\n\n"
        else:
            section_header = f"\n## {section_name}\n\n"
        new_content = content + section_header + feature_block + "\n"

    with open(roadmap_path, "w") as f:
        f.write(new_content)

    print(f"  ✓ {new_fid} added to roadmap — {priority}, deps: {deps_str}")
    print(f"    Title: {feature_desc}")
    phase_map = {"P0": "Phase 1", "P1": "Phase 2", "P2": "Phase 3", "P3": "Icebox"}
    print(f"    Section: {phase_map.get(priority, 'Phase 2')}")
    print(f"    Execution score: {new_score} (lower = execute first)")
    return new_fid



def run_next_setup(interactive: bool = False, feature_hint: str | None = None) -> str | None:
    """Parse roadmap, pick next feature, mark in-progress, return feature string.
       If feature_hint is provided (user-specified feature name), search for it
       in the roadmap instead of using pick_next_feature.
       Returns None if nothing to do. Caller falls through to pipeline after this."""
    global REPO, DEFAULT_BRANCH

    roadmap_path = os.path.join(PROJECT_DIR, "specs", "roadmap.md")

    # 1. Parse
    features = parse_roadmap(roadmap_path)
    if not features:
        print("ERROR: No features found in roadmap.md. Run `dokima init` first.")
        sys.exit(1)

    print(f"  Roadmap: {len(features)} features")
    done = sum(1 for f in features if f.status == "done")
    pending = sum(1 for f in features if f.status == "pending")
    in_prog = sum(1 for f in features if f.status == "in_progress")
    print(f"  Status: {done} done, {pending} pending, {in_prog} in progress")

    # 2. Auto-repair: features with merged PRs → mark [x]
    repaired = auto_repair_status(features, roadmap_path)
    if repaired:
        features = parse_roadmap(roadmap_path)

    # 3. Pick next — respect user-specified feature hint if provided
    if feature_hint:
        hint_upper = feature_hint.upper()
        # Try exact ID match first, then substring match on title/ID
        for f in features:
            if f.id.upper() == hint_upper or feature_hint.lower() in f.title.lower():
                if f.status == "done":
                    print(f"  {f.id} is already done. Use --force to re-run.")
                    sys.exit(0)
                next_feat = f
                break
        if not next_feat:
            print(f"  Feature '{feature_hint}' not found in roadmap. Available: {[f.id for f in features]}")
            sys.exit(1)
    else:
        next_feat = pick_next_feature(features)
    if not next_feat:
        done_count = sum(1 for f in features if f.status == "done")
        total = len(features)
        if done_count == total:
            print(f"All {total} features complete. Nothing to do.")
        sys.exit(0)

    print(f"\n── Next Feature: {next_feat.id} — {next_feat.title} ──")
    print(f"  Priority: {next_feat.priority}")
    print(f"  Dependencies: {', '.join(next_feat.dependencies) or 'none'}")

    # 4. Mark in progress (on default branch)
    update_roadmap_status(roadmap_path, next_feat.id, "in_progress")

    # Update STATUS.md BEFORE commit so it's included
    status_path = os.path.join(PROJECT_DIR, "specs", "STATUS.md")
    branch = f"feat/{slugify(f'{next_feat.id}-{next_feat.title}')[:50]}"
    update_status_md(status_path, next_feat.id, next_feat.title, "in_progress",
                     branch=branch, source="panel")

    commit_roadmap_update(roadmap_path, next_feat.id, "start")

    # 5. Return feature string for the pipeline
    feature = f"{next_feat.id}: {next_feat.title}"

    # 6. Check for existing spec → set env for strategist
    spec_slug = slugify(feature)
    spec_path = os.path.join(PROJECT_DIR, "specs", f"{spec_slug}-spec.md")
    if os.path.exists(spec_path):
        os.environ["PANEL_EXISTING_SPEC"] = spec_path
        print(f"  Existing spec found: {spec_slug}-spec.md (strategist will refine)")

    # 7. Non-interactive by default
    if not interactive:
        os.environ["PANEL_SKIP_HUMAN_GATE"] = "1"

    return feature


# ── init ──────────────────────────────────────────

# ── Profile configuration defaults (F012) — imported from utils module
from utils import _PROFILE_CONFIGS, _PROFILE_ORDER, ensure_profiles, deploy_profile_skills



def run_init(description, project_dir):
    """Discovery & constitution phase. Strategist produces spec-kit docs, no pipeline."""
    global API_KEY, PROJECT_DIR, REPO

    PROJECT_DIR = project_dir

    if not description:
        print("ERROR: init requires a project description.")
        print("  dokima init 'trading dashboard for SGX options' [project_dir]")
        sys.exit(1)

    # Load API key (needed for strategist)
    API_KEY = load_key()
    if not API_KEY:
        print("ERROR: Could not read API_SERVER_KEY from .env")
        sys.exit(1)

    gh_token = load_github_token()
    if gh_token:
        os.environ["GH_TOKEN"] = gh_token

    # ── Detect project state ──
    agents_path = os.path.join(PROJECT_DIR, "AGENTS.md")
    is_greenfield = not os.path.exists(agents_path)

    # Check git
    has_git = os.path.isdir(os.path.join(PROJECT_DIR, ".git"))
    if not has_git:
        try:
            subprocess.run(["git", "-C", PROJECT_DIR, "init"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            has_git = True
            print("  git init", flush=True)
        except Exception:
            pass

    # Detect repo
    try:
        repo = detect_repo()
    except Exception:
        repo = ""
    has_remote = bool(repo)
    if has_remote:
        REPO = repo

    print("═" * 55)
    print("  DOKIMA — init (Discovery & Constitution)")
    print("═" * 55)
    print(f"\nDescription: {description}")
    print(f"Project:    {PROJECT_DIR}")
    print(f"Mode:       {'greenfield' if is_greenfield else 'existing codebase'}")
    print(f"Git:        {'initialized' if has_git else 'not found'}")
    print(f"GitHub:     {repo if has_remote else 'not configured'}")
    print()

    # ── Ensure profiles and skills are set up (F012) ──
    try:
        ensure_profiles()
    except Exception as e:
        print(f"  WARNING: Profile setup failed: {e}", flush=True)

    try:
        deploy_profile_skills()
    except Exception as e:
        print(f"  WARNING: Skill deployment failed: {e}", flush=True)

    # ── Bump max_turns for init ──
    strat_config = os.path.join(PROFILES, "strategist", "config.yaml")
    orig_yaml = None
    orig_max_turns = None
    if os.path.exists(strat_config):
        with open(strat_config) as f:
            orig_yaml = f.read()
        mt_match = re.search(r'^(\s+max_turns:\s*)(\d+)', orig_yaml, re.MULTILINE)
        if mt_match:
            orig_max_turns = mt_match.group(2)
            new_yaml = orig_yaml.replace(
                f"{mt_match.group(1)}{mt_match.group(2)}",
                f"{mt_match.group(1)}300")
            with open(strat_config, "w") as f:
                f.write(new_yaml)
            print(f"  max_turns: {orig_max_turns} → 300 (init needs deeper exploration)", flush=True)

    # ── Build strategist prompt ──
    audit_section = ""
    if not is_greenfield:
        audit_section = f"""\nCODEBASE AUDIT (do this FIRST):
1. Run `find {PROJECT_DIR} -type f -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.rs' -o -name '*.go' -o -name '*.java' | head -100` to discover the project structure.
2. Read the key source files — understand the architecture before designing.
3. Run `git -C {PROJECT_DIR} log --oneline -30` to understand recent work.
4. Catalog: tech debt, duplicated logic, undocumented behavior, test coverage gaps.
5. Your constitution must reflect these findings — add "fix" features to the roadmap for critical debt."""

    strat_prompt = f"""You are the Strategist doing PROJECT DISCOVERY for a {'new' if is_greenfield else 'existing'} project at {PROJECT_DIR}.

YOUR JOB: Produce the four spec-kit constitution documents. No code. No implementation. Discovery only.

DESCRIPTION FROM USER: {description}

PHASE 1 — INTERROGATE THE USER:
- Who are the users? What decisions does this product drive?
- What does "done" look like? What are the success criteria?
- What are the ANTI-GOALS? (what will this NOT do?)
- What are the consequences of wrong/stale output?
- For existing projects: what's wrong with the current state?

PHASE 2 — DOMAIN RESEARCH:
- Who are the competitors? What do they do well/poorly?
- What are common pitfalls in this domain?
- What market/regulatory constraints apply?
{audit_section}
PHASE 3 — PRODUCE THE CONSTITUTION:

Create {PROJECT_DIR}/specs/mission.md:
- Problem statement, target users, success criteria, anti-goals
- JOBS TO BE DONE, not feature requests

Create {PROJECT_DIR}/specs/tech-stack.md:
- Language, framework, database, infrastructure choices
- EVERY choice must have a WHY. No cargo-culting.
- For existing projects: document current stack + what should change

Create {PROJECT_DIR}/specs/roadmap.md using EXACTLY this format for every feature:

### F001: Short Feature Title
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** As a <role>, I want <goal> so that <benefit>.
**Acceptance Criteria:**
- Criterion 1
- Criterion 2

RULES:
- Feature IDs: F001, F002, F003... sequential order.
- Priority: P0 (critical path), P1 (important), P2 (nice to have), P3 (icebox).
- Dependencies: comma-separated feature IDs that must be [x] Done first. Write "None" if no deps.
- Status: ALWAYS start with "[ ] Pending". The panel auto-updates these.
- User Story: standard "As a... I want... so that..." format.
- Acceptance Criteria: concrete, testable bullets.
- Group features under ## Phase headers (Phase 1: Core Stability, Phase 2: Pipeline Intelligence, Phase 3: Distribution, Icebox).
- Each feature must trace to a user need in mission.md.
- EXECUTION ORDER (CRITICAL): Within each Phase, order features by what must be built FIRST — not by F-number. The execution order is: infrastructure/tests → critical bugs → resilience → security → features → docs → distribution → icebox. A P0 integration test framework (F002) comes before a P0 security hardening (F001) because you cannot verify security without tests. The panel's `dokima --next` picks the first pending feature in order — make that order correct.

Create {PROJECT_DIR}/specs/conventions.md:
- Code style, patterns, anti-patterns, boundaries
- Derived from codebase audit (not templated)
- "Never do X" rules

Create {PROJECT_DIR}/AGENTS.md:
- Project title and one-line description
- Exact test, build, and lint commands matching the tech stack you chose
- Non-obvious conventions agents need to know
- Keep it minimal — only what agents cannot infer from reading code

PHASE 4 — VALIDATION LOOP:
- Review ALL four documents. Find gaps.
- Are there features missing from roadmap? Unjustified tech choices?
- Present gap analysis. If anything is uncertain, use best judgment and note the assumption. Do NOT ask questions — make decisions and document them.
- Self-correct before final output.

CRITICAL RULES:
- Every tech choice justified. Every feature traceable to user need.
- Anti-goals explicit in mission.md — "this is NOT a portfolio tracker"
- Do NOT write implementation code. Do NOT create feature specs.
- For existing projects with AGENTS.md: read it, respect it, do NOT overwrite it.
- Exit message: summary of what was created + recommended next steps."""

    # ── Spawn strategist ──
    print("── Phase: Strategist (init) ──", flush=True)
    os.makedirs(os.path.join(PROJECT_DIR, "specs"), exist_ok=True)

    init_skills = ["spec-kit", "saas-ideation"]
    missing_skills = []
    for skill in init_skills:
        # Check if skill exists in profile or global skills dirs
        skill_found = False
        for base in [os.path.join(PROFILES, "strategist", "skills"),
                     os.path.join(HERMES, "skills")]:
            for root, dirs, files in os.walk(base):
                if os.path.basename(root) == skill:
                    skill_found = True
                    break
            if skill_found:
                break
        if not skill_found:
            missing_skills.append(skill)
    if missing_skills:
        print(f"  WARNING: Skills not found: {', '.join(missing_skills)}")
        print(f"  Run the setup script first: scripts/setup-linux.sh (or setup-windows.ps1)")
        print(f"  Or deploy manually to ~/.hermes/skills/software-development/")

    strat_output = spawn_agent(
        "strategist",
        init_skills,
        strat_prompt,
        timeout=1200,  # 20 min for deep discovery
        cwd=PROJECT_DIR,
        fallback_model=FALLBACK_MODELS.get("strategist")
    )

    # ── Restore config ──
    if orig_yaml and os.path.exists(strat_config):
        with open(strat_config, "w") as f:
            f.write(orig_yaml)
        if orig_max_turns:
            print(f"  max_turns restored → {orig_max_turns}", flush=True)

    # ── Post-init: greenfield setup ──
    if is_greenfield:
        # Create AGENTS.md if strategist didn't
        if not os.path.exists(agents_path):
            # Try to detect tech stack from strategist output
            with open(agents_path, "w") as f:
                f.write(f"# {description.split('for ')[-1] if 'for ' in description else description}\n\n")
                f.write(f"{description}\n\n")
                f.write("## Commands\n")
                f.write("Unit tests: `<your test command>`\n")
                f.write("Full build: `<your build command>`\n")
                f.write("Lint: `<your lint command>`\n")
            print(f"  Created AGENTS.md (default — customize as needed)", flush=True)

        # Prompt for GitHub remote if not set
        if not has_remote:
            print("\n  GitHub remote not configured.", flush=True)
            if sys.stdin.isatty():
                remote_url = input("  Paste your GitHub remote URL (or Enter to skip): ").strip()
                if remote_url:
                    try:
                        subprocess.run(
                            ["git", "-C", PROJECT_DIR, "remote", "add", "origin", remote_url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                        print(f"  Remote added: {remote_url}", flush=True)
                        REPO = detect_repo()
                    except Exception as e:
                        print(f"  Could not add remote: {e}", flush=True)
            else:
                print("  Non-interactive — add manually: git remote add origin <url>", flush=True)

    # ── Initialize STATUS.md ──
    status_path = os.path.join(PROJECT_DIR, "specs", "STATUS.md")
    if not os.path.exists(status_path):
        with open(status_path, "w") as sf:
            sf.write(f"# Specs Status — initialized {time.strftime('%Y-%m-%d %H:%M')}\n\n")
            sf.write("## Active\n\n")
            sf.write("## Archived\n\n")
        print("  STATUS.md initialized", flush=True)

    # ── Done ──
    print("\n─── init complete ───")
    print(f"\n  Created in {PROJECT_DIR}/specs/:")
    for fname in ["mission.md", "tech-stack.md", "roadmap.md", "conventions.md"]:
        fp = os.path.join(PROJECT_DIR, "specs", fname)
        if os.path.exists(fp):
            print(f"    ✓ {fname}")
        else:
            print(f"    ✗ {fname} (missing — strategist may have skipped)")
    print()
    print("  Next: review the constitution, then:")
    print(f"    dokima 'F001: first feature' {PROJECT_DIR}")
    print(f"    or develop manually using the roadmap as your guide.")


# ── extracted phase functions ─────────────────────


