"""Core data model for the Supervisor.

The production Supervisor models state as a conjunction of orthogonal flags
(runtime.pids, cooldown, restart_hold, shutdown_requested, etc.) rather than
a single enum.  This public representation collapses those into explicit
lifecycle states so the architecture is easy to follow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProjectState(str, Enum):
    """Lifecycle states a managed project can occupy.

    These correspond conceptually to the real Supervisor's observable states,
    which are derived from a combination of runtime flags, process inspection
    results, cooldown timers, and repair-latch conditions.
    """

    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COOLDOWN = "cooldown"
    REPAIR_REQUIRED = "repair_required"
    PAUSED = "paused"
    RECOVERING = "recovering"


# Legal state transitions.  Each key maps to the set of states it may move to.
# The engine validates every transition against this table.
LEGAL_TRANSITIONS: dict[ProjectState, set[ProjectState]] = {
    ProjectState.READY: {ProjectState.STARTING, ProjectState.PAUSED, ProjectState.REPAIR_REQUIRED},
    ProjectState.STARTING: {ProjectState.RUNNING, ProjectState.COOLDOWN, ProjectState.REPAIR_REQUIRED, ProjectState.STOPPED, ProjectState.STOPPING},
    ProjectState.RUNNING: {ProjectState.STOPPING, ProjectState.COOLDOWN, ProjectState.REPAIR_REQUIRED, ProjectState.PAUSED, ProjectState.STOPPED, ProjectState.RECOVERING},
    ProjectState.STOPPING: {ProjectState.STOPPED, ProjectState.RECOVERING},
    ProjectState.STOPPED: {ProjectState.RECOVERING, ProjectState.READY},
    ProjectState.COOLDOWN: {ProjectState.READY, ProjectState.REPAIR_REQUIRED, ProjectState.PAUSED},
    ProjectState.REPAIR_REQUIRED: {ProjectState.RECOVERING, ProjectState.READY, ProjectState.PAUSED},
    ProjectState.PAUSED: {ProjectState.READY, ProjectState.STOPPED},
    ProjectState.RECOVERING: {ProjectState.READY, ProjectState.STOPPED, ProjectState.REPAIR_REQUIRED},
}


@dataclass
class Project:
    """A managed automation project.

    In the real Supervisor, projects are defined through a registry of
    ProjectDefinition objects with separate type-specific lifecycle contracts
    (live_bot, stale_run_check_bot, local_app).  This public representation
    uses a single unified model.
    """

    name: str
    priority: int
    weight: int
    state: ProjectState = ProjectState.READY
    attempts: int = 0
    max_attempts: int = 3
    cooldown_seconds: float = 30.0
    last_reason: str = "waiting for scheduler"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.priority <= 0:
            raise ValueError(f"priority must be positive, got {self.priority}")
        if self.weight <= 0:
            raise ValueError(f"weight must be positive, got {self.weight}")


@dataclass(frozen=True)
class Event:
    """A structured lifecycle event.

    The real Supervisor emits structured key=value log lines with semantic
    event names (supervisor_started, job_start_blocked_permanent_disable,
    shutdown_start_skipped_already_stopped, etc.) and writes a machine-
    readable decision_summary.json each cycle.  This public representation
    captures the same information in a lightweight dataclass.
    """

    sequence: int
    level: str
    project: str
    action: str
    reason: str
    state: str = ""
    attempt: int = 0
