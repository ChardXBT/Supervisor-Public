from __future__ import annotations


WIDTH = 96


def _row(text: str = "") -> str:
    content = f" {text}" if text else ""
    return "│" + content[: WIDTH - 2].ljust(WIDTH - 2) + "│"


def _divider(title: str = "") -> str:
    if not title:
        return "├" + "─" * (WIDTH - 2) + "┤"
    label = f" {title} "
    return "├" + label + "─" * (WIDTH - 2 - len(label)) + "┤"


def render_monitor() -> str:
    """Render a stable, synthetic monitor-only screen for demonstrations."""
    lines = [
        "┌" + "─" * (WIDTH - 2) + "┐",
        _row("SELF-RECOVERING AUTOMATION"),
        _row("Monitor-only demonstration · no external processes or services"),
        _divider("SYSTEM"),
        _row("Mode            MONITOR ONLY      Automation decisions        DISABLED"),
        _row("Connectivity    SIMULATED / READY  Resource safety gate       SAFE"),
        _row("Recovery state  CONSISTENT         Duplicate-start protection  ARMED"),
        _divider("MANAGED WORKFLOWS"),
        _row("WORKFLOW             STATE       PRIORITY   LAST DECISION"),
        _row("continuous-monitor   IDLE        HIGH       waiting for eligible work"),
        _row("daily-report         IDLE        NORMAL     schedule window not due"),
        _row("catalog-refresh      IDLE        NORMAL     capacity available"),
        _divider("RECENT SUPERVISOR DECISIONS"),
        _row("INFO  State copies validated; recovery is not required."),
        _row("INFO  All demonstration workflows are idle; no action selected."),
        _row("INFO  Monitor-only invariant verified; writes and launches are blocked."),
        _divider(),
        _row("Status: healthy and observing only. Press Ctrl+C to close."),
        "└" + "─" * (WIDTH - 2) + "┘",
    ]
    return "\n".join(lines)
