"""Tests for generate_codebase_map() and _describe_file().

Covers: .mdx inclusion (regression), tech detection, commands, incremental
vs full mode, cache integrity, skip-dir enforcement, and edge cases.
"""
import os
import json
import tempfile
import pytest
from conftest import _load_panel as _load


@pytest.fixture(scope="module")
def panel():
    return _load()


# ── _describe_file ──────────────────────────────────────────────

def test_describe_python_exports(panel):
    desc = panel._describe_file("worker.py", "def process():\n    pass\n\nclass TaskRunner:\n    pass\n", "src/worker.py")
    assert "process" in desc
    assert "TaskRunner" in desc


def test_describe_typescript_exports(panel):
    desc = panel._describe_file("Header.tsx", 'export const Header = () => <div />;\nexport default Header;\n', "src/Header.tsx")
    assert "Header" in desc


def test_describe_jsdoc(panel):
    desc = panel._describe_file("api.ts", "/**\n * Fetch user data from API\n */\nexport async function fetchUser() {}", "src/api.ts")
    assert "Fetch user data" in desc


def test_describe_comment_first_line(panel):
    desc = panel._describe_file("config.py", "# Database connection settings\nDB_HOST = 'localhost'\n", "config.py")
    assert "Database connection" in desc


def test_describe_filename_fallback(panel):
    desc = panel._describe_file("layout.tsx", "export default function Layout({ children }) {}", "src/layout.tsx")
    assert "layout" in desc.lower()


def test_describe_empty_file(panel):
    desc = panel._describe_file("empty.py", "", "empty.py")
    assert desc == ""


def test_describe_mdx_file(panel):
    """MDX files should work — critical since .mdx was missing from source_exts."""
    desc = panel._describe_file("getting-started.mdx", "# Getting Started\n\nWelcome to the guide.\n", "content/getting-started.mdx")
    # MDX doesn't have exports/docstrings, so description may be empty or filename-based
    assert isinstance(desc, str)


def test_describe_rust_no_crash(panel):
    desc = panel._describe_file("main.rs", "fn main() {}\npub fn init() {}\n", "src/main.rs")
    assert isinstance(desc, str)


# ── generate_codebase_map ───────────────────────────────────────

@pytest.fixture
def tmp_project():
    """Create a minimal project tree for map generation."""
    with tempfile.TemporaryDirectory() as d:
        specs_dir = os.path.join(d, "specs")
        os.makedirs(specs_dir, exist_ok=True)

        # AGENTS.md with commands
        with open(os.path.join(d, "AGENTS.md"), "w") as f:
            f.write("Test: pytest\nBuild: npm run build\nLint: eslint\n")

        # package.json for tech detection
        with open(os.path.join(d, "package.json"), "w") as f:
            f.write('{"dependencies": {"next": "^16.0.0", "react": "^19.0.0"}, "devDependencies": {"typescript": "^5.0.0", "vitest": "^2.0.0"}}')

        # Source files
        os.makedirs(os.path.join(d, "src", "components"), exist_ok=True)
        with open(os.path.join(d, "src", "layout.tsx"), "w") as f:
            f.write("// Root layout\nexport default function Layout({ children }) { return <html>{children}</html>; }\n")
        with open(os.path.join(d, "src", "components", "Header.tsx"), "w") as f:
            f.write("export const Header = () => <header>Dokima</header>;\n")
        with open(os.path.join(d, "src", "page.tsx"), "w") as f:
            f.write("export default function Home() { return <h1>Home</h1>; }\n")

        # MDX content file (the extension we fixed)
        os.makedirs(os.path.join(d, "content"), exist_ok=True)
        with open(os.path.join(d, "content", "guide.mdx"), "w") as f:
            f.write("# User Guide\n\nWelcome.\n")

        # CSS
        with open(os.path.join(d, "src", "globals.css"), "w") as f:
            f.write("/* Global styles */\n:root { --color: red; }\n")

        yield d


def test_map_includes_mdx(tmp_project, panel):
    """The map must include .mdx files — regression test for the extension bug."""
    result = panel.generate_codebase_map(tmp_project, full=True)
    assert result is True

    map_path = os.path.join(tmp_project, "specs", "codebase-map.md")
    assert os.path.exists(map_path)

    with open(map_path) as f:
        content = f.read()

    assert "layout.tsx" in content
    assert "Header.tsx" in content
    assert "page.tsx" in content
    assert "globals.css" in content
    assert "guide.mdx" in content, f"MDX file missing from map!\n{content}"


def test_map_tech_detection(tmp_project, panel):
    """Tech stack should be detected from package.json."""
    panel.generate_codebase_map(tmp_project, full=True)
    map_path = os.path.join(tmp_project, "specs", "codebase-map.md")
    with open(map_path) as f:
        content = f.read()
    assert "Next.js" in content
    assert "React" in content
    assert "TypeScript" in content
    assert "Vitest" in content


def test_map_commands_from_agents(tmp_project, panel):
    """Commands should be extracted from AGENTS.md."""
    panel.generate_codebase_map(tmp_project, full=True)
    map_path = os.path.join(tmp_project, "specs", "codebase-map.md")
    with open(map_path) as f:
        content = f.read()
    assert "pytest" in content
    assert "npm run build" in content
    assert "eslint" in content


def test_map_incremental_no_change(tmp_project, panel):
    """Incremental mode with no file changes should return False."""
    result1 = panel.generate_codebase_map(tmp_project, full=True)
    assert result1 is True
    result2 = panel.generate_codebase_map(tmp_project, full=False)
    assert result2 is False


def test_map_incremental_detects_change(tmp_project, panel):
    """Incremental mode should detect a changed file."""
    panel.generate_codebase_map(tmp_project, full=True)
    with open(os.path.join(tmp_project, "src", "Header.tsx"), "a") as f:
        f.write("\n// New comment\n")
    result = panel.generate_codebase_map(tmp_project, full=False)
    assert result is True


def test_map_skips_node_modules(tmp_project, panel):
    """node_modules should never appear in the map."""
    os.makedirs(os.path.join(tmp_project, "node_modules", "some-pkg"), exist_ok=True)
    with open(os.path.join(tmp_project, "node_modules", "some-pkg", "index.js"), "w") as f:
        f.write("module.exports = {};\n")
    panel.generate_codebase_map(tmp_project, full=True)
    map_path = os.path.join(tmp_project, "specs", "codebase-map.md")
    with open(map_path) as f:
        content = f.read()
    assert "node_modules" not in content
    assert "index.js" not in content


def test_map_skips_dot_dirs(tmp_project, panel):
    """.git, .next, .hermes directories should be excluded."""
    for skip_dir in [".git", ".next", ".hermes"]:
        d = os.path.join(tmp_project, skip_dir)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "config.txt"), "w") as f:
            f.write("skip me\n")
    panel.generate_codebase_map(tmp_project, full=True)
    map_path = os.path.join(tmp_project, "specs", "codebase-map.md")
    with open(map_path) as f:
        content = f.read()
    assert "config.txt" not in content


def test_map_file_count(tmp_project, panel):
    """Map should report the correct file count."""
    panel.generate_codebase_map(tmp_project, full=True)
    map_path = os.path.join(tmp_project, "specs", "codebase-map.md")
    with open(map_path) as f:
        content = f.read()
    # 7 source files: AGENTS.md, package.json, layout.tsx, Header.tsx, page.tsx, globals.css, guide.mdx
    assert "7 files" in content


def test_map_cache_written(tmp_project, panel):
    """Incremental cache should be written with hashes and descriptions."""
    panel.generate_codebase_map(tmp_project, full=True)
    cache_path = os.path.join(tmp_project, "specs", ".map-cache.json")
    assert os.path.exists(cache_path)
    with open(cache_path) as f:
        cache = json.load(f)
    assert len(cache) >= 7  # AGENTS.md + package.json + 5 source files (exact count depends on walk order)
    for key in cache:
        assert "hash" in cache[key]
        assert "desc" in cache[key]
        assert len(cache[key]["hash"]) == 32


def test_map_empty_project(panel):
    """Should not crash on a project with no source files."""
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "specs"), exist_ok=True)
        result = panel.generate_codebase_map(d, full=True)
        assert result is True
        assert os.path.exists(os.path.join(d, "specs", "codebase-map.md"))


def test_map_no_agents_md(tmp_project, panel):
    """Should handle missing AGENTS.md gracefully."""
    os.remove(os.path.join(tmp_project, "AGENTS.md"))
    result = panel.generate_codebase_map(tmp_project, full=True)
    assert result is True
    map_path = os.path.join(tmp_project, "specs", "codebase-map.md")
    with open(map_path) as f:
        content = f.read()
    assert "test: ?" in content
    assert "build: ?" in content
    assert "lint: ?" in content


def test_map_full_rebuild(tmp_project, panel):
    """Full rebuild should update everything even after file changes."""
    panel.generate_codebase_map(tmp_project, full=True)
    with open(os.path.join(tmp_project, "src", "Header.tsx"), "a") as f:
        f.write("// v2\n")
    result = panel.generate_codebase_map(tmp_project, full=True)
    assert result is True
    cache_path = os.path.join(tmp_project, "specs", ".map-cache.json")
    with open(cache_path) as f:
        cache = json.load(f)
    assert len(cache) >= 7  # AGENTS.md + package.json + 5 source files (exact count depends on walk order)


# ── F027: Domain-aware map format ─────────────────────────────────

def test_map_domain_aware_sections(tmp_project, panel):
    """F027: Map must output 4 domain-aware sections instead of flat Tree + Commands."""
    panel.generate_codebase_map(tmp_project, full=True)
    map_path = os.path.join(tmp_project, "specs", "codebase-map.md")
    with open(map_path) as f:
        content = f.read()

    # New section headers must exist
    assert "## Start Here" in content, f"Missing Start Here section\n{content}"
    assert "## Domain Map" in content, f"Missing Domain Map section\n{content}"
    assert "## Impact Map" in content, f"Missing Impact Map section\n{content}"
    assert "## Test Map" in content, f"Missing Test Map section\n{content}"

    # Old format headers must NOT exist
    assert "## Tree" not in content, f"Old ## Tree header still present\n{content}"
    assert "## Commands" not in content, f"Old ## Commands header still present\n{content}"
