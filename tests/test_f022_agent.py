"""Test that agent.py module exists and exports the expected public API."""
import sys
import os


def test_agent_importable():
    """agent.py can be imported as a module."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    try:
        import agent  # noqa: F401
    except ImportError as e:
        assert False, f"agent.py is not importable: {e}"
    finally:
        sys.path.pop(0)


def test_agent_exports_call_agent():
    """agent.py exports call_agent() function."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    try:
        import agent
        assert hasattr(agent, 'call_agent'), "agent.py missing call_agent export"
        assert callable(agent.call_agent), "call_agent should be callable"
    finally:
        sys.path.pop(0)


def test_agent_exports_spawn_agent():
    """agent.py exports spawn_agent() function."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    try:
        import agent
        assert hasattr(agent, 'spawn_agent'), "agent.py missing spawn_agent export"
        assert callable(agent.spawn_agent), "spawn_agent should be callable"
    finally:
        sys.path.pop(0)


def test_agent_exports_detect_provider_failure():
    """agent.py exports _detect_provider_failure() for provider health checks."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    try:
        import agent
        assert hasattr(agent, '_detect_provider_failure'), "agent.py missing _detect_provider_failure"
    finally:
        sys.path.pop(0)


def test_agent_module_compiles():
    """agent.py compiles without syntax errors."""
    agent_path = os.path.join(os.path.dirname(__file__), '..', 'agent.py')
    assert os.path.exists(agent_path), "agent.py does not exist"
    with open(agent_path) as f:
        code = f.read()
    compile(code, agent_path, 'exec')
