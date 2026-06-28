# Dokima Conventions

## Anti-Patterns

- No hardcoded 'master' branch — detected from origin/HEAD
- No absolute dollar amounts in docs — provider-agnostic percentages only
- No auto-merge — user must explicitly approve, even LOW risk

## Model Compatibility

Dokima is developed and tested against **DeepSeek** models (v4-pro, v4-flash). The parser compensates for known DeepSeek output quirks:

| Quirk | Parser Behavior |
|-------|----------------|
| Strips `###` from `### Task N:` headers | Accepts `Task N:` (indented, no markdown) |
| Strips `**` from `**Files:**` / `**Dependencies:**` / `**Parallelizable:**` | Accepts plain `Files:` / `Dependencies:` / `Parallelizable:` |
| Drops `Parallelizable:` field entirely | Defaults to `True` (parallelizable) |
| Wave-format task groupings instead of flat `### Task N:` | DAG re-prompt fires; second attempt usually correct |
| `<thinking>` blocks contain `### Task N:` planning → false DAG match | DAG check runs on extracted agent messages, not raw output |

**If using other model families (Claude, Anthropic, Gemini, Qwen),** verify spec output format in your first pipeline run. Claude and Gemini models reliably produce the requested `### Task N:` format with all five fields — the parser degrades gracefully either way, but format compliance triggers model upgrades and parallel scheduling that improve throughput.

## Cross-Family Adversarial Review

The nm (adversarial reviewer) MUST use a different model **family** than the coder:

| Profile | Primary Model | Provider |
|---------|-------------|----------|
| Coder | deepseek-v4-flash | DeepSeek |
| nm | qwen/qwen3-coder-next | OpenRouter |
| nm (fallback) | gemini-2.5-flash | Google |

Same-family review shares blind spots and defeats the adversarial guarantee. Both nm primary AND fallback are cross-family from the coder.

## Profiling

- Full pipeline runs logged to `/tmp/dokima-output.txt`
- Specs archived post-merge (not kept in repo)
- Worktrees cleaned up after pipeline completion or `SIGTERM`
- Lock file at `/tmp/dokima-<project>.lock` prevents concurrent runs

## Security

### Prompt Sanitization
All user-supplied feature descriptions are sanitized before entering agent prompts:
- Backtick-escaped shell commands (`` `rm -rf /` ``) are stripped
- Markdown code blocks (```` ```dangerous-command``` ````) are stripped
- `SYSTEM:` and `OVERRIDE:` prefix injection attempts are stripped
- Sanitization preserves all legitimate text
- Stripped content logs a `WARNING` to stderr for audit
- Sanitization is applied in `_sanitize_prompt()` before both strategist and coder phases

### Token Redaction
GH_TOKEN, GITHUB_TOKEN, and API_SERVER_KEY values are never written verbatim to logs:
- `_redact_secrets()` replaces token values with `[REDACTED]` before log output
- Token values are looked up from the environment at redaction time (not cached)
- Redaction applies to the OUTPUT_LOG file (`/tmp/dokima-output.txt`) and to agent output lines printed by `spawn_agent`
- All agent output lines pass through `_redact_secrets()` before printing

### File Permission Hardening
All `/tmp/dokima-*` artifacts are created with strict permissions:
- `os.umask(0o077)` is set at module initialization — before any file writes
- Lock files, stop signal files, interview JSON, and OUTPUT_LOG each get explicit `os.chmod(path, 0o600)` after creation
- The restrictive umask covers any files we don't explicitly chmod

### Subprocess Safety (Must-Follow Rules)
All subprocess calls MUST use list-based argument syntax:
```python
# CORRECT
subprocess.run(["git", "-C", path, "status"], ...)
subprocess.Popen(["hermes", "--profile", p, "chat", "-q", prompt], ...)

# FORBIDDEN
subprocess.run("git status", shell=True, ...)   # shell=True is banned
os.system("git status")                         # os.system() is banned
```
- `shell=True` is banned — never use it
- `os.system()` is banned — never use it
- String commands (bare strings as first arg) are banned — always use list args
- The existing `_safe_run()` function already uses `shlex.split()` for safe string-to-arg conversion

### PROJECT_DIR Validation
The panel validates PROJECT_DIR before any operation:
- Path must exist and be a directory
- Path must contain a `.git` subdirectory
- Non-repo directories, files, and nonexistent paths are rejected with a clear error message
- Validation prevents path-traversal and symlink-attack vectors

## Model Fallback

The panel supports automatic provider fallback via the `PANEL_FALLBACK_MODEL` environment variable. When configured, `spawn_agent` detects provider failures (rate limits, HTTP 503s, connection refused, model not found, provider errors) in agent output and retries once with the fallback model.

### Configuration

```bash
export PANEL_FALLBACK_MODEL=openrouter/anthropic/claude-sonnet-4
```

Format: `provider/model_name` (same format as the `-m` flag in Hermes CLI). If unset, no fallback occurs — existing behavior is preserved.

### Failure Detection

The following patterns in combined stdout+stderr trigger a fallback retry:
- `rate limit`
- `503`
- `service unavailable`
- `provider.error`
- `model.*not.*(?:found|available)`
- `connection refused`

Fallback does NOT fire on:
- Legitimate output containing words like "error" or "rate" in normal context
- Agent timeouts (timeout is handled separately, not as a provider failure)

### Retry Behavior

- Fallback is **one-shot**: if the fallback model also fails, the original error output is returned
- A `⚠ FALLBACK` log line is printed to stderr when fallback fires
- The fallback call reuses the same profile, skills, prompt, and timeout
- Timeouts are NOT retried — a timed-out agent produces a `[TIMEOUT]` result without fallback
