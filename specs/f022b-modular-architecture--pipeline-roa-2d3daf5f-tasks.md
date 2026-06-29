# Task Breakdown: F022b: Modular Architecture — Pipeline, Roadmap, Tasks

### Task 1: Create tasks.py with infrastructure classes
**Files:** tasks.py, dokima
**Dependencies:** [none]
**Description:** Create tasks.py with infrastructure classes

### Task 2: Add parallel execution functions to tasks.py
**Files:** tasks.py, dokima
**Dependencies:** 1
**Description:** Add parallel execution functions to tasks.py

### Task 3: Create roadmap.py with parsing and feature lifecycle
**Files:** roadmap.py, dokima
**Dependencies:** 1
**Description:** Create roadmap.py with parsing and feature lifecycle

### Task 4: Add CLI commands to roadmap.py
**Files:** roadmap.py, dokima
**Dependencies:** 3
**Description:** Add CLI commands to roadmap.py

### Task 5: Create pipeline.py with phase functions and orchestration
**Files:** pipeline.py, dokima
**Dependencies:** 2, 4
**Description:** Create pipeline.py with phase functions and orchestration

### Task 6: Clean up dokima — remove all moved function bodies
**Files:** dokima
**Dependencies:** 1, 2, 3, 4, 5
**Description:** Clean up dokima — remove all moved function bodies

### Task 7: Create behavioral tests for new modules
**Files:** tests/test_f022_tasks.py, tests/test_f022_roadmap.py, tests/test_f022_pipeline.py
**Dependencies:** 6
**Description:** Create behavioral tests for new modules

### Task 8: Update test imports and verify full test suite
**Files:** tests/conftest.py, tests/test_*.py (as needed)
**Dependencies:** 6, 7
**Description:** Update test imports and verify full test suite
