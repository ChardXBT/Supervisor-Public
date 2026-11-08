"""Supervisor engine: a lightweight state machine demonstrating the
architectural decisions a production automation supervisor makes.

The real Supervisor owns ~10,000 lines of process management, PID-reuse-safe
identity checks, multi-phase stop transactions, unclean-session recovery,
and marketplace compatibility enforcement.  This public representation
models the same decision categories without any operating-system process
control, network calls, or file I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import (
    Event,
    LEGAL_RUN_MODE_TRANSITIONS,
    LEGAL_TRANSITIONS,
    PauseCause,
    Project,
    ProjectState,
    RunMode,
)


@dataclass
class SupervisorEngine:
    """Deterministic state machine used by the public demonstration.

    This engine models the core decision loop:

        load state -> inspect processes -> evaluate safety gates
        -> schedule eligible projects -> observe results -> persist state

    without performing any of those operations for real.
    """

    projects: list[Project]
    capacity: int = 3
    run_mode: RunMode = RunMode.NORMAL
    events: list[Event] = field(default_factory=list)
    _sequence: int = 0

    # -- observation layer ---------------------------------------------------

    def _record(
        self,
        level: str,
        project: str,
        action: str,
        reason: str,
        *,
        state: str = "",
        attempt: int = 0,
    ) -> None:
        self._sequence += 1
        self.events.append(
            Event(self._sequence, level, project, action, reason, state, attempt)
        )

    def _transition(self, project: Project, new_state: ProjectState, reason: str) -> None:
        """Validate and perform a state transition, recording the event."""
        allowed = LEGAL_TRANSITIONS.get(project.state, set())
        if new_state not in allowed:
            raise ValueError(
                f"illegal transition {project.state.value} -> {new_state.value} "
                f"for {project.name}; allowed: {sorted(s.value for s in allowed)}"
            )
        if new_state is ProjectState.PAUSED and not project.paused_by:
            raise ValueError(
                f"cannot pause {project.name} without a recorded pause cause"
            )
        old_state = project.state
        project.state = new_state
        if new_state is not ProjectState.PAUSED:
            project.paused_by.clear()
        project.last_reason = reason
        self._record(
            "INFO" if new_state in (ProjectState.RUNNING, ProjectState.READY, ProjectState.STOPPED) else "WARN",
            project.name,
            f"transition:{old_state.value}->{new_state.value}",
            reason,
            state=new_state.value,
            attempt=project.attempts,
        )

    def _transition_run_mode(self, new_mode: RunMode, reason: str) -> None:
        """Validate and perform a run-mode transition, recording the event.

        Every run-mode change flows through here so a hold can only be
        raised or cleared one axis at a time.
        """
        allowed = LEGAL_RUN_MODE_TRANSITIONS.get(self.run_mode, set())
        if new_mode not in allowed:
            raise ValueError(
                f"illegal run-mode transition {self.run_mode!r} -> {new_mode!r}; "
                f"allowed: {sorted(m.value for m in allowed)}"
            )
        old_mode = self.run_mode
        self.run_mode = new_mode
        self._record(
            "WARN" if new_mode in (RunMode.NETWORK_HOLD, RunMode.DUAL_HOLD) else "INFO",
            "supervisor",
            f"run_mode:{old_mode.value}->{new_mode.value}",
            reason,
            state=new_mode.value,
        )

    @property
    def network_ready(self) -> bool:
        """Derived from run_mode: False while a network hold is active."""
        return self.run_mode in (RunMode.NORMAL, RunMode.OPERATOR_HOLD)

    @property
    def automation_paused(self) -> bool:
        """Derived from run_mode: True while an operator hold is active."""
        return self.run_mode in (RunMode.OPERATOR_HOLD, RunMode.DUAL_HOLD)

    @property
    def running_weight(self) -> int:
        return sum(p.weight for p in self.projects if p.state is ProjectState.RUNNING)

    def project(self, name: str) -> Project:
        for p in self.projects:
            if p.name == name:
                return p
        raise KeyError(name)

    # -- scheduling ----------------------------------------------------------

    def schedule(self) -> Project | None:
        """Select the highest-priority eligible project that fits capacity.

        The real Supervisor's scheduler applies: monitor-only check, pause
        state, network policy, battery/resource gates, unclean-recovery
        block, priority, capacity, cooldown, restart-hold, repair-latch,
        duplicate-start prevention, and schedule-window eligibility.
        This public version models the key decision categories.
        """
        if self.run_mode is RunMode.NETWORK_HOLD:
            self._record("WARN", "supervisor", "hold", "network recovery not yet verified")
            return None
        if self.run_mode is RunMode.OPERATOR_HOLD:
            self._record("INFO", "supervisor", "hold", "automation is paused by operator")
            return None
        if self.run_mode is RunMode.DUAL_HOLD:
            self._record(
                "WARN", "supervisor", "hold",
                "automation paused and network recovery not yet verified",
            )
            return None
        if self.run_mode is not RunMode.NORMAL:
            raise ValueError(f"unknown run mode: {self.run_mode!r}")

        candidates = sorted(
            (p for p in self.projects if p.state is ProjectState.READY),
            key=lambda p: (-p.priority, p.name),
        )
        for project in candidates:
            if self.running_weight + project.weight > self.capacity:
                self._record(
                    "INFO", project.name, "skip",
                    f"capacity exceeded: running_weight={self.running_weight} "
                    f"project_weight={project.weight} capacity={self.capacity}",
                )
                continue
            if project.attempts >= project.max_attempts:
                self._transition(project, ProjectState.REPAIR_REQUIRED, "attempt budget exhausted")
                return None
            self._transition(project, ProjectState.STARTING, "selected by priority and capacity")
            self._transition(project, ProjectState.RUNNING, "process identity confirmed")
            return project

        self._record("INFO", "supervisor", "wait", "no eligible project fits current capacity")
        return None

    # -- lifecycle events ----------------------------------------------------

    def complete(self, name: str) -> None:
        """Project completed successfully with verified completion proof.

        The real Supervisor distinguishes process exit from work completion.
        A fresh, identity-bound artifact must be verified before marking
        a project complete.  This public version models the distinction
        through explicit state validation.
        """
        project = self.project(name)
        if project.state is not ProjectState.RUNNING:
            raise ValueError(f"{name} is not running (state={project.state.value})")
        self._transition(project, ProjectState.STOPPED, "completion proof and clean exit verified")

    def fail(self, name: str, *, repair_required: bool = False) -> None:
        """Report a project failure.

        The real Supervisor separates temporary failures (retry with cooldown)
        from repair-required failures (latched until explicit operator action
        or verified fix evidence).  This distinction prevents retry storms
        on durable problems.
        """
        project = self.project(name)
        if project.state is not ProjectState.RUNNING:
            raise ValueError(f"{name} is not running (state={project.state.value})")
        if repair_required:
            self._transition(
                project, ProjectState.REPAIR_REQUIRED,
                "durable failure; requires operator intervention or verified fix",
            )
        else:
            self._transition(
                project, ProjectState.COOLDOWN,
                f"temporary failure; retry delayed ({project.cooldown_seconds}s cooldown)",
            )

    def release_cooldown(self, name: str) -> None:
        """Cooldown timer expired; project is eligible again."""
        project = self.project(name)
        if project.state is not ProjectState.COOLDOWN:
            raise ValueError(f"{name} is not cooling down (state={project.state.value})")
        self._transition(project, ProjectState.READY, "cooldown expired; eligible to reschedule")

    def acknowledge_repair(self, name: str) -> None:
        """Operator acknowledges repair-required state and clears it.

        In the real Supervisor, a repair-latched project requires fresh
        verified evidence (a newer success or an explicit operator action)
        before it returns to the eligible queue.  This models that concept.
        """
        project = self.project(name)
        if project.state is not ProjectState.REPAIR_REQUIRED:
            raise ValueError(f"{name} is not in repair_required state")
        project.attempts = 0
        self._transition(project, ProjectState.READY, "repair acknowledged; reset attempt budget")

    # -- stop / shutdown -----------------------------------------------------

    def request_stop(self, name: str) -> None:
        """Initiate a graceful stop transaction.

        The real Supervisor models stopping as a multi-phase transaction:
        REQUESTED -> IDENTIFY_OWNER -> SIGNAL -> WAIT -> VERIFY_EXIT -> FINALIZE.
        The stop transaction journal tracks each phase with SHA-256 digests.
        This public version models the entry and exit of the stop sequence.
        """
        project = self.project(name)
        if project.state is ProjectState.RUNNING:
            self._transition(project, ProjectState.STOPPING, "stop requested; awaiting child acknowledgment")
        elif project.state is ProjectState.STARTING:
            self._transition(project, ProjectState.STOPPING, "stop requested during startup window")
        else:
            raise ValueError(f"{name} cannot be stopped from state {project.state.value}")

    def confirm_stop(self, name: str) -> None:
        """Verify that the project process has exited with a valid receipt.

        The real Supervisor requires a correlated shutdown receipt matching
        the specific stop-request ID, plus exact PID+birth-time identity
        verification.  This public version models the verification step.
        """
        project = self.project(name)
        if project.state is not ProjectState.STOPPING:
            raise ValueError(f"{name} is not stopping (state={project.state.value})")
        self._transition(project, ProjectState.STOPPED, "stop verified; process exit confirmed")

    # -- network / health ----------------------------------------------------

    def disconnect(self) -> None:
        """Simulate a network connectivity failure.

        The real Supervisor's NetworkCoordinator escalates through
        ONLINE -> SUSPECT -> OFFLINE_BACKOFF_1/2/3 -> OFFLINE_GRACEFUL_STOP,
        cooperatively pausing affected bots.  This public version models
        the pause-all on connectivity loss.
        """
        target = RunMode.DUAL_HOLD if self.automation_paused else RunMode.NETWORK_HOLD
        self._transition_run_mode(
            target, "connectivity check failed; pausing affected projects"
        )
        for project in self.projects:
            if project.state is ProjectState.RUNNING:
                project.paused_by.add(PauseCause.NETWORK)
                self._transition(project, ProjectState.PAUSED, "paused at safe boundary due to network loss")
            elif project.state is ProjectState.PAUSED:
                project.paused_by.add(PauseCause.NETWORK)
                self._record("WARN", project.name, "hold", "network hold stacked on existing pause")

    def recover_network(self) -> None:
        """Network connectivity restored; resume paused projects.

        The real Supervisor waits for a stable connectivity window before
        resuming, and verifies network state through DNS/HTTP probes.
        Only the network hold is cleared: a project paused for another
        recorded cause (e.g. an operator hold) stays parked.
        """
        target = RunMode.OPERATOR_HOLD if self.automation_paused else RunMode.NORMAL
        self._transition_run_mode(target, "stable connectivity window verified")
        for project in self.projects:
            if project.state is ProjectState.PAUSED:
                project.paused_by.discard(PauseCause.NETWORK)
                if not project.paused_by:
                    self._transition(project, ProjectState.READY, "network recovered; eligible to resume")

    # -- operator hold ------------------------------------------------------

    def pause_automation(self) -> None:
        """Operator hold: park running work and block new starts.

        The real Supervisor exposes pause/resume through its remote
        gateway.  This public version records the hold as one axis of the
        run mode and stacks it per project, so a concurrent network hold
        cannot silently clear it.
        """
        target = RunMode.DUAL_HOLD if not self.network_ready else RunMode.OPERATOR_HOLD
        self._transition_run_mode(target, "automation paused by operator")
        for project in self.projects:
            if project.state is ProjectState.RUNNING:
                project.paused_by.add(PauseCause.OPERATOR)
                self._transition(project, ProjectState.PAUSED, "paused at safe boundary by operator hold")
            elif project.state is ProjectState.PAUSED:
                project.paused_by.add(PauseCause.OPERATOR)
                self._record("INFO", project.name, "hold", "operator hold stacked on existing pause")

    def resume_automation(self) -> None:
        """Release the operator hold; projects it parked become eligible."""
        target = RunMode.NETWORK_HOLD if not self.network_ready else RunMode.NORMAL
        self._transition_run_mode(target, "operator resumed automation")
        for project in self.projects:
            if project.state is ProjectState.PAUSED:
                project.paused_by.discard(PauseCause.OPERATOR)
                if not project.paused_by:
                    self._transition(project, ProjectState.READY, "operator hold released; eligible to resume")

    # -- recovery ------------------------------------------------------------

    def recover_from_unclean_shutdown(self) -> list[str]:
        """Reconcile project state after an unexpected supervisor restart.

        The real Supervisor detects prior unclean shutdowns via a session
        marker, inspects interrupted stop-transaction journals, identifies
        orphaned children by exact PID+birth-time, and holds ambiguous
        projects in a safe recovery state.  This public version models
        the reconciliation pass.
        """
        held: list[str] = []
        for project in self.projects:
            if project.state is ProjectState.RUNNING:
                # In the real system, we would inspect the process table
                # to determine if the child is still alive.  Here we
                # assume uncertain state and move to recovery.
                self._transition(project, ProjectState.RECOVERING, "prior session unclean; ownership unverified")
                held.append(project.name)
            elif project.state is ProjectState.STARTING:
                self._transition(project, ProjectState.RECOVERING, "interrupted launch; state unknown")
                held.append(project.name)
            elif project.state is ProjectState.STOPPING:
                self._transition(project, ProjectState.RECOVERING, "interrupted shutdown; transaction incomplete")
                held.append(project.name)
        if held:
            self._record("WARN", "supervisor", "recovery", f"held {len(held)} project(s) for reconciliation")
        else:
            self._record("INFO", "supervisor", "recovery", "all projects in clean state; no recovery needed")
        return held

    def reconcile_recovering(self, name: str, *, alive: bool) -> None:
        """Resolve a recovering project based on inspection results.

        If the process is still alive, re-adopt it.  If it is gone,
        move it to stopped so the scheduler can relaunch when appropriate.
        """
        project = self.project(name)
        if project.state is not ProjectState.RECOVERING:
            raise ValueError(f"{name} is not recovering (state={project.state.value})")
        if alive:
            self._transition(project, ProjectState.RUNNING, "process re-adopted; ownership confirmed")
        else:
            self._transition(project, ProjectState.STOPPED, "process absent; cleared for relaunch")


def demo_engine() -> SupervisorEngine:
    """Create a demo engine with representative project types.

    These project names and priorities illustrate the kinds of work the
    real Supervisor manages, without referencing any private project.
    """
    return SupervisorEngine(
        projects=[
            Project("worker-alpha", priority=100, weight=1, cooldown_seconds=10),
            Project("worker-beta", priority=30, weight=2, cooldown_seconds=30),
            Project("scheduled-sync", priority=20, weight=2, cooldown_seconds=60),
        ]
    )
