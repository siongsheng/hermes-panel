"""Test that utils.py module exists and exports the expected public API."""
import sys
import os


def test_utils_importable():
    """utils.py can be imported as a module."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    try:
        import utils  # noqa: F401
    except ImportError as e:
        assert False, f"utils.py is not importable: {e}"
    finally:
        sys.path.pop(0)


def test_utils_exports_slugify():
    """utils.py exports slugify() function."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    try:
        import utils
        assert hasattr(utils, 'slugify'), "utils.py missing slugify export"
        assert callable(utils.slugify), "slugify should be callable"
    finally:
        sys.path.pop(0)


def test_utils_exports_git():
    """utils.py exports git() function."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    try:
        import utils
        assert hasattr(utils, 'git'), "utils.py missing git export"
        assert callable(utils.git), "git should be callable"
    finally:
        sys.path.pop(0)


def test_utils_exports_sanitize_prompt():
    """utils.py exports _sanitize_prompt() for security."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    try:
        import utils
        assert hasattr(utils, '_sanitize_prompt'), "utils.py missing _sanitize_prompt export"
        assert callable(utils._sanitize_prompt), "_sanitize_prompt should be callable"
    finally:
        sys.path.pop(0)


def test_utils_exports_load_key():
    """utils.py exports load_key() for API key loading."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    try:
        import utils
        assert hasattr(utils, 'load_key'), "utils.py missing load_key export"
    finally:
        sys.path.pop(0)


def test_utils_module_compiles():
    """utils.py compiles without syntax errors."""
    utils_path = os.path.join(os.path.dirname(__file__), '..', 'utils.py')
    assert os.path.exists(utils_path), "utils.py does not exist"
    with open(utils_path) as f:
        code = f.read()
    compile(code, utils_path, 'exec')
