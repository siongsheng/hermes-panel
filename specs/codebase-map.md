## Project: dokima
## Tech: detected at runtime
## Generated: 2026-06-30 00:56:25 (incremental | 80 files)

## Tree
├── AGENTS.md  — Dokima — Multi-Agent Orchestration Engine
├── MAINTAINERS.md  — Dokima — Maintainer's Reference
├── README.md  — Dokima
├── agent.py  — ── Module-level globals (set by main()) ──────────
├── install.sh  — Dokima Installer — one-command setup
├── pipeline.py  — Set by conftest._load_panel() — see utils.py _IMPORTING_PANEL docstring (F022b).
├── roadmap.py  — Exports: parse_roadmap
├── tasks.py  — Exports: WorktreeManager
├── utils.py  — shutil imported dynamically where needed (deploy_profile_skills)
└── utils_debug.py  — shutil imported dynamically where needed (deploy_profile_skills)
├── docs/
├── pipeline.md  — Dokima — Pipeline Reference
└── setup.md  — Dokima — Deployment & Setup Guide
├── scripts/
└── setup-linux.sh  — ───────────────────────────────────────────────────────────────────
├── skills/
│   ├── adversarial-review-lite/
│   │   └── SKILL.md  — Adversarial Review (Lite — Tech Lead Edition)
│   ├── ai-coding-best-practices-lite/
│   │   └── SKILL.md  — AI Coding Best Practices (Lite — Coder Edition)
│   ├── no-mistakes/
│   │   └── SKILL.md  — No Mistakes — Validation Pipeline
│   │   ├── references/
│   │   │   ├── python-default-argument-pitfall.md  — Python Default Argument Binding Trap
│   │   │   └── vitest-dotenv-setup.md  — Vitest dotenv Setup
│   ├── ponytail-guard/
│   │   └── SKILL.md  — Ponytail Guard — Laziness Ladder for dokima
│   ├── spec-strategist-lite/
│   │   └── SKILL.md  — Spec Strategist (Lite — Panel Edition)
├── tests/
├── conftest.py  — Exports: _load_panel
├── test_acquire_lock.py  — Exports: test_first_acquisition_succeeds, test_second_acquisition_blocked, test_stale_lock_dead_pid
├── test_add_to_roadmap.py
├── test_clean_spec.py  — Exports: TestCleanSpecContent
├── test_codebase_map.py  — assert "Fetch user data" in desc
├── test_conftest_fixtures.py  — Exports: TestTestRepoFixture, TestMockOrchestratorFixture
├── test_continuous.py  — Exports: _setup_two_features, test_continuous_loop_two_features
├── test_control_panel.py  — Exports: test_show_help_exits_zero, test_handle_status_idle, test_handle_status_running, test_handle_stop_no_running, test_handle_stop_creates_stop_file
├── test_dag_format.py  — Exports: panel, test_dag_regex_matches_valid, test_dag_regex_rejects_invalid, test_dag_regex_matches_multiple
├── test_detect_commands.py  — Exports: test_first_acquisition_succeeds, test_second_acquisition_blocked, test_stale_lock_dead_pid
├── test_edge_cases.py  — Exports: _setup
├── test_execution_mode_dispatch.py  — Exports: _reset_called, _mock_run_phase2_coder, _mock_run_phase2_coder_capture, _mock_run_parallel_coders, _mock_halt_and_revert
├── test_extract_agent.py  — Exports: test_hermes_box_format, test_no_box_markers_fallback, test_multiple_boxes, test_empty_box_skipped, test_partial_box_no_match
├── test_extract_file_paths.py  — Exports: TestExtractFilePathsBacktick
├── test_extract_pr.py
├── test_f001_security.py  — Exports: _load_panel, TestPromptSanitizer
├── test_f002_closure.py  — Exports: test_f002_marked_done_in_roadmap, test_f002_recorded_in_status
├── test_f003_robustness.py  — Exports: _make_result, TestRedOnlyCommits
├── test_f005_fallback.py  — Exports: TestDetectProviderFailure
├── test_f006_recovery.py  — Exports: TestCheckpointPath, TestSaveCheckpoint
├── test_f020_help_json.py  — Exports: run_help_json, TestHelpJsonOutput
├── test_f021_version.py  — Exports: _run, test_version_flag_prints_version_and_exits_0, test_help_includes_version_command, test_help_includes_upgrade_command, test_help_json_includes_version
├── test_f022_agent.py  — Exports: test_detect_provider_failure_none, test_detect_provider_failure_empty_nonzero, test_detect_provider_failure_timeout_pattern, test_detect_provider_failure_503, test_detect_provider_failure_429
├── test_f022_pipeline.py  — Exports: test_pipeline_module_importable, test_pipeline_has_run_pipeline, test_pipeline_has_run_phase1_strategist, test_pipeline_has_run_phase2_coder, test_pipeline_has_run_phase3_vet
├── test_f022_roadmap.py  — Exports: test_roadmap_module_importable, test_roadmap_has_parse_roadmap, test_roadmap_has_pick_next_feature, test_roadmap_has_update_roadmap_status, test_roadmap_has_commit_roadmap_update
├── test_f022_tasks.py  — Exports: test_tasks_module_importable, test_tasks_has_worktree_manager, test_tasks_has_task_lock, test_tasks_has_task_class, test_tasks_has_roadmap_feature
├── test_f022_utils.py  — Exports: test_slugify_simple, test_slugify_special_chars, test_slugify_short, test_slugify_long, test_slugify_empty
├── test_f022_utils_complete.py  — Exports: test_utils_has_halt_and_revert, test_utils_has_archive_specs_for_feature
├── test_f023_self_healing.py  — Exports: _git_with_source_diff, test_lock_age_old_lock_with_live_pid_removed
├── test_f024_release.py  — Ensure the project root is on the path so we can import utils
├── test_final_coverage.py  — Exports: _setup
├── test_final_edge.py  — Exports: _setup
├── test_fix_mode.py  — ═══════════════════════════════════════════════════════════════════
├── test_functions_unit.py  — Exports: TestSafeRun, TestGit
├── test_help_text.py  — Exports: test_help_text_documents_panel_max_parallel
├── test_helpers.py  — Exports: test_make_status_entry_pending, test_make_status_entry_done_with_pr, test_make_status_entry_in_progress, test_commit_roadmap_update_dry, test_auto_repair_status_empty
├── test_installer.py  — Exports: _make_fake_cmd, _make_fake_hermes, _make_git_repo
├── test_lock_paths.py  — Exports: test_explicit_project_dir_lock, test_explicit_project_dir_stop, test_implicit_from_global, test_trailing_slash_normalized, test_no_project_dir_no_arg
├── test_main_integration.py  — Exports: _git_with_source_diff, _make_safe_run_result, _setup_test_project
├── test_parallel_robustness.py  — Reuse conftest's _load_panel to get a fresh dokima module
├── test_pick_next.py  — Exports: make_feat, test_empty_list, test_all_done, test_single_pending_no_deps, test_p0_beats_p1
├── test_pick_next_feature.py  — Helper to build RoadmapFeature objects for testing
├── test_pid_utils.py  — Exports: test_check_live_pid, test_check_dead_pid, test_check_non_numeric, test_check_empty_string, test_verify_owner_on_self
├── test_pipeline_integration.py  — Exports: _setup_test_project
├── test_profile_templates.py  — Exports: _fresh_panel, TestEnsureProfiles
├── test_rich_pipeline.py  — Exports: _setup_project
├── test_roadmap_parse.py  — Exports: test_file_not_found, test_empty_file, test_single_feature_all_fields
├── test_roadmap_update.py  — Exports: test_pending_to_in_progress, test_in_progress_to_done, test_done_to_pending_revert, test_feature_not_found_no_change, test_file_not_found_no_crash
├── test_root_cause_regressions.py  — Exports: TestSpecPathDetection
├── test_safe_run.py  — Exports: test_simple_echo, test_command_fails, test_shell_metachar_not_injected, test_complex_command, test_unsplittable_falls_back_to_bash
├── test_slugify.py  — Exports: test_clean_input_no_change, test_spaces_to_hyphens, test_special_chars_removed, test_exactly_40_chars_no_hash, test_41_chars_appends_hash
├── test_spec_quality_gates.py  — Sample well-formed spec with all required sections
├── test_status_md.py  — Exports: test_empty_status_file, test_single_active_entry, test_update_existing_entry, test_new_entry_appended, test_timestamp_auto_generated
├── test_task_dag.py  — Exports: panel, _make_dag, test_all_parallel_3tasks_2files_single_session, test_non_parallelizable_task_returns_single_session
├── test_tl_extraction.py  — Exports: panel
├── test_triple_bug_fix.py  — ── Bug 1: Spec archive ──────────────────────────────────────
└── test_unit_helpers.py  — ═══════════════════════════════════════════════════════════════════
│   ├── htmlcov/
│   │   ├── coverage_html_cb_dd2e7eb5.js  — Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
│   │   ├── status.json
│   │   └── style_cb_4667309f.css

## Commands
- test: `python3 -m pytest tests/ -q`
- build: `python3 -c "compile(open('dokima').read(), 'dokima', 'exec')"`
- lint: `python3 -m py_compile dokima`
