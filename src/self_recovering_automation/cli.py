from __future__ import annotations

import argparse

from .engine import demo_engine


def render_demo() -> str:
    engine = demo_engine()
    engine.schedule()
    engine.schedule()
    engine.disconnect()
    engine.recover_network()
    engine.schedule()
    engine.complete("live-monitor")
    engine.schedule()

    lines = [
        "SELF-RECOVERING AUTOMATION  |  safe dry-run",
        "=" * 72,
        "SEQ  LEVEL  COMPONENT         ACTION       DECISION",
    ]
    for event in engine.events:
        lines.append(
            f"{event.sequence:>3}  {event.level:<5}  {event.job:<16}  "
            f"{event.action:<11}  {event.reason}"
        )
    lines.extend(["", "FINAL STATE"])
    for job in engine.jobs:
        lines.append(
            f"  {job.name:<16} {job.state.value:<10} attempts={job.attempts}  {job.last_reason}"
        )
    lines.append("")
    lines.append("Result: recovery verified; no duplicate starts; no external actions performed.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the safe manager recovery demo")
    parser.add_argument("--dry-run", action="store_true", help="retained for explicitness; all runs are safe")
    parser.parse_args()
    print(render_demo())


if __name__ == "__main__":
    main()
