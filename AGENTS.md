# Dokima — Multi-Agent Orchestration Engine

Python script that routes feature development through a pipeline of AI agents.
This repo IS the panel — you don't run the panel on itself.

## Tech Stack
- Python 3.6+ (single script, no dependencies)
- Bash for companion scripts (nm, vet)
- Hermes Agent for profile spawning
- GitHub CLI for PR/issue management

## Commands
- Test: `python3 -m pytest tests/ -q`
- Build: `python3 -c "compile(open('dokima').read(), 'dokima', 'exec')"`
- Lint: `python3 -m py_compile dokima`
- Verify nm script: `bash -n ~/bin/nm`
- Verify vet script: `bash -n ~/bin/vet`

## Testing
177 tests (pytest). Coverage: core functions + control panel + edge cases.
```bash
# Full suite (excludes slow integration tests)
python3 -m pytest tests/ -q --ignore=tests/test_main_integration.py

# All tests including integration (may be slow)
python3 -m pytest tests/ -q

# Single file
python3 -m pytest tests/test_slugify.py -v
```

## Conventions
- No hardcoded 'master' branch — detected from origin/HEAD
- No absolute dollar amounts in docs — provider-agnostic percentages only
- Skills are SKILL.md files with YAML frontmatter
- Panel spawns agents via `hermes --profile <role> --yolo -s <skill> chat -q "..."`
