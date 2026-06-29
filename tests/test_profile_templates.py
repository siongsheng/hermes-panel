"""Tests for F012: Profile Templates — ensure_profiles() and deploy_profile_skills()."""
import os
import sys
import subprocess
import pytest
from unittest.mock import patch, MagicMock, call
from conftest import _load_panel

panel = None  # set by _fresh_panel fixture before each test


@pytest.fixture(autouse=True)
def _fresh_panel():
    """F022b: Create a fresh panel for each test.
    Module-level panel references go stale when other tests'
    _load_panel() calls replace sys.modules entries. A per-test
    fixture ensures this module always has a panel whose
    _IMPORTING_PANEL references are correct."""
    global panel
    panel = _load_panel()
    yield


class TestEnsureProfiles:
    """Tests for ensure_profiles() — creating agent profiles via hermes CLI."""

    # ── Profiles to create ──
    DOKIMA_PROFILES = ["strategist", "coder", "tech-lead", "nm"]

    def test_all_missing_creates_all(self):
        """When all profiles are missing, all four are created and configured."""
        with patch.object(os.path, "isdir", return_value=False), \
             patch.object(subprocess, "run") as mock_run:
            # Mock hermes profile list to return nothing
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            panel.ensure_profiles()

            # Should call hermes profile create for each
            create_calls = [c for c in mock_run.call_args_list
                          if len(c[0][0]) >= 3 and c[0][0][1] == "profile"
                          and c[0][0][2] == "create"]
            assert len(create_calls) == 4
            created_names = sorted(c[0][0][3] for c in create_calls)
            assert created_names == ["coder", "nm", "strategist", "tech-lead"]

            # Should call config set for model.default on each
            model_calls = [c for c in mock_run.call_args_list
                          if any("config" in str(a) for a in c[0][0])
                          and any("model.default" in str(a) for a in c[0][0])]
            assert len(model_calls) == 4

    def test_all_exist_skips_all(self):
        """When all profiles already exist, nothing is created."""
        with patch.object(os.path, "isdir", return_value=True), \
             patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout="strategist\ncoder\ntech-lead\nnm\n",
                                              stderr="", returncode=0)

            panel.ensure_profiles()

            # No profile create calls
            create_calls = [c for c in mock_run.call_args_list
                          if len(c[0][0]) >= 3 and c[0][0][1] == "profile"
                          and c[0][0][2] == "create"]
            assert len(create_calls) == 0

    def test_some_missing_creates_only_missing(self):
        """Only missing profiles are created; existing ones skipped."""
        def isdir_side_effect(path):
            if "strategist" in path and "coder" in path:
                # Both strategist and coder exist
                return any(p in path for p in ["strategist", "coder"])
            return "strategist" in path or "coder" in path

        with patch.object(os.path, "isdir") as mock_isdir, \
             patch.object(subprocess, "run") as mock_run:
            mock_isdir.side_effect = lambda p: any(
                name in p for name in ["strategist", "coder"]
            )
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            panel.ensure_profiles()

            create_calls = [c for c in mock_run.call_args_list
                          if len(c[0][0]) >= 3 and c[0][0][1] == "profile"
                          and c[0][0][2] == "create"]
            created = [c[0][0][3] for c in create_calls]
            assert sorted(created) == ["nm", "tech-lead"]
            assert "strategist" not in created
            assert "coder" not in created

    def test_strategist_gets_reasoning_high(self):
        """Strategist profile gets agent.reasoning_effort set to 'high'."""
        with patch.object(os.path, "isdir", return_value=False), \
             patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            panel.ensure_profiles()

            # Find the strategist reasoning_effort call
            reasoning_calls = [c for c in mock_run.call_args_list
                             if "reasoning_effort" in str(c[0][0])]
            assert len(reasoning_calls) == 1
            # Verify it sets to 'high'
            args = reasoning_calls[0][0][0]
            assert "high" in args[-1] or "high" in str(args)

    def test_model_default_set_for_all(self):
        """All profiles get model.default set to deepseek-v4-pro."""
        with patch.object(os.path, "isdir", return_value=False), \
             patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            panel.ensure_profiles()

            model_calls = [c for c in mock_run.call_args_list
                          if "model.default" in str(c[0][0])
                          and "deepseek-v4-pro" in str(c[0][0])]
            assert len(model_calls) == 4

    def test_provider_set_for_all(self):
        """All profiles get model.provider set to 'deepseek'."""
        with patch.object(os.path, "isdir", return_value=False), \
             patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            panel.ensure_profiles()

            provider_calls = [c for c in mock_run.call_args_list
                            if "model.provider" in str(c[0][0])
                            and "deepseek" in str(c[0][0])]
            assert len(provider_calls) == 4

    def test_max_turns_set_for_all(self):
        """All profiles get agent.max_turns set to 150."""
        with patch.object(os.path, "isdir", return_value=False), \
             patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            panel.ensure_profiles()

            turns_calls = [c for c in mock_run.call_args_list
                         if "max_turns" in str(c[0][0])
                         and "150" in str(c[0][0])]
            assert len(turns_calls) == 4

    def test_non_interactive_no_io_error(self):
        """When stdin is not a TTY, ensure_profiles does not crash or prompt."""
        with patch.object(os.path, "isdir", return_value=False), \
             patch.object(subprocess, "run") as mock_run, \
             patch.object(sys.stdin, "isatty", return_value=False):
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            # Should not raise
            panel.ensure_profiles()

            # Should still create profiles
            create_calls = [c for c in mock_run.call_args_list
                          if len(c[0][0]) >= 3 and c[0][0][1] == "profile"
                          and c[0][0][2] == "create"]
            assert len(create_calls) == 4

    def test_profile_create_failure_handled(self):
        """When hermes profile create fails, the error is reported but continues."""
        call_count = [0]

        def run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            cmd_str = " ".join(str(x) for x in cmd) if isinstance(cmd, list) else str(cmd)
            if "profile" in cmd_str and "create" in cmd_str and "nm" in cmd_str:
                call_count[0] += 1
                if call_count[0] == 1:
                    # Simulate failure for one profile
                    return MagicMock(stdout="", stderr="Error creating profile", returncode=1)
            return MagicMock(stdout="", stderr="", returncode=0)

        with patch.object(os.path, "isdir", return_value=False), \
             patch.object(subprocess, "run", side_effect=run_side_effect):
            # Should not raise — handles failure gracefully
            panel.ensure_profiles()

    def test_idempotent_double_run(self):
        """Running ensure_profiles twice does not create duplicates or fail."""
        with patch.object(os.path, "isdir", return_value=False) as mock_isdir, \
             patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            panel.ensure_profiles()
            create_count_first = len([c for c in mock_run.call_args_list
                                      if len(c[0][0]) >= 3
                                      and c[0][0][1] == "profile"
                                      and c[0][0][2] == "create"])

            # Second run — now pretend profiles exist
            mock_isdir.return_value = True
            mock_run.reset_mock()
            panel.ensure_profiles()
            create_count_second = len([c for c in mock_run.call_args_list
                                       if len(c[0][0]) >= 3
                                       and c[0][0][1] == "profile"
                                       and c[0][0][2] == "create"])

            assert create_count_first == 4  # First run created all 4
            assert create_count_second == 0  # Second run created none

    def test_env_passthrough_set_for_all(self):
        """All profiles get terminal.env_passthrough set."""
        with patch.object(os.path, "isdir", return_value=False), \
             patch.object(subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            panel.ensure_profiles()

            env_calls = [c for c in mock_run.call_args_list
                        if "env_passthrough" in str(c[0][0])
                        and "GH_TOKEN" in str(c[0][0])]
            assert len(env_calls) == 4


class TestDeployProfileSkills:
    """Tests for deploy_profile_skills() — copying skills to profile directories."""

    def _setup_source_skills(self, tmpdir, panel_ref):
        """Create a fake dokima skills directory with test skill dirs."""
        skills_dir = os.path.join(tmpdir, "skills")
        for skill in ["spec-strategist-lite", "ponytail-guard",
                      "ai-coding-best-practices-lite", "adversarial-review-lite",
                      "no-mistakes"]:
            skill_dir = os.path.join(skills_dir, skill)
            os.makedirs(skill_dir)
            with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
                f.write(f"# {skill}\\n\\nTest skill content.\\n")
        # Patch PANEL_DIR to point to our temp dir
        panel_ref.PANEL_DIR = tmpdir
        panel_ref._utils.PANEL_DIR = tmpdir
        return skills_dir

    def test_skills_deployed_to_correct_dirs(self, tmpdir):
        """Skills are copied to the correct profile directories."""
        import shutil
        # Set up source
        self._setup_source_skills(str(tmpdir), panel)

        # Set up profile skill dirs
        profiles_dir = os.path.join(str(tmpdir), "profiles")
        for name in ["strategist", "coder", "tech-lead", "nm"]:
            os.makedirs(os.path.join(profiles_dir, name, "skills", "software-development"),
                       exist_ok=True)

        hermes_dir = os.path.join(str(tmpdir), "skills", "software-development")
        os.makedirs(hermes_dir, exist_ok=True)

        # Patch the module's PROFILES and HERMES paths
        with patch.object(panel._utils, "PROFILES", profiles_dir), \
             patch.object(panel._utils, "HERMES", os.path.join(str(tmpdir))):
            panel.deploy_profile_skills()

            # Check strategist skills
            strat_dir = os.path.join(profiles_dir, "strategist", "skills", "software-development")
            assert os.path.isdir(os.path.join(strat_dir, "spec-strategist-lite"))
            assert os.path.isdir(os.path.join(strat_dir, "ponytail-guard"))

            # Check coder skills
            coder_dir = os.path.join(profiles_dir, "coder", "skills", "software-development")
            assert os.path.isdir(os.path.join(coder_dir, "ai-coding-best-practices-lite"))

            # Check tech-lead skills
            tl_dir = os.path.join(profiles_dir, "tech-lead", "skills", "software-development")
            assert os.path.isdir(os.path.join(tl_dir, "adversarial-review-lite"))
            assert os.path.isdir(os.path.join(tl_dir, "ponytail-guard"))

            # Check nm skill in global dir
            nm_dir = os.path.join(str(tmpdir), "skills", "software-development")
            assert os.path.isdir(os.path.join(nm_dir, "no-mistakes"))

    def test_idempotent_no_overwrite(self, tmpdir):
        """Re-running deploy does not fail or overwrite existing skills."""
        self._setup_source_skills(str(tmpdir), panel)

        profiles_dir = os.path.join(str(tmpdir), "profiles")
        for name in ["strategist", "coder", "tech-lead"]:
            os.makedirs(os.path.join(profiles_dir, name, "skills", "software-development"),
                       exist_ok=True)
        hermes_dir = os.path.join(str(tmpdir), "skills", "software-development")
        os.makedirs(hermes_dir, exist_ok=True)

        with patch.object(panel._utils, "PROFILES", profiles_dir), \
             patch.object(panel._utils, "HERMES", os.path.join(str(tmpdir))):
            # First deploy
            panel.deploy_profile_skills()
            # Second deploy — should not crash
            panel.deploy_profile_skills()

            # Skills should still be there
            strat_dir = os.path.join(profiles_dir, "strategist", "skills", "software-development")
            assert os.path.isdir(os.path.join(strat_dir, "spec-strategist-lite"))

    def test_missing_source_skill_warns(self, tmpdir):
        """When a source skill is missing, it warns but does not crash."""
        # Only create some skills, not all
        skills_dir = os.path.join(str(tmpdir), "skills")
        # Create only one skill — the rest are missing
        os.makedirs(os.path.join(skills_dir, "spec-strategist-lite"))
        with open(os.path.join(skills_dir, "spec-strategist-lite", "SKILL.md"), "w") as f:
            f.write("# spec-strategist-lite\\n")
        panel.PANEL_DIR = str(tmpdir)
        panel._utils.PANEL_DIR = str(tmpdir)

        profiles_dir = os.path.join(str(tmpdir), "profiles")
        for name in ["strategist", "coder"]:
            os.makedirs(os.path.join(profiles_dir, name, "skills", "software-development"),
                       exist_ok=True)

        with patch.object(panel._utils, "PROFILES", profiles_dir), \
             patch.object(panel._utils, "HERMES", os.path.join(str(tmpdir))):
            # Should not raise
            panel.deploy_profile_skills()

            # Existing skill should be deployed
            strat_dir = os.path.join(profiles_dir, "strategist", "skills", "software-development")
            assert os.path.isdir(os.path.join(strat_dir, "spec-strategist-lite"))

    def test_no_profiles_dir_yet(self, tmpdir):
        """When profile dirs don't exist, they are created automatically."""
        self._setup_source_skills(str(tmpdir), panel)

        profiles_dir = os.path.join(str(tmpdir), "profiles")
        # Don't pre-create profile dirs — deploy should create them

        with patch.object(panel._utils, "PROFILES", profiles_dir), \
             patch.object(panel._utils, "HERMES", os.path.join(str(tmpdir))):
            panel.deploy_profile_skills()

            # Profile dirs should have been created
            strat_dir = os.path.join(profiles_dir, "strategist", "skills", "software-development")
            assert os.path.isdir(os.path.join(strat_dir, "spec-strategist-lite"))


class TestIntegrationRunInit:
    """Integration tests — verify ensure_profiles + deploy_profile_skills
    are called during run_init()."""

    def test_init_calls_ensure_profiles(self):
        """run_init() calls ensure_profiles() before strategist phase."""
        # Use side_effect counters to verify call order
        call_order = []

        def mock_ensure():
            call_order.append("ensure_profiles")

        def mock_deploy():
            call_order.append("deploy_profile_skills")

        def mock_spawn(*args, **kwargs):
            call_order.append("spawn_agent")
            return "Mock output"

        with patch.object(panel, "ensure_profiles", side_effect=mock_ensure), \
             patch.object(panel, "deploy_profile_skills", side_effect=mock_deploy), \
             patch.object(panel._agent, "spawn_agent", side_effect=mock_spawn), \
             patch.object(panel, "load_key", return_value="test-key"), \
             patch.object(panel, "load_github_token", return_value="test-gh-token"), \
             patch.object(panel, "detect_repo", return_value="test/test"), \
             patch.object(subprocess, "run") as mock_run, \
             patch.object(os.path, "isdir", return_value=True), \
             patch.object(os.path, "exists", return_value=True):
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            panel.run_init("test description", "/tmp/test-dir")

            # Both should have been called
            assert "ensure_profiles" in call_order
            assert "deploy_profile_skills" in call_order

            # Both should be called BEFORE spawn_agent
            ensure_idx = call_order.index("ensure_profiles")
            deploy_idx = call_order.index("deploy_profile_skills")
            spawn_idx = call_order.index("spawn_agent")
            assert ensure_idx < spawn_idx, "ensure_profiles must run before spawn_agent"
            assert deploy_idx < spawn_idx, "deploy_profile_skills must run before spawn_agent"

    def test_init_proceeds_when_ensure_fails(self):
        """run_init() continues even if ensure_profiles raises an exception."""
        call_order = []

        def mock_ensure():
            call_order.append("ensure_profiles")
            raise RuntimeError("hermes not found")

        def mock_deploy():
            call_order.append("deploy_profile_skills")

        def mock_spawn(*args, **kwargs):
            call_order.append("spawn_agent")
            return "Mock output"

        with patch.object(panel, "ensure_profiles", side_effect=mock_ensure), \
             patch.object(panel, "deploy_profile_skills", side_effect=mock_deploy), \
             patch.object(panel._agent, "spawn_agent", side_effect=mock_spawn), \
             patch.object(panel, "load_key", return_value="test-key"), \
             patch.object(panel, "load_github_token", return_value="test-gh-token"), \
             patch.object(panel, "detect_repo", return_value="test/test"), \
             patch.object(subprocess, "run") as mock_run, \
             patch.object(os.path, "isdir", return_value=True), \
             patch.object(os.path, "exists", return_value=True):
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)

            # Should not raise — error is caught and logged
            panel.run_init("test description", "/tmp/test-dir")

            # deploy and spawn should still happen
            assert "deploy_profile_skills" in call_order
            assert "spawn_agent" in call_order
