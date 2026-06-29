"""Dokima agent module — agent spawning, API calls, provider fallback, session extraction.

All functions extracted from dokima monolith (F022: Modular Architecture).
Imports load_key, load_github_token, _redact_secrets, _write_log_line from utils.
"""
import sys, os, json, re, subprocess

from utils import load_key, load_github_token, _redact_secrets, _write_log_line, HERMES_BIN, OUTPUT_LOG

# ── Module-level globals (set by main()) ──────────
# Set by conftest._load_panel() — see utils.py _IMPORTING_PANEL docstring (F022b).
_IMPORTING_PANEL = None
API_KEY = ""
PANEL_PORT = {"strategist": 8647, "tech-lead": 8644, "coder": 8645, "nm": 8648}
FALLBACK_MODELS = {}

# ── provider failure detection ────────────────

_PROVIDER_FAILURE_PATTERNS = [
    re.compile(r'TIMEOUT[:\s]', re.IGNORECASE),
    re.compile(r'HTTP\s+[45]\d{2}', re.IGNORECASE),
    re.compile(r'5\d{2}\s+(Service Unavailable|Internal Server Error|Bad Gateway)', re.IGNORECASE),
    re.compile(r'429\s+Too Many Requests', re.IGNORECASE),
    re.compile(r'(40[13])\s+(Unauthorized|Forbidden)', re.IGNORECASE),
    re.compile(r'connection\s+refused', re.IGNORECASE),
    re.compile(r'upstream connect error|disconnect/reset before headers', re.IGNORECASE),
    re.compile(r'provider\.error', re.IGNORECASE),
    re.compile(r'model\s+not\s+(found|available)', re.IGNORECASE),
    re.compile(r'model\.not\.available', re.IGNORECASE),
    re.compile(r'service\s+unavailable', re.IGNORECASE),
]

# ── fallback model config ─────────────────────

FALLBACK_MODEL_RE = re.compile(r'^[a-zA-Z0-9_./-]+$')

def call_agent(port, system_prompt, user_prompt, model="deepseek-v4-pro", max_tokens=1500):
    payload = {"model": model, "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], "max_tokens": max_tokens}
    import urllib.request
    data = json.dumps(payload).encode()
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    auth_header = "Bearer " + API_KEY
    req = urllib.request.Request(url, data=data,
        headers={"Authorization": auth_header,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read().decode()
    except Exception as e:
        raise ValueError(f"API call failed on port {port}: {e}")
    if not body.strip():
        raise ValueError(f"Empty response from strategist API on port {port}")
    try:
        resp = json.loads(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from API on port {port}: {body[:200]}")
    if "error" in resp:
        return {"error": resp["error"]["message"][:500]}
    return {"content": resp["choices"][0]["message"]["content"],
            "tokens": resp["usage"]["completion_tokens"]}

def _detect_provider_failure(output, returncode=0):
    """Scan combined stdout+stderr for known provider failure patterns.
    Returns True if the provider is definitively down — non-zero returncode
    AND/OR matching a known error pattern. Returns False for valid output
    or output that merely contains the word 'error' in non-provider context.
    Used by spawn_agent to decide whether to trigger model-family fallback."""
    if output is None:
        return False
    output = str(output)
    if not output and returncode != 0:
        return True
    if not output:
        return False
    for pattern in _PROVIDER_FAILURE_PATTERNS:
        if pattern.search(output):
            return True
    return False

def _load_fallback_config():
    """Read PANEL_FALLBACK_STRATEGIST, PANEL_FALLBACK_CODER, PANEL_FALLBACK_TECH_LEAD
    from environment. Validates each with FALLBACK_MODEL_RE safe pattern.
    Returns a dict keyed by profile name (strategist, coder, tech-lead).
    Invalid or absent vars are skipped with a warning."""
    config = {}
    role_map = {"strategist": "PANEL_FALLBACK_STRATEGIST",
                "coder": "PANEL_FALLBACK_CODER",
                "tech-lead": "PANEL_FALLBACK_TECH_LEAD"}
    for role, env_var in role_map.items():
        val = os.environ.get(env_var, "")
        if not val:
            continue
        if not FALLBACK_MODEL_RE.match(val):
            print(f"  WARNING: {env_var} has invalid format (must match {FALLBACK_MODEL_RE.pattern}), skipping", flush=True)
            continue
        config[role] = val
    return config

def spawn_agent(profile, skills, prompt, timeout=900, cwd=None, model=None, fallback_model=None):
    """Spawn a Hermes agent as a subprocess. Returns stdout or raises on failure.
    If model is specified (e.g. 'deepseek-v4-pro'), passes -m/--provider to override the profile default.
    If fallback_model is specified, on provider failure the agent is re-spawned
    with the fallback model. Output tagged with [profile:fallback] on fallback success."""
    # Allow test patching via dokima.spawn_agent or agent.spawn_agent override (F022 modular refactor)
    dokima_mod = _IMPORTING_PANEL
    # Check if agent.spawn_agent was patched (tests use panel._agent.spawn_agent)
    if dokima_mod is not None:
        agent_mod = getattr(dokima_mod, '_agent', None)
        if agent_mod is not None:
            agent_override = getattr(agent_mod, 'spawn_agent', None)
            if agent_override is not None and agent_override is not _SPAWN_ORIGINAL:
                return agent_override(profile, skills, prompt, timeout=timeout, cwd=cwd, model=model, fallback_model=fallback_model)
    # Check if dokima.spawn_agent was patched (tests use panel.spawn_agent)
    if dokima_mod is not None:
        dokima_override = getattr(dokima_mod, 'spawn_agent', None)
        if dokima_override is not None and dokima_override is not _SPAWN_ORIGINAL:
            return dokima_override(profile, skills, prompt, timeout=timeout, cwd=cwd, model=model, fallback_model=fallback_model)

    result, returncode = _run_agent(profile, skills, prompt, timeout, cwd, model)

    # Check if fallback is needed
    if fallback_model and _detect_provider_failure(result, returncode):
        print(f"\n[{profile}] ⚠ Primary model failed — retrying with fallback model {fallback_model}", flush=True)
        fallback_result, fb_returncode = _run_agent(profile, skills, prompt, timeout, cwd, fallback_model)
        if not _detect_provider_failure(fallback_result, fb_returncode):
            print(f"\n[{profile}] ✓ Fallback model succeeded", flush=True)
            return f"[{profile}:fallback] {fallback_result}"
        else:
            print(f"\n[{profile}] ⚠ Fallback model also failed — returning original error", flush=True)
            return result

    return result

def _run_agent(profile, skills, prompt, timeout, cwd, model):
    """Core logic for spawning and running a single Hermes agent subprocess.
    Returns (output_string, returncode). Extracted for reuse with fallback."""
    cmd = [HERMES_BIN, "--profile", profile, "--yolo"]
    if model:
        if "/" in model:
            provider, model_name = model.split("/", 1)
            cmd.extend(["--provider", provider, "-m", model_name])
        else:
            cmd.extend(["-m", model])
    for s in skills:
        # F012 deploys skills under software-development/ category.
        # Hermes -s requires category prefix for profile-local skills.
        if "/" not in s:
            s = f"software-development/{s}"
        cmd.extend(["-s", s])
    cmd.extend(["chat", "-q", prompt])
    tag = f"[{profile}]"
    print(f"\n{tag} ⏳ Spawning (timeout={timeout}s)...", flush=True)
    print(f"{tag} CMD: {' '.join(cmd[:4])} ...\n", flush=True)

    env = os.environ.copy()
    gh_token = load_github_token()
    if gh_token:
        env["GH_TOKEN"] = gh_token

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, cwd=cwd, env=env)
    output = []
    timed_out = False
    try:
        for line in proc.stdout:
            redacted = _redact_secrets(line.rstrip())
            print(f"{tag} {redacted}", flush=True)
            output.append(line)
            # Also write redacted output to log file
            try:
                _write_log_line(f"{tag} {redacted}")
            except Exception:
                pass
    except Exception:
        pass
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        print(f"\n{tag} ⚠ TIMEOUT after {timeout}s — killing process", flush=True)
        proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.terminate()
        # Drain any remaining output after kill
        try:
            remaining_out, remaining_err = proc.communicate(timeout=10)
            if remaining_out:
                output.append(remaining_out)
            if remaining_err:
                output.append(f"\n[stderr]\n{remaining_err}")
        except Exception:
            pass

    # Collect stderr
    try:
        stderr_output = proc.stderr.read()
        if stderr_output and stderr_output.strip():
            print(f"{tag} [stderr] {stderr_output.strip()[:500]}", flush=True)
            output.append(f"\n[stderr]\n{stderr_output}")
    except Exception:
        pass

    result = "".join(output)
    if timed_out:
        result += f"\n\n[TIMEOUT: agent exceeded {timeout}s. Partial output above.]"
    try:
        return result, proc.returncode
    except Exception:
        return result, 0

# Module-level original reference for delegation check (F022 modular refactor)
_SPAWN_ORIGINAL = spawn_agent

