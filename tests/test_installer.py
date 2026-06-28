"""Tests for install.sh — the dokima installer script.

Test approach: run install.sh in a controlled temp HOME with fake commands
in PATH to test dependency checks and filesystem operations without network.
"""
import os
import shutil
import stat
import subprocess
import tempfile
import pytest


INSTALLER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "install.sh"))
BASH = shutil.which("bash") or "/usr/bin/bash"


def _make_fake_cmd(bindir, name):
    """Create a fake executable script in bindir that echoes its name."""
    path = os.path.join(bindir, name)
    with open(path, "w") as f:
        f.write("#!/bin/bash\necho 'fake {}'\n".format(name))
    os.chmod(path, 0o755)
    return path


def _make_git_repo(path):
    """Create a minimal git repo at path containing a 'dokima' file."""
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", path], capture_output=True, check=True)
    dokima_path = os.path.join(path, "dokima")
    with open(dokima_path, "w") as f:
        f.write("#!/usr/bin/env python3\nprint('dokima')\n")
    os.chmod(dokima_path, 0o755)
    subprocess.run(["git", "-C", path, "add", "dokima"], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", path, "-c", "user.name=test", "-c", "user.email=test@test",
         "commit", "-m", "init"], capture_output=True, check=True
    )
    return path


def _run_installer(home, args="", env_extra=None):
    """Run install.sh with isolated PATH (only fake-bin). Use for dep-check tests."""
    env = os.environ.copy()
    env["HOME"] = home
    env["PATH"] = "{}/fake-bin".format(home)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [BASH, INSTALLER] + (args.split() if args else []),
        capture_output=True, text=True, timeout=30, env=env,
    )


def _run_installer_full(home, args="", env_extra=None):
    """Run install.sh with fake-bin first, then system PATH. Use for clone/symlink tests."""
    env = os.environ.copy()
    env["HOME"] = home
    env["PATH"] = "{}/fake-bin:{}".format(home, os.environ.get("PATH", "/usr/bin:/bin"))
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [BASH, INSTALLER] + (args.split() if args else []),
        capture_output=True, text=True, timeout=30, env=env,
    )


class TestDependencyChecks:
    """install.sh checks for Python 3.6+, gh CLI, and Hermes Agent before doing anything."""

    def test_missing_python3(self, tmp_path):
        """When python3 not found, exit 1 with clear error message."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        result = _run_installer(home)
        assert result.returncode == 1
        assert "python" in (result.stdout + result.stderr).lower()

    def test_missing_gh(self, tmp_path):
        """When gh CLI not found, exit 1 with clear error message."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "hermes")
        result = _run_installer(home)
        assert result.returncode == 1
        assert "gh" in (result.stdout + result.stderr).lower()

    def test_missing_hermes(self, tmp_path):
        """When Hermes Agent not found, exit 1 with clear error message."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        result = _run_installer(home)
        assert result.returncode == 1
        assert "hermes" in (result.stdout + result.stderr).lower()


class TestHappyPath:
    """Full install: clone repo, create symlinks, print success."""

    def test_fresh_install(self, tmp_path):
        """install.sh clones the repo and symlinks dokima into ~/.local/bin."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_cmd("{}/fake-bin".format(home), "hermes")

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        result = _run_installer_full(home, env_extra={"PANEL_REPO": repo_path})
        assert result.returncode == 0, "installer failed: {}".format(result.stderr)

        clone_dir = os.path.join(home, ".local", "share", "dokima")
        assert os.path.isdir(clone_dir), "Expected clone at {}".format(clone_dir)

        symlink = os.path.join(home, ".local", "bin", "dokima")
        assert os.path.islink(symlink), "Expected symlink at {}".format(symlink)
        assert os.path.realpath(symlink) == os.path.join(clone_dir, "dokima")

        output = result.stdout + result.stderr
        assert "installed" in output.lower() or "dokima" in output.lower()

    def test_creates_bin_dir(self, tmp_path):
        """install.sh creates ~/.local/bin if it doesn't exist."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_cmd("{}/fake-bin".format(home), "hermes")

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        bin_dir = os.path.join(home, ".local", "bin")
        assert not os.path.exists(bin_dir)

        result = _run_installer_full(home, env_extra={"PANEL_REPO": repo_path})
        assert result.returncode == 0
        assert os.path.isdir(bin_dir)
