# F019: Data-Driven Execution Mode (Orchestrator Computes)

**Status:** Draft v2
**Confidence:** High
**Impact:** MEDIUM

---

## 1. Decision Table

**SINGLE APPROACH:** The orchestrator computes execution mode from signals the strategist already provides — task count, file count, parallelizability, and task descriptions. No new strategist output field. 5 lines of Python at the dispatch point.

---

## 2. Impact

Pipeline auto-selects batch (`run_phase2_coder`) for small additive features (2-4× faster, no worktree overhead) and per-task spawn (`run_parallel_coders`) for complex/refactor features. Zero strategist complexity added.

---

## 3. What Changed

- **`dokima` (TaskDAG):** Add `compute_execution_mode()` method — derives `"single_session"` or `"per_task_spawn"` from parsed DAG
- **`dokima` (pipeline dispatch ~L4236):** Route based on `dag.compute_execution_mode()` instead of hardcoded `--continuous` flag
- **`tests/test_task_dag.py`:** Unit tests for compute_execution_mode with edge cases

---

## 4. Confidence + Impact

Confidence: High
Impact: MEDIUM

---

## 5. API/Interface Proposal

N/A — no API change. Internal method on TaskDAG.

**`TaskDAG.compute_execution_mode() -> str`:**

```python
def compute_execution_mode(self) -> str:
    """Derive execution mode from DAG signals. Returns 'single_session' or 'per_task_spawn'."""
    tasks = list(self.tasks.values())
    all_files = set()
    all_parallelizable = True
    for t in tasks:
        for f in t.files:
            all_files.add(f.strip().lower())
        if not t.parallelizable:
            all_parallelizable = False

    # --- per_task_spawn triggers ---
    # Any task is non-parallelizable (refactor, same-file dependency)
    if not all_parallelizable:
        return "per_task_spawn"

    # Too many tasks for one coder context window
    if len(tasks) > 10:
        return "per_task_spawn"

    # Too many distinct files for one coder to hold
    if len(all_files) > 3:
        return "per_task_spawn"

    # --- single_session triggers ---
    # Every task is parallelizable, ≤10 tasks, ≤3 files → batch
    return "single_session"
```

---

## 6. Security Considerations

N/A — no attack surface change. The mode is derived from strategist output, not user input.

---

## 7. Documentation Impact

README: No change needed (internal dispatch logic).

---

## 8. Task Breakdown

### Task 1: Add `compute_execution_mode()` to TaskDAG
**Files:** dokima
**Dependencies:** [none]
**Parallelizable:** yes
**Description:** Add method to TaskDAG class (~L614) that derives `"single_session"` or `"per_task_spawn"` from parsed tasks. Three triggers: non-parallelizable tasks, >10 tasks, >3 distinct files → `per_task_spawn`. Otherwise → `single_session`.

### Task 2: Wire execution mode into pipeline dispatch
**Files:** dokima
**Dependencies:** [Task 1]
**Parallelizable:** no
**Description:** At dispatch point (~L4236), replace `if parallel_enabled and depth in (...)` with `if dag.compute_execution_mode() == "single_session": run_phase2_coder(...) else: run_parallel_coders(...)`. Both active and continuous modes use the same dispatch logic. Mode override via env var `PANEL_FORCE_EXECUTION_MODE` for testing.

### Task 3: Unit tests for compute_execution_mode
**Files:** tests/test_task_dag.py
**Dependencies:** [Task 1]
**Parallelizable:** no
**Description:** 10 tests: all parallelizable + 3 tasks/2 files → single_session; non-parallelizable task → per_task_spawn; 11 tasks → per_task_spawn; 4 distinct files → per_task_spawn; 1 task → single_session; 10 tasks/3 files/all parallel → single_session; empty DAG → single_session; mixed case (5 parallel + 1 non-parallel) → per_task_spawn; all tasks have empty files → single_session; duplicate file normalization → still ≤3.

### Task 4: Integration test for mode-driven dispatch
**Files:** tests/test_pipeline_integration.py
**Dependencies:** [Task 3]
**Parallelizable:** no
**Description:** Mock pipeline with DAG that computes single_session → verify `run_phase2_coder` called (not parallel). Mock DAG that computes per_task_spawn → verify `run_parallel_coders` called. PANEL_FORCE_EXECUTION_MODE overrides.

---

## 9. Edge Cases

### EC1: Active mode with per_task_spawn DAG
**Handling:** Dispatch no longer checks `--continuous` flag. Mode is purely DAG-driven. Active mode with refactor → parallel coders fire.

### EC2: Continuous mode with single_session DAG
**Handling:** Same — mode wins. Continuous loop with batch coder per iteration.

### EC3: Parallelizable: yes but Files: overlap ("file collision")
**Handling:** Existing `validate_parallel_files()` in `run_parallel_coders` catches this at wave time → sequential fallback. `compute_execution_mode()` doesn't need to check it — the fallback handles it.

### EC4: >10 tasks but all touch 1 file and are parallelizable
**Handling:** >10 tasks → `per_task_spawn` (hard cap). A single coder can't hold 10+ task descriptions + file context. 1 file means sequential anyway (file collision), so the batch speed gain doesn't exist.

### EC5: Tasks have no Files: fields (all empty)
**Handling:** `len(all_files) == 0 ≤ 3` → single_session path eligible. Other triggers still apply (task count, parallelizability).

### EC6: Duplicate files normalized ("src/a.py", " src/a.py ")
**Handling:** `f.strip().lower()` in `compute_execution_mode()` deduplicates. Only distinct files count.

### EC7: Pre-existing `parallel_enabled` flag
**Handling:** Retained as secondary gate. If `parallel_enabled=False` (e.g., `--sequential` flag), `per_task_spawn` is downgraded to sequential single-coder as today.

### EC8: PANEL_FORCE_EXECUTION_MODE override
**Handling:** For testing/debugging. `PANEL_FORCE_EXECUTION_MODE=single_session` skips `compute_execution_mode()`. Not documented for users — internal only.
