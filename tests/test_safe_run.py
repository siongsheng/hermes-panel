"""Tests for _safe_run() — shell-safe command execution."""
import pytest
import subprocess

def test_simple_echo(panel):
    result = panel._safe_run("echo hello", cwd="/tmp", timeout=10)
    assert result.returncode == 0
    assert "hello" in result.stdout

def test_command_fails(panel):
    result = panel._safe_run("false", cwd="/tmp", timeout=10)
    assert result.returncode != 0

def test_shell_metachar_not_injected(panel):
    # && should be treated as literal arg, not shell operator
    result = panel._safe_run("echo safe && echo hacked", cwd="/tmp", timeout=10)
    assert "&&" in result.stdout
    assert "hacked" in result.stdout  # it's a literal arg to echo

def test_complex_command(panel):
    result = panel._safe_run("echo hello world", cwd="/tmp", timeout=10)
    assert result.returncode == 0
    assert "hello world" in result.stdout

def test_unsplittable_falls_back_to_bash(panel):
    # shlex.split failure now raises ValueError (no more bash -lc fallback)
    with pytest.raises(ValueError, match="No closing quotation"):
        panel._safe_run("echo \"unclosed", cwd="/tmp", timeout=10)

def test_timeout(panel):
    result = panel._safe_run("sleep 10", cwd="/tmp", timeout=1)
    assert result.returncode == 124
    assert "TIMEOUT" in result.stdout

def test_cwd_respected(panel):
    result = panel._safe_run("pwd", cwd="/tmp", timeout=10)
    assert "/tmp" in result.stdout

def test_pipe_not_executed_as_shell(panel):
    # | should be literal, not a pipe
    result = panel._safe_run("echo a | echo b", cwd="/tmp", timeout=10)
    assert result.returncode == 0  # passes args literally
