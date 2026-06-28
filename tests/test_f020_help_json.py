"""Tests for F020: --help-json structured CLI output."""
import json
import subprocess
import sys
import os

PANEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dokima"))


def run_help_json(*extra_args):
    """Run dokima --help-json with optional extra args, return (returncode, stdout, stderr)."""
    cmd = [sys.executable, PANEL_PATH, "--help-json"] + list(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return result.returncode, result.stdout, result.stderr


class TestHelpJsonOutput:
    """Task 4: --help-json output validation."""

    def test_help_json_exits_zero(self):
        """--help-json exits 0."""
        rc, stdout, _ = run_help_json()
        assert rc == 0, f"Expected exit 0, got {rc}"

    def test_help_json_produces_valid_json(self):
        """--help-json stdout is valid parseable JSON."""
        _, stdout, _ = run_help_json()
        data = json.loads(stdout)
        assert isinstance(data, dict)

    def test_help_json_has_required_top_level_keys(self):
        """JSON has tool, commands, flags, env_vars keys."""
        _, stdout, _ = run_help_json()
        data = json.loads(stdout)
        for key in ("tool", "commands", "flags", "env_vars"):
            assert key in data, f"Missing key: {key}"

    def test_help_json_tool_is_dokima(self):
        """tool field is 'dokima'."""
        _, stdout, _ = run_help_json()
        data = json.loads(stdout)
        assert data["tool"] == "dokima"

    def test_help_json_commands_are_non_empty(self):
        """Commands list has entries."""
        _, stdout, _ = run_help_json()
        data = json.loads(stdout)
        assert len(data["commands"]) >= 5, f"Expected >=5 commands, got {len(data['commands'])}"

    def test_help_json_flags_are_non_empty(self):
        """Flags list has entries."""
        _, stdout, _ = run_help_json()
        data = json.loads(stdout)
        assert len(data["flags"]) >= 8, f"Expected >=8 flags, got {len(data['flags'])}"

    def test_help_json_env_vars_are_non_empty(self):
        """env_vars list has entries."""
        _, stdout, _ = run_help_json()
        data = json.loads(stdout)
        assert len(data["env_vars"]) >= 5, f"Expected >=5 env_vars, got {len(data['env_vars'])}"

    def test_each_command_has_required_fields(self):
        """Every command has name, syntax, description."""
        _, stdout, _ = run_help_json()
        data = json.loads(stdout)
        for cmd in data["commands"]:
            for field in ("name", "syntax", "description"):
                assert field in cmd, f"Command {cmd.get('name', '?')} missing {field}"
                assert isinstance(cmd[field], str), f"Command {cmd['name']} {field} is not string"

    def test_each_flag_has_required_fields(self):
        """Every flag has flag, args, env_var, description."""
        _, stdout, _ = run_help_json()
        data = json.loads(stdout)
        for f in data["flags"]:
            for field in ("flag", "args", "env_var", "description"):
                assert field in f, f"Flag {f.get('flag', '?')} missing {field}"

    def test_each_env_var_has_required_fields(self):
        """Every env_var has name, description, related_flag."""
        _, stdout, _ = run_help_json()
        data = json.loads(stdout)
        for ev in data["env_vars"]:
            for field in ("name", "description", "related_flag"):
                assert field in ev, f"Env var {ev.get('name', '?')} missing {field}"

    def test_panel_max_parallel_in_flags(self):
        """PANEL_MAX_PARALLEL env var appears in flags or env_vars."""
        _, stdout, _ = run_help_json()
        data = json.loads(stdout)
        all_flag_names = {f["flag"] for f in data["flags"]}
        all_env_names = {ev["name"] for ev in data["env_vars"]}
        # --max-parallel has env_var PANEL_MAX_PARALLEL
        assert "--max-parallel" in all_flag_names or "PANEL_MAX_PARALLEL" in all_env_names, \
            "PANEL_MAX_PARALLEL / --max-parallel not found in output"


class TestHelpJsonEdgeCases:
    """Edge case behavior for --help-json."""

    def test_help_json_with_no_args(self):
        """--help-json exits 0 with no other args (doesn't demand feature description)."""
        rc, stdout, _ = run_help_json()
        assert rc == 0

    def test_help_json_with_extra_arg(self):
        """--help-json ignores extra positional arg."""
        rc, stdout, _ = run_help_json("/tmp")
        assert rc == 0
        data = json.loads(stdout)
        assert data["tool"] == "dokima"

    def test_help_json_before_help_flag(self):
        """When both --help-json and --help present, --help-json wins."""
        rc, stdout, _ = run_help_json("--help")
        assert rc == 0
        data = json.loads(stdout)
        assert isinstance(data, dict)
        assert "tool" in data


class TestHelpUnchanged:
    """--help behavior is untouched by --help-json addition."""

    def test_help_still_works(self):
        """--help exits 0 and shows usage."""
        cmd = [sys.executable, PANEL_PATH, "--help"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0
        assert "COMMANDS:" in result.stdout


class TestNoRegression:
    """Verify --help-json doesn't break anything."""

    def test_syntax_check_passes(self):
        """Panel compiles without syntax errors."""
        cmd = [sys.executable, "-c", f"compile(open('{PANEL_PATH}').read(), 'dokima', 'exec')"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Syntax check failed: {result.stderr}"
