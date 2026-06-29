"""Dokima tasks module — infrastructure classes and parallel execution.

All classes and functions extracted from dokima monolith (F022: Modular Architecture).
Imports slugify, git, _safe_run, load_github_token from utils.
Imports spawn_agent from agent.
"""
import sys, os, json, re, subprocess, time, shutil

from utils import (slugify, git, _safe_run, load_github_token,
                   HERMES_BIN, DEFAULT_BRANCH, PANEL_FEATURE,
                   TEST_CMD, BUILD_CMD, LINT_CMD,
                   FALLBACK_MODELS, max_parallel_override,
                   OUTPUT_LOG)
from agent import spawn_agent

# Module-level globals (set by main())
PROJECT_DIR = ""

class WorktreeManager:
    """Git worktree isolation — each agent gets its own filesystem sandbox.
    Pattern adapted from Baton (symphony/workspace.py, MIT license)."""
    def __init__(self, project_root):
        self.project_root = os.path.abspath(project_root)
        self.worktrees_dir = os.path.join(project_root, ".dokima", "worktrees")

    def worktree_path(self, task_id: str) -> str:
        path = os.path.join(self.worktrees_dir, task_id)
        abs_path = os.path.abspath(path)
        if not abs_path.startswith(os.path.abspath(self.worktrees_dir)):
            raise ValueError(f"Worktree path {abs_path} escapes panel dir")
        return abs_path

    def create(self, task_id: str, branch: str) -> str:
        path = self.worktree_path(task_id)
        if os.path.isdir(path):
            print(f"  [worktree] Reusing existing worktree at {path}", flush=True)
            return path
        os.makedirs(self.worktrees_dir, exist_ok=True)
        # Clean up stale worktrees from crashed runs
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.project_root, check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
                text=True
            )
            for line in result.stdout.split("\n"):
                if line.startswith("worktree ") and os.path.abspath(line.split(" ", 1)[1]) == path:
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", path],
                        cwd=self.project_root,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
                    )
                    break
        except Exception:
            pass
        # Force-delete stale branch if it exists
        try:
            subprocess.run(
                ["git", "branch", "-D", branch],
                cwd=self.project_root,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
            )
        except Exception:
            pass
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, path, "HEAD"],
            cwd=self.project_root, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30
        )
        print(f"  [worktree] Created: {path} (branch: {branch})", flush=True)
        return path

    def cleanup(self, task_id: str) -> None:
        path = self.worktree_path(task_id)
        if not os.path.exists(path):
            return
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", path],
                cwd=self.project_root,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30
            )
        except Exception:
            pass
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
        # Prune the branch reference
        branch = f"feat/{slugify(PANEL_FEATURE)}-{task_id}"
        try:
            subprocess.run(
                ["git", "branch", "-D", branch],
                cwd=self.project_root,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
            )
        except Exception:
            pass
        print(f"  [worktree] Cleaned up: {path}", flush=True)

    def cleanup_all(self, task_ids: list[str]) -> None:
        for tid in task_ids:
            self.cleanup(tid)


class TaskLock:
    """Atomic task claiming via O_EXCL lockfiles.
    Pattern adapted from Claude Code Agent Teams (.claude/tasks/)."""
    def __init__(self, panel_dir):
        self.tasks_dir = os.path.join(panel_dir, "tasks")
        self.cleanup_stale()

    def cleanup_stale(self, stale_seconds: int = 1800) -> None:
        """Remove lock files older than stale_seconds (default 30 min).

        Lock files without a parseable timestamp are treated as corrupt
        and removed. Missing tasks directory is silently skipped.
        """
        if not os.path.isdir(self.tasks_dir):
            return
        cutoff = time.time() - stale_seconds
        try:
            for entry in os.listdir(self.tasks_dir):
                if not entry.endswith(".lock"):
                    continue
                lockfile = os.path.join(self.tasks_dir, entry)
                try:
                    with open(lockfile) as f:
                        content = f.read()
                    ts_match = re.search(r"timestamp:\s*([\d.]+)", content)
                    if ts_match:
                        lock_ts = float(ts_match.group(1))
                        if lock_ts < cutoff:
                            os.remove(lockfile)
                    else:
                        # No timestamp found — corrupted, remove
                        os.remove(lockfile)
                except (PermissionError, OSError):
                    pass  # Can't read/delete, skip
                except ValueError:
                    # Unparseable timestamp — corrupted, remove
                    try:
                        os.remove(lockfile)
                    except OSError:
                        pass
        except OSError:
            pass  # Can't list directory, skip

    def claim(self, task_id: str, agent_id: str) -> bool:
        os.makedirs(self.tasks_dir, exist_ok=True)
        lockfile = os.path.join(self.tasks_dir, f"{task_id}.lock")
        try:
            fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"owner: {agent_id}\ntimestamp: {time.time()}\n".encode())
            os.close(fd)
            return True
        except FileExistsError:
            return False

    def release(self, task_id: str) -> None:
        lockfile = os.path.join(self.tasks_dir, f"{task_id}.lock")
        try:
            os.remove(lockfile)
        except FileNotFoundError:
            pass

    def owner(self, task_id: str) -> str | None:
        lockfile = os.path.join(self.tasks_dir, f"{task_id}.lock")
        try:
            with open(lockfile) as f:
                for line in f:
                    if line.startswith("owner: "):
                        return line.split(": ", 1)[1].strip()
        except FileNotFoundError:
            return None

class Task:
    """A single task from the strategist's breakdown."""
    def __init__(self, tid: str, description: str, files: list[str],
                 dependencies: list[str], parallelizable: bool):
        self.id = tid
        self.description = description
        self.files = files
        self.dependencies = dependencies
        self.parallelizable = parallelizable
        self.status = "pending"   # pending | in_progress | completed | failed | timed_out
        self.branch = ""
        self.output = ""


class RoadmapFeature:
    """A feature from specs/roadmap.md — parsed for --next."""
    def __init__(self, fid: str, title: str, priority: str,
                 dependencies: list[str], status: str, story: str, section: str = ""):
        self.id = fid
        self.title = title
        self.priority = priority           # "P0", "P1", "P2"
        self.dependencies = dependencies   # ["F001", "F002"]
        self.status = status               # "pending", "in_progress", "done"
        self.story = story                 # User Story text
        self.section = section             # "P0 — Critical Path" etc.


class TaskDAG:
    """Parses strategist output into a dependency graph, computes execution waves."""
    def __init__(self):
        self.tasks: dict[str, Task] = {}

    def parse(self, strategist_output: str, feature_slug: str) -> None:
        """Extract tasks with dependency markers from strategist output."""
        # Match task blocks: ### Task N: or Task N: (DeepSeek strips ###)
        # Anchored to line start, accepts leading whitespace
        task_pattern = re.compile(
            r'^\s*(?:###\s*)?Task\s*(\d+)[:\s]+(.+?)\n'
            r'(.*?)(?=^\s*(?:###\s*)?Task\s*\d+|^\s*####\s|\Z)',
            re.DOTALL | re.MULTILINE
        )
        for m in task_pattern.finditer(strategist_output):
            tid = m.group(1)
            desc = m.group(2).strip()
            body = m.group(3)

            files = []
            files_m = re.search(r'^\s*(?:\*\*)?Files?:?(?:\*\*)?\s*(.+)', body, re.MULTILINE)
            if files_m:
                files = [f.strip() for f in files_m.group(1).split(",")]

            deps = []
            deps_m = re.search(r'^\s*(?:\*\*)?Dependencies?:?(?:\*\*)?\s*(.+)', body, re.MULTILINE)
            if deps_m:
                dep_text = deps_m.group(1).strip()
                if dep_text.lower() not in ("none", "[]", "n/a", ""):
                    deps = re.findall(r'(\d+)', dep_text)

            parallel = True  # default: most tasks are parallelizable; file-collision check catches conflicts
            par_m = re.search(r'^\s*(?:\*\*)?Parallelizable?:?(?:\*\*)?\s*(.+)', body, re.MULTILINE)
            if par_m:
                par_val = par_m.group(1).strip().lower()
                if par_val == "no":
                    parallel = False

            self.tasks[tid] = Task(
                tid=tid, description=desc, files=files,
                dependencies=deps, parallelizable=parallel
            )
            self.tasks[tid].branch = f"feat/{feature_slug}-t{tid}"

    def compute_waves(self) -> list[list[str]]:
        """Compute execution waves: each wave = tasks with all deps satisfied."""
        waves = []
        remaining = set(self.tasks.keys())
        completed = set()
        while remaining:
            ready = {tid for tid in remaining
                     if all(dep in completed for dep in self.tasks[tid].dependencies)}
            if not ready:
                unresolvable = remaining - {tid for tid in remaining
                    if all(dep in self.tasks for dep in self.tasks[tid].dependencies)}
                if unresolvable:
                    print(f"  ⚠ Dead tasks (deps not found): {unresolvable}", flush=True)
                break
            waves.append(sorted(ready, key=lambda x: int(x)))
            remaining -= ready
            completed |= ready
        return waves

    def validate_parallel_files(self, wave: list[str]) -> bool:
        """Check that no two tasks in the same wave claim the same file."""
        all_files = []
        for tid in wave:
            all_files.extend((tid, f) for f in self.tasks[tid].files)
        seen = {}
        for tid, f in all_files:
            f_norm = os.path.normpath(f.strip()).lower()
            if f_norm in seen and seen[f_norm] != tid:
                print(f"  ⚠ File collision: {f} claimed by tasks {seen[f_norm]} and {tid}", flush=True)
                return False
            seen[f_norm] = tid
        return True

    def compute_execution_mode(self) -> str:
        """Derive execution mode from DAG signals.

        Returns 'single_session' or 'per_task_spawn' based on task count,
        distinct file count, and parallelizability.

        single_session: one coder, sequential (safe for shared-file tasks).
        per_task_spawn: parallel task branches (only when all parallelizable)."""
        tasks = list(self.tasks.values())
        all_files: set[str] = set()
        all_parallelizable = True
        for t in tasks:
            for f in t.files:
                all_files.add(f.strip().lower())
            if not t.parallelizable:
                all_parallelizable = False

        # --- per_task_spawn triggers ---
        # Only spawn parallel when it's SAFE: all tasks parallelizable AND
        # the feature is too large for one coder session.
        if all_parallelizable and (len(tasks) > 10 or len(all_files) > 3):
            return "per_task_spawn"

        # --- single_session triggers (safe default) ---
        # Any non-parallelizable task → shared files → must run sequentially.
        # Small features (≤10 tasks, ≤3 files) → single coder session.
        return "single_session"


def spawn_coder_in_worktree(task: Task, worktree_path: str, spec_path: str,
                            parent_branch: str = DEFAULT_BRANCH,
                            tasks_extract_path: str = "") -> subprocess.Popen:
    """Spawn a coder agent in an isolated worktree. Returns the Popen process."""
    spec_ref = tasks_extract_path if tasks_extract_path else spec_path
    spec_ctx = f"{spec_path} for context" if spec_path else "the task description"
    coder_prompt = f"""Read the task breakdown at {spec_ref} (full spec: {spec_ctx}).

You are working on Task {task.id}: {task.description}
Files to create/modify: {', '.join(task.files) if task.files else 'determine from spec'}

FIRST: Verify you are in the correct worktree and on branch '{task.branch}' (parent: {parent_branch}).

TDD — TWO SEPARATE COMMITS on this branch:
RED: Write tests → {TEST_CMD} must FAIL → git add <test files only> && git commit -m "test: {task.description[:60]}"
GREEN: Write minimum code → {TEST_CMD} must PASS → {BUILD_CMD} must succeed → git add <impl files only> && git commit -m "feat: {task.description[:60]}"
CRITICAL: Two distinct commits, RED before GREEN. No task numbers in commit messages. Do NOT modify files outside task scope.
BEFORE PUSHING: Check if the spec requires a README update. If yes, update README.md and commit as "docs: update README". Run lint ({LINT_CMD}) + FULL test suite ({TEST_CMD}). If either fails, fix and retry. Only push when clean.
Report: both commit hashes, files changed, test results, lint status, branch name.
"""

    env = os.environ.copy()
    gh_token = load_github_token()
    if gh_token:
        env["GH_TOKEN"] = gh_token

    tag = f"[coder-t{task.id}]"
    print(f"\n{tag} ⏳ Spawning in worktree {worktree_path}...", flush=True)

    cmd = [HERMES_BIN, "--profile", "coder", "--yolo",
           "-s", "software-development/ai-coding-best-practices-lite", "chat", "-q", coder_prompt]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True, cwd=worktree_path, env=env)
    return proc

def _reap_completed(running: dict, tasks: dict[str, Task], locks: TaskLock) -> list[str]:
    """Check for completed/failed processes. Returns list of task IDs that finished.

    Uses non-blocking stdout drain to avoid proc.communicate() hanging on zombie
    children that hold pipe handles open. Escalates to SIGKILL if wait() times out
    after 2 seconds, marking the task as 'orphaned'.
    """
    finished = []
    for tid, proc in list(running.items()):
        ret = proc.poll()
        if ret is not None:
            # Drain stdout in non-blocking chunks (avoids communicate() hang)
            output_chunks = []
            if proc.stdout is not None:
                try:
                    while True:
                        chunk = proc.stdout.read(4096)
                        if not chunk:
                            break
                        if isinstance(chunk, bytes):
                            output_chunks.append(chunk.decode(errors="replace"))
                        else:
                            output_chunks.append(str(chunk))
                except BrokenPipeError:
                    pass
                except Exception:
                    pass
            output = "".join(output_chunks)

            # Reap the process; escalate to SIGKILL if stuck
            orphaned = False
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                ret = proc.poll()
                orphaned = True

            task = tasks[tid]
            if orphaned or (ret is not None and ret < 0):
                task.status = "orphaned"
                print(f"  ⚠ Task {tid} orphaned (SIGKILL)", flush=True)
            elif ret == 0:
                task.status = "completed"
                print(f"  ✅ Task {tid} completed", flush=True)
            else:
                task.status = "failed"
                print(f"  ❌ Task {tid} failed (exit={ret})", flush=True)
            task.output = output
            locks.release(tid)
            finished.append(tid)
            del running[tid]
    return finished

def _poll_until_wave_done(wave: list[str], running: dict, tasks: dict[str, Task],
                          locks: TaskLock, timeout: int = 600) -> None:
    """Poll until all tasks in a wave complete or time out."""
    deadline = time.time() + timeout
    pending = set(wave)
    while pending and time.time() < deadline:
        finished = _reap_completed(running, tasks, locks)
        pending -= set(finished)
        if not pending:
            break
        time.sleep(2)

    # Timeout: kill stragglers
    for tid in list(pending):
        proc = running.get(tid)
        if proc:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.terminate()
        tasks[tid].status = "timed_out"
        locks.release(tid)
        print(f"  ⚠ Task {tid} timed out after {timeout}s", flush=True)
        if tid in running:
            del running[tid]

def merge_worktree_branches(feature_branch: str, tasks: dict[str, Task],
                            worktrees: WorktreeManager, project_dir: str) -> bool:
    """Merge all completed task branches into a single feature branch."""
    completed_tasks = [t for t in tasks.values() if t.status == "completed"]
    if not completed_tasks:
        print("  ⚠ No completed tasks to merge", flush=True)
        return False

    print(f"\n── Merge Assembly: {len(completed_tasks)} branches → {feature_branch} ──", flush=True)

    # Create feature branch from default (skip if already exists from spec commit)
    subprocess.run(["git", "checkout", DEFAULT_BRANCH], cwd=project_dir,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    result = subprocess.run(["git", "checkout", "-b", feature_branch, DEFAULT_BRANCH], cwd=project_dir,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if result.returncode != 0:
        # Branch already exists (spec was committed) — just checkout
        subprocess.run(["git", "checkout", feature_branch], cwd=project_dir,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

    # Pre-check: detect file overlap between task branches before merging
    task_branches = [(t.id, t.branch, t.files) for t in completed_tasks]
    for i, (tid1, br1, files1) in enumerate(task_branches):
        for tid2, br2, files2 in task_branches[i+1:]:
            if not files1 or not files2:
                continue
            overlap = set(files1) & set(files2)
            if overlap:
                print(f"  🔴 BLOCKED — File overlap detected between tasks:", flush=True)
                print(f"     Task {tid1} ({br1}): {sorted(files1)}", flush=True)
                print(f"     Task {tid2} ({br2}): {sorted(files2)}", flush=True)
                print(f"     Overlapping: {sorted(overlap)}", flush=True)
                print(f"  Parallel coders modified the same files — merge will conflict.", flush=True)
                return False

    # Merge in dependency order
    for task in sorted(completed_tasks, key=lambda t: int(t.id)):
        print(f"  Merging {task.branch} (Task {task.id}: {task.description[:50]}...)")
        result = subprocess.run(
            ["git", "merge", task.branch, "--no-edit"],
            cwd=project_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60
        )
        if result.returncode != 0:
            print(f"  ❌ Merge conflict merging {task.branch}", flush=True)
            print(f"  {result.stderr[:500]}", flush=True)
            # Abort merge, delete feature branch (merge failed)
            subprocess.run(["git", "merge", "--abort"], cwd=project_dir,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            subprocess.run(["git", "branch", "-D", feature_branch], cwd=project_dir,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            return False

    # Push feature branch
    subprocess.run(["git", "push", "-u", "origin", feature_branch], cwd=project_dir,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    print(f"  ✅ Merged and pushed: {feature_branch}", flush=True)
    return True

def run_parallel_coders(tasks: dict[str, Task], waves: list[list[str]],
                        project_dir: str, spec_path: str,
                        tasks_extract_path: str = "") -> bool:
    """Execute parallel coder phase with worktree isolation."""
    # Allow test patching via tasks.run_parallel_coders override (F022 modular refactor)
    import sys as _sys_rpc
    _tasks_mod = _sys_rpc.modules.get('tasks')
    if _tasks_mod is not None:
        _fn = getattr(_tasks_mod, 'run_parallel_coders', None)
        if _fn is not None and _fn is not _RPC_ORIGINAL:
            return _fn(tasks, waves, project_dir, spec_path, tasks_extract_path)

    panel_dir = os.path.join(project_dir, ".dokima")
    os.makedirs(panel_dir, exist_ok=True)

    # Allow test patching via dokima module (F022 modular refactor)
    _dokima = _sys_rpc.modules.get('dokima')
    _WorktreeManager = getattr(_dokima, 'WorktreeManager', WorktreeManager) if _dokima else WorktreeManager
    _TaskLock = getattr(_dokima, 'TaskLock', TaskLock) if _dokima else TaskLock

    worktrees = _WorktreeManager(project_dir)
    locks = _TaskLock(panel_dir)
    running = {}  # task_id → Popen

    max_parallel = max_parallel_override if max_parallel_override is not None else 5
    print(f"  Max parallel agents: {max_parallel}", flush=True)

    all_completed = True
    try:

        for wave_num, wave in enumerate(waves, 1):
            print(f"\n── Wave {wave_num}: {len(wave)} task(s) ──", flush=True)
            wave_ids = ", ".join(f"Task {tid}" for tid in wave)
            print(f"  {wave_ids}", flush=True)

            # Validate no file collisions within the wave
            dag = TaskDAG()
            dag.tasks = tasks
            if not dag.validate_parallel_files(wave):
                print("  ⚠ File collision detected — run sequentially instead", flush=True)
                # Fall back to sequential execution using spawn_agent (mockable, synchronous)
                for tid in wave:
                    if not locks.claim(tid, f"coder-wave{wave_num}-seq"):
                        continue
                    task = tasks[tid]
                    parent_branch = DEFAULT_BRANCH
                    if task.dependencies:
                        dep_id = task.dependencies[0]
                        if dep_id in tasks and tasks[dep_id].branch:
                            parent_branch = tasks[dep_id].branch
                    wt_path = worktrees.create(tid, task.branch)

                    # Build coder prompt inline — same as spawn_coder_in_worktree
                    spec_ref = tasks_extract_path if tasks_extract_path else spec_path
                    spec_ctx = f"{spec_path} for context" if spec_path else "the task description"
                    coder_prompt = f"""Read the task breakdown at {spec_ref} (full spec: {spec_ctx}).

    You are working on Task {task.id}: {task.description}
    Files to create/modify: {', '.join(task.files) if task.files else 'determine from spec'}

    FIRST: Verify you are in the correct worktree and on branch '{task.branch}' (parent: {parent_branch}).

    TDD — TWO SEPARATE COMMITS on this branch:
    RED: Write tests → {TEST_CMD} must FAIL → git add <test files only> && git commit -m "test: {task.description[:60]}"
    GREEN: Write minimum code → {TEST_CMD} must PASS → {BUILD_CMD} must succeed → git add <impl files only> && git commit -m "feat: {task.description[:60]}"
    CRITICAL: Two distinct commits, RED before GREEN. No task numbers in commit messages. Do NOT modify files outside task scope.
    BEFORE PUSHING: Check if the spec requires a README update. If yes, update README.md and commit as \"docs: update README\". Run lint ({LINT_CMD}) + FULL test suite ({TEST_CMD}). If either fails, fix and retry. Only push when clean.
    Report: both commit hashes, files changed, test results, lint status, branch name.
    """
                    try:
                        output = spawn_agent("coder", ["ai-coding-best-practices-lite"],
                                             coder_prompt, timeout=900, cwd=wt_path, fallback_model=FALLBACK_MODELS.get("coder"))
                        task.status = "completed"
                        task.output = output
                        print(f"  ✅ Task {tid} completed ({len(output)} chars)", flush=True)
                    except Exception as e:
                        task.status = "failed"
                        task.output = str(e)
                        print(f"  ❌ Task {tid} failed: {e}", flush=True)
                    locks.release(tid)
            else:
                # Parallel spawn — honour max_parallel cap
                spawned_this_wave = 0
                overflow = []  # tasks that exceed the cap, run after first batch

                for tid in wave:
                    if spawned_this_wave >= max_parallel:
                        overflow.append(tid)
                        continue
                    if not locks.claim(tid, f"coder-wave{wave_num}"):
                        print(f"  ⚠ Task {tid} already claimed — skipping", flush=True)
                        continue
                    task = tasks[tid]
                    parent_branch = DEFAULT_BRANCH
                    if task.dependencies:
                        dep_id = task.dependencies[0]
                        if dep_id in tasks and tasks[dep_id].branch:
                            parent_branch = tasks[dep_id].branch
                    wt_path = worktrees.create(tid, task.branch)
                    proc = spawn_coder_in_worktree(task, wt_path, spec_path, parent_branch, tasks_extract_path)
                    running[tid] = proc
                    spawned_this_wave += 1

                if overflow:
                    print(f"  ⚠ {len(overflow)} task(s) exceed max_parallel ({max_parallel}) — queued", flush=True)

                _poll_until_wave_done(wave, running, tasks, locks, timeout=900)

                # Run overflow tasks in sub-waves (parallel batches)
                overflow_idx = 0
                while overflow_idx < len(overflow):
                    sub_wave = overflow[overflow_idx:overflow_idx + max_parallel]
                    overflow_idx += len(sub_wave)

                    print(f"  ⚠ Overflow sub-wave: {len(sub_wave)} task(s)", flush=True)

                    # Spawn all tasks in this sub-wave
                    for tid in sub_wave:
                        if not locks.claim(tid, f"coder-wave{wave_num}-overflow"):
                            continue
                        task = tasks[tid]
                        parent_branch = DEFAULT_BRANCH
                        if task.dependencies:
                            dep_id = task.dependencies[0]
                            if dep_id in tasks and tasks[dep_id].branch:
                                parent_branch = tasks[dep_id].branch
                        wt_path = worktrees.create(tid, task.branch)
                        proc = spawn_coder_in_worktree(task, wt_path, spec_path, parent_branch, tasks_extract_path)
                        running[tid] = proc

                    # Poll the sub-wave in parallel
                    _poll_until_wave_done(sub_wave, running, tasks, locks, timeout=900)

            # Report wave results
            for tid in wave:
                task = tasks[tid]
                if task.status == "failed":
                    all_completed = False
                    print(f"  ❌ Task {tid} FAILED: {task.description[:80]}", flush=True)
                elif task.status == "timed_out":
                    all_completed = False
                    print(f"  ⚠ Task {tid} TIMED OUT: {task.description[:80]}", flush=True)
                elif task.status == "completed":
                    print(f"  ✅ Task {tid} done: {task.description[:80]}", flush=True)

    finally:
        all_ids = list(tasks.keys())
        worktrees.cleanup_all(all_ids)

    return all_completed

# Module-level original reference for delegation check (F022 modular refactor)
_RPC_ORIGINAL = run_parallel_coders
