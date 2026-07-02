"""Tests for F021: Semantic Versioning + GitHub Releases — version and upgrade subcommands."""
import subprocess, os, sys, json

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dokima")

def _run(*args):
    """Run dokima with given args and return (returncode, stdout, stderr)."""
    p = subprocess.run(
        [sys.executable, SCRIPT] + list(args),
        capture_output=True, text=True, timeout=10
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


# ── Version subcommand tests ────────────────────────────────────────

def test_version_subcommand_prints_version_and_exits_0():
    """dokima version prints 'dokima vX.Y.Z' and exits 0."""
    rc, out, err = _run("version")
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {err}"
    assert out.startswith("dokima v"), f"Expected 'dokima v...', got: {out}"
    parts = out.split("v", 1)
    assert len(parts) == 2, f"Expected 'dokima v<version>', got: {out}"
    version = parts[1]
    assert "." in version, f"Expected semver, got version: {version}"


def test_version_works_in_non_git_directory():
    """dokima version works even in a non-git directory (no git dependency)."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = subprocess.run(
            [sys.executable, SCRIPT, "version"],
            capture_output=True, text=True, timeout=10, cwd=td
        )
        assert p.returncode == 0, f"Expected exit 0, got {p.returncode}. stderr: {p.stderr}"
        assert p.stdout.strip().startswith("dokima v"), \
            f"Expected 'dokima v...', got: {p.stdout.strip()!r}"


def test_version_help_shows_subcommand_usage():
    """dokima version --help shows version-specific argparse help."""
    rc, out, err = _run("version", "--help")
    combined = out + err
    assert "dokima version" in combined, \
        f"version --help must show usage as 'dokima version':\nout={out}\nerr={err}"


# ── Upgrade subcommand tests ───────────────────────────────────────

def test_upgrade_subcommand_no_install_dir_exits_0():
    """dokima upgrade exits 0 with helpful message when not installed via install.sh."""
    rc, out, err = _run("upgrade")
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {err}"
    lower = (out + err).lower()
    assert "install" in lower or "not installed" in lower, \
        f"Expected message about install, got: out={out!r} err={err!r}"


# ── --help / --help-json tests ──────────────────────────────────────

def test_help_includes_version_subcommand():
    """--help output includes 'dokima version' subcommand syntax."""
    rc, out, err = _run("--help")
    assert rc == 0, f"Expected exit 0, got {rc}"
    assert "dokima version" in out, f"'dokima version' not in help output:\n{out}"


def test_help_includes_upgrade_subcommand():
    """--help output includes 'dokima upgrade' subcommand syntax."""
    rc, out, err = _run("--help")
    assert rc == 0, f"Expected exit 0, got {rc}"
    assert "dokima upgrade" in out, f"'dokima upgrade' not in help output:\n{out}"


def test_help_still_works():
    """--help output is unchanged (still exits 0)."""
    rc, out, err = _run("--help")
    assert rc == 0, f"Expected exit 0, got {rc}"
    assert "Dokima" in out, f"Help output missing 'Dokima': {out[:100]}"


def test_help_json_includes_version():
    """--help-json includes version field and version/upgrade commands."""
    rc, out, err = _run("--help-json")
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {err}"
    data = json.loads(out)
    assert "version" in data, f"No 'version' field in help-json: {data}"
    assert data["version"], f"version field is empty"
    commands = data.get("commands", [])
    version_cmds = [c for c in commands if c.get("name") == "version"]
    assert version_cmds, f"'version' not in commands array: {commands}"
    upgrade_cmds = [c for c in commands if c.get("name") == "upgrade"]
    assert upgrade_cmds, f"'upgrade' not in commands array: {commands}"


# ── Old flag regression tests (must be rejected) ────────────────────

def test_old_flag_version_is_rejected():
    """dokima --version (old flag form) must fail with argparse."""
    rc, out, err = _run("--version")
    assert rc != 0, f"Old --version flag must fail with argparse, got exit {rc}"


def test_old_v_shorthand_is_rejected():
    """dokima -v (old shorthand) must fail — no longer valid."""
    rc, out, err = _run("-v")
    assert rc != 0, f"Old -v shorthand must fail with argparse, got exit {rc}"


def test_old_flag_upgrade_is_rejected():
    """dokima --upgrade (old flag form) must fail with argparse."""
    rc, out, err = _run("--upgrade")
    assert rc != 0, f"Old --upgrade flag must fail with argparse, got exit {rc}"


# ── VERSION file integrity test ─────────────────────────────────────

def test_version_file_is_valid():
    """VERSION file exists and contains valid semver."""
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    version_path = os.path.join(script_dir, "VERSION")
    assert os.path.exists(version_path), f"VERSION file not found at {version_path}"
    with open(version_path) as f:
        content = f.read()
    version = content.strip()
    assert version, "VERSION file is empty"
    import re
    assert re.match(r'^\d+\.\d+\.\d+$', version), f"VERSION not semver: {version!r}"
