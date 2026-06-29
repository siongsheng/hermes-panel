"""F022 Modular Architecture — behavioral tests for agent.py.

Tests call functions with real data (not just hasattr checks).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


# ── _detect_provider_failure ────────────────────────

def test_detect_provider_failure_none():
    """None output with returncode=0 is not a failure."""
    import agent
    assert agent._detect_provider_failure(None, 0) is False


def test_detect_provider_failure_empty_nonzero():
    """Empty output with non-zero returncode IS a failure."""
    import agent
    assert agent._detect_provider_failure("", 1) is True


def test_detect_provider_failure_timeout_pattern():
    """TIMEOUT: in output is a provider failure."""
    import agent
    assert agent._detect_provider_failure("TIMEOUT: connection timed out") is True


def test_detect_provider_failure_503():
    """HTTP 503 is a provider failure."""
    import agent
    assert agent._detect_provider_failure("HTTP 503 Service Unavailable") is True


def test_detect_provider_failure_429():
    """429 Too Many Requests is a provider failure."""
    import agent
    assert agent._detect_provider_failure("429 Too Many Requests") is True


def test_detect_provider_failure_connection_refused():
    """connection refused is a provider failure."""
    import agent
    assert agent._detect_provider_failure("connection refused") is True


def test_detect_provider_failure_normal_output():
    """Normal output is NOT a failure."""
    import agent
    assert agent._detect_provider_failure("Everything is fine here", 0) is False


# ── _load_fallback_config ─────────────────────────

def test_load_fallback_config_no_env():
    """With no env vars set, returns empty dict."""
    import agent
    # Save and clear relevant env vars
    saved = {}
    for k in ("PANEL_FALLBACK_STRATEGIST", "PANEL_FALLBACK_CODER", "PANEL_FALLBACK_TECH_LEAD"):
        saved[k] = os.environ.pop(k, None)
    try:
        result = agent._load_fallback_config()
        assert result == {}
    finally:
        # Restore
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_load_fallback_config_valid():
    """Valid env var returns expected config key."""
    import agent
    saved = os.environ.get("PANEL_FALLBACK_STRATEGIST")
    try:
        os.environ["PANEL_FALLBACK_STRATEGIST"] = "gpt-4"
        result = agent._load_fallback_config()
        assert "strategist" in result
        assert result["strategist"] == "gpt-4"
    finally:
        if saved is not None:
            os.environ["PANEL_FALLBACK_STRATEGIST"] = saved
        else:
            os.environ.pop("PANEL_FALLBACK_STRATEGIST", None)


def test_load_fallback_config_invalid_skipped():
    """Invalid format value is skipped with warning."""
    import agent
    saved = os.environ.get("PANEL_FALLBACK_CODER")
    try:
        os.environ["PANEL_FALLBACK_CODER"] = "model with spaces!"
        result = agent._load_fallback_config()
        assert "coder" not in result
    finally:
        if saved is not None:
            os.environ["PANEL_FALLBACK_CODER"] = saved
        else:
            os.environ.pop("PANEL_FALLBACK_CODER", None)


# ── call_agent ─────────────────────────────────────

def test_call_agent_connection_refused():
    """call_agent raises ValueError when nothing listens on port."""
    import agent
    # Use a port that's very unlikely to be in use
    with pytest.raises(ValueError, match="API call failed"):
        agent.call_agent(port=19999, system_prompt="test", user_prompt="test", max_tokens=10)


# ── Module compiles and imports ────────────────────

def test_agent_module_compiles():
    """agent.py compiles without syntax errors."""
    agent_path = os.path.join(os.path.dirname(__file__), '..', 'agent.py')
    assert os.path.exists(agent_path)
    with open(agent_path) as f:
        code = f.read()
    compile(code, agent_path, 'exec')
