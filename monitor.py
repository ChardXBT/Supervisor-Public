from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from self_recovering_automation.monitor import render_monitor  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Open the safe monitor-only demonstration")
    parser.add_argument("--once", action="store_true", help="render one frame and exit")
    args = parser.parse_args()
    if args.once:
        print(render_monitor())
        return
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print(render_monitor(), flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMonitor-only demonstration closed cleanly.")


if __name__ == "__main__":
    main()
