# Task Breakdown: F001: Security Hardening

### Task 1: Add prompt sanitization utility
**Files:** dokima
**Dependencies:** [none]
**Description:** Add prompt sanitization utility

### Task 2: Filter GH_TOKEN from agent log output
**Files:** dokima
**Dependencies:** [none]
**Description:** Filter GH_TOKEN from agent log output

### Task 3: Harden /tmp file permissions
**Files:** dokima
**Dependencies:** [none]
**Description:** Harden /tmp file permissions

### Task 4: Validate PROJECT_DIR is a real git repo
**Files:** dokima
**Dependencies:** [none]
**Description:** Validate PROJECT_DIR is a real git repo

### Task 5: Security regression test suite
**Files:** tests/test_f001_security.py
**Dependencies:** 1, 2, 3, 4
**Description:** Security regression test suite

### Task 6: Add security section to conventions
**Files:** specs/conventions.md
**Dependencies:** 1, 2
**Description:** Add security section to conventions
