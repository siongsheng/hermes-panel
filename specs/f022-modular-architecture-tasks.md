# Task Breakdown: F022: Modular Architecture

### Task 1: Create utils.py with all shared utilities and helpers
**Files:** utils.py, dokima
**Dependencies:** [none]
**Description:** Create utils.py with all shared utilities and helpers

### Task 2: Create agent.py with agent spawning and API call logic
**Files:** agent.py, dokima
**Dependencies:** 1
**Description:** Create agent.py with agent spawning and API call logic

### Task 3: Create tasks.py with infrastructure classes and parallel execution
**Files:** tasks.py, dokima
**Dependencies:** 1
**Description:** Create tasks.py with infrastructure classes and parallel execution

### Task 4: Create roadmap.py with roadmap parsing and CLI commands
**Files:** roadmap.py, dokima
**Dependencies:** 1, 3
**Description:** Create roadmap.py with roadmap parsing and CLI commands

### Task 5: Create pipeline.py with all 5 phase functions and fix mode
**Files:** pipeline.py, dokima
**Dependencies:** 1, 2, 3, 4
**Description:** Create pipeline.py with all 5 phase functions and fix mode

### Task 6: Refactor main dokima script to import from modules
**Files:** dokima
**Dependencies:** 1, 2, 3, 4, 5
**Description:** Refactor main dokima script to import from modules

### Task 7: Update test imports and verify test suite
**Files:** tests/conftest.py, tests/test_*.py (as needed)
**Dependencies:** 6
**Description:** Update test imports and verify test suite

### Task 8: Integration validation — full pipeline end-to-end
**Files:** none (verification only)
**Dependencies:** 7
**Description:** Integration validation — full pipeline end-to-end
