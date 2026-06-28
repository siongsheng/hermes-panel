"""Tests for extract_file_paths() — parses backtick-quoted and **Files:** paths.

Two patterns: (1) `path/to/file.tsx` backtick-quoted,
(2) **Files:** path/to/file1, path/to/file2 from task extracts.
"""
import pytest
from conftest import _load_panel as _load


class TestExtractFilePathsBacktick:
    """Pattern 1: backtick-quoted paths `like/this.tsx`."""

    def test_single_path(self, panel):
        result = panel.extract_file_paths("Fix `src/components/Sidebar.tsx`")
        assert result == ["src/components/Sidebar.tsx"]

    def test_path_with_line_numbers(self, panel):
        result = panel.extract_file_paths("See `src/app/layout.tsx:29-33`")
        assert result == ["src/app/layout.tsx"]

    def test_path_with_single_line_number(self, panel):
        result = panel.extract_file_paths("Bug at `src/utils/helpers.ts:42`")
        assert result == ["src/utils/helpers.ts"]

    def test_leading_dot_slash_stripped(self, panel):
        result = panel.extract_file_paths("Import from `./src/lib/auth.ts`")
        assert result == ["src/lib/auth.ts"]

    def test_multiple_backtick_paths(self, panel):
        text = "Changed `src/components/Header.tsx` and `src/app/page.tsx`"
        result = panel.extract_file_paths(text)
        assert result == ["src/app/page.tsx", "src/components/Header.tsx"]

    def test_ignores_urls(self, panel):
        result = panel.extract_file_paths("See `https://example.com/api/docs.md`")
        assert result == []

    def test_ignores_git_commands(self, panel):
        result = panel.extract_file_paths("Run `git checkout main` first")
        assert result == []

    def test_ignores_bare_filename_no_slash(self, panel):
        """Filenames without a directory separator are ambiguous — skip."""
        result = panel.extract_file_paths("Edit `layout.tsx`")
        assert result == []

    def test_dedup_duplicate_paths(self, panel):
        text = "Fix `src/app/layout.tsx` here and `src/app/layout.tsx` there"
        result = panel.extract_file_paths(text)
        assert result == ["src/app/layout.tsx"]

    def test_empty_text(self, panel):
        assert panel.extract_file_paths("") == []

    def test_text_with_no_paths(self, panel):
        result = panel.extract_file_paths("This text has no file paths at all.")
        assert result == []

    def test_non_code_paths_with_extension(self, panel):
        """Assets, data files, etc. should also be extracted."""
        result = panel.extract_file_paths("Update `public/logo.svg`")
        assert result == ["public/logo.svg"]


class TestExtractFilePathsTaskExtract:
    """Pattern 2: **Files:** lines from strategist task extracts."""

    def test_single_file_on_files_line(self, panel):
        result = panel.extract_file_paths(
            "**Files:** src/app/(docs)/guides/cli/page.mdx\n"
            "**Dependencies:** \n"
        )
        assert result == ["src/app/(docs)/guides/cli/page.mdx"]

    def test_multiple_comma_separated_files(self, panel):
        result = panel.extract_file_paths(
            "**Files:** src/components/Header.tsx, src/app/layout.tsx, src/lib/auth.ts\n"
        )
        assert result == [
            "src/app/layout.tsx",
            "src/components/Header.tsx",
            "src/lib/auth.ts",
        ]

    def test_semicolon_separated_files(self, panel):
        result = panel.extract_file_paths(
            "**Files:** src/a.ts; src/b.ts; src/c.ts\n"
        )
        assert result == ["src/a.ts", "src/b.ts", "src/c.ts"]

    def test_mixed_comma_and_semicolon(self, panel):
        result = panel.extract_file_paths(
            "**Files:** src/Header.tsx, src/Footer.tsx; src/Sidebar.tsx\n"
        )
        assert result == ["src/Footer.tsx", "src/Header.tsx", "src/Sidebar.tsx"]

    def test_leading_trailing_whitespace(self, panel):
        result = panel.extract_file_paths(
            "**Files:**   src/app/page.tsx ,  src/lib/helpers.ts  \n"
        )
        assert result == ["src/app/page.tsx", "src/lib/helpers.ts"]

    def test_files_line_with_extra_description(self, panel):
        """Only paths before the end of line should be extracted."""
        result = panel.extract_file_paths(
            "**Files:** src/app/page.mdx, src/test/page.test.ts\n"
            "**Dependencies:** Task 1\n"
            "**Description:** Write the page and test it\n"
        )
        assert result == ["src/app/page.mdx", "src/test/page.test.ts"]

    def test_multiple_files_lines(self, panel):
        text = (
            "### Task 1: Create page\n"
            "**Files:** src/app/about/page.mdx\n\n"
            "### Task 2: Add test\n"
            "**Files:** src/__tests__/about.test.ts, src/__tests__/setup.ts\n"
        )
        result = panel.extract_file_paths(text)
        assert result == [
            "src/__tests__/about.test.ts",
            "src/__tests__/setup.ts",
            "src/app/about/page.mdx",
        ]

    def test_files_line_ignores_urls(self, panel):
        result = panel.extract_file_paths(
            "**Files:** https://docs.example.com/api.md, src/local/file.ts\n"
        )
        assert result == ["src/local/file.ts"]

    def test_files_line_without_slash_skipped(self, panel):
        """Bare filenames in **Files:** lines are now accepted (explicit from task extract)."""
        result = panel.extract_file_paths("**Files:** page.mdx, layout.tsx\n")
        assert result == ["layout.tsx", "page.mdx"]


class TestExtractFilePathsCombined:
    """Both patterns present in the same text."""

    def test_both_patterns_in_same_text(self, panel):
        text = (
            "BLOCKER: Fix `src/components/Sidebar.tsx:42` per the spec.\n\n"
            "### Task 1: Update sidebar\n"
            "**Files:** src/components/Sidebar.tsx, src/__tests__/Sidebar.test.tsx\n"
        )
        result = panel.extract_file_paths(text)
        # Sidebar.tsx appears in both — deduped
        assert result == [
            "src/__tests__/Sidebar.test.tsx",
            "src/components/Sidebar.tsx",
        ]

    def test_realistic_task_extract(self, panel):
        """Simulate a full strategist task extract with 3 tasks."""
        text = (
            "### Task 1: Create CLI reference page\n"
            "**Files:** src/app/(docs)/guides/cli/page.mdx\n"
            "**Dependencies:** \n"
            "**Parallelizable:** no\n"
            "**Description:** Write the MDX page with all commands and flags.\n\n"
            "### Task 2: Add validation test\n"
            "**Files:** src/__tests__/guides/cli-reference.test.ts\n"
            "**Dependencies:** Task 1\n"
            "**Parallelizable:** yes\n"
            "**Description:** Test completeness against command/flag manifest.\n\n"
            "### Task 3: Update README\n"
            "**Files:** README.md, src/config/sidebar.ts\n"
            "**Dependencies:** Task 1\n"
            "**Parallelizable:** yes\n"
            "**Description:** Add new page to project structure docs.\n"
        )
        result = panel.extract_file_paths(text)
        # Capped at 12 by the caller, not here — this returns all
        assert "src/app/(docs)/guides/cli/page.mdx" in result
        assert "src/__tests__/guides/cli-reference.test.ts" in result
        assert "src/config/sidebar.ts" in result
        # README.md now accepted (bare filenames from **Files:** lines are explicit)
        assert "README.md" in result
        assert len(result) == 4
