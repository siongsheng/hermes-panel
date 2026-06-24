"""Tests for slugify() — string normalization with collision prevention."""
import pytest

def test_clean_input_no_change(panel):
    assert panel.slugify("hello-world") == "hello-world"

def test_spaces_to_hyphens(panel):
    assert panel.slugify("Hello World Feature") == "hello-world-feature"

def test_special_chars_removed(panel):
    result = panel.slugify("Fix: OAuth2 login (urgent!!)")
    assert result == "fix-oauth2-login-urgent"

def test_exactly_40_chars_no_hash(panel):
    s = "a" * 40
    assert panel.slugify(s) == s

def test_41_chars_appends_hash(panel):
    s = "a" * 41
    result = panel.slugify(s)
    assert len(result) == 49  # 40 + hyphen + 8 hex
    assert result[40] == "-"
    assert len(result[41:]) == 8  # 8-char hex suffix

def test_long_input_truncated_with_hash(panel):
    s = "x" * 150
    result = panel.slugify(s)
    assert len(result) == 49
    assert result.startswith("x" * 40 + "-")

def test_empty_string(panel):
    assert panel.slugify("") == ""

def test_all_special_chars(panel):
    assert panel.slugify("!@#$%^&*()") == ""

def test_unicode_emoji_stripped(panel):
    result = panel.slugify("\U0001f389 deploy \U0001f680")
    assert "deploy" in result
    assert "\U0001f389" not in result

def test_different_suffix_different_hash(panel):
    s1 = "a" * 40 + "x"
    s2 = "a" * 40 + "y"
    r1 = panel.slugify(s1)
    r2 = panel.slugify(s2)
    assert r1 != r2  # different hashes
