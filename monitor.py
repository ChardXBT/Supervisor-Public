"""Entry point for the Supervisor Public monitor display."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from supervisor_public.monitor import render_monitor  # noqa: E402


def main() -> None:
    if "--once" in sys.argv:
        print(render_monitor())
        return
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print(render_monitor())
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
