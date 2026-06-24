"""Tests for extract_agent_messages() — session transcript parsing."""
import pytest

BOX_MSG = "\u256d\u2500 \u2695 Hermes \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256e\nhello world\n\u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256f"

def test_hermes_box_format(panel):
    result = panel.extract_agent_messages(BOX_MSG)
    assert "hello world" in result

def test_no_box_markers_fallback(panel):
    result = panel.extract_agent_messages("plain text output")
    assert result == "plain text output"

def test_multiple_boxes(panel):
    msg = BOX_MSG + "\n\n" + BOX_MSG.replace("hello world", "second message")
    result = panel.extract_agent_messages(msg)
    assert "hello world" in result
    assert "second message" in result

def test_empty_box_skipped(panel):
    empty_box = "\u256d\u2500 \u2695 Hermes \u2500\u2500\u256e\n   \n\u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256f"
    result = panel.extract_agent_messages(empty_box)
    assert result.strip() == "" or result == empty_box

def test_partial_box_no_match(panel):
    # Only opening marker, no closing
    partial = "\u256d\u2500 \u2695 Hermes \u2500\u2500\u256e\ncontent"
    result = panel.extract_agent_messages(partial)
    # Should fall through to raw since no closing marker
    assert result == partial
