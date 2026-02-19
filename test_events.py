"""
Quick test to verify the event loop captures real-time events.
Runs for 8 seconds, prints events, then stops.
"""

import sys
import threading
import time

from sauliethwm.core.manager import WindowManager, WMEvent
from sauliethwm.core.window import Window


def safe(text: str) -> str:
    enc = sys.stdout.encoding or "utf-8"
    return text.encode(enc, errors="replace").decode(enc, errors="replace")


def on_event(event: WMEvent, window: Window | None, wm: WindowManager) -> None:
    ts = time.strftime("%H:%M:%S")
    if window and window.is_valid:
        print(f"  [{ts}] {event.value:<20s} | {window.hwnd:#010x} | {safe(window.title[:60])}")
    else:
        hwnd = window.hwnd if window else 0
        print(f"  [{ts}] {event.value:<20s} | {hwnd:#010x} | <gone>")


def main() -> None:
    wm = WindowManager()
    wm.on_all(on_event)

    # Auto-stop after 8 seconds
    def _timer():
        time.sleep(8)
        print("\n  [Timer] 8 seconds elapsed, stopping...")
        wm.stop()

    t = threading.Thread(target=_timer, daemon=True)
    t.start()

    print(f"\n  Managed: {wm.count} windows (before start)")
    print("  Listening for events for 8 seconds...\n")
    print(f"  {'Event':<26s} | {'HWND':<12s} | Title")
    print("  " + "-" * 70)

    wm.start()

    print(f"\n  Final state: {wm.count} managed windows")
    print("  Done.")


if __name__ == "__main__":
    main()
