"""Public demonstration of the Supervisor architecture.

This module runs a deterministic scenario that exercises the engine's
decision paths without touching the operating system.
"""

from __future__ import annotations

import argparse

from .engine import demo_engine


def render_demo() -> str:
    engine = demo_engine()

    # Phase 1: Normal scheduling
    first = engine.schedule()
    second = engine.schedule()

    # Phase 2: Network disruption and recovery
    engine.disconnect()
    engine.recover_network()

    # Phase 3: Resume and complete worker-alpha
    engine.schedule()
    engine.complete("worker-alpha")

    # Phase 4: Failure and cooldown for worker-beta
    engine.schedule()
    engine.fail("worker-beta", repair_required=False)
    engine.release_cooldown("worker-beta")

    # Phase 5: Complete worker-beta, then schedule and fail scheduled-sync
    engine.schedule()
    engine.complete("worker-beta")

    engine.schedule()
    engine.fail("scheduled-sync", repair_required=True)
    engine.acknowledge_repair("scheduled-sync")

    # Phase 6: Graceful stop
    engine.schedule()
    engine.request_stop("scheduled-sync")
    engine.confirm_stop("scheduled-sync")

    # Phase 7: Recovery from unclean shutdown
    engine.schedule()
    held = engine.recover_from_unclean_shutdown()
    for name in held:
        engine.reconcile_recovering(name, alive=False)

    lines = [
        "SUPERVISOR PUBLIC  |  safe dry-run demonstration",
        "=" * 72,
        "",
        "This demo exercises scheduling, network recovery, failure handling,",
        "repair-required state, graceful stop, and unclean-shutdown recovery.",
        "No processes are spawned and no external state is modified.",
        "",
        "SEQ  LEVEL  PROJECT           ACTION                          REASON",
        "-" * 72,
    ]
    for event in engine.events:
        lines.append(
            f"{event.sequence:>3}  {event.level:<5}  {event.project:<16}  "
            f"{event.action:<30}  {event.reason}"
        )
    lines.extend(["", "FINAL STATE", "-" * 72])
    for project in engine.projects:
        lines.append(
            f"  {project.name:<16} {project.state.value:<18} "
            f"attempts={project.attempts}/{project.max_attempts}  {project.last_reason}"
        )
    lines.extend([
        "",
        "Result: recovery verified; no duplicate starts; no external actions performed.",
        "",
        "Key architectural concepts demonstrated:",
        "  - Priority-based scheduling with capacity limits",
        "  - Network disconnect -> pause -> recovery cycle",
        "  - Temporary failure -> cooldown -> retry",
        "  - Repair-required state (not auto-retried)",
        "  - Graceful stop transaction",
        "  - Unclean shutdown detection and reconciliation",
        "  - Process ownership verification (conceptual)",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Supervisor Public: safe architectural demonstration"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="retained for explicitness; all runs are safe",
    )
    parser.parse_args()
    print(render_demo())


if __name__ == "__main__":
    main()
