# Task Breakdown: F005: Model Family Fallback

### Task 1: Add failure-detection helper to spawn_agent
**Files:** dokima
**Dependencies:** [none]
**Description:** Add failure-detection helper to spawn_agent

### Task 2: Wire fallback env vars into main() config loading
**Files:** dokima
**Dependencies:** [none]
**Description:** Wire fallback env vars into main() config loading

### Task 3: Add fallback retry path to spawn_agent
**Files:** dokima
**Dependencies:** 1, 2
**Description:** Add fallback retry path to spawn_agent

### Task 4: Update all spawn_agent call sites to pass fallback
**Files:** dokima
**Dependencies:** 3
**Description:** Update all spawn_agent call sites to pass fallback

### Task 5: Preserve cross-family invariant for nm fallback
**Files:** dokima
**Dependencies:** 2
**Description:** Preserve cross-family invariant for nm fallback

### Task 6: Write test suite for fallback behavior
**Files:** tests/test_f005_fallback.py
**Dependencies:** 1, 3
**Description:** Write test suite for fallback behavior
