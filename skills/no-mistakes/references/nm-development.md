# nm Script Development Notes

## How nm works
The `~/bin/nm` script spawns a fresh `hermes chat -q` session with `--yolo` to run the 7-stage validation pipeline autonomously. It loads `no-mistakes` + `ai-coding-best-practices` skills.

## Key design decisions

### Dual-mode diff detection
- If uncommitted changes exist: validates the working tree diff
- If committed but not pushed: validates `HEAD~1` diff
- If nothing to validate: exits with message

### Secrets handling
The script `source ~/.hermes/.env` before spawning hermes. This provides `GH_TOKEN` for `gh pr create`. The `.env` file must contain `GH_TOKEN=<value>` (same as `GITHUB_TOKEN`).

### Hermes invocation
```bash
hermes chat -q "$PROMPT" -s no-mistakes -s ai-coding-best-practices --yolo
```
- `-q` with quoted prompt string (NOT stdin pipe)
- `--yolo` skips terminal command approval prompts (no user present)
- `-s` preloads both skills

## Known issues

### OpenRouter credit exhaustion
Stage 4 (fresh-context review) delegates to Qwen3 Coder Next via OpenRouter. If credits are exhausted (HTTP 402), the agent falls back to reviewing in the current session. The critical property — reviewer didn't write the code — still holds since it's a fresh session.

### gh CLI auth
`gh auth login` with device flow times out on headless servers. The solution: set `GH_TOKEN` in `.env` and source it. `gh auth status` confirms logged in as siongsheng.

## Location
`~/bin/nm` — source at https://github.com/siongsheng/hermes-huat (in the server's ~/bin, not in the repo)
