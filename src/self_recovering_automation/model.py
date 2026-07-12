from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class JobState(str, Enum):
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COOLDOWN = "cooldown"
    COMPLETE = "complete"
    ATTENTION = "attention"


@dataclass
class Job:
    name: str
    priority: int
    weight: int
    state: JobState = JobState.READY
    attempts: int = 0
    last_reason: str = "waiting for capacity"


@dataclass(frozen=True)
class Event:
    sequence: int
    level: str
    job: str
    action: str
    reason: str
