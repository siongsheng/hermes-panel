"""Dokima pipeline status — live dashboard data model, file I/O, and terminal renderer.

Thread-safe: writes use atomic rename. Reads are tolerant of missing/incomplete files.
"""

import json, os, time, datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

STATUS_FILE = ".pipeline-status.json"  # written to PROJECT_DIR

PHASES = ["strategist", "coder", "vet", "nm", "tech-lead"]
PHASE_LABELS = {
    "strategist": "Strategist (spec)",
    "coder": "Coder (implementation)",
    "vet": "vet (build+test)",
    "nm": "nm (adversarial review)",
    "tech-lead": "Tech Lead (review)",
}
TASK_STATES = ["pending", "running", "completed", "failed"]


@dataclass
class TaskStatus:
    id: str
    description: str = ""
    state: str = "pending"          # pending | running | completed | failed
    branch: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: str = ""


@dataclass
class PhaseTiming:
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class PipelineStatus:
    feature: str = ""
    project: str = ""
    branch: str = ""
    depth: str = ""
    risk: str = ""
    mode: str = "passive"
    log_path: str = ""
    started_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    current_phase: str = "init"
    phases: dict = field(default_factory=lambda: {p: PhaseTiming() for p in PHASES})
    tasks: list = field(default_factory=list)
    task_total: int = 0
    task_completed: int = 0
    task_failed: int = 0
    verdict: str = ""
    pr_url: str = ""
    errors: list = field(default_factory=list)

    def elapsed(self) -> str:
        try:
            delta = datetime.datetime.now() - datetime.datetime.fromisoformat(self.started_at)
            mins, secs = divmod(int(delta.total_seconds()), 60)
            hrs, mins = divmod(mins, 60)
            if hrs:
                return f"{hrs}h {mins:02d}m"
            return f"{mins}m {secs:02d}s"
        except Exception:
            return "?"

    def task_progress(self) -> str:
        return f"{self.task_completed}/{self.task_total}"


def load_status(project_dir: str) -> Optional[PipelineStatus]:
    """Load pipeline status from file. Returns None if absent or corrupt."""
    path = os.path.join(project_dir, STATUS_FILE)
    try:
        with open(path) as f:
            data = json.load(f)
        # Rebuild tasks from raw dicts
        raw_tasks = data.pop("tasks", [])
        tasks = [TaskStatus(**t) for t in raw_tasks]
        # Rebuild phases
        raw_phases = data.pop("phases", {})
        phases = {k: PhaseTiming(**v) if isinstance(v, dict) else PhaseTiming() for k, v in raw_phases.items()}
        return PipelineStatus(tasks=tasks, phases=phases, **data)
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return None


def save_status(status: PipelineStatus, project_dir: str):
    """Atomically write status to file (write temp + rename)."""
    path = os.path.join(project_dir, STATUS_FILE)
    tmp = path + ".tmp"
    try:
        data = asdict(status)
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2, default=str)
        os.rename(tmp, path)
    except OSError:
        pass  # best-effort — don't crash the pipeline for status file I/O


def update_phase(status: PipelineStatus, phase: str, started: bool = True):
    """Mark a phase as started or completed."""
    if phase not in status.phases:
        return
    now = datetime.datetime.now().isoformat()
    if started:
        status.current_phase = phase
        status.phases[phase].started_at = now
    else:
        status.phases[phase].completed_at = now


def add_task(status: PipelineStatus, task_id: str, desc: str, branch: str = ""):
    """Register a new task."""
    status.tasks.append(TaskStatus(id=task_id, description=desc, branch=branch))
    status.task_total = len(status.tasks)


def update_task(status: PipelineStatus, task_id: str, state: str, error: str = ""):
    """Update a task's state."""
    for t in status.tasks:
        if t.id == task_id:
            now = datetime.datetime.now().isoformat()
            t.state = state
            if state == "running" and not t.started_at:
                t.started_at = now
            elif state in ("completed", "failed"):
                t.completed_at = now
            if error:
                t.error = error
            break
    # Recompute counters
    status.task_completed = sum(1 for t in status.tasks if t.state == "completed")
    status.task_failed = sum(1 for t in status.tasks if t.state == "failed")


def render(status: PipelineStatus) -> str:
    """Render pipeline status as a terminal dashboard string."""
    W = 68  # terminal width
    BAR = "═" * (W - 2)
    THIN = "─" * (W - 2)

    def box(header, lines):
        out = [f"╔{BAR}╗", f"║  {header:<{W-4}}║", f"╠{THIN}╣"]
        for line in lines:
            out.append(f"║  {line:<{W-4}}║")
        out.append(f"╚{BAR}╝")
        return "\n".join(out)

    # Header section
    header_lines = [
        f"Feature:  {status.feature}",
        f"Project:  {status.project}",
        f"Branch:   {status.branch or '(not created)'}",
        f"Depth:    {status.depth.upper()}     Risk: {status.risk}     Mode: {status.mode.upper()}",
        f"Elapsed:  {status.elapsed()}",
    ]
    result = [box("Dokima Pipeline", header_lines), ""]

    # Phase section
    phase_lines = []
    for p in PHASES:
        pt = status.phases.get(p)
        if not pt:
            continue
        if pt.started_at and pt.completed_at:
            marker = "✅"
        elif pt.started_at:
            marker = "🟢"
        else:
            marker = "⬜"
        phase_lines.append(f"{marker} {PHASE_LABELS[p]:<28s}")
    if phase_lines:
        result.append(box("Phases", phase_lines))
        result.append("")

    # Task section (if any)
    if status.tasks:
        task_lines = [f"{'ID':<6s} {'State':<12s} {'Description':<40s}"]
        for t in status.tasks:
            state_icon = {"pending": "⏳", "running": "🟢", "completed": "✅", "failed": "❌"}.get(t.state, "?")
            task_lines.append(f"T{t.id:<5s} {state_icon} {t.state:<9s} {t.description[:38]:<38s}")
            if t.error:
                task_lines.append(f"       {'↳':>1s} {t.error[:55]:<55s}")
        result.append(box(f"Tasks ({status.task_completed}/{status.task_total})", task_lines))
        result.append("")

    # Errors section
    if status.errors:
        result.append(box("Errors", [e[:60] for e in status.errors[-5:]]))
        result.append("")

    # Footer
    footer_lines = [
        f"Log:  {status.log_path}",
        f"PR:   {status.pr_url or '(not created)'}",
        f"Verdict: {status.verdict or '(pending)'}",
    ]
    result.append(box("Info", footer_lines))

    return "\n".join(result)
