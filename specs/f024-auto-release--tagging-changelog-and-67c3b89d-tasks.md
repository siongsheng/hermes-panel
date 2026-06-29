# Task Breakdown: F024: Auto-Release — Tagging, Changelog, and GitHub Releases

### Task 1: Add _bump_version() helper to utils.py
**Files:** utils.py
**Dependencies:** [none]
**Description:** Add _bump_version() helper to utils.py

### Task 2: Add _prune_old_tags() helper to utils.py
**Files:** utils.py
**Dependencies:** [none]
**Description:** Add _prune_old_tags() helper to utils.py

### Task 3: Add do_release() function to utils.py
**Files:** utils.py
**Dependencies:** 1, 2
**Description:** Add do_release() function to utils.py

### Task 4: Add --release flag scanning to dokima main()
**Files:** dokima
**Dependencies:** [none]
**Description:** Add --release flag scanning to dokima main()

### Task 5: Add --release early-exit dispatch to dokima main()
**Files:** dokima
**Dependencies:** 3, 4
**Description:** Add --release early-exit dispatch to dokima main()

### Task 6: Add --dry-run support to --release
**Files:** dokima, utils.py
**Dependencies:** 4, 5
**Description:** Add --dry-run support to --release

### Task 7: Add do_release import to dokima header
**Files:** dokima
**Dependencies:** 3
**Description:** Add do_release import to dokima header

### Task 8: Add --release to HELP_TEXT in utils.py
**Files:** utils.py
**Dependencies:** [none]
**Description:** Add --release to HELP_TEXT in utils.py

### Task 9: Add --release to CLI_METADATA in utils.py
**Files:** utils.py
**Dependencies:** [none]
**Description:** Add --release to CLI_METADATA in utils.py

### Task 10: Create tests for --release
**Files:** tests/test_f024_release.py
**Dependencies:** 5
**Description:** Create tests for --release

### Task 11: Run full test suite and verify
**Files:** none (verification only)
**Dependencies:** 10
**Description:** Run full test suite and verify
