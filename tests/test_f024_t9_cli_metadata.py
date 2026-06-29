"""Tests for Task 9: --release in CLI_METADATA."""
import sys
import os

# Add parent dir to path so we can import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_cli_metadata_has_release_command():
    """CLI_METADATA commands array includes --release entry."""
    import utils
    commands = utils.CLI_METADATA["commands"]
    release_entries = [c for c in commands if c.get("name") == "--release"]
    assert len(release_entries) == 1, (
        f"Expected exactly 1 --release entry in CLI_METADATA commands, "
        f"found {len(release_entries)}"
    )


def test_release_command_has_required_fields():
    """--release CLI_METADATA entry has name, syntax, description."""
    import utils
    commands = utils.CLI_METADATA["commands"]
    release = [c for c in commands if c.get("name") == "--release"][0]
    for field in ("name", "syntax", "description"):
        assert field in release, f"--release entry missing '{field}'"
        assert isinstance(release[field], str), (
            f"--release {field} is not a string"
        )
        assert release[field], f"--release {field} is empty"


def test_release_command_syntax_matches_spec():
    """--release syntax matches spec: dokima --release <patch|minor|major> [--dry-run] [project_dir]."""
    import utils
    commands = utils.CLI_METADATA["commands"]
    release = [c for c in commands if c.get("name") == "--release"][0]
    expected_syntax = "dokima --release <patch|minor|major> [--dry-run] [project_dir]"
    assert release["syntax"] == expected_syntax, (
        f"--release syntax mismatch.\n"
        f"Expected: {expected_syntax!r}\n"
        f"Got:      {release['syntax']!r}"
    )


def test_release_command_description_matches_spec():
    """--release description matches spec."""
    import utils
    commands = utils.CLI_METADATA["commands"]
    release = [c for c in commands if c.get("name") == "--release"][0]
    expected_desc = (
        "Bump version, generate changelog, tag, and publish GitHub Release"
    )
    assert release["description"] == expected_desc, (
        f"--release description mismatch.\n"
        f"Expected: {expected_desc!r}\n"
        f"Got:      {release['description']!r}"
    )
