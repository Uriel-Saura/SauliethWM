"""
SauliethWM - Entry point.

Run with:  python -m sauliethwm
"""

import logging
import sys

from sauliethwm.core.manager import WindowManager, WMEvent
from sauliethwm.core.window import Window
from sauliethwm.tiling.engine import TilingEngine


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


def create_tiling_handler(engine: TilingEngine):
    """
    Crea un callback que conecta los eventos del WindowManager
    con el TilingEngine para reorganizar automaticamente.

    El handler reacciona a:
        - WINDOW_ADDED:     Agrega la ventana al tiling y reorganiza.
        - WINDOW_REMOVED:   Elimina la ventana del tiling y reorganiza.
        - WINDOW_RESTORED:  Re-aplica el layout (la ventana vuelve a su lugar).
        - WINDOW_MINIMIZED: Elimina temporalmente del tiling y reorganiza.
    """

    def tiling_handler(
        event: WMEvent, window: Window | None, wm: WindowManager
    ) -> None:
        if window is None:
            return

        if event == WMEvent.WINDOW_ADDED:
            engine.add_window(window)

        elif event == WMEvent.WINDOW_REMOVED:
            engine.remove_window(window)

        elif event == WMEvent.WINDOW_RESTORED:
            # La ventana vuelve de minimizada: asegurar que esta en el tiling
            if not engine.contains(window):
                engine.add_window(window)
            else:
                engine.apply()

        elif event == WMEvent.WINDOW_MINIMIZED:
            # Sacar del tiling para que las demas ocupen su espacio
            engine.remove_window(window)

    return tiling_handler


def main() -> None:
    setup_logging()

    wm = WindowManager()

    # Crear el motor de tiling
    engine = TilingEngine(auto_apply=True)

    # Sincronizar con las ventanas existentes despues del scan inicial
    # (el scan ocurre dentro de wm.start(), asi que conectamos via eventos)

    # Conectar eventos del WM al tiling engine
    tiling_handler = create_tiling_handler(engine)
    wm.on(WMEvent.WINDOW_ADDED, tiling_handler)
    wm.on(WMEvent.WINDOW_REMOVED, tiling_handler)
    wm.on(WMEvent.WINDOW_RESTORED, tiling_handler)
    wm.on(WMEvent.WINDOW_MINIMIZED, tiling_handler)

    # Suscribir logger global de eventos
    wm.on_all(on_event)

    # Show initial state
    print("\n" + wm.dump_state() + "\n")
    print("\n" + engine.dump_state() + "\n")
    print("=" * 60)
    print("  SauliethWM event loop running. Press Ctrl+C to stop.")
    print(f"  Layout: {engine.layout_name}")
    print(f"  Work area: {engine.work_area}")
    print("=" * 60 + "\n")

    # Enter the blocking event loop
    # (wm.start() does the initial scan and emits WINDOW_ADDED for each,
    #  which triggers the tiling handler to add them to the engine)
    wm.start()


if __name__ == "__main__":
    main()
