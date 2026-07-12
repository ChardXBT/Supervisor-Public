from __future__ import annotations

from dataclasses import dataclass, field

from .model import Event, Job, JobState


@dataclass
class AutomationEngine:
    """Small deterministic state machine used by the public demonstration.

    The engine intentionally has no operating-system process control. It models
    the decisions a production orchestrator would make while keeping this
    repository safe to run on any machine.
    """

    jobs: list[Job]
    capacity: int = 3
    network_ready: bool = True
    automation_paused: bool = False
    events: list[Event] = field(default_factory=list)
    _sequence: int = 0

    def _record(self, level: str, job: str, action: str, reason: str) -> None:
        self._sequence += 1
        self.events.append(Event(self._sequence, level, job, action, reason))

    @property
    def running_weight(self) -> int:
        return sum(job.weight for job in self.jobs if job.state is JobState.RUNNING)

    def schedule(self) -> Job | None:
        if self.automation_paused:
            self._record("INFO", "supervisor", "hold", "automation is paused")
            return None
        if not self.network_ready:
            self._record("WARN", "supervisor", "hold", "network recovery is not verified")
            return None
        candidates = sorted(
            (job for job in self.jobs if job.state is JobState.READY),
            key=lambda job: (-job.priority, job.name),
        )
        for job in candidates:
            if self.running_weight + job.weight > self.capacity:
                continue
            job.state = JobState.RUNNING
            job.attempts += 1
            job.last_reason = "selected by priority and available capacity"
            self._record("INFO", job.name, "start", job.last_reason)
            return job
        self._record("INFO", "supervisor", "wait", "no eligible job fits current capacity")
        return None

    def disconnect(self) -> None:
        self.network_ready = False
        self._record("WARN", "supervisor", "pause", "connectivity check failed")
        for job in self.jobs:
            if job.state is JobState.RUNNING:
                job.state = JobState.PAUSED
                job.last_reason = "paused at a safe boundary"
                self._record("WARN", job.name, "checkpoint", job.last_reason)

    def recover_network(self) -> None:
        self.network_ready = True
        self._record("INFO", "supervisor", "recover", "stable connectivity window verified")
        for job in self.jobs:
            if job.state is JobState.PAUSED:
                job.state = JobState.READY
                job.last_reason = "checkpoint validated; eligible to resume"

    def complete(self, job_name: str) -> None:
        job = self._job(job_name)
        if job.state is not JobState.RUNNING:
            raise ValueError(f"{job_name} is not running")
        job.state = JobState.COMPLETE
        job.last_reason = "completion proof and clean exit verified"
        self._record("INFO", job.name, "complete", job.last_reason)

    def fail(self, job_name: str, *, retryable: bool) -> None:
        job = self._job(job_name)
        if job.state is not JobState.RUNNING:
            raise ValueError(f"{job_name} is not running")
        job.state = JobState.COOLDOWN if retryable else JobState.ATTENTION
        job.last_reason = (
            "temporary failure; retry delayed" if retryable else "explicit operator attention required"
        )
        self._record("WARN", job.name, job.state.value, job.last_reason)

    def release_cooldown(self, job_name: str) -> None:
        job = self._job(job_name)
        if job.state is not JobState.COOLDOWN:
            raise ValueError(f"{job_name} is not cooling down")
        job.state = JobState.READY
        job.last_reason = "cooldown expired"
        self._record("INFO", job.name, "eligible", job.last_reason)

    def _job(self, job_name: str) -> Job:
        for job in self.jobs:
            if job.name == job_name:
                return job
        raise KeyError(job_name)


def demo_engine() -> AutomationEngine:
    return AutomationEngine(
        jobs=[
            Job("live-monitor", priority=100, weight=1),
            Job("daily-report", priority=30, weight=2),
            Job("catalog-refresh", priority=20, weight=2),
        ]
    )
