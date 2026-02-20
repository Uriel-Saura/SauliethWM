"""
sauliethwm.tiling.workspace - Workspace virtual.

Cada workspace tiene un ID, un nombre, su layout activo, y dos listas:
tiled_windows y floating_windows. Tambien guarda si esta activo o inactivo.

El workspace no sabe nada de monitores: el monitor le pasa su area de
trabajo cuando le pide que se retilee.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sauliethwm.core.window import Window
from sauliethwm.core import win32
from sauliethwm.tiling.rect import Rect
from sauliethwm.tiling.layouts import (
    Layout,
    LayoutType,
    TallLayout,
    WideLayout,
    MonocleLayout,
    ThreeColumnLayout,
)

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


# Layouts por defecto para cada workspace nuevo
def _default_layouts() -> list[Layout]:
    """Crea una copia fresca de los layouts por defecto."""
    return [
        TallLayout(),
        WideLayout(),
        MonocleLayout(),
        ThreeColumnLayout(),
    ]


class Workspace:
    """
    Representa un workspace virtual.

    Cada workspace mantiene su propia lista de ventanas tileadas y
    flotantes, su propio layout activo con su estado (ratio, gap), y
    sabe si esta activo (visible en algun monitor) o inactivo.

    El workspace NO conoce el monitor: cuando necesita retilear, recibe
    el area de trabajo como parametro.
    """

    def __init__(
        self,
        ws_id: int,
        name: str | None = None,
        layouts: list[Layout] | None = None,
    ) -> None:
        self._id = ws_id
        self._name = name or f"Workspace {ws_id}"
        self._layouts = layouts if layouts is not None else _default_layouts()
        self._layout_index = 0

        self._tiled_windows: list[Window] = []
        self._floating_windows: list[Window] = []

        # Posiciones guardadas para restaurar al volver al workspace.
        # Mapa hwnd -> (x, y, w, h).  Se llena en hide_all_windows()
        # y se consume en show_all_windows().
        self._saved_positions: dict[int, tuple[int, int, int, int]] = {}

        # Si el workspace esta visible en algun monitor
        self._active = False

    # ------------------------------------------------------------------
    # Propiedades basicas
    # ------------------------------------------------------------------
    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def is_active(self) -> bool:
        return self._active

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self._active = value

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    @property
    def current_layout(self) -> Layout:
        """Layout activo de este workspace."""
        return self._layouts[self._layout_index]

    @property
    def layout_name(self) -> str:
        return self.current_layout.name

    @property
    def layout_index(self) -> int:
        return self._layout_index

    def next_layout(self) -> Layout:
        """Cambia al siguiente layout (circular)."""
        self._layout_index = (self._layout_index + 1) % len(self._layouts)
        log.info("WS %d layout -> %s", self._id, self.layout_name)
        return self.current_layout

    def prev_layout(self) -> Layout:
        """Cambia al layout anterior (circular)."""
        self._layout_index = (self._layout_index - 1) % len(self._layouts)
        log.info("WS %d layout -> %s", self._id, self.layout_name)
        return self.current_layout

    def set_layout(self, layout_type: LayoutType) -> bool:
        """Cambia a un layout especifico por tipo."""
        for i, layout in enumerate(self._layouts):
            if layout.layout_type == layout_type:
                self._layout_index = i
                log.info("WS %d layout = %s", self._id, layout.name)
                return True
        return False

    # ------------------------------------------------------------------
    # Gestion de ventanas tileadas
    # ------------------------------------------------------------------
    @property
    def tiled_windows(self) -> list[Window]:
        """Lista de ventanas tileadas (copia)."""
        return list(self._tiled_windows)

    @property
    def tiled_windows_mut(self) -> list[Window]:
        """
        Referencia directa (mutable) a la lista interna de ventanas tileadas.

        Solo usar para operaciones que necesitan modificar el orden
        in-place (como swap_direction). Retornar siempre retile despues.
        """
        return self._tiled_windows

    @property
    def floating_windows(self) -> list[Window]:
        """Lista de ventanas flotantes (copia)."""
        return list(self._floating_windows)

    @property
    def all_windows(self) -> list[Window]:
        """Todas las ventanas (tiled + floating)."""
        return self._tiled_windows + self._floating_windows

    @property
    def window_count(self) -> int:
        return len(self._tiled_windows) + len(self._floating_windows)

    @property
    def tiled_count(self) -> int:
        return len(self._tiled_windows)

    def contains(self, window: Window) -> bool:
        """True si la ventana esta en este workspace (tiled o floating)."""
        return window in self._tiled_windows or window in self._floating_windows

    def add_window(self, window: Window, floating: bool = False) -> bool:
        """
        Agrega una ventana al workspace.

        Args:
            window:   Ventana a agregar.
            floating: Si True, agregar como flotante; si False, como tileada.

        Returns:
            True si se agrego, False si ya estaba.
        """
        if self.contains(window):
            return False

        if floating:
            self._floating_windows.append(window)
            log.info("WS %d +FLOAT %s", self._id, window)
        else:
            self._tiled_windows.append(window)
            log.info("WS %d +TILE %s", self._id, window)

        return True

    def remove_window(self, window: Window) -> bool:
        """
        Remueve una ventana del workspace (tiled o floating).

        Returns:
            True si se removio, False si no estaba.
        """
        try:
            self._tiled_windows.remove(window)
            log.info("WS %d -TILE %s", self._id, window)
            return True
        except ValueError:
            pass

        try:
            self._floating_windows.remove(window)
            log.info("WS %d -FLOAT %s", self._id, window)
            return True
        except ValueError:
            pass

        return False

    # ------------------------------------------------------------------
    # Manipulacion del stack de ventanas
    # ------------------------------------------------------------------
    def swap_master(self) -> None:
        """Intercambia la segunda ventana tileada con el master."""
        if len(self._tiled_windows) < 2:
            return
        self._tiled_windows[0], self._tiled_windows[1] = (
            self._tiled_windows[1],
            self._tiled_windows[0],
        )

    def swap_with_master(self, window: Window) -> None:
        """Promueve una ventana especifica a master."""
        if window not in self._tiled_windows:
            return
        idx = self._tiled_windows.index(window)
        if idx == 0 or len(self._tiled_windows) < 2:
            return
        self._tiled_windows[0], self._tiled_windows[idx] = (
            self._tiled_windows[idx],
            self._tiled_windows[0],
        )

    def rotate_next(self) -> None:
        """Rota ventanas tileadas hacia adelante."""
        if len(self._tiled_windows) < 2:
            return
        last = self._tiled_windows.pop()
        self._tiled_windows.insert(0, last)

    def rotate_prev(self) -> None:
        """Rota ventanas tileadas hacia atras."""
        if len(self._tiled_windows) < 2:
            return
        first = self._tiled_windows.pop(0)
        self._tiled_windows.append(first)

    # ------------------------------------------------------------------
    # Retile: calcula y aplica posiciones
    # ------------------------------------------------------------------
    def retile(self, work_area: Rect, monitor_full_rect: Rect | None = None) -> None:
        """
        Recalcula y aplica el layout a las ventanas tileadas.

        Ventanas en modo fullscreen son excluidas del layout y se
        reposicionan para cubrir el monitor completo. Las demas ventanas
        participan normalmente en el layout.

        El workspace NO conoce el monitor: recibe el area de trabajo
        como parametro del exterior.

        Args:
            work_area:         Area disponible para tilear (Rect del monitor).
            monitor_full_rect: Area total del monitor (para fullscreen).
                               Si None, se usa work_area como fallback.
        """
        if not self._tiled_windows:
            return

        full = monitor_full_rect or work_area

        # Separar ventanas fullscreen de las tileables
        fullscreen_wins: list[Window] = []
        tileable_wins: list[Window] = []

        for w in self._tiled_windows:
            if w.is_fullscreen:
                fullscreen_wins.append(w)
            else:
                tileable_wins.append(w)

        # Reposicionar ventanas fullscreen al monitor completo
        for window in fullscreen_wins:
            try:
                if not window.is_valid:
                    continue
                window.reapply_fullscreen(full.x, full.y, full.w, full.h)
            except Exception:
                log.exception(
                    "WS %d: error reapplying fullscreen %s", self._id, window
                )

        # Layout normal para las ventanas tileables
        count = len(tileable_wins)
        if count == 0:
            return

        layout = self.current_layout
        rects = layout.arrange(count, work_area)

        if len(rects) != count:
            log.error(
                "WS %d: layout %s retorno %d rects para %d ventanas",
                self._id,
                layout.name,
                len(rects),
                count,
            )
            return

        for window, rect in zip(tileable_wins, rects):
            try:
                if not window.is_valid:
                    log.warning("WS %d: ventana invalida %s", self._id, window)
                    continue

                if window.is_minimized:
                    window.restore()
                elif window.is_maximized:
                    window.restore()

                window.move_resize(rect.x, rect.y, rect.w, rect.h)
            except Exception:
                log.exception(
                    "WS %d: error al tillear %s", self._id, window
                )

        log.debug(
            "WS %d retile: %s | %d tiled + %d fullscreen | area=%s",
            self._id,
            layout.name,
            count,
            len(fullscreen_wins),
            work_area,
        )

    # ------------------------------------------------------------------
    # Ocultar / Mostrar todas las ventanas (Z-order)
    # ------------------------------------------------------------------
    # Posicion off-screen para ventanas ocultas
    _OFFSCREEN_X = -32000
    _OFFSCREEN_Y = -32000

    def hide_all_windows(self) -> None:
        """
        Oculta todas las ventanas del workspace usando Z-order.

        En vez de usar SW_HIDE (que causa problemas con ventanas borderless
        y juegos), este metodo:
          1. Guarda la posicion actual de cada ventana.
          2. Mueve la ventana fuera de la pantalla (off-screen).
          3. Envia la ventana al fondo del Z-order (HWND_BOTTOM).

        Las ventanas siguen "visibles" para el OS (no se disparan eventos
        EVENT_OBJECT_HIDE), pero al estar off-screen y en el fondo del
        Z-order, el usuario no las ve.

        Las posiciones guardadas se usan en show_all_windows() para
        restaurar las ventanas a sus posiciones originales.
        """
        for window in self.all_windows:
            if not window.is_valid:
                continue

            if window.is_fullscreen:
                # Ventanas fullscreen se manejan con suspend_fullscreen
                window.suspend_fullscreen()
                continue

            # Guardar posicion actual en el dict _saved_positions
            rect = window.rect
            self._saved_positions[window.hwnd] = (
                rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
            )

            # Mover off-screen y enviar al fondo del Z-order
            win32.set_window_pos(
                window.hwnd,
                self._OFFSCREEN_X, self._OFFSCREEN_Y, 0, 0,
                flags=win32.SWP_NOSIZE | win32.SWP_NOACTIVATE,
                insert_after=win32.HWND_BOTTOM,
            )

        log.debug("WS %d: ocultadas %d ventanas (z-order)", self._id, self.window_count)

    def show_all_windows(self) -> None:
        """
        Muestra todas las ventanas del workspace.

        Restaura las ventanas desde off-screen a sus posiciones guardadas
        y las trae al frente del Z-order (HWND_TOP).

        Las ventanas fullscreen se restauran via reapply_fullscreen()
        durante retile().  Las ventanas normales se restauran a su
        posicion guardada; el retile posterior las reposiciona
        correctamente de todas formas.
        """
        for window in self.all_windows:
            if not window.is_valid:
                continue

            if window.is_fullscreen:
                # Las fullscreen se restauran durante retile via
                # reapply_fullscreen(); aqui solo aseguramos que sean
                # visibles con SW_RESTORE por si suspend_fullscreen
                # las dejo en un estado raro.
                win32.show_window(window.hwnd, win32.SW_RESTORE)
                continue

            # Restaurar posicion guardada y traer al frente
            saved = self._saved_positions.pop(window.hwnd, None)
            if saved is not None:
                sx, sy, sw, sh = saved
                win32.set_window_pos(
                    window.hwnd,
                    sx, sy, sw, sh,
                    flags=win32.SWP_NOACTIVATE,
                    insert_after=win32.HWND_TOP,
                )
            else:
                # No hay posicion guardada: restaurar si estaba minimizada
                if window.is_minimized:
                    win32.show_window(window.hwnd, win32.SW_RESTORE)
                # Traer al frente del Z-order
                win32.set_window_pos(
                    window.hwnd,
                    0, 0, 0, 0,
                    flags=(
                        win32.SWP_NOMOVE | win32.SWP_NOSIZE
                        | win32.SWP_NOACTIVATE
                    ),
                    insert_after=win32.HWND_TOP,
                )

        log.debug("WS %d: mostradas %d ventanas (z-order)", self._id, self.window_count)

    # ------------------------------------------------------------------
    # Ajustes del layout activo
    # ------------------------------------------------------------------
    def grow_master(self) -> None:
        self.current_layout.grow_master()

    def shrink_master(self) -> None:
        self.current_layout.shrink_master()

    def increase_gap(self) -> None:
        self.current_layout.increase_gap()

    def decrease_gap(self) -> None:
        self.current_layout.decrease_gap()

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------
    def dump_state(self) -> str:
        lines = [
            f"--- Workspace {self._id}: {self._name} ---",
            f"    Active: {self._active}",
            f"    Layout: {self.layout_name} ({self._layout_index + 1}/{len(self._layouts)})",
            f"    Master ratio: {self.current_layout.master_ratio:.0%}",
            f"    Gap: {self.current_layout.gap}px",
            f"    Tiled: {len(self._tiled_windows)}",
            f"    Floating: {len(self._floating_windows)}",
        ]
        for i, w in enumerate(self._tiled_windows):
            role = "master" if i == 0 else f"stack-{i}"
            fs = " [FULLSCREEN]" if w.is_fullscreen else ""
            lines.append(f"    [{role}] {w}{fs}")
        for w in self._floating_windows:
            lines.append(f"    [float] {w}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"Workspace(id={self._id}, name={self._name!r}, "
            f"layout={self.layout_name}, "
            f"tiled={len(self._tiled_windows)}, "
            f"floating={len(self._floating_windows)}, "
            f"active={self._active})"
        )
