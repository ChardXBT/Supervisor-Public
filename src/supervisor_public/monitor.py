"""Terminal monitor display for the Supervisor.

The real Supervisor uses a Textual/Rich-based terminal UI that renders
live engine state and submits guarded operator commands.  This public
representation renders a static monitor-only display to demonstrate
the monitoring concept without any write access.
"""

from __future__ import annotations


WIDTH = 96


def _row(text: str = "") -> str:
    content = f" {text}" if text else ""
    return "|" + content[: WIDTH - 2].ljust(WIDTH - 2) + "|"


def _divider(title: str = "") -> str:
    if not title:
        return "+" + "-" * (WIDTH - 2) + "+"
    label = f" {title} "
    return "+" + label + "-" * (WIDTH - 2 - len(label)) + "+"


def render_monitor() -> str:
    """Render a stable monitor-only screen using representative state."""
    lines = [
        "+" + "-" * (WIDTH - 2) + "+",
        _row("SUPERVISOR PUBLIC"),
        _row("Monitor-only view | no external processes or services"),
        _divider("SYSTEM"),
        _row("Mode              MONITOR ONLY        Automation decisions      DISABLED"),
        _row("Network           SIMULATED / READY   Resource safety gate     SAFE"),
        _row("Recovery          CONSISTENT          Duplicate-start guard    ARMED"),
        _row("Process ownership PID-reuse-safe      Stale state check       ACTIVE"),
        _divider("MANAGED PROJECTS"),
        _row("PROJECT              STATE         PRIORITY   LAST DECISION"),
        _row("worker-alpha         IDLE          HIGH       waiting for eligible work"),
        _row("worker-beta          IDLE          NORMAL     schedule window not due"),
        _row("scheduled-sync       IDLE          NORMAL     capacity available"),
        _divider("SUPERVISOR DECISION LOG"),
        _row("INFO  State snapshot validated; recovery is not required."),
        _row("INFO  All demonstration projects are idle; no action selected."),
        _row("INFO  Monitor-only invariant verified; writes and launches are blocked."),
        _divider(),
        _row("Status: healthy and observing only. Press Ctrl+C to close."),
        "+" + "-" * (WIDTH - 2) + "+",
    ]
    return "\n".join(lines)
