"""F022 Modular Architecture — test that all spec-mandated functions are importable from utils.py."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest


def test_utils_has_halt_and_revert():
    """halt_and_revert is importable from utils.py."""
    import utils
    assert hasattr(utils, "halt_and_revert")
    assert callable(utils.halt_and_revert)


def test_utils_has_archive_specs_for_feature():
    """archive_specs_for_feature is importable from utils.py."""
    import utils
    assert hasattr(utils, "archive_specs_for_feature")
    assert callable(utils.archive_specs_for_feature)
