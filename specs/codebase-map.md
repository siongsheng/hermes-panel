## Project: dokima
## Tech: detected at runtime
## Generated: 2026-07-03 02:48:38 (incremental | 83 files)

## Start Here
**dokima** is a software project in this directory.
- Test: ``python3 -m pytest tests/ -q``
- Build: ``python3 -c "compile(open('dokima').read(), 'dokima', 'exec')"``
- Lint: ``python3 -m py_compile dokima``
Key files: agent.py, pipeline.py, utils.py
Read the Domain Map below to understand the file organization before exploring individual files.

## Domain Map
### Pipeline Orchestration
- .pipeline-status.json
- pipeline.py  — Set by conftest._load_panel() — see utils.py _IMPORTING_PANEL docstring (F022b).
- roadmap.py  — Exports: parse_roadmap
- status.py  — Exports: TaskStatus, PhaseTiming, PipelineStatus
- tasks.py  — Exports: WorktreeManager

### Agent Management
- agent.py  — ── Module-level globals (set by main()) ──────────

### Utilities
- utils.py  — shutil imported dynamically where needed (deploy_profile_skills)

### Scripts
- install.sh  — Dokima Installer — one-command setup
- scripts/setup-linux.sh  — ───────────────────────────────────────────────────────────────────

### Skills
- skills/adversarial-review-lite/SKILL.md  — Adversarial Review (Lite — Tech Lead Edition)
- skills/ai-coding-best-practices-lite/SKILL.md  — AI Coding Best Practices (Lite — Coder Edition)
- skills/no-mistakes/SKILL.md  — No Mistakes — Validation Pipeline
- skills/no-mistakes/references/python-default-argument-pitfall.md  — Python Default Argument Binding Trap
- skills/no-mistakes/references/vitest-dotenv-setup.md  — Vitest dotenv Setup
- skills/ponytail-guard/SKILL.md  — Ponytail Guard — Laziness Ladder for dokima
- skills/spec-strategist-lite/SKILL.md  — Spec Strategist (Lite — Panel Edition)

### Tests
- tests/conftest.py  — Exports: _load_panel
- tests/htmlcov/coverage_html_cb_dd2e7eb5.js  — Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
- tests/htmlcov/status.json
- tests/htmlcov/style_cb_4667309f.css
- tests/test_acquire_lock.py  — Exports: test_first_acquisition_succeeds, test_second_acquisition_blocked, test_stale_lock_dead_pid
- tests/test_add_to_roadmap.py
- tests/test_clean_spec.py  — Exports: TestCleanSpecContent
- tests/test_codebase_map.py  — assert "Fetch user data" in desc
- tests/test_conftest_fixtures.py  — Exports: TestTestRepoFixture, TestMockOrchestratorFixture
- tests/test_continuous.py  — Exports: _setup_two_features, test_continuous_loop_two_features
- tests/test_control_panel.py  — Exports: test_show_help_exits_zero, test_handle_status_idle, test_handle_status_running, test_handle_stop_no_running, test_handle_stop_creates_stop_file
- tests/test_dag_format.py  — Exports: panel, test_dag_regex_matches_valid, test_dag_regex_rejects_invalid, test_dag_regex_matches_multiple
- tests/test_detect_commands.py  — Exports: test_first_acquisition_succeeds, test_second_acquisition_blocked, test_stale_lock_dead_pid
- tests/test_edge_cases.py  — Exports: _setup
- tests/test_execution_mode_dispatch.py  — Exports: _reset_called, _mock_run_phase2_coder, _mock_run_phase2_coder_capture, _mock_run_parallel_coders, _mock_halt_and_revert
- tests/test_extract_agent.py  — Exports: test_hermes_box_format, test_no_box_markers_fallback, test_multiple_boxes, test_empty_box_skipped, test_partial_box_no_match
- tests/test_extract_file_paths.py  — Exports: TestExtractFilePathsBacktick
- tests/test_extract_pr.py
- tests/test_f001_security.py  — Exports: _load_panel, TestPromptSanitizer
- tests/test_f002_closure.py  — Exports: test_f002_marked_done_in_roadmap, test_f002_recorded_in_status
- tests/test_f003_robustness.py  — Exports: _make_result, TestRedOnlyCommits
- tests/test_f005_fallback.py  — Exports: TestDetectProviderFailure
- tests/test_f006_recovery.py  — Exports: TestCheckpointPath, TestSaveCheckpoint
- tests/test_f020_help_json.py  — Exports: run_help_json, TestHelpJsonOutput
- tests/test_f021_version.py  — Exports: _run, test_version_flag_prints_version_and_exits_0, test_help_includes_version_command, test_help_includes_upgrade_command, test_help_json_includes_version
- tests/test_f022_agent.py  — Exports: test_detect_provider_failure_none, test_detect_provider_failure_empty_nonzero, test_detect_provider_failure_timeout_pattern, test_detect_provider_failure_503, test_detect_provider_failure_429
- tests/test_f022_pipeline.py  — Exports: test_pipeline_module_importable, test_pipeline_has_run_pipeline, test_pipeline_has_run_phase1_strategist, test_pipeline_has_run_phase2_coder, test_pipeline_has_run_phase3_vet
- tests/test_f022_roadmap.py  — Exports: test_roadmap_module_importable, test_roadmap_has_parse_roadmap, test_roadmap_has_pick_next_feature, test_roadmap_has_update_roadmap_status, test_roadmap_has_commit_roadmap_update
- tests/test_f022_tasks.py  — Exports: test_tasks_module_importable, test_tasks_has_worktree_manager, test_tasks_has_task_lock, test_tasks_has_task_class, test_tasks_has_roadmap_feature
- tests/test_f022_utils.py  — Exports: test_slugify_simple, test_slugify_special_chars, test_slugify_short, test_slugify_long, test_slugify_empty
- tests/test_f022_utils_complete.py  — Exports: test_utils_has_halt_and_revert, test_utils_has_archive_specs_for_feature
- tests/test_f023_self_healing.py  — Exports: _git_with_source_diff, test_lock_age_old_lock_with_live_pid_removed
- tests/test_f024_release.py  — Ensure the project root is on the path so we can import utils
- tests/test_f025_dashboard.py  — Exports: TestPipelineStatus, TestSaveLoad
- tests/test_final_coverage.py  — Exports: _setup
- tests/test_final_edge.py  — Exports: _setup
- tests/test_fix_mode.py  — ═══════════════════════════════════════════════════════════════════
- tests/test_functions_unit.py  — Exports: TestSafeRun, TestGit
- tests/test_help_text.py  — Exports: test_help_text_documents_panel_max_parallel
- tests/test_helpers.py  — Exports: test_make_status_entry_pending, test_make_status_entry_done_with_pr, test_make_status_entry_in_progress, test_commit_roadmap_update_dry, test_auto_repair_status_empty
- tests/test_installer.py  — Exports: _make_fake_cmd, _make_fake_hermes, _make_git_repo
- tests/test_lock_paths.py  — Exports: test_explicit_project_dir_lock, test_explicit_project_dir_stop, test_implicit_from_global, test_trailing_slash_normalized, test_no_project_dir_no_arg
- tests/test_main_integration.py  — Exports: _git_with_source_diff, _make_safe_run_result, _setup_test_project
- tests/test_parallel_robustness.py  — Reuse conftest's _load_panel to get a fresh dokima module
- tests/test_pick_next.py  — Exports: make_feat, test_empty_list, test_all_done, test_single_pending_no_deps, test_p0_beats_p1
- tests/test_pick_next_feature.py  — Helper to build RoadmapFeature objects for testing
- tests/test_pid_utils.py  — Exports: test_check_live_pid, test_check_dead_pid, test_check_non_numeric, test_check_empty_string, test_verify_owner_on_self
- tests/test_pipeline_integration.py  — Exports: _setup_test_project
- tests/test_profile_templates.py  — Exports: _fresh_panel, TestEnsureProfiles
- tests/test_rich_pipeline.py  — Exports: _setup_project
- tests/test_roadmap_parse.py  — Exports: test_file_not_found, test_empty_file, test_single_feature_all_fields
- tests/test_roadmap_update.py  — Exports: test_pending_to_in_progress, test_in_progress_to_done, test_done_to_pending_revert, test_feature_not_found_no_change, test_file_not_found_no_crash
- tests/test_root_cause_regressions.py  — Exports: TestSpecPathDetection
- tests/test_safe_run.py  — Exports: test_simple_echo, test_command_fails, test_shell_metachar_not_injected, test_complex_command, test_unsplittable_falls_back_to_bash
- tests/test_sandbox_fixes.py  — Exports: TestDokimaMain, TestSkillSourcePath
- tests/test_slugify.py  — Exports: test_clean_input_no_change, test_spaces_to_hyphens, test_special_chars_removed, test_exactly_40_chars_no_hash, test_41_chars_appends_hash
- tests/test_spec_quality_gates.py  — Sample well-formed spec with all required sections
- tests/test_status_md.py  — Exports: test_empty_status_file, test_single_active_entry, test_update_existing_entry, test_new_entry_appended, test_timestamp_auto_generated
- tests/test_task_dag.py  — Exports: panel, _make_dag, test_all_parallel_3tasks_2files_single_session, test_non_parallelizable_task_returns_single_session
- tests/test_tl_extraction.py  — Exports: panel
- tests/test_triple_bug_fix.py  — ── Bug 1: Spec archive ──────────────────────────────────────
- tests/test_unit_helpers.py  — ═══════════════════════════════════════════════════════════════════

### Documentation
- AGENTS.md  — Dokima — Multi-Agent Orchestration Engine
- MAINTAINERS.md  — Dokima — Maintainer's Reference
- README.md  — Dokima
- docs/pipeline.md  — Dokima — Pipeline Reference
- docs/setup.md  — Dokima — Deployment & Setup Guide

## Impact Map
- agent.py → imports from utils; external: urllib
- pipeline.py → imports from agent, roadmap, status, tasks, utils; external: select, string
- roadmap.py → imports from agent, tasks, utils
- status.py → external: dataclasses
- tasks.py → imports from agent, status, utils; external: shutil
- tests/conftest.py → external: pytest, types, unittest
- tests/test_acquire_lock.py → external: pytest
- tests/test_add_to_roadmap.py → external: pytest
- tests/test_clean_spec.py → external: pytest
- tests/test_codebase_map.py → imports from conftest; external: pytest
- tests/test_conftest_fixtures.py → external: unittest
- tests/test_continuous.py → imports from conftest; external: pytest, unittest
- tests/test_control_panel.py → external: pytest
- tests/test_dag_format.py → imports from conftest; external: pytest
- tests/test_detect_commands.py → external: pytest
- tests/test_edge_cases.py → imports from agent, conftest; external: pytest, unittest
- tests/test_execution_mode_dispatch.py → imports from conftest; external: pytest, unittest
- tests/test_extract_agent.py → external: pytest
- tests/test_extract_file_paths.py → imports from conftest; external: pytest
- tests/test_extract_pr.py → external: pytest
- tests/test_f001_security.py → external: io, types
- tests/test_f002_closure.py → standalone (stdlib only)
- tests/test_f003_robustness.py → imports from conftest; external: pytest, unittest
- tests/test_f005_fallback.py → imports from conftest; external: unittest
- tests/test_f006_recovery.py → imports from conftest
- tests/test_f020_help_json.py → standalone (stdlib only)
- tests/test_f021_version.py → standalone (stdlib only)
- tests/test_f022_agent.py → imports from agent; external: pytest
- tests/test_f022_pipeline.py → imports from pipeline; external: pytest
- tests/test_f022_roadmap.py → imports from roadmap; external: pytest
- tests/test_f022_tasks.py → imports from tasks; external: pytest
- tests/test_f022_utils.py → imports from utils; external: pytest
- tests/test_f022_utils_complete.py → imports from utils; external: pytest
- tests/test_f023_self_healing.py → external: pytest, unittest
- tests/test_f024_release.py → imports from utils; external: io, unittest
- tests/test_f025_dashboard.py → imports from status; external: pytest
- tests/test_final_coverage.py → imports from conftest; external: pytest, unittest
- tests/test_final_edge.py → imports from conftest; external: pytest, unittest
- tests/test_fix_mode.py → imports from conftest; external: contextlib, io, unittest
- tests/test_functions_unit.py → imports from conftest, utils; external: pytest, unittest
- tests/test_help_text.py → standalone (stdlib only)
- tests/test_helpers.py → external: pytest
- tests/test_installer.py → external: pytest, shutil, stat
- tests/test_lock_paths.py → external: pytest
- tests/test_main_integration.py → imports from conftest; external: contextlib, pytest, unittest
- tests/test_parallel_robustness.py → imports from conftest; external: pytest, unittest
- tests/test_pick_next.py → external: pytest
- tests/test_pick_next_feature.py → imports from conftest; external: pytest
- tests/test_pid_utils.py → external: pytest
- tests/test_pipeline_integration.py → imports from conftest; external: contextlib, pytest, unittest
- tests/test_profile_templates.py → imports from conftest; external: pytest, shutil, unittest
- tests/test_rich_pipeline.py → imports from conftest; external: pytest, unittest
- tests/test_roadmap_parse.py → external: pytest
- tests/test_roadmap_update.py → external: pytest
- tests/test_root_cause_regressions.py → external: inspect, pytest
- tests/test_safe_run.py → external: pytest
- tests/test_sandbox_fixes.py → imports from roadmap, utils; external: inspect, pytest
- tests/test_slugify.py → external: pytest
- tests/test_spec_quality_gates.py → external: contextlib, inspect, pytest, unittest
- tests/test_status_md.py → external: pytest
- tests/test_task_dag.py → imports from conftest; external: pytest
- tests/test_tl_extraction.py → imports from conftest; external: pytest
- tests/test_triple_bug_fix.py → external: pytest
- tests/test_unit_helpers.py → imports from conftest; external: pytest, unittest
- utils.py → imports from status; external: glob, importlib, shutil

## Test Map
- tests/test_acquire_lock.py → (no matching source module)
- tests/test_add_to_roadmap.py → (no matching source module)
- tests/test_clean_spec.py → (no matching source module)
- tests/test_codebase_map.py → (no matching source module)
- tests/test_conftest_fixtures.py → (no matching source module)
- tests/test_continuous.py → (no matching source module)
- tests/test_control_panel.py → (no matching source module)
- tests/test_dag_format.py → (no matching source module)
- tests/test_detect_commands.py → (no matching source module)
- tests/test_edge_cases.py → (no matching source module)
- tests/test_execution_mode_dispatch.py → (no matching source module)
- tests/test_extract_agent.py → (no matching source module)
- tests/test_extract_file_paths.py → (no matching source module)
- tests/test_extract_pr.py → (no matching source module)
- tests/test_f001_security.py → (no matching source module)
- tests/test_f002_closure.py → (no matching source module)
- tests/test_f003_robustness.py → (no matching source module)
- tests/test_f005_fallback.py → (no matching source module)
- tests/test_f006_recovery.py → (no matching source module)
- tests/test_f020_help_json.py → (no matching source module)
- tests/test_f021_version.py → (no matching source module)
- tests/test_f022_agent.py → (no matching source module)
- tests/test_f022_pipeline.py → (no matching source module)
- tests/test_f022_roadmap.py → (no matching source module)
- tests/test_f022_tasks.py → (no matching source module)
- tests/test_f022_utils.py → (no matching source module)
- tests/test_f022_utils_complete.py → (no matching source module)
- tests/test_f023_self_healing.py → (no matching source module)
- tests/test_f024_release.py → (no matching source module)
- tests/test_f025_dashboard.py → (no matching source module)
- tests/test_final_coverage.py → (no matching source module)
- tests/test_final_edge.py → (no matching source module)
- tests/test_fix_mode.py → (no matching source module)
- tests/test_functions_unit.py → (no matching source module)
- tests/test_help_text.py → (no matching source module)
- tests/test_helpers.py → (no matching source module)
- tests/test_installer.py → (no matching source module)
- tests/test_lock_paths.py → (no matching source module)
- tests/test_main_integration.py → (no matching source module)
- tests/test_parallel_robustness.py → (no matching source module)
- tests/test_pick_next.py → (no matching source module)
- tests/test_pick_next_feature.py → (no matching source module)
- tests/test_pid_utils.py → (no matching source module)
- tests/test_pipeline_integration.py → (no matching source module)
- tests/test_profile_templates.py → (no matching source module)
- tests/test_rich_pipeline.py → (no matching source module)
- tests/test_roadmap_parse.py → (no matching source module)
- tests/test_roadmap_update.py → (no matching source module)
- tests/test_root_cause_regressions.py → (no matching source module)
- tests/test_safe_run.py → (no matching source module)
- tests/test_sandbox_fixes.py → (no matching source module)
- tests/test_slugify.py → (no matching source module)
- tests/test_spec_quality_gates.py → (no matching source module)
- tests/test_status_md.py → (no matching source module)
- tests/test_task_dag.py → (no matching source module)
- tests/test_tl_extraction.py → (no matching source module)
- tests/test_triple_bug_fix.py → (no matching source module)
- tests/test_unit_helpers.py → (no matching source module)
