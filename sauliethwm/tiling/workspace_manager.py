"""
sauliethwm.tiling.workspace_manager - Gestor de workspaces virtuales.

El WorkspaceManager es el intermediario entre los eventos del event loop
y los workspaces individuales. Gestiona todos los workspaces del sistema,
sabe cual esta activo en cada monitor, y decide a que workspace asignar
cada nueva ventana.

Responsabilidades:
    - Crear y mantener los workspaces (por defecto 9).
    - Asignar cada monitor a un workspace activo.
    - Cambiar de workspace en un monitor (ocultar/mostrar ventanas).
    - Mover ventanas entre workspaces.
    - Mover ventanas entre monitores.
    - Emitir eventos cuando cambia el workspace activo.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Optional, TYPE_CHECKING

from sauliethwm.core.window import Window
from sauliethwm.core import win32
from sauliethwm.tiling.rect import Rect
from sauliethwm.tiling.monitor import Monitor, get_monitors
from sauliethwm.tiling.workspace import Workspace

if TYPE_CHECKING:
    from sauliethwm.core.manager import WindowManager

log = logging.getLogger(__name__)


# Tipo para callbacks de cambio de workspace
# callback(monitor_index, old_ws_id, new_ws_id)
WorkspaceChangedCallback = Callable[[int, int, int], None]


# Numero de workspaces por defecto
DEFAULT_WORKSPACE_COUNT = 9


class WorkspaceManager:
    """
    Gestiona todos los workspaces del sistema.

    Cada monitor tiene su propio workspace activo independiente.
    El manager es el punto de entrada para todas las operaciones
    de workspace: cambio, asignacion de ventanas, movimiento, etc.
    """

    def __init__(
        self,
        workspace_count: int = DEFAULT_WORKSPACE_COUNT,
        monitors: list[Monitor] | None = None,
    ) -> None:
        # Detectar monitores
        self._monitors = monitors if monitors is not None else get_monitors()
        if not self._monitors:
            raise RuntimeError("No se detectaron monitores")

        # Referencia al WindowManager (se asigna con set_window_manager)
        self._wm: WindowManager | None = None

        # Crear workspaces (IDs 1..N)
        self._workspaces: dict[int, Workspace] = {}
        for i in range(1, workspace_count + 1):
            self._workspaces[i] = Workspace(ws_id=i)

        # Mapa: indice_monitor -> workspace_id activo
        # Por defecto, monitor 0 -> ws 1, monitor 1 -> ws 2, etc.
        self._monitor_ws: dict[int, int] = {}
        for i in range(len(self._monitors)):
            ws_id = i + 1
            if ws_id > workspace_count:
                ws_id = 1
            self._monitor_ws[i] = ws_id
            self._workspaces[ws_id].is_active = True

        # Callbacks para cambio de workspace
        self._on_ws_changed: list[WorkspaceChangedCallback] = []

        log.info(
            "WorkspaceManager: %d workspaces, %d monitores",
            len(self._workspaces),
            len(self._monitors),
        )
        for mi, ws_id in self._monitor_ws.items():
            log.info(
                "  Monitor %d (%s) -> Workspace %d",
                mi,
                self._monitors[mi].name,
                ws_id,
            )

    # ------------------------------------------------------------------
    # Enlace con WindowManager (para suprimir eventos hide/show)
    # ------------------------------------------------------------------
    def set_window_manager(self, wm: WindowManager) -> None:
        """
        Registra la referencia al WindowManager para poder suprimir
        los eventos hide/show durante operaciones internas.
        """
        self._wm = wm

    def _suppress_events(self) -> None:
        """Activa la supresion de eventos hide/show en el WindowManager."""
        if self._wm is not None:
            self._wm.suppress_events()

    def _resume_events(self) -> None:
        """Desactiva la supresion de eventos hide/show."""
        if self._wm is not None:
            self._wm.resume_events()

    def _register_suppressed_hwnds(self, *workspaces: Workspace) -> None:
        """
        Registra los HWNDs de los workspaces dados para que eventos
        tardios de hide/show sean ignorados incluso despues de
        resume_events().
        """
        if self._wm is None:
            return
        hwnds: set[int] = set()
        for ws in workspaces:
            for w in ws.all_windows:
                if w.is_valid:
                    hwnds.add(w.hwnd)
        if hwnds:
            self._wm.add_suppressed_hwnds(hwnds)

    def _ensure_windows_tracked(self, ws: Workspace) -> None:
        """
        Asegura que todas las ventanas validas de un workspace estan
        registradas en el dict _windows del WindowManager.

        Esto cubre el caso donde una ventana fue removida de _windows
        (por un evento destroy/hide tardio) mientras el workspace
        estaba inactivo, pero el HWND sigue siendo valido.
        """
        if self._wm is None:
            return
        stale: list[Window] = []
        for w in ws.all_windows:
            if not w.is_valid:
                stale.append(w)
                continue
            if self._wm.get(w.hwnd) is None:
                # Ventana valida que no esta en _windows: re-registrar
                self._wm._windows[w.hwnd] = w
                log.debug("Re-tracked window %s for ws %d", w, ws.id)
        # Limpiar ventanas invalidas del workspace
        for w in stale:
            ws.remove_window(w)
            log.debug("Removed stale window %s from ws %d", w, ws.id)

    def _retile_ws(self, ws: Workspace, monitor_index: int) -> None:
        """
        Helper: retilea un workspace pasando work_rect y full_rect
        del monitor indicado.
        """
        mon = self._monitors[monitor_index]
        ws.retile(mon.work_rect, mon.full_rect)

    # ------------------------------------------------------------------
    # Propiedades
    # ------------------------------------------------------------------
    @property
    def monitors(self) -> list[Monitor]:
        return list(self._monitors)

    @property
    def monitor_count(self) -> int:
        return len(self._monitors)

    @property
    def workspace_count(self) -> int:
        return len(self._workspaces)

    @property
    def workspace_ids(self) -> list[int]:
        return sorted(self._workspaces.keys())

    def get_workspace(self, ws_id: int) -> Optional[Workspace]:
        """Obtiene un workspace por ID."""
        return self._workspaces.get(ws_id)

    def get_active_workspace(self, monitor_index: int = 0) -> Workspace:
        """Retorna el workspace activo en un monitor dado."""
        ws_id = self._monitor_ws.get(monitor_index, 1)
        return self._workspaces[ws_id]

    def get_active_ws_id(self, monitor_index: int = 0) -> int:
        """Retorna el ID del workspace activo en un monitor."""
        return self._monitor_ws.get(monitor_index, 1)

    def get_monitor_for_workspace(self, ws_id: int) -> Optional[int]:
        """Retorna el indice del monitor que muestra este workspace, o None."""
        for mi, active_ws in self._monitor_ws.items():
            if active_ws == ws_id:
                return mi
        return None

    # ------------------------------------------------------------------
    # Suscripcion a eventos de cambio de workspace (3.8)
    # ------------------------------------------------------------------
    def on_workspace_changed(self, callback: WorkspaceChangedCallback) -> None:
        """
        Registra un callback que se invoca cuando cambia el workspace
        activo en cualquier monitor.

        El callback recibe (monitor_index, old_ws_id, new_ws_id).
        """
        self._on_ws_changed.append(callback)

    def off_workspace_changed(self, callback: WorkspaceChangedCallback) -> None:
        """Desregistra un callback de cambio de workspace."""
        try:
            self._on_ws_changed.remove(callback)
        except ValueError:
            pass

    def _emit_workspace_changed(
        self, monitor_index: int, old_ws_id: int, new_ws_id: int
    ) -> None:
        """Emite el evento de cambio de workspace a todos los suscriptores."""
        for cb in self._on_ws_changed:
            try:
                cb(monitor_index, old_ws_id, new_ws_id)
            except Exception:
                log.exception("Error en callback on_workspace_changed")

    # ------------------------------------------------------------------
    # Cambiar workspace en un monitor (3.3)
    # ------------------------------------------------------------------
    def switch_workspace(
        self, target_ws_id: int, monitor_index: int = 0
    ) -> bool:
        """
        Cambia al workspace target_ws_id en el monitor dado.

        Proceso:
            1. Ocultar todas las ventanas del workspace actual (SW_HIDE).
            2. Mostrar todas las ventanas del workspace destino (SW_SHOW).
            3. Retilear el workspace destino.
            4. Emitir evento on_workspace_changed.

        Args:
            target_ws_id:  ID del workspace destino.
            monitor_index: Indice del monitor donde cambiar.

        Returns:
            True si se cambio, False si ya estaba activo o es invalido.
        """
        if target_ws_id not in self._workspaces:
            log.warning("switch_workspace: ws_id %d no existe", target_ws_id)
            return False

        if monitor_index not in self._monitor_ws:
            log.warning("switch_workspace: monitor %d no existe", monitor_index)
            return False

        current_ws_id = self._monitor_ws[monitor_index]

        # Si ya estamos en ese workspace, no hacer nada
        if current_ws_id == target_ws_id:
            log.debug("switch_workspace: ya en ws %d", target_ws_id)
            return False

        # Si el workspace destino esta activo en otro monitor, intercambiar
        target_monitor = self.get_monitor_for_workspace(target_ws_id)
        if target_monitor is not None and target_monitor != monitor_index:
            # Intercambiar workspaces entre monitores
            return self._swap_workspaces_between_monitors(
                monitor_index, target_monitor
            )

        current_ws = self._workspaces[current_ws_id]
        target_ws = self._workspaces[target_ws_id]

        # 1. Suprimir eventos hide/show para evitar feedback loop
        self._suppress_events()
        try:
            # Registrar HWNDs para supresion tardia de eventos asincrono
            self._register_suppressed_hwnds(current_ws, target_ws)

            # 2. Ocultar ventanas del workspace actual
            current_ws.hide_all_windows()
            current_ws.is_active = False

            # 3. Mostrar ventanas del workspace destino
            target_ws.show_all_windows()
            target_ws.is_active = True

            # 4. Re-registrar ventanas del workspace destino en el
            #    WindowManager por si alguna fue removida de _windows
            #    mientras el workspace estaba inactivo.
            self._ensure_windows_tracked(target_ws)
        finally:
            self._resume_events()

        # 4. Actualizar mapa
        self._monitor_ws[monitor_index] = target_ws_id

        # 5. Retilear el workspace destino
        self._retile_ws(target_ws, monitor_index)

        log.info(
            "SWITCH ws %d -> ws %d (monitor %d)",
            current_ws_id,
            target_ws_id,
            monitor_index,
        )

        # 5. Emitir evento
        self._emit_workspace_changed(monitor_index, current_ws_id, target_ws_id)

        return True

    def _swap_workspaces_between_monitors(
        self, monitor_a: int, monitor_b: int
    ) -> bool:
        """
        Intercambia los workspaces activos entre dos monitores.

        Oculta y muestra las ventanas correspondientes, retilea ambos.
        """
        ws_a_id = self._monitor_ws[monitor_a]
        ws_b_id = self._monitor_ws[monitor_b]

        ws_a = self._workspaces[ws_a_id]
        ws_b = self._workspaces[ws_b_id]

        # Suprimir eventos hide/show para evitar feedback loop
        self._suppress_events()
        try:
            # Registrar HWNDs para supresion tardia de eventos asincrono
            self._register_suppressed_hwnds(ws_a, ws_b)

            # Ocultar ambos
            ws_a.hide_all_windows()
            ws_b.hide_all_windows()

            # Intercambiar
            self._monitor_ws[monitor_a] = ws_b_id
            self._monitor_ws[monitor_b] = ws_a_id

            # Mostrar en sus nuevos monitores
            ws_a.show_all_windows()
            ws_b.show_all_windows()

            # Re-registrar ventanas en el WindowManager
            self._ensure_windows_tracked(ws_a)
            self._ensure_windows_tracked(ws_b)
        finally:
            self._resume_events()

        # Retilear ambos con las areas de sus nuevos monitores
        self._retile_ws(ws_b, monitor_a)
        self._retile_ws(ws_a, monitor_b)

        log.info(
            "SWAP ws %d (mon %d) <-> ws %d (mon %d)",
            ws_a_id,
            monitor_a,
            ws_b_id,
            monitor_b,
        )

        self._emit_workspace_changed(monitor_a, ws_a_id, ws_b_id)
        self._emit_workspace_changed(monitor_b, ws_b_id, ws_a_id)

        return True

    # ------------------------------------------------------------------
    # Asignacion de ventanas
    # ------------------------------------------------------------------
    def add_window(
        self,
        window: Window,
        monitor_index: int = 0,
        floating: bool = False,
    ) -> bool:
        """
        Agrega una ventana al workspace activo del monitor indicado.

        Ventanas en fullscreen exclusivo (juegos en Direct3D/Vulkan que
        toman el display completo) son ignoradas y no se agregan.

        Ventanas borderless windowed (sin bordes, windowed) se gestionan
        normalmente: se pueden mover entre workspaces y ocultar/mostrar.

        Args:
            window:        Ventana a agregar.
            monitor_index: Monitor donde agregar (default: primario).
            floating:      Si True, agregar como flotante.

        Returns:
            True si se agrego, False si ya estaba, es fullscreen exclusivo,
            o no se pudo agregar.
        """
        # Verificar que no este ya en algun workspace
        for ws in self._workspaces.values():
            if ws.contains(window):
                return False

        # Detectar ventanas en fullscreen exclusivo real (juegos en
        # Direct3D/Vulkan exclusive fullscreen). Estas ventanas se
        # ignoran completamente: no se agregan a ningun workspace.
        #
        # Las ventanas borderless windowed (sin bordes, pueden cubrir
        # o no el monitor) se gestionan normalmente: se pueden mover
        # entre workspaces, ocultar y mostrar.
        mon = self._monitors[monitor_index]
        fr = mon.full_rect
        if window.is_native_fullscreen(fr.x, fr.y, fr.w, fr.h):
            log.info(
                "Ignoring exclusive fullscreen window (not managed): %s",
                window,
            )
            return False

        ws = self.get_active_workspace(monitor_index)
        if ws.add_window(window, floating=floating):
            if ws.is_active and not floating:
                self._retile_ws(ws, monitor_index)
            return True
        return False

    def remove_window(self, window: Window) -> bool:
        """
        Remueve una ventana de cualquier workspace donde este.

        Retilea el workspace si estaba activo.

        Returns:
            True si se removio.
        """
        for ws in self._workspaces.values():
            if ws.remove_window(window):
                if ws.is_active:
                    mi = self.get_monitor_for_workspace(ws.id)
                    if mi is not None:
                        self._retile_ws(ws, mi)
                return True
        return False

    def find_window_workspace(self, window: Window) -> Optional[Workspace]:
        """Encuentra el workspace que contiene una ventana."""
        for ws in self._workspaces.values():
            if ws.contains(window):
                return ws
        return None

    # ------------------------------------------------------------------
    # Mover ventana entre workspaces (3.4)
    # ------------------------------------------------------------------
    def move_window_to_workspace(
        self, window: Window, target_ws_id: int
    ) -> bool:
        """
        Mueve una ventana de su workspace actual al workspace destino.

        Proceso:
            1. Registrar HWND en _suppressed_hwnds para ignorar eventos
               tardios de hide/show/foreground sobre esta ventana.
            2. Remover la ventana de su workspace actual.
            3. Retilear el workspace origen.
            4. Agregar al workspace destino.
            5. Si el destino esta activo, retilear. Si no, ocultar.
            6. Re-registrar la ventana en WindowManager._windows para
               que no se pierda al cambiar al workspace destino.

        Args:
            window:       Ventana a mover.
            target_ws_id: ID del workspace destino.

        Returns:
            True si se movio exitosamente.
        """
        if target_ws_id not in self._workspaces:
            log.warning("move_window_to_workspace: ws %d no existe", target_ws_id)
            return False

        target_ws = self._workspaces[target_ws_id]

        # Ya esta en el destino?
        if target_ws.contains(window):
            return False

        # Encontrar workspace origen
        source_ws = self.find_window_workspace(window)
        if source_ws is None:
            log.warning("move_window_to_workspace: ventana no encontrada")
            return False

        # 1. Registrar el HWND para supresion de eventos tardios.
        #    Esto evita que _handle_hide/_handle_foreground procesen
        #    eventos asincrono para esta ventana despues de resume_events(),
        #    lo cual causaria _unmanage() -> WINDOW_REMOVED -> remove_window()
        #    eliminando la ventana del workspace destino.
        if self._wm is not None:
            self._wm.add_suppressed_hwnds({window.hwnd})

        # 2. Remover del origen
        source_ws.remove_window(window)

        # 3. Retilear origen si esta activo
        if source_ws.is_active:
            mi = self.get_monitor_for_workspace(source_ws.id)
            if mi is not None:
                self._retile_ws(source_ws, mi)

        # 4. Agregar al destino
        target_ws.add_window(window)

        # 5. Si el destino esta activo, retilear; si no, ocultar ventana
        if target_ws.is_active:
            mi = self.get_monitor_for_workspace(target_ws.id)
            if mi is not None:
                self._retile_ws(target_ws, mi)
        else:
            # Ocultar inmediatamente usando Z-order (off-screen + HWND_BOTTOM)
            # en vez de SW_HIDE para evitar eventos de hide.
            self._suppress_events()
            try:
                if window.is_valid:
                    if window.is_fullscreen:
                        window.suspend_fullscreen()
                    else:
                        # Guardar posicion y mover off-screen con z-order bajo
                        rect = win32.get_window_rect(window.hwnd)
                        target_ws._saved_positions[window.hwnd] = (
                            rect[0], rect[1],
                            rect[2] - rect[0], rect[3] - rect[1],
                        )
                        win32.set_window_pos(
                            window.hwnd,
                            -32000, -32000, 0, 0,
                            flags=win32.SWP_NOSIZE | win32.SWP_NOACTIVATE,
                            insert_after=win32.HWND_BOTTOM,
                        )
            finally:
                self._resume_events()

            # 6. Re-registrar la ventana en _windows del WindowManager.
            #    Necesitamos asegurar que la ventana siga en _windows para
            #    que _ensure_windows_tracked la encuentre al cambiar
            #    al workspace destino.
            if self._wm is not None and window.is_valid:
                self._wm._windows[window.hwnd] = window

        log.info(
            "MOVE ventana %s: ws %d -> ws %d",
            window,
            source_ws.id,
            target_ws_id,
        )

        return True

    # ------------------------------------------------------------------
    # Mover ventana al monitor siguiente (3.7)
    # ------------------------------------------------------------------
    def move_window_to_next_monitor(self, window: Window) -> bool:
        """
        Mueve la ventana enfocada al workspace activo del monitor
        siguiente (en orden circular).

        Proceso:
            1. Encontrar en que workspace/monitor esta la ventana.
            2. Removerla del workspace actual, retilear.
            3. Agregarla al workspace activo del siguiente monitor.
            4. Retilear el workspace destino.

        Returns:
            True si se movio exitosamente.
        """
        if len(self._monitors) < 2:
            log.debug("move_window_to_next_monitor: solo hay 1 monitor")
            return False

        # Encontrar workspace y monitor de la ventana
        source_ws = self.find_window_workspace(window)
        if source_ws is None:
            return False

        source_mi = self.get_monitor_for_workspace(source_ws.id)
        if source_mi is None:
            return False

        # Siguiente monitor (circular)
        next_mi = (source_mi + 1) % len(self._monitors)
        target_ws = self.get_active_workspace(next_mi)

        # Remover del origen
        source_ws.remove_window(window)
        self._retile_ws(source_ws, source_mi)

        # Agregar al destino
        target_ws.add_window(window)
        self._retile_ws(target_ws, next_mi)

        log.info(
            "MOVE TO MONITOR ventana %s: mon %d (ws %d) -> mon %d (ws %d)",
            window,
            source_mi,
            source_ws.id,
            next_mi,
            target_ws.id,
        )

        return True

    # ------------------------------------------------------------------
    # Retilear workspace activo de un monitor
    # ------------------------------------------------------------------
    def retile(self, monitor_index: int = 0) -> None:
        """Retilea el workspace activo en el monitor dado."""
        ws = self.get_active_workspace(monitor_index)
        if ws.is_active:
            self._retile_ws(ws, monitor_index)

    def retile_all(self) -> None:
        """Retilea todos los workspaces activos."""
        for mi, ws_id in self._monitor_ws.items():
            ws = self._workspaces[ws_id]
            self._retile_ws(ws, mi)

    # ------------------------------------------------------------------
    # Refresh de monitores
    # ------------------------------------------------------------------
    def refresh_monitors(self) -> None:
        """Redetecta monitores y reajusta la asignacion."""
        new_monitors = get_monitors()
        if not new_monitors:
            log.warning("refresh_monitors: no se detectaron monitores")
            return

        self._monitors = new_monitors

        # Ajustar: si hay menos monitores, comprimir
        self._suppress_events()
        try:
            for mi in list(self._monitor_ws.keys()):
                if mi >= len(self._monitors):
                    # Mover ventanas de este monitor al primario
                    ws_id = self._monitor_ws.pop(mi)
                    ws = self._workspaces[ws_id]
                    ws.is_active = False
                    ws.hide_all_windows()
        finally:
            self._resume_events()

        # Retilear los activos
        self.retile_all()

    # ------------------------------------------------------------------
    # Restaurar todas las ventanas al cerrar el WM
    # ------------------------------------------------------------------
    def restore_all_windows(self) -> None:
        """
        Muestra todas las ventanas ocultas de workspaces inactivos y
        restaura las ventanas que fueron puestas en fullscreen por el WM.

        Debe llamarse al cerrar el WM para que las ventanas que fueron
        movidas off-screen al cambiar de workspace vuelvan a ser
        visibles. Sin esto, las ventanas en workspaces inactivos quedan
        permanentemente fuera de pantalla al salir del WM.

        Tambien restaura los estilos originales de ventanas en fullscreen
        para que no queden sin bordes despues de cerrar el WM.
        """
        self._suppress_events()
        try:
            for ws_id, ws in self._workspaces.items():
                # Restaurar ventanas fullscreen a su estado original
                for window in ws.all_windows:
                    if window.is_valid and window.is_fullscreen:
                        window.exit_fullscreen()
                        log.debug(
                            "Restored fullscreen window %s from ws %d",
                            window, ws_id,
                        )

                if ws.is_active:
                    continue

                for window in ws.all_windows:
                    if not window.is_valid:
                        continue

                    # Restaurar desde posiciones guardadas (Z-order)
                    saved = ws._saved_positions.pop(window.hwnd, None)
                    if saved is not None:
                        sx, sy, sw, sh = saved
                        win32.set_window_pos(
                            window.hwnd,
                            sx, sy, sw, sh,
                            flags=win32.SWP_NOACTIVATE,
                            insert_after=win32.HWND_TOP,
                        )
                    else:
                        # Fallback: restaurar con SW_RESTORE
                        win32.show_window(window.hwnd, win32.SW_RESTORE)

                    log.debug(
                        "Restored hidden window %s from ws %d",
                        window, ws_id,
                    )
                log.info(
                    "Restored %d windows from inactive ws %d",
                    ws.window_count, ws_id,
                )
        finally:
            self._resume_events()

        log.info("All hidden windows restored for WM shutdown")

    # ------------------------------------------------------------------
    # Resumen de estado para cierre
    # ------------------------------------------------------------------
    def get_status_summary(self) -> str:
        """
        Genera un resumen legible del estado de todos los workspaces,
        indicando cual esta activo en cada monitor y listando las
        ventanas de cada workspace que tenga ventanas.

        Util para mostrar al cerrar el WM.
        """
        lines = [
            "=" * 60,
            "  SauliethWM - Estado al cerrar",
            "=" * 60,
        ]

        # Mostrar workspace activo por monitor
        for mi, ws_id in sorted(self._monitor_ws.items()):
            mon = self._monitors[mi]
            lines.append(
                f"  Monitor {mi} ({mon.name}): Workspace {ws_id} [activo]"
            )

        lines.append("")

        # Listar cada workspace que tenga ventanas
        any_windows = False
        for ws_id in sorted(self._workspaces.keys()):
            ws = self._workspaces[ws_id]
            if ws.window_count == 0:
                continue
            any_windows = True

            active_mark = " <-- activo" if ws.is_active else ""
            lines.append(
                f"  Workspace {ws_id} ({ws.window_count} ventanas){active_mark}"
            )
            for i, w in enumerate(ws.tiled_windows):
                role = "master" if i == 0 else f"stack-{i}"
                title = "<invalid>" if not w.is_valid else w.title
                lines.append(f"    [{role}] {title}")
            for w in ws.floating_windows:
                title = "<invalid>" if not w.is_valid else w.title
                lines.append(f"    [float] {title}")

        if not any_windows:
            lines.append("  (No hay ventanas gestionadas)")

        lines.append("=" * 60)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------
    def dump_state(self) -> str:
        lines = [
            f"=== WorkspaceManager: {len(self._workspaces)} workspaces, "
            f"{len(self._monitors)} monitores ===",
            "",
        ]
        for mi, ws_id in sorted(self._monitor_ws.items()):
            mon = self._monitors[mi]
            lines.append(
                f"  Monitor {mi} ({mon.name}) -> Workspace {ws_id}"
            )

        lines.append("")

        for ws_id in sorted(self._workspaces.keys()):
            ws = self._workspaces[ws_id]
            if ws.window_count > 0 or ws.is_active:
                lines.append(ws.dump_state())
                lines.append("")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"WorkspaceManager("
            f"workspaces={len(self._workspaces)}, "
            f"monitors={len(self._monitors)})"
        )
