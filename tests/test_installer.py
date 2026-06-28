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


def _make_fake_hermes(bindir):
    """Create a fake hermes that handles 'profile create <name>' by making a marker dir."""
    path = os.path.join(bindir, "hermes")
    with open(path, "w") as f:
        f.write("""#!/usr/bin/env bash
# Fake hermes for testing
if [[ "$1" == "profile" && "$2" == "create" ]]; then
    mkdir -p "$HOME/.hermes/profiles/$3"
    echo "profile $3 created"
elif [[ "$1" == "--version" ]]; then
    echo "hermes v1.0.0"
else
    echo "fake hermes: $*"
fi
""")
    os.chmod(path, 0o755)
    return path


def _make_git_repo(path):
    """Create a minimal git repo at path containing dokima, bin/nm, and bin/vet."""
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", path], capture_output=True, check=True)
    # Create a minimal dokima script
    dokima_path = os.path.join(path, "dokima")
    with open(dokima_path, "w") as f:
        f.write("#!/usr/bin/env python3\nprint('dokima')\n")
    os.chmod(dokima_path, 0o755)
    # Create bin/nm and bin/vet
    bin_dir = os.path.join(path, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    for name in ("nm", "vet"):
        script_path = os.path.join(bin_dir, name)
        with open(script_path, "w") as f:
            f.write("#!/usr/bin/env bash\necho '{} ok'\n".format(name))
        os.chmod(script_path, 0o755)
    subprocess.run(["git", "-C", path, "add", "."], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", path, "-c", "user.name=test", "-c", "user.email=test@test",
         "commit", "-m", "add bin scripts"], capture_output=True, check=True
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


class TestNmAndVet:
    """install.sh symlinks bin/nm and bin/vet into ~/.local/bin."""

    def test_symlinks_nm_and_vet(self, tmp_path):
        """After install, nm and vet are symlinked into ~/.local/bin."""
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
        for script in ("nm", "vet"):
            symlink = os.path.join(home, ".local", "bin", script)
            assert os.path.islink(symlink), "Expected symlink for {}".format(script)
            assert os.path.realpath(symlink) == os.path.join(clone_dir, "bin", script)

    def test_nm_vet_availability_printed(self, tmp_path):
        """install.sh prints that nm and vet are available."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_cmd("{}/fake-bin".format(home), "hermes")

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        result = _run_installer_full(home, env_extra={"PANEL_REPO": repo_path})
        output = result.stdout + result.stderr
        assert "nm" in output.lower()
        assert "vet" in output.lower()


class TestWithProfiles:
    """--with-profiles flag creates Hermes agent profiles."""

    def test_without_flag_no_profiles(self, tmp_path):
        """Without --with-profiles, no hermes profiles are created."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_hermes("{}/fake-bin".format(home))

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        result = _run_installer_full(home, env_extra={"PANEL_REPO": repo_path})
        assert result.returncode == 0

        profiles_dir = os.path.join(home, ".hermes", "profiles")
        for profile in ("strategist", "coder", "tech-lead", "nm"):
            profile_dir = os.path.join(profiles_dir, profile)
            assert not os.path.isdir(profile_dir), \
                "Profile {} should not exist without --with-profiles".format(profile)

    def test_with_profiles_creates_all(self, tmp_path):
        """--with-profiles creates all 4 agent profiles."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_hermes("{}/fake-bin".format(home))

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        result = _run_installer_full(home, args="--with-profiles",
                                     env_extra={"PANEL_REPO": repo_path})
        assert result.returncode == 0, "installer failed: {}".format(result.stderr)

        profiles_dir = os.path.join(home, ".hermes", "profiles")
        for profile in ("strategist", "coder", "tech-lead", "nm"):
            profile_dir = os.path.join(profiles_dir, profile)
            assert os.path.isdir(profile_dir), \
                "Expected profile {} to be created".format(profile)

    def test_with_profiles_prints_profile_info(self, tmp_path):
        """--with-profiles output mentions profile creation."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_hermes("{}/fake-bin".format(home))

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        result = _run_installer_full(home, args="--with-profiles",
                                     env_extra={"PANEL_REPO": repo_path})
        output = result.stdout + result.stderr
        assert "profile" in output.lower()


class TestPathDetection:
    """install.sh detects if ~/.local/bin is in PATH and updates shell config."""

    def test_adds_to_bashrc_when_not_in_path(self, tmp_path):
        """When ~/.local/bin is not in PATH, installer appends to ~/.bashrc."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_cmd("{}/fake-bin".format(home), "hermes")

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        # PATH intentionally excludes ~/.local/bin
        result = _run_installer_full(
            home,
            env_extra={
                "PANEL_REPO": repo_path,
                "SHELL": "/bin/bash",
                "PATH": "{}/fake-bin:/usr/bin:/bin".format(home),
            },
        )
        assert result.returncode == 0

        bashrc = os.path.join(home, ".bashrc")
        assert os.path.isfile(bashrc), "Expected ~/.bashrc to be created"
        content = open(bashrc).read()
        assert "$HOME/.local/bin" in content or home in content
        assert "PATH" in content

    def test_idempotent_no_duplicate_entries(self, tmp_path):
        """Running installer twice doesn't add duplicate PATH entries."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_cmd("{}/fake-bin".format(home), "hermes")

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        env = {
            "PANEL_REPO": repo_path,
            "SHELL": "/bin/bash",
            "PATH": "{}/fake-bin:/usr/bin:/bin".format(home),
        }

        # First run
        result1 = _run_installer_full(home, env_extra=env)
        assert result1.returncode == 0

        # Second run with PATH now containing ~/.local/bin
        env2 = dict(env)
        env2["PATH"] = "{}/.local/bin:{}/fake-bin:/usr/bin:/bin".format(home, home)
        result2 = _run_installer_full(home, env_extra=env2)
        assert result2.returncode == 0

        bashrc = os.path.join(home, ".bashrc")
        content = open(bashrc).read()
        # PATH export should appear at most once
        assert content.count("export PATH=") <= 1

    def test_prints_source_instruction(self, tmp_path):
        """When PATH is modified, installer prints 'source ~/.bashrc' instruction."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_cmd("{}/fake-bin".format(home), "hermes")

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        result = _run_installer_full(
            home,
            env_extra={
                "PANEL_REPO": repo_path,
                "SHELL": "/bin/bash",
                "PATH": "{}/fake-bin:/usr/bin:/bin".format(home),
            },
        )
        output = result.stdout + result.stderr
        assert "source" in output.lower()

    def test_zsh_detects_zshrc(self, tmp_path):
        """When SHELL is zsh, installer modifies ~/.zshrc."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_cmd("{}/fake-bin".format(home), "hermes")

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        result = _run_installer_full(
            home,
            env_extra={
                "PANEL_REPO": repo_path,
                "SHELL": "/usr/bin/zsh",
                "PATH": "{}/fake-bin:/usr/bin:/bin".format(home),
            },
        )
        assert result.returncode == 0

        zshrc = os.path.join(home, ".zshrc")
        assert os.path.isfile(zshrc), "Expected ~/.zshrc to be created"
        content = open(zshrc).read()
        assert "$HOME/.local/bin" in content or home in content


class TestEndToEnd:
    """Comprehensive verification: idempotency, re-run, git pull path."""

    def test_idempotent_full_rerun(self, tmp_path):
        """Running installer twice produces identical state without errors."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_cmd("{}/fake-bin".format(home), "hermes")

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        env = {"PANEL_REPO": repo_path}

        # First run
        result1 = _run_installer_full(home, env_extra=env)
        assert result1.returncode == 0, "First run failed: {}".format(result1.stderr)

        # Verify dokima symlink exists
        dokima_link = os.path.join(home, ".local", "bin", "dokima")
        assert os.path.islink(dokima_link)

        # Second run — should succeed without errors
        result2 = _run_installer_full(home, env_extra=env)
        assert result2.returncode == 0, "Second run failed: {}".format(result2.stderr)

        # Verify state is still intact
        assert os.path.islink(dokima_link)
        assert os.path.isdir(os.path.join(home, ".local", "share", "dokima"))

    def test_git_pull_on_existing_clone(self, tmp_path):
        """When repo already cloned, installer runs git pull instead of clone."""
        home = str(tmp_path / "home")
        os.makedirs("{}/fake-bin".format(home), exist_ok=True)
        _make_fake_cmd("{}/fake-bin".format(home), "python3")
        _make_fake_cmd("{}/fake-bin".format(home), "gh")
        _make_fake_cmd("{}/fake-bin".format(home), "hermes")

        repo_path = str(tmp_path / "mock-repo")
        _make_git_repo(repo_path)

        # Pre-create the clone directory as if already installed
        clone_dir = os.path.join(home, ".local", "share", "dokima")
        os.makedirs(clone_dir, exist_ok=True)

        # Manually clone the mock repo there first
        subprocess.run(["git", "clone", repo_path, clone_dir],
                       capture_output=True, check=True)

        env = {"PANEL_REPO": repo_path}
        result = _run_installer_full(home, env_extra=env)
        assert result.returncode == 0
        output = result.stdout + result.stderr

        # Should indicate it pulled rather than cloned
        assert "pull" in output.lower() or "exists" in output.lower() or "already" in output.lower()

