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
    def retile(self, work_area: Rect) -> None:
        """
        Recalcula y aplica el layout a las ventanas tileadas.

        El workspace no conoce el monitor; recibe el area de trabajo
        como parametro del exterior.

        Args:
            work_area: Area disponible para tilear (Rect del monitor).
        """
        count = len(self._tiled_windows)
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

        for window, rect in zip(self._tiled_windows, rects):
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
            "WS %d retile: %s | %d ventanas | area=%s",
            self._id,
            layout.name,
            count,
            work_area,
        )

    # ------------------------------------------------------------------
    # Ocultar / Mostrar todas las ventanas
    # ------------------------------------------------------------------
    def hide_all_windows(self) -> None:
        """Oculta todas las ventanas del workspace con SW_HIDE."""
        for window in self.all_windows:
            if window.is_valid:
                win32.show_window(window.hwnd, win32.SW_HIDE)
        log.debug("WS %d: ocultadas %d ventanas", self._id, self.window_count)

    def show_all_windows(self) -> None:
        """Muestra todas las ventanas del workspace con SW_SHOWNOACTIVATE."""
        for window in self.all_windows:
            if window.is_valid:
                win32.show_window(window.hwnd, win32.SW_SHOWNOACTIVATE)
        log.debug("WS %d: mostradas %d ventanas", self._id, self.window_count)

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
            lines.append(f"    [{role}] {w}")
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
