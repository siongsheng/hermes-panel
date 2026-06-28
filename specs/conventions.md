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
