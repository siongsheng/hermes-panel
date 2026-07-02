"""Tests for F021: Semantic Versioning + GitHub Releases — --version and --upgrade flags."""
import subprocess, os, sys, json

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dokima")

def _run(*args):
    """Run dokima with given args and return (returncode, stdout, stderr)."""
    p = subprocess.run(
        [sys.executable, SCRIPT] + list(args),
        capture_output=True, text=True, timeout=10
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def test_version_flag_prints_version_and_exits_0():
    """dokima --version prints 'dokima vX.Y.Z' and exits 0."""
    rc, out, err = _run("--version")
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {err}"
    assert out.startswith("dokima v"), f"Expected 'dokima v...', got: {out}"
    # Should have a semver-like version after the 'v'
    parts = out.split("v", 1)
    assert len(parts) == 2, f"Expected 'dokima v<version>', got: {out}"
    version = parts[1]
    # Should be something like X.Y.Z
    assert "." in version, f"Expected semver, got version: {version}"


def test_help_includes_version_command():
    """--help output includes --version in CONTROL section."""
    rc, out, err = _run("--help")
    assert rc == 0, f"Expected exit 0, got {rc}"
    assert "dokima --version" in out, f"--version not in help output:\n{out}"


def test_help_includes_upgrade_command():
    """--help output includes --upgrade in CONTROL section."""
    rc, out, err = _run("--help")
    assert rc == 0, f"Expected exit 0, got {rc}"
    assert "dokima --upgrade" in out, f"--upgrade not in help output:\n{out}"


def test_help_json_includes_version():
    """--help-json includes version field and --version command."""
    rc, out, err = _run("--help-json")
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {err}"
    data = json.loads(out)
    assert "version" in data, f"No 'version' field in help-json: {data}"
    assert data["version"], f"version field is empty"
    commands = data.get("commands", [])
    version_cmds = [c for c in commands if c.get("name") == "version"]
    assert version_cmds, f"version not in commands array: {commands}"
    upgrade_cmds = [c for c in commands if c.get("name") == "upgrade"]
    assert upgrade_cmds, f"upgrade not in commands array: {commands}"


def test_upgrade_no_install_dir_exits_0():
    """--upgrade exits 0 with helpful message when not installed via install.sh."""
    rc, out, err = _run("--upgrade")
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {err}"
    # Should mention install.sh or not installed
    lower = (out + err).lower()
    assert "install" in lower or "not installed" in lower, \
        f"Expected message about install, got: out={out!r} err={err!r}"


def test_v_shorthand_works():
    """-v shorthand prints version same as --version."""
    rc, out, err = _run("-v")
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {err}"
    assert out.startswith("dokima v"), f"Expected 'dokima v...', got: {out}"


def test_help_still_works():
    """--help output is unchanged (still exits 0)."""
    rc, out, err = _run("--help")
    assert rc == 0, f"Expected exit 0, got {rc}"
    assert "Dokima" in out, f"Help output missing 'Dokima': {out[:100]}"


def test_version_with_extra_args_exits_0():
    """--version with extra args still exits 0, ignoring extra args."""
    rc, out, err = _run("--version", "/some/path")
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {err}"
    assert out.startswith("dokima v"), f"Expected 'dokima v...', got: {out}"


def test_version_works_in_non_git_directory():
    """--version works even in a non-git directory (no git dependency)."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = subprocess.run(
            [sys.executable, SCRIPT, "--version"],
            capture_output=True, text=True, timeout=10, cwd=td
        )
        assert p.returncode == 0, f"Expected exit 0, got {p.returncode}. stderr: {p.stderr}"
        assert p.stdout.strip().startswith("dokima v"), f"Expected 'dokima v...', got: {p.stdout.strip()!r}"


def test_version_first_flag_wins():
    """--version --help: first flag wins, --version prints and exits."""
    rc, out, err = _run("--version", "--help")
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {err}"
    assert out.startswith("dokima v"), f"Expected 'dokima v...', got: {out}"


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
