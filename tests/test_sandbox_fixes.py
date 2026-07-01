"""Tests for sandbox installation fixes — double main(), skill paths, spec-kit name."""
import os
import re
import pytest


class TestDokimaMain:
    """Verify dokima has exactly one main() call (double-execution bug fix)."""

    def test_only_one_main_call(self):
        dokima_path = os.path.join(os.path.dirname(__file__), "..", "dokima")
        with open(dokima_path) as f:
            content = f.read()
        # Count occurrences of "if __name__ == \"__main__\":"
        count = content.count('if __name__ == "__main__":')
        assert count == 1, (
            f"Expected exactly 1 main() call, found {count}. "
            "Duplicate causes double-execution bugs (--release, init, etc.)"
        )


class TestSkillSourcePath:
    """Verify deploy_profile_skills finds skills from source directory."""

    def test_skill_source_fallback(self):
        """When PANEL_DIR has no skills/, fall back to utils.py directory."""
        import utils
        # Read the deploy_profile_skills function source to verify it has the fallback
        import inspect
        src = inspect.getsource(utils.deploy_profile_skills)
        assert 'os.path.dirname(os.path.abspath(__file__))' in src or \
               'os.path.dirname(__file__)' in src, (
            "deploy_profile_skills must fall back to source directory "
            "when PANEL_DIR/skills/ doesn't exist"
        )

    def test_spec_strategist_skill_deployed(self, panel):
        """spec-strategist-lite (not spec-kit) is in the deploy mapping."""
        import utils
        # Check the _SKILL_MAPPINGS inside deploy_profile_skills
        import inspect
        src = inspect.getsource(utils.deploy_profile_skills)
        assert '"spec-strategist-lite"' in src, (
            "deploy_profile_skills must deploy spec-strategist-lite"
        )
        # Also verify spec-kit is NOT in the mapping
        # (spec-kit is the old name that caused Unknown skill errors)
        assert '"spec-kit"' not in src, (
            "deploy_profile_skills must NOT deploy spec-kit — "
            "use spec-strategist-lite instead"
        )


class TestInitSkillName:
    """Verify run_init uses correct skill names."""

    def test_init_uses_spec_strategist_lite(self):
        """run_init spawns strategist with spec-strategist-lite, not spec-kit."""
        import roadmap
        import inspect
        src = inspect.getsource(roadmap.run_init)
        assert 'spec-strategist-lite' in src, (
            "run_init must use spec-strategist-lite (not spec-kit)"
        )
        assert 'spec-kit' not in src or 'spec-strategist-lite' in src.replace('spec-kit', ''), (
            "run_init must NOT use spec-kit (deprecated name)"
        )
