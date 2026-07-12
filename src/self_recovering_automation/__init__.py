"""Public demo of a manager for scheduling and recovering automation jobs."""

from .engine import AutomationEngine, demo_engine
from .model import Event, Job, JobState

__all__ = ["AutomationEngine", "Event", "Job", "JobState", "demo_engine"]
