"""Tests for F012: Profile Templates — ensure_profiles() and deploy_profile_skills()."""
import os
import sys
import subprocess
from unittest.mock import patch, MagicMock, call
from conftest import _load_panel as _load

panel = _load()


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
