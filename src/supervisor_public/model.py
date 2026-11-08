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


class PauseCause(str, Enum):
    """A recorded reason a project is held in PAUSED.

    A project stays paused until every cause in ``paused_by`` has cleared,
    so an operator hold and a network hold stack without overwriting each
    other.
    """

    NETWORK = "network"
    OPERATOR = "operator"


class RunMode(str, Enum):
    """Supervisor run mode: network readiness x operator hold as one state.

    These were previously two independent booleans whose combination had no
    name and no validated transitions.  The closed vocabulary makes the
    hold interaction explicit.
    """

    NORMAL = "normal"
    NETWORK_HOLD = "network_hold"
    OPERATOR_HOLD = "operator_hold"
    DUAL_HOLD = "dual_hold"


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


# Legal run-mode transitions.  Each move flips exactly one hold axis, so
# DUAL_HOLD is entered and left one hold at a time and diagonal jumps
# (NORMAL <-> DUAL_HOLD) are impossible.
LEGAL_RUN_MODE_TRANSITIONS: dict[RunMode, set[RunMode]] = {
    RunMode.NORMAL: {RunMode.NETWORK_HOLD, RunMode.OPERATOR_HOLD},
    RunMode.NETWORK_HOLD: {RunMode.NORMAL, RunMode.DUAL_HOLD},
    RunMode.OPERATOR_HOLD: {RunMode.NORMAL, RunMode.DUAL_HOLD},
    RunMode.DUAL_HOLD: {RunMode.NETWORK_HOLD, RunMode.OPERATOR_HOLD},
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
    paused_by: set[PauseCause] = field(default_factory=set)
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
        self.paused_by = {PauseCause(cause) for cause in self.paused_by}
        if self.state is ProjectState.PAUSED and not self.paused_by:
            raise ValueError("PAUSED requires at least one recorded pause cause")
        if self.state is not ProjectState.PAUSED and self.paused_by:
            raise ValueError("pause causes recorded for a non-PAUSED project")


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
