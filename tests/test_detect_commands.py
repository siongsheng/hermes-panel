"""Tests for detect_commands()."""
import os
import pytest


def test_detect_commands_has_structure(panel, test_repo):
    """detect_commands() returns test, build, lint commands."""
    panel.PROJECT_DIR = test_repo
    test_cmd, build_cmd, lint_cmd = panel.detect_commands()
    assert test_cmd is not None
    assert build_cmd is not None
    assert lint_cmd is not None
