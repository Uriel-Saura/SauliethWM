"""
SauliethWM - Entry point.

Run with:  python -m sauliethwm
"""

import logging
import sys

from sauliethwm.core.manager import WindowManager, WMEvent
from sauliethwm.core.window import Window


class SafeStreamHandler(logging.StreamHandler):
    """Handler that replaces unencodable characters instead of crashing."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            enc = getattr(self.stream, "encoding", "utf-8") or "utf-8"
            safe = msg.encode(enc, errors="replace").decode(enc, errors="replace")
            self.stream.write(safe + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


def setup_logging() -> None:
    """Configure logging for the WM."""
    fmt = "%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s"
    handler = SafeStreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    # Quiet down noisy loggers
    logging.getLogger("sauliethwm.core.filter").setLevel(logging.INFO)


def on_event(event: WMEvent, window: Window | None, wm: WindowManager) -> None:
    """Example global event handler that logs everything."""
    safe_title = ""
    if window is not None:
        try:
            safe_title = window.title.encode(
                sys.stdout.encoding or "utf-8", errors="replace"
            ).decode(sys.stdout.encoding or "utf-8", errors="replace")
        except Exception:
            safe_title = "<encoding error>"

    if window is not None:
        print(
            f"  EVENT: {event.value:<20s} | "
            f"hwnd={window.hwnd:#010x} | "
            f"{safe_title!r}"
        )
    else:
        print(f"  EVENT: {event.value}")


def main() -> None:
    setup_logging()

    wm = WindowManager()

    # Subscribe to all events
    wm.on_all(on_event)

    # Show initial state
    print("\n" + wm.dump_state() + "\n")
    print("=" * 60)
    print("  SauliethWM event loop running. Press Ctrl+C to stop.")
    print("=" * 60 + "\n")

    # Enter the blocking event loop
    wm.start()


if __name__ == "__main__":
    main()
