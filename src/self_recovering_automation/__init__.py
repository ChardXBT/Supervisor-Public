"""Public-safe reference implementation for resilient automation."""

from .engine import AutomationEngine, demo_engine
from .model import Event, Job, JobState

__all__ = ["AutomationEngine", "Event", "Job", "JobState", "demo_engine"]
