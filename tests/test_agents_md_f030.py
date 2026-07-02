"""Tests that AGENTS.md has no stale dokima --flag references (F030 CLI redesign).

Task 13: Update AGENTS.md (if needed). The F030 CLI redesign replaces standalone
--flags (--add, --next, --fix, --status, --stop, --kill, --list-crons,
--version, --upgrade, --release, --continuous) with subcommands (dokima add,
dokima next, etc.). AGENTS.md should not reference the old flag-style invocations.
"""

import os


def _read_agents_md():
    path = os.path.join(os.path.dirname(__file__), '..', 'AGENTS.md')
    with open(path) as f:
        return f.read()


# ── Old flag-style standalone commands that must NOT appear ──

OLD_DOKIMA_FLAGS = [
    'dokima --add ',
    'dokima --next ',
    'dokima --fix ',
    'dokima --status ',
    'dokima --stop ',
    'dokima --kill ',
    'dokima --list-crons',
    'dokima --version',
    'dokima --upgrade',
    'dokima --release ',
    'dokima --continuous ',
    'dokima --from-spec',
]

# ── Expected section headers (development workflow, not CLI usage) ──

EXPECTED_HEADERS = [
    '## Tech Stack',
    '## Commands',
    '## Testing',
    '## Conventions',
]

EXPECTED_COMMANDS = [
    'python3 -m pytest tests/ -q',
    'python3 -m py_compile dokima',
    'bash -n scripts/nm',
    'bash -n scripts/vet',
]


def test_agents_md_exists():
    """AGENTS.md exists at project root."""
    path = os.path.join(os.path.dirname(__file__), '..', 'AGENTS.md')
    assert os.path.exists(path), "AGENTS.md must exist at project root"


def test_no_old_flag_commands_in_agents_md():
    """AGENTS.md must NOT reference old flag-style dokima commands."""
    md = _read_agents_md()
    for pattern in OLD_DOKIMA_FLAGS:
        assert pattern not in md, (
            f"AGENTS.md contains old flag-style command: '{pattern}'. "
            f"Replace with subcommand form if a CLI example is needed."
        )


def test_agents_md_has_expected_headers():
    """AGENTS.md must have expected section headers."""
    md = _read_agents_md()
    for header in EXPECTED_HEADERS:
        assert header in md, (
            f"AGENTS.md missing expected header: '{header}'"
        )


def test_agents_md_has_development_commands():
    """AGENTS.md must have expected development commands (test, lint, verify)."""
    md = _read_agents_md()
    for cmd in EXPECTED_COMMANDS:
        assert cmd in md, (
            f"AGENTS.md missing expected development command: '{cmd}'"
        )
