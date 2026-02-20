"""
SauliethWM - Entry point.

Run with:  python -m sauliethwm
"""

import logging
import sys

from sauliethwm.core.manager import WindowManager, WMEvent
from sauliethwm.core.window import Window
from sauliethwm.core import win32
from sauliethwm.core.keybinds import HotkeyManager
from sauliethwm.core.commands import CommandDispatcher, build_default_commands
from sauliethwm.tiling.workspace_manager import WorkspaceManager
from sauliethwm.config.hotkeys import register_all_hotkeys


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
    """Global event handler that logs everything."""
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


def create_workspace_handler(ws_manager: WorkspaceManager):
    """
    Crea un callback que conecta los eventos del WindowManager
    con el WorkspaceManager para gestionar ventanas en workspaces.

    El handler reacciona a:
        - WINDOW_ADDED:     Agrega la ventana al workspace activo y retilea.
        - WINDOW_REMOVED:   Elimina la ventana de su workspace y retilea.
        - WINDOW_RESTORED:  Re-agrega al workspace si no esta, o retilea.
        - WINDOW_MINIMIZED: Elimina temporalmente del workspace y retilea.
    """

    # Mapa hwnd -> workspace_id para recordar de donde vino
    # una ventana minimizada, y restaurarla al workspace correcto.
    _minimized_origins: dict[int, int] = {}

    def workspace_handler(
        event: WMEvent, window: Window | None, wm: WindowManager
    ) -> None:
        if window is None:
            return

        if event == WMEvent.WINDOW_ADDED:
            ws_manager.add_window(window)

        elif event == WMEvent.WINDOW_REMOVED:
            # Solo remover si la ventana esta en un workspace activo.
            # Si esta en un workspace inactivo, fue movida ahi
            # intencionalmente y no debe ser removida por eventos
            # tardios de hide que disparan _unmanage -> WINDOW_REMOVED.
            ws = ws_manager.find_window_workspace(window)
            if ws is not None and not ws.is_active:
                return
            ws_manager.remove_window(window)

        elif event == WMEvent.WINDOW_RESTORED:
            # La ventana vuelve de minimizada: intentar restaurar
            # al workspace original donde estaba antes de minimizar.
            ws = ws_manager.find_window_workspace(window)
            if ws is None:
                origin_ws_id = _minimized_origins.pop(window.hwnd, None)
                if origin_ws_id is not None:
                    target_ws = ws_manager.get_workspace(origin_ws_id)
                    if target_ws is not None:
                        target_ws.add_window(window)
                        if target_ws.is_active:
                            mi = ws_manager.get_monitor_for_workspace(target_ws.id)
                            if mi is not None:
                                ws_manager.retile(mi)
                        else:
                            # El workspace no esta activo: ocultar la ventana
                            ws_manager._suppress_events()
                            try:
                                if window.is_valid:
                                    win32.show_window(window.hwnd, win32.SW_HIDE)
                            finally:
                                ws_manager._resume_events()
                        return
                # Fallback: agregar al workspace activo
                ws_manager.add_window(window)
            else:
                # Retilear su workspace si esta activo
                mi = ws_manager.get_monitor_for_workspace(ws.id)
                if mi is not None:
                    ws_manager.retile(mi)

        elif event == WMEvent.WINDOW_MINIMIZED:
            # Guardar el workspace de origen antes de remover,
            # para poder restaurarla al workspace correcto.
            ws = ws_manager.find_window_workspace(window)
            if ws is not None:
                _minimized_origins[window.hwnd] = ws.id
            ws_manager.remove_window(window)

    return workspace_handler


def on_workspace_changed(monitor_index: int, old_ws_id: int, new_ws_id: int) -> None:
    """Callback que se ejecuta cuando cambia el workspace activo."""
    print(
        f"  WORKSPACE CHANGED: monitor {monitor_index} | "
        f"ws {old_ws_id} -> ws {new_ws_id}"
    )


def main() -> None:
    setup_logging()

    wm = WindowManager()

    # Crear el gestor de workspaces (reemplaza al TilingEngine directo)
    ws_manager = WorkspaceManager()

    # Enlazar WorkspaceManager con WindowManager para supresion de eventos
    ws_manager.set_window_manager(wm)

    # Registrar callback de cambio de workspace
    ws_manager.on_workspace_changed(on_workspace_changed)

    # Conectar eventos del WM al WorkspaceManager
    ws_handler = create_workspace_handler(ws_manager)
    wm.on(WMEvent.WINDOW_ADDED, ws_handler)
    wm.on(WMEvent.WINDOW_REMOVED, ws_handler)
    wm.on(WMEvent.WINDOW_RESTORED, ws_handler)
    wm.on(WMEvent.WINDOW_MINIMIZED, ws_handler)

    # Configurar hotkeys globales y dispatcher de comandos
    hk_manager = HotkeyManager()
    wm.set_hotkey_manager(hk_manager)

    # Registrar todos los comandos internos en el dispatcher (Phase 4)
    dispatcher = CommandDispatcher()
    build_default_commands(dispatcher, wm, ws_manager, hk_manager)

    # Vincular hotkeys a comandos del dispatcher
    hk_count = register_all_hotkeys(hk_manager, dispatcher)

    # Suscribir logger global de eventos
    wm.on_all(on_event)

    # Show initial state
    print("\n" + wm.dump_state() + "\n")
    print("=" * 60)
    print("  SauliethWM event loop running. Press Ctrl+C to stop.")
    print(f"  Monitors: {ws_manager.monitor_count}")
    print(f"  Workspaces: {ws_manager.workspace_count}")
    print(f"  Hotkeys: {hk_count}")
    print(f"  Commands: {dispatcher.count}")
    for mi in range(ws_manager.monitor_count):
        ws = ws_manager.get_active_workspace(mi)
        print(f"  Monitor {mi}: Workspace {ws.id} ({ws.layout_name})")
    print("")
    print("  Keybindings:")
    print("    Alt + 1..9            Switch workspace")
    print("    Alt + Shift + 1..9    Move window to workspace")
    print("    Alt + H/J/K/L         Focus left/down/up/right")
    print("    Alt + Shift + H/J/K/L Move window left/down/up/right")
    print("    Alt + Shift + C       Close focused window")
    print("    Alt + Shift + M       Swap with master")
    print("    Alt + Space           Next layout")
    print("    Alt + Shift + Space   Previous layout")
    print("    Alt + =/−             Grow/shrink master")
    print("    Alt + Shift + =/−     Increase/decrease gap")
    print("    Alt + R               Resize mode (arrows, Esc to exit)")
    print("    Alt + Return          Launch terminal")
    print("    Alt + E               Launch explorer")
    print("    Alt + Shift + R       Retile all")
    print("    Alt + Shift + Q       Quit SauliethWM")
    print("=" * 60 + "\n")

    # Enter the blocking event loop
    # (wm.start() does the initial scan and emits WINDOW_ADDED for each,
    #  which triggers the workspace handler to add them to the active ws)
    wm.start()

    # Restore all hidden windows from inactive workspaces before exiting.
    # Without this, windows on non-active workspaces remain permanently
    # hidden (SW_HIDE) after the WM exits, making them inaccessible.
    ws_manager.restore_all_windows()

    # Print final state
    print("\n" + ws_manager.dump_state())


if __name__ == "__main__":
    main()
