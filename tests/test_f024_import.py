"""Tests for F024 Task 7: do_release import addition to dokima."""
import os, re


def _read_dokima_source():
    """Read the dokima script source."""
    script_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dokima"
    )
    with open(script_path) as f:
        return f.read()


def test_do_release_in_utils_import_block():
    """Verify do_release is listed in the 'from utils import (...)' block in dokima."""
    source = _read_dokima_source()

    # Find the from utils import block
    match = re.search(
        r'from utils import \((.*?)\)',
        source,
        re.DOTALL,
    )
    assert match, "from utils import (...) block not found in dokima"
    import_block = match.group(1)

    # Check do_release is among the imported names
    # Split on commas and strip whitespace
    imported_names = [name.strip() for name in import_block.split(",") if name.strip()]
    assert "do_release" in imported_names, (
        f"do_release not found in from utils import block. "
        f"Names present: {imported_names}"
    )


def test_do_release_next_to_check_upgrade_and_version_newer():
    """Verify do_release is positioned next to check_upgrade / _version_newer."""
    source = _read_dokima_source()

    # Extract the specific line(s) containing check_upgrade, _version_newer, do_release
    match = re.search(
        r'from utils import \((.*?)\)',
        source,
        re.DOTALL,
    )
    assert match, "from utils import (...) block not found in dokima"
    import_block = match.group(1)

    # do_release should be on the same conceptual line as check_upgrade and _version_newer
    # Find the line that contains check_upgrade
    lines = import_block.split("\n")
    found = False
    for line in lines:
        if "check_upgrade" in line and "_version_newer" in line:
            if "do_release" in line:
                found = True
            break
    assert found, (
        "do_release must appear on the same import line as "
        "check_upgrade and _version_newer"
    )
