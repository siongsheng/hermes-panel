"""Dokima utilities — shared helpers, git/GitHub wrappers, security, spec extraction, checkpointing.

All functions extracted from dokima monolith (F022: Modular Architecture).
Module-level globals are set by main() in the dokima entry script before any function calls.
"""
import sys, json, subprocess, os, pwd, time, shlex, re, fcntl, signal, datetime, tempfile

# shutil imported dynamically where needed (deploy_profile_skills)

# ── Module-level globals (set by main()) ──────────
# Set by conftest._load_panel() after importing this module.
# Used by override-detection to find the correct panel instance
# without relying on sys.modules (which can be stale from
# other _load_panel() calls in tests — F022b).
_IMPORTING_PANEL = None
PROJECT_DIR = ""
REPO = ""
DEFAULT_BRANCH = "master"
API_KEY = ""
OUTPUT_LOG = "/tmp/dokima-output.txt"
REAL_HOME = pwd.getpwuid(os.getuid()).pw_dir
HERMES = os.path.join(REAL_HOME, ".hermes")
HERMES_BIN = os.path.join(HERMES, "hermes-agent/venv/bin/hermes")
PROFILES = os.path.join(HERMES, "profiles")
PANEL_PORT = {"strategist": 8647, "tech-lead": 8644, "coder": 8645, "nm": 8648}
PANEL_FEATURE = ""
PANEL_DIR = ""
FALLBACK_MODELS = {}
SKIP_AUTOFIX = False
FORCE_FULL = False
SKIP_HUMAN_GATE = False
max_parallel_override = None
RESUME = None
TEST_CMD = "npm test"
BUILD_CMD = "npm run build"
LINT_CMD = "npm run lint"

# Version
_script_dir = os.path.dirname(os.path.abspath(__file__))
_version_path = os.path.join(_script_dir, "VERSION")
try:
    VERSION = open(_version_path).read().strip()
except OSError:
    VERSION = "unknown"

# ── Global state ─────────────────────────────────
_LOG_FILE_HANDLE = None
_LOCK_FD = None
_LOG_FILE = None
_STDOUT_ORIG = None
_GH_TOKEN_CACHE = None
MAX_CONTINUOUS = 20

HELP_TEXT = """Dokima — Multi-Agent Orchestration Engine

COMMANDS:
  dokima "Feature description" [dir]     Run full pipeline for a feature
  dokima init "description" [dir]        Project discovery & constitution
  dokima --add "Feature" [--priority=P1] [dir]  Add feature to roadmap (auto-priority, auto-deps)
  dokima --next [dir]                    Build next feature from roadmap
  dokima --continuous [dir]              Full sprint: build + auto-merge + loop
  dokima --fix [dir]                     Fix BLOCKED PR: detect blockers, fix, verify

CONTROL:
  dokima --status [dir]                  Show pipeline state
  dokima --stop [dir]                    Graceful stop after current feature
  dokima --kill [dir]                    Emergency kill (SIGTERM then SIGKILL)
  dokima --list-crons                    List all scheduled pipelines
  dokima --version                       Print version and exit
  dokima --upgrade                       Check for newer version and show upgrade instructions

FLAGS:
  --interactive        Show human gate (with --next/--continuous)
  --answers <file>     Resume from saved interview state
  --fix-all            Include SHOULD FIX items (with --fix)
  --skip-autofix       Disable auto-fix loopback (nm + TL phases)
  --force-full         Run all 5 phases regardless of depth gating
  --skip-auto-archive  Don't auto-archive merged specs
  --skip-human-gate    Skip Human Gate prompt (for automation)
  --resume             Resume from last checkpoint (re-runs incomplete phases only)
  --no-resume          Ignore any existing checkpoint and start fresh
  --max-parallel=N     Max parallel coder agents (env: PANEL_MAX_PARALLEL, default: 5)
  --base-branch <b>    Override default branch for PR base (default: detected from origin/HEAD)

  All flags also accept their legacy PANEL_* env var equivalents
  (e.g., PANEL_FORCE_FULL=1). Flags take priority.

EXAMPLES:
  dokima init "trading dashboard" ~/huat
  dokima --add "Dark mode toggle" ~/huat
  dokima --next ~/huat
  dokima --continuous ~/huat
  dokima --fix ~/huat
  dokima --status ~/huat"""
# KEEP IN SYNC with HELP_TEXT — add any new command/flag/env_var here too
CLI_METADATA = {
    "tool": "dokima",
    "version": VERSION,
    "commands": [
        {"name": "run", "syntax": "dokima \"Feature description\" [dir]", "description": "Run full pipeline for a feature"},
        {"name": "init", "syntax": "dokima init \"description\" [dir]", "description": "Project discovery & constitution"},
        {"name": "--add", "syntax": "dokima --add \"Feature\" [--priority=P1] [dir]", "description": "Add feature to roadmap (auto-priority, auto-deps)"},
        {"name": "--next", "syntax": "dokima --next [dir]", "description": "Build next feature from roadmap"},
        {"name": "--continuous", "syntax": "dokima --continuous [dir]", "description": "Full sprint: build + auto-merge + loop"},
        {"name": "--fix", "syntax": "dokima --fix [dir]", "description": "Fix BLOCKED PR: detect blockers, fix, verify"},
        {"name": "--status", "syntax": "dokima --status [dir]", "description": "Show pipeline state"},
        {"name": "--stop", "syntax": "dokima --stop [dir]", "description": "Graceful stop after current feature"},
        {"name": "--kill", "syntax": "dokima --kill [dir]", "description": "Emergency kill (SIGTERM then SIGKILL)"},
        {"name": "--list-crons", "syntax": "dokima --list-crons", "description": "List all scheduled pipelines"},
        {"name": "--version", "syntax": "dokima --version", "description": "Print version and exit"},
        {"name": "--upgrade", "syntax": "dokima --upgrade", "description": "Check for newer version and show upgrade instructions"},
    ],
    "flags": [
        {"flag": "--interactive", "args": None, "env_var": None, "description": "Show human gate (with --next/--continuous)"},
        {"flag": "--answers", "args": "<file>", "env_var": None, "description": "Resume from saved interview state"},
        {"flag": "--fix-all", "args": None, "env_var": "PANEL_FIX_ALL", "description": "Include SHOULD FIX items (with --fix)"},
        {"flag": "--skip-autofix", "args": None, "env_var": "PANEL_SKIP_AUTOFIX", "description": "Disable auto-fix loopback (nm + TL phases)"},
        {"flag": "--force-full", "args": None, "env_var": "PANEL_FORCE_FULL", "description": "Run all 5 phases regardless of depth gating"},
        {"flag": "--skip-auto-archive", "args": None, "env_var": "PANEL_SKIP_AUTO_ARCHIVE", "description": "Don't auto-archive merged specs"},
        {"flag": "--skip-human-gate", "args": None, "env_var": "PANEL_SKIP_HUMAN_GATE", "description": "Skip Human Gate prompt (for automation)"},
        {"flag": "--resume", "args": None, "env_var": "PANEL_RESUME", "description": "Resume from last checkpoint (re-runs incomplete phases only)"},
        {"flag": "--no-resume", "args": None, "env_var": "PANEL_NO_RESUME", "description": "Ignore any existing checkpoint and start fresh"},
        {"flag": "--max-parallel", "args": "N", "env_var": "PANEL_MAX_PARALLEL", "description": "Max parallel coder agents (default: 5)"},
        {"flag": "--base-branch", "args": "<b>", "env_var": "PANEL_BASE_BRANCH", "description": "Override default branch for PR base"},
    ],
    "env_vars": [
        {"name": "PANEL_FIX_ALL", "description": "Include SHOULD FIX items", "related_flag": "--fix-all"},
        {"name": "PANEL_SKIP_AUTOFIX", "description": "Disable auto-fix loopback", "related_flag": "--skip-autofix"},
        {"name": "PANEL_FORCE_FULL", "description": "Run all 5 phases regardless of depth gating", "related_flag": "--force-full"},
        {"name": "PANEL_SKIP_AUTO_ARCHIVE", "description": "Don't auto-archive merged specs", "related_flag": "--skip-auto-archive"},
        {"name": "PANEL_SKIP_HUMAN_GATE", "description": "Skip Human Gate prompt", "related_flag": "--skip-human-gate"},
        {"name": "PANEL_RESUME", "description": "Resume from last checkpoint", "related_flag": "--resume"},
        {"name": "PANEL_NO_RESUME", "description": "Ignore existing checkpoint and start fresh", "related_flag": "--no-resume"},
        {"name": "PANEL_MAX_PARALLEL", "description": "Max parallel coder agents", "related_flag": "--max-parallel"},
        {"name": "PANEL_BASE_BRANCH", "description": "Override default branch for PR base", "related_flag": "--base-branch"},
        {"name": "PANEL_FALLBACK_STRATEGIST", "description": "Fallback model for strategist role", "related_flag": None},
        {"name": "PANEL_FALLBACK_CODER", "description": "Fallback model for coder role", "related_flag": None},
        {"name": "PANEL_FALLBACK_TECH_LEAD", "description": "Fallback model for tech-lead role", "related_flag": None},
    ],
}


def _sanitize_prompt(text):
    """Strip known injection patterns from user-supplied text before it enters agent prompts.
    Strips backtick-escaped shell commands, markdown code blocks with dangerous commands,
    and SYSTEM:/OVERRIDE: prefix injection attempts. Logs a warning on any strip."""
    if not text:
        return text
    original = text
    # Strip SYSTEM: / OVERRIDE: prefix injection (case-insensitive, word-boundary)
    text = re.sub(r'\b(?:SYSTEM|OVERRIDE)\s*:\s*', '', text, count=0, flags=re.IGNORECASE)
    # Strip backtick content that looks like a shell command (has spaces, pipes,
    # redirects, or starts with $ for expansion). Single-word inline code like
    # `--help-json` or `config.yaml` is legitimate Markdown — don't strip it.
    SHELL_PATTERN = r'[\s|&;<>$]'
    text = re.sub(r'`[^`]*' + SHELL_PATTERN + r'[^`]*`', '', text)
    # Strip markdown code blocks (```cmd``` or ```\ncmd\n```) containing dangerous patterns
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text).strip()
    if text != original:
        stripped = original[:80].strip()
        print(f"  WARNING: Sanitized prompt injection from feature text: {stripped!r}", file=sys.stderr, flush=True)
    return text


def _validate_project_dir(path):
    """Verify path is a real directory containing .git (a valid git repo).
    Returns True if valid, False otherwise."""
    if not path:
        return False
    if not os.path.isdir(path):
        return False
    git_dir = os.path.join(path, ".git")
    if not os.path.isdir(git_dir):
        return False
    return True

def _redact_secrets(text):
    """Strip GH_TOKEN, GITHUB_TOKEN, and API_SERVER_KEY values from text.
    Looks up current values from the environment at call time (not cached).
    Redacts with [REDACTED]. Returns the redacted text unmodified if no tokens found."""
    if not text:
        return text
    tokens = []
    for env_name in ("GH_TOKEN", "GITHUB_TOKEN", "API_SERVER_KEY"):
        val = os.environ.get(env_name, "")
        if val:
            tokens.append(val)
    if not tokens:
        return text
    result = text
    for tok in tokens:
        result = result.replace(tok, "[REDACTED]")
    return result

def _write_log_line(text):
    """Append a redacted line to OUTPUT_LOG. Creates the file if it doesn't exist."""
    global _LOG_FILE_HANDLE
    try:
        if _LOG_FILE_HANDLE is None:
            _LOG_FILE_HANDLE = open(OUTPUT_LOG, "a")
            os.chmod(OUTPUT_LOG, 0o600)
        _LOG_FILE_HANDLE.write(text + "\n")
        _LOG_FILE_HANDLE.flush()
    except Exception:
        pass

def load_key():
    # Allow test patching via dokima.load_key override (F022b)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, 'load_key', None)
        if override is not None and override is not load_key:
            return override()
    env_path = os.path.join(PROFILES, "work", ".env")
    if not os.path.exists(env_path):
        return ""
    key_prefix = 'API_SERVER_KEY' + '='
    with open(env_path) as f:
        for line in f:
            if line.startswith(key_prefix):
                return line.strip().split("=", 1)[1]
    return ""

def load_github_token():
    # Allow test patching via dokima.load_github_token override (F022b)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, 'load_github_token', None)
        if override is not None and override is not load_github_token:
            return override()
    env_path = os.path.join(PROFILES, "work", ".env")
    if not os.path.exists(env_path):
        return ""
    prefix = 'GH_TOKEN' + '='
    with open(env_path) as f:
        for line in f:
            if line.startswith(prefix) and not line.startswith("#"):
                return line.strip().split("=", 1)[1]
    return ""

def git(*args, **kwargs):
    """Run git in PROJECT_DIR. Returns (stdout, stderr, returncode)."""
    # Allow test patching via dokima.git override (F022 modular refactor)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, 'git', None)
        if override is not None and override is not git:
            return override(*args, **kwargs)

    result = subprocess.run(["git", "-C", PROJECT_DIR] + list(args),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def gh(*args, **kwargs):
    """Run gh CLI with GH_TOKEN. Returns (stdout, stderr, returncode)."""
    # Allow test patching via dokima.gh override (F022 modular refactor)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, 'gh', None)
        if override is not None and override is not gh:
            return override(*args, **kwargs)

    global _GH_TOKEN_CACHE
    env = os.environ.copy()
    if _GH_TOKEN_CACHE is None:
        _GH_TOKEN_CACHE = load_github_token()
    if _GH_TOKEN_CACHE:
        env["GH_TOKEN"] = _GH_TOKEN_CACHE
    result = subprocess.run(["gh"] + list(args),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30, env=env)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def _safe_run(cmd_str: str, cwd: str, timeout: int = 300):
    """Safely run a command string without shell injection.
    Uses shlex.split to parse into argument list.
    Returns a CompletedProcess-like object. On timeout, returns object
    with returncode=124 and timeout error message in stdout."""
    # Allow test patching via dokima._safe_run override (F022 modular refactor)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, '_safe_run', None)
        if override is not None and override is not _safe_run:
            # Patched in tests — call the mock with the same signature
            return override(cmd_str, cwd, timeout=timeout)

    import subprocess as _sp
    try:
        args = shlex.split(cmd_str)
        return _sp.run(args, stdout=_sp.PIPE, stderr=_sp.STDOUT,
                       universal_newlines=True, timeout=timeout, cwd=cwd)
    except _sp.TimeoutExpired as e:
        # Return a synthetic CompletedProcess so callers can check returncode
        result = _sp.CompletedProcess(args=shlex.split(cmd_str), returncode=124)
        result.stdout = f"TIMEOUT: {e}"
        result.stderr = ""
        return result
    except Exception as e:
        print(f"  _safe_run: failed for '{cmd_str[:100]}': {e}")
        raise

def slugify(text):
    import hashlib
    base = re.sub(r'[^a-z0-9-]', '', text.lower().replace(" ", "-"))[:40]
    if len(text) > 40:
        h = hashlib.md5(text.encode()).hexdigest()[:8]
        return f"{base}-{h}"
    return base

def extract_pr_sections(spec_text: str, feature: str) -> str:
    """Extract Why, Impact, and What Changed from the strategist's spec.
    Returns markdown sections: ## Why, ## Impact, ## What Changed.
    Handles both modern (## N. Section) and legacy (Field:) formats."""

    # 1. ## Why — feature purpose
    why = f"## Why\n\n{feature}"
    # Legacy: Position: <text>
    pos_m = re.search(
        r'Position:\s*(.+?)(?=\n\s*\n\s*(?:\d\.\s*DECISION|DECISION|IMPACT|CONFIDENCE|### Task|Task \d|\Z))',
        spec_text, re.DOTALL | re.IGNORECASE)
    if pos_m:
        pos = pos_m.group(1).strip()
        pos = re.sub(r'\s+', ' ', pos)
        if len(pos) > 400:
            pos = pos[:397] + "..."
        why += f"\n\n{pos}"

    # 2. ## Impact — what's affected (paragraph under ## N. Impact header)
    impact = ""
    # Modern: ^## N. Impact (section header, not **Impact:** metadata)
    imp_m = re.search(
        r'^##\s*\d*\.?\s*Impact\s*\n+(.+?)(?=\n##\s|\n###\s|\n\*\*Confidence|\Z)',
        spec_text, re.DOTALL | re.IGNORECASE | re.MULTILINE)
    if imp_m:
        impact_text = imp_m.group(1).strip()
        if impact_text:
            impact = f"## Impact\n\n{impact_text}"
    if not impact:
        # Legacy: Impact: <text> (colon format)
        imp_m = re.search(
            r'Impact:\s*(.+?)(?=\n\s*\n|\n(?:What Changed|Confidence|### Task|\Z))',
            spec_text, re.DOTALL | re.IGNORECASE)
        if imp_m and imp_m.group(1).strip():
            impact = f"## Impact\n\n{imp_m.group(1).strip()}"
    if not impact:
        # Fallback: Executive Summary section
        exec_m = re.search(
            r'^##?\s*Executive\s+Summary\s*\n+(.+?)(?=\n##\s|\n###\s|\n\*\*Confidence|\Z)',
            spec_text, re.DOTALL | re.IGNORECASE | re.MULTILINE)
        if exec_m and exec_m.group(1).strip():
            impact = f"## Impact\n\n{exec_m.group(1).strip()}"
    if not impact:
        # Fallback: Position: <text> (used in older spec formats)
        pos_m = re.search(
            r'Position:\s*(.+?)(?=\n\s*\n\s*(?:F\d{3}:|\Z))',
            spec_text, re.DOTALL | re.IGNORECASE)
        if pos_m and pos_m.group(1).strip():
            text = pos_m.group(1).strip()
            # Clean up: remove internal newlines, truncate
            text = re.sub(r'\n\s+', ' ', text)
            if len(text) > 500:
                text = text[:497] + "..."
            impact = f"## Impact\n\n{text}"

    # 3. ## What Changed — bullet list under ## N. What Changed header
    what_changed = ""
    # Modern: ^## N. What Changed (bullet list until next ## or EOF)
    wc_m = re.search(
        r'^##\s*\d*\.?\s*What\s+Changed\s*\n+((?:\s*[-*]\s*.+(?:\n|$))+)',
        spec_text, re.IGNORECASE | re.MULTILINE)
    if wc_m:
        what_changed = f"## What Changed\n{wc_m.group(1).strip()}"
    if not what_changed:
        # Legacy: What Changed: <bullet list>
        wc_m = re.search(
            r'What Changed:\s*\n((?:\s*[-*]\s*.+\n?)+)',
            spec_text, re.IGNORECASE)
        if wc_m:
            what_changed = f"## What Changed\n{wc_m.group(1).strip()}"

    parts = [why]
    if impact:
        parts.append(impact)
    if what_changed:
        parts.append(what_changed)

    result = "\n\n".join(parts)
    if len(result) < 100:
        result = f"## Why\n\n{feature}\n\n## Impact\n\nSee What Changed below.\n\n## What Changed\n\nSee diff for details."
    return result

def extract_agent_messages(session_output: str, last_only: bool = False) -> str:
    """Extract agent messages from hermes session transcript, stripping noise
    (prompt echo, tool output, init markers). Keeps ALL agent reasoning.

    When last_only=True (spec extraction), returns only the LAST agent message
    — which is the final spec output, free of intermediate exploration chatter."""
    # Hermes boxes: ╭─ ⚕ Hermes ──...──╮  ...content...  ╰──...──╯
    messages = re.findall(r'╭─ ⚕ Hermes .+?╮\n(.*?)╰─+╯', session_output, re.DOTALL)
    if messages:
        if last_only:
            return messages[-1].strip()
        return "\n\n".join(m.strip() for m in messages if m.strip())
    # Fallback for unknown format: return raw output
    return session_output

def clean_spec_content(raw: str) -> str:
    """Strip model thinking, Ponytail Guard verdicts, and session metadata
    from strategist output — keep only the actual spec content."""
    # Strip text before the first markdown header (agent exploration chatter)
    header_match = re.search(r'^#\s+', raw, re.MULTILINE)
    if header_match:
        raw = raw[header_match.start():]
    # Remove session resume text and everything after
    raw = re.sub(r'\nResume this session with:.*', '', raw, flags=re.DOTALL)
    # Remove Ponytail Guard blocks
    raw = re.sub(r'\n\s*Ponytail Guard verdict:.*?(\n\n|\Z)', '\n', raw, flags=re.DOTALL)
    # Remove model sign-off/chatter lines — only strip the single line, not everything after
    chatter_patterns = [
        r'The spec is ready.*',
        r'Do you want me to.*',
        r'Shall I.*',
        r'Let me know if.*',
        r'Would you like me to.*',
        r'I can make changes.*',
        r'Is there anything.*',
        r'Feel free to.*',
    ]
    for pat in chatter_patterns:
        raw = re.sub(rf'\n\s*{pat}\n?', '\n', raw, flags=re.IGNORECASE)
    # Strip leading/trailing blank lines
    raw = raw.strip()
    return raw

def verify_spec_quality(spec_text: str, confidence: str = "Medium") -> tuple:
    """Verify spec quality against structural and content gates.

    Checks that the spec has required section headers:
    - Impact section (## Impact or ## N. Impact)
    - What Changed section (## What Changed or ## N. What Changed)
    - Task breakdown headers (### Task N:)

    Also checks:
    - Task field completeness (Files, Dependencies, Parallelizable)
    - PR body quality: detect thin fallback from extract_pr_sections()
    - Brevity: warns if spec exceeds confidence-based char threshold

    Also checks PR body quality:
    - Detects when extract_pr_sections() returns thin fallback
      despite spec having >=200 chars of real Impact + What Changed content.

    Args:
        spec_text: The spec content to check.
        confidence: Confidence level ("High", "Medium", "Low").

    Returns:
        (passed: bool, failures: list[str]) — True + empty list means clean.
        Brevity warnings appear in failures but passed remains True (soft warning).
    """
    failures = []

    # Check 1: Impact section — ## Impact or ## N. Impact
    if not re.search(r'##\s+\d*\.?\s*Impact', spec_text):
        failures.append("Missing: Impact section")

    # Check 2: What Changed section — ## What Changed or ## N. What Changed
    if not re.search(r'##\s+\d*\.?\s*What Changed', spec_text):
        failures.append("Missing: What Changed section")

    # Check 3: Task breakdown headers — ### Task N:
    if not re.search(r'###\s+Task\s+\d+:', spec_text):
        failures.append("Missing: Task N: headers")

    # Check 4: Task field completeness — verify task blocks have all required fields
    # Parse task blocks using same approach as TaskDAG.parse
    task_block_pattern = re.compile(
        r'^\s*(?:###\s*)?Task\s*(\d+):[ \t]*(.*?)\n'
        r'(.*?)(?=^\s*(?:###\s*)?Task\s*\d+|^\s*####\s|\Z)',
        re.DOTALL | re.MULTILINE
    )
    for m in task_block_pattern.finditer(spec_text):
        tid = m.group(1)
        desc = m.group(2).strip()
        body = m.group(3)

        # Check description (task title)
        if not desc:
            failures.append(f"Task {tid}: missing Description field")

        # Check Files field
        files_m = re.search(r'^\s*(?:\*\*)?Files?:?(?:\*\*)?[ \t]*(.*?)\s*$', body, re.MULTILINE)
        if not files_m or not files_m.group(1).strip():
            failures.append(f"Task {tid}: missing Files field")

        # Check Dependencies field
        deps_m = re.search(r'^\s*(?:\*\*)?Dependencies?:?(?:\*\*)?[ \t]*(.*?)\s*$', body, re.MULTILINE)
        if not deps_m or not deps_m.group(1).strip():
            failures.append(f"Task {tid}: missing Dependencies field")

        # Check Parallelizable field
        par_m = re.search(r'^\s*(?:\*\*)?Parallelizable?:?(?:\*\*)?[ \t]*(.*?)\s*$', body, re.MULTILINE)
        if not par_m or not par_m.group(1).strip():
            failures.append(f"Task {tid}: missing Parallelizable field")

    passed = len(failures) == 0
    return passed, failures

def _check_pr_body_quality(spec_text: str, failures: list) -> None:
    """Check if extract_pr_sections() returns thin fallback despite spec having
    >=200 chars of real Impact + What Changed content.

    extract_pr_sections requires bullet items for What Changed sections.
    If the section contains prose (no bullets), extract_pr_sections won't
    capture it and returns the thin fallback. This check independently
    extracts content with a broader pattern and flags the discrepancy.

    Args:
        spec_text: The full spec text.
        failures: Accumulated failure list (mutated in place).
    """
    pr_body = extract_pr_sections(spec_text, "PR Body")
    is_thin_fallback = len(pr_body) < 100 and "See diff for details" in pr_body
    if not is_thin_fallback:
        return

    # Independently extract Impact + What Changed content with broader patterns
    # (no bullet requirement for What Changed — extract_pr_sections requires bullets)
    impact_m = re.search(
        r'^##\s*\d*\.?\s*Impact\s*\n+(.+?)(?=\n##\s|\n###\s|\Z)',
        spec_text, re.DOTALL | re.IGNORECASE | re.MULTILINE
    )
    wc_m = re.search(
        r'^##\s*\d*\.?\s*What\s+Changed\s*\n+(.+?)(?=\n##\s|\n###\s|\Z)',
        spec_text, re.DOTALL | re.IGNORECASE | re.MULTILINE
    )

    impact_len = len(impact_m.group(1).strip()) if impact_m else 0
    wc_len = len(wc_m.group(1).strip()) if wc_m else 0

    if impact_len + wc_len >= 200:
        failures.append(
            "PR body degraded to fallback despite spec having real content."
        )

def detect_repo():
    """Extract owner/repo from git remote origin."""
    # Allow test patching via dokima.detect_repo override (F022b)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, 'detect_repo', None)
        if override is not None and override is not detect_repo:
            return override()
    result = subprocess.run(["git", "-C", PROJECT_DIR, "remote", "get-url", "origin"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=10)
    if result.returncode == 0:
        url = result.stdout.strip()
        m = re.search(r'github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$', url)
        if m:
            return m.group(1)
    print("WARNING: Could not detect GitHub repo from git remote. Some gh commands may fail.")
    return None

def detect_commands():
    """Read test/build/lint commands from AGENTS.md in PROJECT_DIR."""
    test_cmd = "npm test"
    build_cmd = "npm run build"
    lint_cmd = "npm run lint"
    agents_path = os.path.join(PROJECT_DIR, "AGENTS.md")
    if os.path.exists(agents_path):
        with open(agents_path) as f:
            agent_content = f.read()
            # Primary: backtick-enclosed commands
            test_m = re.search(r'(?:[Uu]nit )?[Tt]est[s]?.*?:\s*`([^`]+)`', agent_content)
            build_m = re.search(r'(?:[Ff]ull )?[Bb]uild.*?:\s*`([^`]+)`', agent_content)
            lint_m = re.search(r'(?:[Ll]int).*?:\s*`([^`]+)`', agent_content)
            # Fallback: fenced code blocks after "Test:" / "Build:" / "Lint:" labels
            if not test_m:
                test_m = re.search(r'(?:[Uu]nit )?[Tt]est[s]?.*?:\s*```\s*(.+?)```', agent_content, re.DOTALL)
            if not build_m:
                build_m = re.search(r'(?:[Ff]ull )?[Bb]uild.*?:\s*```\s*(.+?)```', agent_content, re.DOTALL)
            if not lint_m:
                lint_m = re.search(r'(?:[Ll]int).*?:\s*```\s*(.+?)```', agent_content, re.DOTALL)
            if test_m:
                test_cmd = test_m.group(1).strip()
            if build_m:
                build_cmd = build_m.group(1).strip()
            if lint_m:
                lint_cmd = lint_m.group(1).strip()
    return test_cmd, build_cmd, lint_cmd

def _detect_referenced_repo(agents_path: str) -> str:
    """If this project documents an external system (e.g. dokima-docs documents dokima),
    parse AGENTS.md first line for a GitHub link, check if that repo exists locally,
    and return its AGENTS.md content + key architecture facts. Returns empty string
    if no referenced repo is found or accessible."""
    if not os.path.exists(agents_path):
        return ""
    with open(agents_path) as f:
        # Read first 10 lines — the reference is usually in the opening description
        header = "".join([f.readline() for _ in range(10)])
    # Match "Documentation site for [Name](https://github.com/owner/repo)"
    # or any markdown link with a github.com URL in the header
    gh_matches = list(re.finditer(
        r'https?://github\.com/([^/\s)]+)/([^/\s)]+?)(?:\.git)?(?:\)|[\s/#])',
        header[:3000]))
    if not gh_matches:
        return ""
    ref_context = ""
    for m in gh_matches:
        owner, repo = m.group(1), m.group(2)
        repo_name = repo.rstrip(')').rstrip('/')
        # Common local paths: ~/<repo>, ~/Projects/<repo>, /home/opc/<repo>
        candidates = [
            os.path.expanduser(f"~/{repo_name}"),
            os.path.expanduser(f"~/Projects/{repo_name}"),
        ]
        found = None
        for cand in candidates:
            if os.path.isdir(cand) and os.path.exists(os.path.join(cand, "AGENTS.md")):
                found = cand
                break
        if not found:
            continue
        try:
            with open(os.path.join(found, "AGENTS.md")) as ref_f:
                ref_agents = ref_f.read()[:4000]
            ref_context += ("\n\nEXTERNAL REFERENCE — This project documents {0}/{1}. "
                            "The REFERENCED SYSTEM lives at {2}. "
                            "Its AGENTS.md (below) is THE TRUTH — verify every claim against it. "
                            "If this reference contradicts what the project being documented says, "
                            "the reference wins.\n\n"
                            "REFERENCED AGENTS.md:\n{3}\n--- END EXTERNAL REFERENCE ---\n"
                            ).format(owner, repo_name, found, ref_agents)
        except Exception as e:
            ref_context += ("\n\nNOTE: Could not read AGENTS.md from {0}: {1}\n").format(found, e)
    return ref_context

def _lock_path(project_dir=None):
    """Project-scoped lock file path."""
    if project_dir:
        slug = os.path.basename(os.path.abspath(project_dir))
    else:
        try:
            slug = os.path.basename(os.path.abspath(PROJECT_DIR))
        except NameError:
            slug = "unknown"
    return f"/tmp/dokima-{slug or 'unknown'}.lock"

def _stop_path(project_dir=None):
    """Project-scoped stop signal file path."""
    if project_dir:
        slug = os.path.basename(os.path.abspath(project_dir))
    else:
        try:
            slug = os.path.basename(os.path.abspath(PROJECT_DIR))
        except NameError:
            slug = "unknown"
    return f"/tmp/dokima-{slug or 'unknown'}.stop"

def _checkpoint_path(slug):
    """Return the checkpoint file path for a given feature slug."""
    return f"/tmp/dokima-{slug}-checkpoint.json"

def save_checkpoint(slug, data):
    """Save checkpoint data to disk. If data is None, delete the checkpoint."""
    if data is None:
        delete_checkpoint(slug)
        return
    cpath = _checkpoint_path(slug)
    with open(cpath, "w") as f:
        json.dump(data, f)
    os.chmod(cpath, 0o600)

def load_checkpoint(slug):
    """Load checkpoint data from disk. Returns None if not found or invalid."""
    cpath = _checkpoint_path(slug)
    if not os.path.exists(cpath):
        return None
    try:
        with open(cpath) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, ValueError):
        return None

def delete_checkpoint(slug):
    """Delete checkpoint file if it exists. No error if missing."""
    cpath = _checkpoint_path(slug)
    if os.path.exists(cpath):
        os.remove(cpath)

def _phase_should_skip(phases_completed, phase_name, resume=None):
    """Check if a phase should be skipped during resume.
    Returns True if phase_name is in phases_completed AND resume is True.
    If resume is None (auto-detect) or False, never skip."""
    if not resume:
        return False
    return phase_name in phases_completed

def validate_checkpoint(slug):
    """Validate a stored checkpoint: branch exists, spec file exists.
    Returns True if valid, False otherwise."""
    data = load_checkpoint(slug)
    if not data:
        return False
    # Check spec file exists
    spec_path = data.get("spec_path", "")
    if not spec_path or not os.path.exists(spec_path):
        return False
    # Check branch exists via git
    branch = data.get("branch", "")
    if not branch:
        return False
    result = _safe_run("git rev-parse --verify " + shlex.quote(branch), cwd=PROJECT_DIR)
    if result.returncode != 0:
        return False
    return True

def acquire_lock():
    """Try to acquire an advisory lock. Returns (held, fd)."""
    max_attempts = 3
    for attempt in range(max_attempts):
        # Capture lock mtime before truncation (F023: lock-age auto-cleanup)
        lp = _lock_path()
        lock_mtime = None
        if os.path.exists(lp):
            try:
                lock_mtime = os.path.getmtime(lp)
            except OSError:
                pass

        fd = open(lp, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fd.write(f"{os.getpid()}\n")
            fd.flush()
            os.chmod(lp, 0o600)
            return True, fd
        except (IOError, OSError):
            fd.close()
            try:
                with open(lp) as lf:
                    stale_pid = lf.read().strip()
            except Exception:
                stale_pid = ""
            if stale_pid and stale_pid.isdigit():
                if _check_pid(stale_pid) and _verify_pid_owner(int(stale_pid)):
                    # F023: Lock-age auto-cleanup — handle SIGKILL + PID recycled edge case
                    lock_max_age = int(os.environ.get("PANEL_LOCK_MAX_AGE_SECS", "43200"))
                    if lock_mtime is not None:
                        lock_age = time.time() - lock_mtime
                        if lock_age > lock_max_age:
                            print(f"  Stale lock (> {lock_max_age}s old, PID {stale_pid} recycled) — removing and retrying...")
                            try:
                                os.remove(lp)
                            except OSError:
                                pass
                            continue
                    print(f"ERROR: Panel already running (PID {stale_pid}). If stuck, remove {lp}.")
                    sys.exit(1)
                else:
                    print(f"  Stale lock (PID {stale_pid} is dead/wrong process) — removing and retrying...")
                    try:
                        os.remove(lp)
                    except OSError:
                        pass
                    continue
            sys.exit(1)
    sys.exit(1)

def _cleanup_lock():
    """Release lock and restore stdout on interrupt or normal exit."""
    global _LOCK_FD, _LOG_FILE, _STDOUT_ORIG, _LOG_FILE_HANDLE
    # Also check dokima's _LOCK_FD (may be set by tests without syncing)
    dokima_mod = _IMPORTING_PANEL
    panel_fd = getattr(dokima_mod, '_LOCK_FD', None) if dokima_mod else None
    fd_to_close = _LOCK_FD or panel_fd
    if fd_to_close:
        try:
            fd_to_close.close()
        except Exception:
            pass
        _LOCK_FD = None
        # Sync to dokima module if loaded (F022 modular refactor)
        if dokima_mod is not None:
            dokima_mod._LOCK_FD = None
    try:
        os.remove(_lock_path())
    except OSError:
        pass
    if _STDOUT_ORIG:
        sys.stdout = _STDOUT_ORIG
    if _LOG_FILE:
        try:
            _LOG_FILE.close()
        except Exception:
            pass

def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM — clean up and exit."""
    print(f"\n  ⚠ Signal {signum} received — cleaning up...")
    _cleanup_lock()
    sys.exit(1)

def try_auto_merge(pr_url: str) -> str:
    """Try to merge a PR. Returns: 'merged', 'queued', 'failed'."""
    if not pr_url:
        return "failed"
    pr_num = pr_url.rstrip("/").split("/")[-1]
    if not pr_num.isdigit():
        print(f"  Cannot parse PR number from: {pr_url}")
        return "failed"
    if not REPO:
        print("  REPO not configured, cannot merge")
        return "failed"
    try:
        merge_stdout, merge_stderr, merge_rc = gh("pr", "merge", pr_num, "--repo", REPO,
                            "--merge", "--delete-branch")
    except Exception as e:
        print(f"  gh merge failed with exception: {e}")
        return "failed"
    if merge_rc == 0:
        print(f"  PR #{pr_num} merged")
        return "merged"
    merge_err_lower = (merge_stderr or "").lower()
    if any(kw in merge_err_lower for kw in
           ("required status", "required check", "status check", "required")):
        print(f"  PR #{pr_num} - branch protection requires CI. Queuing auto-merge...")
        try:
            _, queue_stderr, queue_rc = gh("pr", "merge", pr_num, "--repo", REPO,
                              "--auto", "--delete-branch")
        except Exception:
            print(f"  Auto-merge queue exception")
            return "failed"
        if queue_rc == 0:
            print(f"  PR #{pr_num} auto-merge queued")
            return "queued"
        print(f"  Auto-merge queue failed: {queue_stderr[:200]}")
        return "failed"
    print(f"  PR #{pr_num} merge failed: {(merge_stderr or 'unknown')[:200]}")
    return "failed"

def _supplement_pr_sections(pr_sections, project_dir, branch, default_branch):
    """Supplement thin PR sections with git diff summary. Returns enriched pr_sections string."""
    result = pr_sections
    if "## Impact" not in pr_sections or "## What Changed" not in pr_sections:
        try:
            diff_stat = subprocess.run(
                ["git", "-C", project_dir, "diff", "--stat", f"{default_branch}...{branch}"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                universal_newlines=True, timeout=15)
            diff_summary = diff_stat.stdout.strip()
            if diff_summary:
                if "## Impact" not in pr_sections:
                    result += f"\n\n## Impact\n\nMinimal — see What Changed."
                if "## What Changed" not in pr_sections:
                    result += f"\n\n## What Changed\n\n```\n{diff_summary}\n```"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
            print(f"  ⚠ _supplement_pr_sections: git diff failed ({e}) — proceeding without supplement", flush=True)
    return result

def _detect_default_branch(project_dir):
    """Detect default branch from origin/HEAD. Returns branch name string."""
    try:
        result = subprocess.run(
            ["git", "-C", project_dir, "symbolic-ref", "refs/remotes/origin/HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            universal_newlines=True, timeout=10)
        if result.returncode == 0:
            ref = result.stdout.strip()
            return ref.split("/")[-1] if "/" in ref else "master"
    except Exception:
        pass
    return "master"

def _set_gh_token():
    """Load GH_TOKEN and export to environment if available."""
    gh_token = load_github_token()
    if gh_token:
        os.environ["GH_TOKEN"] = gh_token

def show_help():
    print(HELP_TEXT)
    sys.exit(0)

def show_help_json():
    """Print CLI_METADATA as formatted JSON and exit."""
    print(json.dumps(CLI_METADATA, indent=2))
    sys.exit(0)

def check_upgrade():
    """--upgrade handler: check for newer version on GitHub."""
    install_dir = os.path.join(REAL_HOME, ".local", "share", "dokima")
    git_dir = os.path.join(install_dir, ".git")
    if not os.path.isdir(git_dir):
        print("Not installed via install.sh — cannot check for upgrades")
        sys.exit(0)

    # Check git is available
    git_path = shutil.which("git")
    if not git_path:
        print("git required for --upgrade")
        sys.exit(1)

    # Fetch tags from origin
    try:
        subprocess.run(
            [git_path, "-C", install_dir, "fetch", "--tags", "origin"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30
        )
    except subprocess.TimeoutExpired:
        print("Could not check for updates: network timeout")
        sys.exit(1)
    except OSError:
        print("Could not check for updates: network error")
        sys.exit(1)

    # Read installed VERSION
    installed_version_path = os.path.join(install_dir, "VERSION")
    try:
        with open(installed_version_path) as f:
            installed_version = f.read().strip()
    except OSError:
        print("Could not determine installed version (VERSION file missing)")
        sys.exit(1)

    # Get latest semver tag
    try:
        tag_result = subprocess.run(
            [git_path, "-C", install_dir, "tag", "--sort=-v:refname"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            universal_newlines=True, timeout=10
        )
        tags = tag_result.stdout.strip().split("\n") if tag_result.stdout.strip() else []
        # Filter to vX.Y.Z patterns only
        semver_tags = [t for t in tags if re.match(r'^v\d+\.\d+\.\d+$', t)]
    except (subprocess.TimeoutExpired, OSError):
        print("Could not check for updates: failed to fetch tags")
        sys.exit(1)

    if not semver_tags:
        print("No releases found")
        sys.exit(0)

    latest_tag = semver_tags[0]
    latest_version = latest_tag.lstrip("v")

    # Compare versions
    if _version_newer(latest_version, installed_version):
        print(f"dokima v{latest_version} available (you have v{installed_version}) — "
              f"run: curl -sSL https://get.dokima.dev | bash")
    else:
        print(f"dokima v{installed_version} is up to date")
    sys.exit(0)

def _version_newer(a, b):
    """Return True if semver a > b. Both are 'X.Y.Z' strings."""
    try:
        parts_a = [int(x) for x in a.split(".")]
        parts_b = [int(x) for x in b.split(".")]
        return parts_a > parts_b
    except (ValueError, AttributeError):
        return False

def _bump_version(current, bump):
    """Increment semver string current (X.Y.Z) by bump type.

    bump must be one of: patch, minor, major.
    Returns new X.Y.Z string.  Raises ValueError on invalid input.
    """
    valid = {"patch", "minor", "major"}
    if bump not in valid:
        raise ValueError(
            f"Invalid bump type: {bump!r}. Must be one of: patch, minor, major"
        )

    current = current.strip()
    parts = current.split(".")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid semver version: {current!r}. Expected X.Y.Z format"
        )

    try:
        x, y, z = int(parts[0]), int(parts[1]), int(parts[2])
    except (ValueError, TypeError):
        raise ValueError(
            f"Invalid semver version: {current!r}. Parts must be integers"
        )

    if bump == "patch":
        z += 1
    elif bump == "minor":
        y += 1
        z = 0
    elif bump == "major":
        x += 1
        y = 0
        z = 0

    return f"{x}.{y}.{z}"

def _prune_old_tags(keep_count=10):
    """Prune old vX.Y.Z tags from origin, keeping only the newest keep_count.

    If fewer than keep_count semver tags exist on origin, silent no-op.
    Warns for each deleted tag.  Swallows individual push failures so one
    broken tag doesn't block the rest.
    """
    import re as _re

    # List tags sorted newest-first
    try:
        result = subprocess.run(
            ["git", "-C", PROJECT_DIR, "tag", "--sort=-v:refname"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            universal_newlines=True, timeout=10
        )
    except (subprocess.TimeoutExpired, OSError):
        return

    if result.returncode != 0:
        return

    tags = result.stdout.strip().split("\n") if result.stdout.strip() else []

    # Filter to vX.Y.Z pattern (semver release tags only)
    semver_tags = [t for t in tags if _re.match(r'^v\d+\.\d+\.\d+$', t)]

    if len(semver_tags) <= keep_count:
        return  # nothing to prune

    to_delete = semver_tags[keep_count:]

    for tag in to_delete:
        print(f"  Pruning old tag: {tag}")
        try:
            subprocess.run(
                ["git", "-C", PROJECT_DIR, "push", "origin", "--delete", tag],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=30
            )
        except (subprocess.TimeoutExpired, OSError):
            pass  # one failure shouldn't block the rest

def do_release(bump, project_dir, dry_run=False):
    """Automate the release workflow: bump VERSION, tag, push, and create GitHub Release.

    bump must be one of: patch, minor, major.
    On dry_run=True, prints the plan without making any changes.
    Exits with code 1 and a clear message on any precondition failure.
    """
    import shutil as _shutil

    # ── 0. Validate bump type ──────────────────────────────────────────
    valid_bumps = {"patch", "minor", "major"}
    if bump not in valid_bumps:
        print(f"Invalid bump type: {bump!r}. Must be one of: patch, minor, major")
        sys.exit(1)

    # ── 1. Validate project_dir is a git repo ──────────────────────────
    git_dir = os.path.join(project_dir, ".git")
    if not os.path.isdir(git_dir):
        print(f"Not a git repository: {project_dir}")
        sys.exit(1)

    # ── 2. gh CLI must be available ────────────────────────────────────
    if not _shutil.which("gh"):
        print("gh CLI required for --release. Install: https://cli.github.com")
        sys.exit(1)

    # ── 3. Detect default branch ───────────────────────────────────────
    default_branch = _detect_default_branch(project_dir)

    # ── 4. Validate: on default branch ─────────────────────────────────
    try:
        br_result = subprocess.run(
            ["git", "-C", project_dir, "rev-parse", "--abbrev-ref", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=10
        )
        current_branch = br_result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"Could not determine current branch: {e}")
        sys.exit(1)

    if current_branch != default_branch:
        print(
            f"Not on default branch. "
            f"Current: {current_branch}, expected: {default_branch}"
        )
        sys.exit(1)

    # ── 5. Validate: clean working tree ────────────────────────────────
    try:
        dirty_result = subprocess.run(
            ["git", "-C", project_dir, "diff-index", "--quiet", "HEAD", "--"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if dirty_result.returncode != 0:
            print("Working tree is dirty. Commit or stash changes first.")
            # Show git status for context
            try:
                st = subprocess.run(
                    ["git", "-C", project_dir, "status", "--short"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    universal_newlines=True, timeout=10
                )
                if st.stdout.strip():
                    print(st.stdout)
            except Exception:
                pass
            sys.exit(1)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"Could not check working tree: {e}")
        sys.exit(1)

    # ── 6. Validate: up to date with origin ────────────────────────────
    try:
        subprocess.run(
            ["git", "-C", project_dir, "fetch", "origin"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30
        )
        behind_result = subprocess.run(
            ["git", "-C", project_dir, "rev-list", f"HEAD..origin/{default_branch}"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            universal_newlines=True, timeout=10
        )
        behind = behind_result.stdout.strip()
        if behind:
            behind_count = len(behind.split("\n"))
            print(
                f"Behind origin/{default_branch} by {behind_count} commit(s). "
                "Pull latest changes first."
            )
            sys.exit(1)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"Could not reach origin: {e}")
        sys.exit(1)

    # ── 7. Read current VERSION ────────────────────────────────────────
    version_path = os.path.join(project_dir, "VERSION")
    if not os.path.isfile(version_path):
        print(f"VERSION file not found: {version_path}")
        sys.exit(1)

    try:
        with open(version_path) as f:
            current_version = f.read().strip()
    except OSError as e:
        print(f"Could not read VERSION file: {e}")
        sys.exit(1)

    # ── 8. Compute new version ─────────────────────────────────────────
    try:
        new_version = _bump_version(current_version, bump)
    except ValueError as e:
        print(f"Version bump failed: {e}")
        sys.exit(1)

    tag_name = f"v{new_version}"
    commit_msg = f"chore: bump version to {tag_name}"

    # ── 9. Dry-run: print plan and exit ────────────────────────────────
    if dry_run:
        print(f"[DRY RUN] Would bump VERSION: {current_version} -> {new_version}")
        print(f"[DRY RUN] Would commit:  {commit_msg}")
        print(f"[DRY RUN] Would tag:     {tag_name}")
        print(f"[DRY RUN] Would push:    origin/{default_branch} + {tag_name}")
        print(
            f"[DRY RUN] Would release: "
            f"gh release create {tag_name} --generate-notes "
            f"--title \"{tag_name}\" --target {default_branch}"
        )
        print("[DRY RUN] No changes made.")
        return

    # ── 10. Write new VERSION (atomic: temp + rename) ───────────────────
    try:
        version_dir = os.path.dirname(version_path)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".version", prefix="dokima-releas", dir=version_dir
        )
        with os.fdopen(fd, "w") as tf:
            tf.write(new_version + "\n")
        os.rename(tmp_path, version_path)
    except OSError as e:
        print(f"Could not write VERSION file: {e}")
        sys.exit(1)

    # ── 11. Git: add VERSION, commit, tag ──────────────────────────────
    git_cmds = [
        (["add", "VERSION"], "git add VERSION"),
        (["commit", "-m", commit_msg], f"git commit -m \"{commit_msg}\""),
        (["tag", "-a", tag_name, "-m", f"Release {tag_name}"],
         f"git tag -a {tag_name}"),
    ]
    for args, desc in git_cmds:
        try:
            result = subprocess.run(
                ["git", "-C", project_dir] + args,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=30
            )
            if result.returncode != 0:
                err = _redact_secrets(result.stderr.strip())
                print(f"{desc} failed: {err}")
                sys.exit(1)
        except (subprocess.TimeoutExpired, OSError) as e:
            print(f"{desc} failed: {e}")
            sys.exit(1)

    # ── 12. Push branch ────────────────────────────────────────────────
    try:
        push_result = subprocess.run(
            ["git", "-C", project_dir, "push", "origin", default_branch],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=60
        )
        if push_result.returncode != 0:
            err = _redact_secrets(push_result.stderr.strip())
            print(f"Push failed: {err}")
            sys.exit(1)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"Push failed: {e}")
        sys.exit(1)

    # ── 13. Push tag ───────────────────────────────────────────────────
    try:
        push_tag_result = subprocess.run(
            ["git", "-C", project_dir, "push", "origin", tag_name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=30
        )
        if push_tag_result.returncode != 0:
            err = _redact_secrets(push_tag_result.stderr.strip())
            print(f"Tag push failed: {err}")
            sys.exit(1)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"Tag push failed: {e}")
        sys.exit(1)

    # ── 14. Prune old tags ─────────────────────────────────────────────
    try:
        _prune_old_tags()
    except Exception:
        pass  # non-fatal — tag already pushed

    # ── 15. GitHub Release ─────────────────────────────────────────────
    stdout, stderr, rc = gh(
        "release", "create", tag_name,
        "--generate-notes",
        "--title", tag_name,
        "--target", default_branch,
    )
    if rc != 0:
        print(f"gh release create failed: {_redact_secrets(stderr)}")
        sys.exit(1)

    # ── 16. Summary ────────────────────────────────────────────────────
    # Extract the release URL from gh output
    release_url = ""
    for line in stdout.split("\n"):
        line = line.strip()
        if line.startswith("https://"):
            release_url = line
            break
    if release_url:
        print(f"Released dokima {tag_name} — {release_url}")
    else:
        print(f"Released dokima {tag_name}")

def _parse_status_md(status_path: str) -> tuple:
    """Parse STATUS.md into (header, active_entries, archived_entries).
       Returns defaults if file doesn't exist."""
    if not os.path.exists(status_path):
        header = f"# Specs Status — initialized {time.strftime('%Y-%m-%d %H:%M')}\n\n"
        return header, [], []

    with open(status_path) as f:
        content = f.read()

    # Extract header (everything before ## Active or ## Archived)
    header_end = len(content)
    for marker in ["\n## Active", "\n## Archived"]:
        idx = content.find(marker)
        if idx != -1 and idx < header_end:
            header_end = idx
    header = content[:header_end].strip() + "\n"

    # Parse active entries
    active = []
    active_m = re.search(r'## Active\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if active_m:
        for line in active_m.group(1).strip().split("\n"):
            line = line.strip()
            if line:
                active.append(line)

    # Parse archived entries
    archived = []
    archive_m = re.search(r'## Archived\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if archive_m:
        for line in archive_m.group(1).strip().split("\n"):
            line = line.strip()
            if line:
                archived.append(line)

    return header, active, archived

def _make_status_entry(feature_id: str, title: str, status: str, timestamp: str = "",
                       branch: str = "", pr_url: str = "", source: str = "panel") -> str:
    """Build a structured STATUS.md entry line."""
    ts = timestamp or time.strftime('%Y-%m-%d %H:%M')

    if status == "in_progress":
        branch_part = f", branch `{branch}`" if branch else ""
        return f"- **{feature_id}: {title}** — in progress since {ts}{branch_part} [{source}]"
    elif status == "done":
        if pr_url:
            pr_match = re.search(r'/pull/(\d+)', pr_url)
            pr_num = pr_match.group(1) if pr_match else "?"
            pr_part = f", PR [#{pr_num}]({pr_url})"
        else:
            pr_part = ""
        return f"- **{feature_id}: {title}** — done {ts}{pr_part} [{source}]"
    else:
        # pending or other
        branch_part = f", branch `{branch}`" if branch else ""
        return f"- **{feature_id}: {title}** — {status} {ts}{branch_part} [{source}]"

def update_status_md(status_path: str, feature_id: str, title: str, status: str,
                     timestamp: str = "", branch: str = "", pr_url: str = "",
                     source: str = "panel"):
    """Update STATUS.md for a feature lifecycle event.
       status: 'in_progress' or 'done'. Dedupes, preserves manual entries."""

    header, active, archived = _parse_status_md(status_path)

    new_entry = _make_status_entry(feature_id, title, status, timestamp,
                                   branch, pr_url, source)

    # Pattern to match existing panel-managed entries for this feature
    entry_pattern = re.compile(rf'^- \*\*{feature_id}:')

    # Remove existing entry for this feature from both sections
    active = [e for e in active if not entry_pattern.match(e)]
    archived = [e for e in archived if not entry_pattern.match(e)]

    # Place in correct section
    if status == "in_progress":
        active.append(new_entry)
    else:
        archived.append(new_entry)

    # Update header timestamp
    ts = timestamp or time.strftime('%Y-%m-%d %H:%M')
    header = re.sub(r'(# Specs Status).*', rf'\1 — last updated {ts}', header)

    # Build output
    output = header + "\n"
    output += "## Active\n"
    if active:
        output += "\n".join(active) + "\n"
    output += "\n## Archived\n"
    if archived:
        output += "\n".join(archived) + "\n"

    os.makedirs(os.path.dirname(status_path), exist_ok=True)
    with open(status_path, "w") as f:
        f.write(output)

def _check_pid(pid_str):
    """Check if PID is alive. Returns True/False."""
    # Allow test patching via dokima._check_pid override (F022 modular refactor)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, '_check_pid', None)
        if override is not None and override is not _check_pid:
            return override(pid_str)

    try:
        os.kill(int(pid_str), 0)
        return True
    except (OSError, ValueError):
        return False

def _verify_pid_owner(pid: int) -> bool:
    """Verify /proc/{pid}/comm is dokima or python. Returns True/False."""
    # Allow test patching via dokima._verify_pid_owner override (F022 modular refactor)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, '_verify_pid_owner', None)
        if override is not None and override is not _verify_pid_owner:
            return override(pid)

    try:
        with open(f"/proc/{pid}/comm") as f:
            comm = f.read().strip()
        return comm in ("dokima", "python3", "python")
    except Exception:
        return False

def _get_lock_state(project_dir):
    """Read lock file for a project. Returns (running, pid, info_dict)."""
    lp = _lock_path(project_dir)
    if not os.path.exists(lp):
        return False, "", {}
    try:
        with open(lp) as f:
            pid = f.read().strip()
    except Exception:
        return False, "", {}
    if not pid or not _check_pid(pid):
        try:
            os.remove(lp)
        except OSError:
            pass
        return False, "", {}

    # F023: Lock-age auto-cleanup for --status — handle SIGKILL + PID recycled
    lock_max_age = int(os.environ.get("PANEL_LOCK_MAX_AGE_SECS", "43200"))
    try:
        lock_age = time.time() - os.path.getmtime(lp)
        if lock_age > lock_max_age:
            try:
                os.remove(lp)
            except OSError:
                pass
            return False, "", {}
    except OSError:
        pass  # Can't stat — proceed with existing logic

    # Read roadmap for current feature
    info = {}
    roadmap_path = os.path.join(project_dir, "specs", "roadmap.md")
    if os.path.exists(roadmap_path):
        try:
            # Lazy import from dokima monolith — parse_roadmap lives there until
            # it's extracted into a roadmap.py module (future refactor).
            import importlib
            dokima_mod = importlib.import_module('dokima')
            parse_roadmap = dokima_mod.parse_roadmap
            features = parse_roadmap(roadmap_path)
            current = [f for f in features if f.status == "in_progress"]
            if current:
                info["feature"] = f"{current[0].id}: {current[0].title}"
            info["done"] = sum(1 for f in features if f.status == "done")
            info["total"] = len(features)
        except ImportError:
            pass  # dokima not importable (fresh extraction context)
        except Exception:
            pass  # roadmap parsing errors are non-fatal for lock state
    # Read log tail for phase
    if os.path.exists(OUTPUT_LOG):
        try:
            with open(OUTPUT_LOG) as lf:
                for line in reversed(lf.readlines()):
                    for marker in ["── Phase", "── Next Feature", "── Continuous"]:
                        if marker in line:
                            info["activity"] = line.strip()
                            break
                    if "activity" in info:
                        break
        except Exception:
            pass
    return True, pid, info

def handle_status(project_dir):
    """--status handler."""
    running, pid, info = _get_lock_state(project_dir)
    print(f"── Panel Status: {os.path.basename(os.path.abspath(project_dir))} ──")
    if running:
        # Compute elapsed
        elapsed = ""
        try:
            import time as _t
            st = os.stat(f"/proc/{pid}").st_ctime
            mins = int((_t.time() - st) // 60)
            elapsed = f"{mins}min" if mins < 120 else f"{mins//60}h{min%60}m"
        except Exception:
            elapsed = "?"
        print(f"State:       RUNNING (PID {pid}, {elapsed} elapsed)")
        if info.get("feature"):
            print(f"Feature:     {info['feature']}")
        if info.get("activity"):
            print(f"Activity:    {info['activity']}")
        if "done" in info:
            print(f"Roadmap:     {info['done']}/{info['total']} done")
        print(f"Log:         {OUTPUT_LOG}")
    else:
        print("State:       IDLE")
        if "done" in info:
            print(f"Roadmap:     {info['done']}/{info['total']} done")
    sys.exit(0)

def handle_stop(project_dir):
    """--stop handler."""
    running, pid, _ = _get_lock_state(project_dir)
    sp = _stop_path(project_dir)
    if not running:
        print(f"No pipeline running for {os.path.basename(os.path.abspath(project_dir))}.")
        sys.exit(0)
    if os.path.exists(sp):
        print(f"Stop signal already sent to PID {pid}.")
    else:
        with open(sp, "w") as f:
            f.write(f"stop at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        os.chmod(sp, 0o600)
        print(f"Stop signal sent to PID {pid}. Pipeline will stop after current feature.")
    sys.exit(0)

def handle_kill(project_dir):
    """--kill handler."""
    running, pid, _ = _get_lock_state(project_dir)
    if not running:
        print(f"No pipeline running for {os.path.basename(os.path.abspath(project_dir))}.")
        sys.exit(0)
    # Verify PID still belongs to dokima before signaling
    if not _verify_pid_owner(int(pid)):
        print(f"PID {pid} is not dokima (recycled?) — cleaning stale lock")
        try:
            os.remove(_lock_path(project_dir))
        except OSError:
            pass
        sys.exit(0)
    print(f"Sending SIGTERM to PID {pid}...")
    try:
        os.kill(int(pid), signal.SIGTERM)
        print(f"  SIGTERM sent successfully to PID {pid}")
    except OSError as e:
        print(f"  Failed to send SIGTERM: {e}")
    time.sleep(2)
    if _check_pid(pid) and _verify_pid_owner(int(pid)):
        print(f"Process still alive — sending SIGKILL to PID {pid}")
        try:
            os.kill(int(pid), signal.SIGKILL)
            print(f"  SIGKILL sent successfully to PID {pid}")
        except OSError as e:
            print(f"  Failed to send SIGKILL: {e}")
        time.sleep(1)
    elif not _check_pid(pid):
        print(f"  Process already exited")
    # Clean up
    try:
        os.remove(_lock_path(project_dir))
    except OSError:
        pass
    try:
        os.remove(_stop_path(project_dir))
    except OSError:
        pass
    print(f"Pipeline killed (was PID {pid})")
    sys.exit(0)

def handle_list_crons():
    """--list-crons handler."""
    # Parse crontab
    import subprocess as sp
    result = sp.run(["crontab", "-l"], stdout=sp.PIPE, stderr=sp.PIPE,
                    universal_newlines=True, timeout=10)
    cron_entries = []
    if result.returncode == 0:
        for line in result.stdout.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "dokima" in line:
                parts = line.split(None, 5)
                if len(parts) >= 6:
                    schedule = " ".join(parts[:5])
                    cmd = parts[5]
                    proj_match = re.search(r'(?:--continuous|--next)\s+(\S+)', cmd)
                    proj = os.path.expanduser(proj_match.group(1)) if proj_match else "cwd"
                    mode = "--continuous" if "--continuous" in cmd else "--next"
                    cron_entries.append((proj, schedule, mode))

    # Scan lock files for running state
    import glob as _glob
    lock_files = _glob.glob("/tmp/dokima-*.lock")
    running_projects = {}
    for lf in lock_files:
        try:
            slug = os.path.basename(lf).replace("dokima-", "").replace(".lock", "")
            with open(lf) as f:
                pid_str = f.read().strip()
            if pid_str and _check_pid(pid_str):
                running_projects[slug] = pid_str
            else:
                try:
                    os.remove(lf)
                except OSError:
                    pass
        except Exception:
            pass

    print("── Continuous Pipelines ──")
    if not cron_entries and not running_projects:
        print("No dokima pipelines found.")
        sys.exit(0)

    print(f"{'PROJECT':<30} {'SCHEDULE':<18} {'STATE'}")
    print("-" * 70)
    shown = set()
    for proj, schedule, mode in sorted(cron_entries):
        shown.add(os.path.basename(proj))
        slug = os.path.basename(os.path.abspath(proj))
        if slug in running_projects:
            state = f"RUNNING (PID {running_projects[slug]})"
        else:
            state = "IDLE"
        print(f"{proj:<30} {schedule:<18} {state}")
    # Show running projects not in crontab
    for slug, pid in running_projects.items():
        if slug not in shown:
            print(f"{slug:<30} {'manual':<18} RUNNING (PID {pid})")
    sys.exit(0)

def extract_file_paths(text):
    """Extract file paths from blocker descriptions or task lists.
    Matches:
    - Backtick-quoted paths like `src/app/layout.tsx:29-33`
    - **Files:** lines in task extracts: **Files:** path/to/file1, path/to/file2
    Returns sorted unique list of relative paths."""
    paths = set()
    # Pattern 1: backtick-quoted paths with optional line numbers
    for match in re.finditer(r'`([^`]+\.[a-z]{2,6}(?::\d+(?:-\d+)?)?)`', text):
        raw = match.group(1)
        # Strip line numbers
        path = re.sub(r':\d+(?:-\d+)?', '', raw)
        # Normalize: remove leading ./ or src/ if it's a relative reference
        if path.startswith('./'):
            path = path[2:]
        # Only keep paths that look like real files (not URLs or commands)
        # Require a / — bare filenames like 'layout.tsx' are ambiguous
        if '/' in path:
            if not path.startswith('http') and not path.startswith('git '):
                paths.add(path)
    # Pattern 2: **Files:** lines in task extracts (unquoted, comma-separated)
    for match in re.finditer(r'\*\*Files:\*\*\s+(.+)', text):
        files_line = match.group(1)
        for part in re.split(r'[,;]\s*', files_line):
            part = part.strip()
            # Strip "(NEW)" suffix
            part = re.sub(r'\s*\(NEW\)', '', part).strip()
            if not part.startswith('http') and not part.startswith('git '):
                paths.add(part)
    return sorted(paths)

def _hash_output(text):
    """Return MD5 hex digest of text for cycle detection (F023)."""
    import hashlib
    if text is None:
        text = ""
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()

def _detect_truncation(text):
    """Detect truncated coder output. Returns True if output appears truncated.

    A non-truncated output has a Report: line OR ends with terminal
    punctuation (., !, ?). None input returns False (safety); empty input
    returns True (coder crashed).
    """
    if text is None:
        return False
    if not text:
        return True
    # Check for Report: marker (case-insensitive, word boundary)
    if re.search(r'\bReport:', text, re.IGNORECASE):
        return False
    # Check if last non-whitespace character is terminal punctuation
    stripped = text.rstrip()
    if stripped and stripped[-1] in ('.', '!', '?'):
        return False
    return True

def _extract_code_context(spec_text, task_text, project_dir):
    """Extract relevant code snippets from line-range references in spec/task text.
    
    Parses patterns like:
    - "lines 4583–4594 in dokima"
    - "dokima:4583-4594"
    - "line 4584 of src/foo.py"
    
    Reads the target files and returns a code-context string for the coder prompt.
    Returns empty string if no line references found or files unreadable.
    """
    snippets = []
    # Pattern: "lines N–M" or "line N" with optional filename mention
    line_refs = re.findall(
        r'(?:lines?\s+|:)(\d{2,6})\s*(?:[–\-—]|\s*to\s*)\s*(\d{2,6})',
        spec_text + '\n' + task_text, re.IGNORECASE
    )
    if not line_refs:
        return ""
    
    # Build a set of (filename, start, end) to read — up to 5 snippets
    seen = set()
    for start, end in line_refs[:5]:
        start_i, end_i = int(start), int(end)
        if start_i > end_i:
            start_i, end_i = end_i, start_i
        # Expand context window: 3 lines before and after
        read_start = max(1, start_i - 3)
        read_end = end_i + 3
        
        # Try to find which file this refers to from task Files: fields
        files_m = re.findall(r'\*\*Files:\*\*\s*(.+)', task_text)
        target_files = []
        for fl in files_m:
            for f in re.split(r'[,;]\s*', fl):
                f = re.sub(r'\s*\(NEW\)', '', f).strip()
                if f and not f.startswith('http'):
                    target_files.append(f)
        
        for fname in target_files[:3]:
            key = (fname, read_start, read_end)
            if key in seen:
                continue
            seen.add(key)
            fpath = os.path.join(project_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath) as f:
                    lines = f.readlines()
                if read_start > len(lines):
                    continue
                actual_end = min(read_end, len(lines))
                chunk = ''.join(
                    f"{i}:{lines[i-1]}" 
                    for i in range(read_start, actual_end + 1)
                )
                if chunk.strip():
                    snippets.append(
                        f"```{fname}:{read_start}-{actual_end}\n{chunk}```"
                    )
            except Exception:
                pass
    
    if not snippets:
        return ""
    
    return (
        "\n### ⚡ Relevant Code (read ONLY these snippets — no full-file exploration)\n"
        + "\n".join(snippets)
        + "\n⚡ These are the EXACT lines to modify. Start here.\n"
    )

def generate_codebase_map(project_dir, full=False):
    """Generate a deterministic codebase map for the coder to read at session start.
    Uses file hashes to skip unchanged files (incremental mode).
    Output: specs/codebase-map.md with directory tree + per-file descriptions.
    Returns True if map was updated."""
    specs_dir = os.path.join(project_dir, "specs")
    map_path = os.path.join(specs_dir, "codebase-map.md")
    cache_path = os.path.join(specs_dir, ".map-cache.json")
    os.makedirs(specs_dir, exist_ok=True)

    # Load cache
    cache = {}
    if not full and os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                cache = json.loads(f.read())
        except (json.JSONDecodeError, IOError):
            cache = {}

    # Tech stack detection (heuristic)
    tech = []
    if os.path.exists(os.path.join(project_dir, "package.json")):
        try:
            with open(os.path.join(project_dir, "package.json")) as f:
                pkg = json.loads(f.read())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in deps: tech.append(f"Next.js {deps['next'].lstrip('^~')}")
            if "react" in deps: tech.append(f"React {deps['react'].lstrip('^~')}")
            if "tailwindcss" in deps: tech.append("Tailwind CSS")
            if "typescript" in deps: tech.append("TypeScript")
            if "vitest" in deps: tech.append("Vitest")
        except Exception:
            pass
    if os.path.exists(os.path.join(project_dir, "Cargo.toml")):
        tech.append("Rust")
    if os.path.exists(os.path.join(project_dir, "pyproject.toml")):
        tech.append("Python")

    # Read AGENTS.md for commands
    agents_path = os.path.join(project_dir, "AGENTS.md")
    test_cmd = build_cmd = lint_cmd = "?"
    if os.path.exists(agents_path):
        try:
            with open(agents_path) as f:
                agents = f.read()
            for cmd_name, prefix in [("test", "Test:"), ("build", "Build:"), ("lint", "Lint:")]:
                m = re.search(rf'{prefix}\s+(.+)', agents)
                if m:
                    cmd = m.group(1).strip().rstrip('.')
                    if cmd_name == "test": test_cmd = cmd
                    elif cmd_name == "build": build_cmd = cmd
                    elif cmd_name == "lint": lint_cmd = cmd
        except Exception:
            pass

    # Build directory tree — depth-first, insert parent headers as we go
    source_exts = {'.py', '.ts', '.tsx', '.js', '.jsx', '.rs', '.go', '.css', '.scss',
                   '.md', '.mdx', '.json', '.yaml', '.yml', '.toml', '.sh', '.bash'}
    skip_dirs = {'node_modules', '.git', '__pycache__', '.venv', 'venv', 'target',
                 '.next', 'dist', 'build', '.turbo', '.hermes', 'specs', '.map-cache.json'}

    tree_lines = []
    changed = False
    new_cache = {}
    analyzed_files = 0
    seen_dirs = set()
    last_dir = None

    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = sorted([d for d in dirnames if d not in skip_dirs and not d.startswith('.')])
        rel_dir = os.path.relpath(dirpath, project_dir)
        if rel_dir == '.':
            rel_dir = ''

        source_files = sorted([f for f in filenames if any(f.endswith(ext) for ext in source_exts)])
        if not source_files:
            continue

        # Insert ALL missing ancestor directory headers
        if rel_dir:
            parts = rel_dir.split(os.sep)
            for i in range(len(parts)):
                ancestor = os.sep.join(parts[:i+1])
                if ancestor not in seen_dirs:
                    seen_dirs.add(ancestor)
                    a_indent = "│   " * i
                    a_name = parts[i]
                    tree_lines.append(f"{a_indent}├── {a_name}/")

        d_depth = rel_dir.count(os.sep) if rel_dir else 0
        d_indent = "│   " * d_depth if d_depth > 0 else ""

        for j, fname in enumerate(source_files):
            rel_path = os.path.join(rel_dir, fname) if rel_dir else fname
            fpath = os.path.join(dirpath, fname)

            # Compute hash
            try:
                with open(fpath, 'rb') as f:
                    import hashlib
                    fhash = hashlib.md5(f.read()).hexdigest()
            except Exception:
                continue

            entry = cache.get(rel_path, {})
            old_hash = entry.get("hash", "")
            description = ""
            if old_hash == fhash and not full:
                description = entry.get("desc", "")
            else:
                try:
                    with open(fpath, errors='replace') as f:
                        content = f.read()
                    description = _describe_file(fname, content, rel_path)
                    changed = True
                except Exception:
                    description = ""

            new_cache[rel_path] = {"hash": fhash, "desc": description}

            is_last = (j == len(source_files) - 1)
            branch = "└── " if is_last else "├── "
            prefix = f"{d_indent}│   " if d_depth > 0 else ""
            tree_lines.append(f"{prefix}{branch}{fname}")
            if description:
                tree_lines[-1] += f"  — {description}"

            analyzed_files += 1

    if not changed and os.path.exists(map_path) and not full:
        return False  # Nothing changed, no need to rewrite

    # Write map
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    project_name = os.path.basename(os.path.abspath(project_dir))
    mode = "full" if full else "incremental"

    map_content = f"""## Project: {project_name}
## Tech: {', '.join(tech) if tech else 'detected at runtime'}
## Generated: {now} ({mode} | {analyzed_files} files)

## Tree
{chr(10).join(tree_lines)}

## Commands
- test: {test_cmd}
- build: {build_cmd}
- lint: {lint_cmd}
"""
    with open(map_path, 'w') as f:
        f.write(map_content)
    with open(cache_path, 'w') as f:
        json.dump(new_cache, f, indent=2)

    print(f"  📄 Codebase map: {map_path} ({analyzed_files} files, {mode})", flush=True)
    return True

def _describe_file(filename, content, rel_path):
    """Extract a one-line description from a source file.
    Uses exports, JSDoc, docstrings, and inferred roles."""
    lines = content.split('\n')
    ext = os.path.splitext(filename)[1]
    basename = os.path.splitext(filename)[0]

    # Try first docstring/comment
    for line in lines[:10]:
        line = line.strip()
        if line.startswith('# ') or line.startswith('// '):
            desc = line[2:].strip()
            if len(desc) > 5:
                return desc
        if line.startswith('/**') or line.startswith('/*'):
            continue
    # Try JSDoc
    for i, line in enumerate(lines):
        if '/**' in line and i + 1 < len(lines):
            next_line = lines[i + 1].strip().lstrip('*').strip()
            if next_line and len(next_line) > 5:
                return next_line

    # Exports for JS/TS
    if ext in ('.ts', '.tsx', '.js', '.jsx'):
        exports = []
        for line in lines[:50]:
            m = re.search(r'export\s+(?:default\s+)?(?:function|class|const|interface|type|enum)\s+(\w+)', line)
            if m:
                exports.append(m.group(1))
        if exports:
            return f"Exports: {', '.join(exports[:5])}"

    # Functions/classes for Python
    if ext == '.py':
        exports = []
        for line in lines[:50]:
            m = re.search(r'^(?:def|class)\s+(\w+)', line)
            if m:
                exports.append(m.group(1))
        if exports:
            return f"Exports: {', '.join(exports[:5])}"

    # Fallback: infer from filename
    role_map = {
        'layout': 'RootLayout: <html> + <body> + children',
        'page': 'Page component',
        'globals': 'Global styles / CSS variables',
        'config': 'Configuration / constants',
        'setup': 'Test setup / fixtures',
        'index': 'Entry point / barrel export',
    }
    for key, desc in role_map.items():
        if key in basename.lower():
            return desc

    return ""

def _extract_tl_verdict(tl_output: str) -> str:
    """Extract the LAST VERDICT from TL output.

    TL may quote earlier verdicts or change its mind mid-review.
    Always use the final verdict line.
    """
    if not tl_output or not tl_output.strip():
        return "UNKNOWN"
    if "[TIMEOUT:" in tl_output and "VERDICT:" not in tl_output.upper():
        return "TIMED_OUT"

    all_verdicts = re.findall(
        r'VERDICT:\s*(APPROVED|BLOCKED|CHANGES\s+REQUESTED)',
        tl_output.upper()
    )
    if not all_verdicts:
        return "UNKNOWN"

    last = all_verdicts[-1].strip()
    if "CHANGES" in last:
        return "CHANGES REQUESTED"
    elif "BLOCKED" in last:
        return "BLOCKED"
    return "APPROVED"

def _extract_tl_blockers(tl_output: str) -> list[str]:
    """Extract structured BLOCKER findings from TL output, filtering monologue.

    Handles varied TL output formats:
    - ### BLOCKERs (must fix before merge) — flexible header matching
    - ### Blockers — case-insensitive
    - Fallback: bold-numbered items near BLOCKER mentions

    Returns clean, human-readable blocker descriptions.
    """
    if not tl_output or not tl_output.strip():
        return []

    lines = tl_output.split("\n")
    blockers = []
    noise_patterns = [
        "now let me", "however,", "let me check", "let me look",
        "let me read", "let me verify", "this coverage gap",
        "previous reviewer", "previous review", "unfixed by",
        "severity: 🔴 blocker", "- severity: 🔴",
        "severity: blocker", "blocker:", "blockers found",
        "what the coder needs", "move ", "remove ", "add tests",
    ]

    # ── Pass 1: find ### section containing "BLOCKER" (flexible) ──
    in_blockers_section = False
    section_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_blockers_section:
                section_lines.append("")  # preserve paragraph breaks
            continue

        # Section header: any ### line containing BLOCKER (case-insensitive)
        if stripped.startswith("###") and "BLOCKER" in stripped.upper():
            in_blockers_section = True
            continue

        # Next section ends it (## or ### without BLOCKER)
        if in_blockers_section:
            if stripped.startswith("###") or stripped.startswith("## "):
                in_blockers_section = False
                continue
            if not any(p in stripped.lower() for p in noise_patterns):
                section_lines.append(stripped)

    # ── Pass 2: if section found, extract numbered + detail items ──
    if section_lines:
        current = None
        for sl in section_lines:
            # Bold-numbered item: **1. Title**
            if sl.startswith("**") and len(sl) > 4 and sl[2:3].isdigit():
                if current:
                    blockers.append(current)
                current = sl
            elif sl.startswith("- ") and current:
                # Detail line under current blocker
                detail = sl.lstrip("- ").rstrip(".")
                if " — " not in current:
                    current = current + " — " + detail
                elif detail not in current:
                    current = current + "; " + detail
            elif current and sl and not sl.startswith("#"):
                # Continuation line
                if not current.endswith(sl[:30]):
                    current = current + " " + sl.rstrip(".")
        if current:
            blockers.append(current)

    # ── Pass 3: fallback — line-level heuristics (original approach, relaxed) ──
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        if "BLOCKER" not in upper and "MUST FIX" not in upper:
            continue
        if any(p in stripped.lower() for p in noise_patterns):
            continue
        if (
            stripped.startswith("**") or
            (stripped.startswith("- ") and ":" in stripped[2:40]) or
            stripped.startswith("1.") or stripped.startswith("2.") or
            stripped.startswith("3.")
        ):
            blockers.append(stripped)

    # Merge bold-numbered title + detail
    merged = []
    for b in blockers:
        if b.startswith("**") and b[2:3].isdigit():
            merged.append(b)
        elif merged and not b.startswith("**"):
            merged[-1] = merged[-1] + " — " + b.lstrip("- ").rstrip(".")
        else:
            merged.append(b)

    # Strip ** markers from final output for clean PR formatting
    merged = [m.replace("**", "") for m in merged]

    return merged[:10]

# ── Profile configuration defaults (F012) ──
_PROFILE_CONFIGS = {
    "strategist": {
        "model.default": "deepseek-v4-pro",
        "model.provider": "deepseek",
        "agent.max_turns": "150",
        "agent.reasoning_effort": "high",
        "terminal.env_passthrough": "[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]",
    },
    "coder": {
        "model.default": "deepseek-v4-pro",
        "model.provider": "deepseek",
        "agent.max_turns": "150",
        "terminal.env_passthrough": "[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]",
    },
    "tech-lead": {
        "model.default": "deepseek-v4-pro",
        "model.provider": "deepseek",
        "agent.max_turns": "150",
        "terminal.env_passthrough": "[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]",
    },
    "nm": {
        "model.default": "deepseek-v4-pro",
        "model.provider": "deepseek",
        "agent.max_turns": "150",
        "terminal.env_passthrough": "[GH_TOKEN, GITHUB_TOKEN, HERMES_HOME, HOME]",
    },
}
_PROFILE_ORDER = ["strategist", "coder", "tech-lead", "nm"]


def ensure_profiles():
    """Create agent profiles (strategist, coder, tech-lead, nm) if they don't exist.
    Configures sensible defaults: model, provider, max_turns, env_passthrough.
    Strategist also gets agent.reasoning_effort=high.
    Idempotent — skips profiles that already exist.
    Non-interactive safe — works without a TTY."""
    # Allow test patching via dokima module (F022 modular refactor)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, 'ensure_profiles', None)
        if override is not None and override is not _ENSURE_PROFILES_ORIGINAL:
            return override()

    for name in _PROFILE_ORDER:
        profile_dir = os.path.join(PROFILES, name)

        # Check if profile already exists
        if os.path.isdir(profile_dir):
            print(f"  Profile '{name}' already exists — skipping", flush=True)
            continue

        # Create the profile
        print(f"  Creating profile: {name}", flush=True)
        try:
            result = subprocess.run(
                [HERMES_BIN, "profile", "create", name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=30
            )
            if result.returncode != 0:
                print(f"  WARNING: Failed to create profile '{name}': {result.stderr.strip()[:200]}", flush=True)
                continue
        except Exception as e:
            print(f"  WARNING: Failed to create profile '{name}': {e}", flush=True)
            continue

        # Apply configuration
        config = _PROFILE_CONFIGS.get(name, {})
        for key, value in config.items():
            try:
                subprocess.run(
                    [HERMES_BIN, "--profile", name, "config", "set", key, value],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    universal_newlines=True, timeout=30
                )
            except Exception as e:
                print(f"  WARNING: Failed to set {key} for '{name}': {e}", flush=True)

        print(f"  Profile '{name}' configured", flush=True)

    # Verify profiles exist after creation (for idempotency check on re-run)
    missing_after = [n for n in _PROFILE_ORDER
                     if not os.path.isdir(os.path.join(PROFILES, n))]
    if missing_after:
        print(f"  WARNING: Profiles still missing after creation attempt: {', '.join(missing_after)}", flush=True)

def deploy_profile_skills():
    """Deploy panel skills from PANEL_DIR/skills/ to profile skill directories.
    Idempotent — skips existing skill directories.
    nm's 'no-mistakes' skill goes to the global skills dir (~/.hermes/skills/)."""
    # Allow test patching via dokima module (F022 modular refactor)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, 'deploy_profile_skills', None)
        if override is not None and override is not _DEPLOY_PROFILE_SKILLS_ORIGINAL:
            return override()

    import shutil as _shutil

    skills_dir = os.path.join(PANEL_DIR, "skills")
    software_dev = "software-development"

    # (profile, skill, is_global) — is_global=True deploys to HERMES/skills/
    _SKILL_MAPPINGS = [
        ("strategist", "spec-strategist-lite", False),
        ("strategist", "ponytail-guard", False),
        ("coder", "ai-coding-best-practices-lite", False),
        ("tech-lead", "adversarial-review-lite", False),
        ("tech-lead", "ponytail-guard", False),
        ("nm", "no-mistakes", True),
    ]

    for profile, skill, is_global in _SKILL_MAPPINGS:
        src = os.path.join(skills_dir, skill)

        if is_global:
            dest_parent = os.path.join(HERMES, "skills", software_dev)
        else:
            dest_parent = os.path.join(PROFILES, profile, "skills", software_dev)
        dest = os.path.join(dest_parent, skill)

        if not os.path.isdir(src):
            print(f"  WARNING: Source skill not found: {skill} — skipping", flush=True)
            continue

        if os.path.isdir(dest):
            print(f"  Skill '{skill}' already deployed for {profile} — skipping", flush=True)
            continue

        os.makedirs(dest_parent, exist_ok=True)
        _shutil.copytree(src, dest)
        print(f"  Deployed skill '{skill}' → {profile}", flush=True)


def halt_and_revert(reason, phase, branch, task_ids=None, worktrees=None):
    """Revert all changes and print failure summary for orchestrator.

    Args:
        reason: Why the pipeline halted.
        phase: Which phase failed (e.g., 'PHASE 2 (Parallel Coders)').
        branch: The main feature branch to delete.
        task_ids: Optional list of task IDs. When provided, deletes task
                  branches (feat/<slug>-tN) before the main branch.
        worktrees: Optional WorktreeManager reference. When provided,
                   calls cleanup_all() to remove worktree directories.
    """
    # Allow test patching via dokima.halt_and_revert override (F022 modular refactor)
    dokima_mod = _IMPORTING_PANEL
    if dokima_mod is not None:
        override = getattr(dokima_mod, 'halt_and_revert', None)
        if override is not None and override is not halt_and_revert:
            return override(reason, phase, branch, task_ids=task_ids, worktrees=worktrees)

    print(f"\n{'═'*55}", flush=True)
    print(f"  PIPELINE HALTED — {phase} Failed", flush=True)
    print(f"{'═'*55}", flush=True)
    print(f"\nReason: {reason}", flush=True)
    print("\nReverting all changes...", flush=True)

    # Delete task branches first (feat/<slug>-tN)
    if task_ids:
        for tid in task_ids:
            task_branch = f"{branch}-t{tid}"
            try:
                git("branch", "-D", task_branch)
            except Exception:
                pass  # Branch might not exist if created before worktree

    git("checkout", DEFAULT_BRANCH)
    git("branch", "-D", branch)
    git("stash", "clear")
    print(f"  Branch '{branch}' deleted, back on master", flush=True)

    # Clean up worktree directories if manager provided
    if worktrees and task_ids:
        try:
            worktrees.cleanup_all(task_ids)
        except Exception:
            pass

    print("\n── Orchestrator Action Required ──", flush=True)
    print(f"  1. Review the failure context above", flush=True)
    print(f"  2. Diagnose root cause", flush=True)
    print(f"  3. Fix the issue (code, config, prompt, etc.)", flush=True)
    print(f"  4. Ask user for go-ahead before retrying", flush=True)
    print(f"\nFull log: {OUTPUT_LOG}", flush=True)


def archive_specs_for_feature(spec_path, branch, pr_url):
    """Move a feature's spec directory to archive/ if PR is merged.
    Returns True if archived, False otherwise."""
    if not pr_url:
        return False
    import shutil as _shutil
    pr_num = pr_url.rstrip("/").split("/")[-1]
    if not pr_num.isdigit():
        return False
    try:
        stdout, _, rc = gh("pr", "view", pr_num, "--json", "merged,state")
        if rc != 0 or not stdout.strip():
            return False
        import json as _json
        data = _json.loads(stdout)
        if data.get("merged") is True:
            parent_dir = os.path.dirname(spec_path)
            archive_dir = os.path.join(parent_dir, "archive")
            os.makedirs(archive_dir, exist_ok=True)
            dirname = os.path.basename(spec_path)
            archive_target = os.path.join(archive_dir, dirname)
            if os.path.exists(archive_target):
                if os.path.isdir(archive_target):
                    _shutil.rmtree(archive_target)
                else:
                    os.remove(archive_target)
            _shutil.move(spec_path, archive_target)
            return True
    except Exception:
        pass
    return False

# Module-level original references for delegation checks (F022 modular refactor)
_ENSURE_PROFILES_ORIGINAL = ensure_profiles
_DEPLOY_PROFILE_SKILLS_ORIGINAL = deploy_profile_skills

