"""
sauliethwm.tiling.engine - Motor principal de tiling.

El TilingEngine es el corazon del sistema de organizacion automatica.
Coordina la lista de ventanas gestionadas, el layout activo y el area
del monitor para calcular y aplicar las posiciones de todas las ventanas.

Responsabilidades:
    - Mantener una lista ordenada de ventanas tileadas.
    - Insertar/remover ventanas y reorganizar automaticamente.
    - Aplicar el layout activo calculando coordenadas con Rect.
    - Mover fisicamente las ventanas via Window.move_resize().
    - Permitir cambio de layout en caliente.
    - Rotar ventanas (swap master, rotate stack).
"""

from __future__ import annotations

import logging

from sauliethwm.core.window import Window
from sauliethwm.tiling.rect import Rect
from sauliethwm.tiling.monitor import get_work_area, Monitor, get_monitors
from sauliethwm.tiling.layouts import (
    Layout,
    LayoutType,
    TallLayout,
    WideLayout,
    MonocleLayout,
    ThreeColumnLayout,
)

log = logging.getLogger(__name__)


# ============================================================================
# Layouts disponibles por defecto
# ============================================================================
DEFAULT_LAYOUTS: list[Layout] = [
    TallLayout(),
    WideLayout(),
    MonocleLayout(),
    ThreeColumnLayout(),
]


# ============================================================================
# TilingEngine
# ============================================================================
class TilingEngine:
    """
    Motor de tiling que organiza ventanas automaticamente.

    Mantiene una lista ordenada de ventanas y un layout activo.
    Cada vez que cambia la lista de ventanas (add/remove) o el layout,
    recalcula las posiciones y mueve fisicamente las ventanas.

    Uso tipico:
        engine = TilingEngine()
        engine.add_window(window)      # Inserta y reorganiza
        engine.remove_window(window)   # Elimina y reorganiza
        engine.next_layout()           # Cambia al siguiente layout
    """

    def __init__(
        self,
        layouts: list[Layout] | None = None,
        monitor: Monitor | None = None,
        auto_apply: bool = True,
    ) -> None:
        """
        Inicializa el motor de tiling.

        Args:
            layouts:    Lista de layouts disponibles. Si es None, usa los default.
            monitor:    Monitor a usar. Si es None, detecta el primario.
            auto_apply: Si True, aplica el layout cada vez que cambia la lista.
        """
        self._layouts = layouts if layouts is not None else list(DEFAULT_LAYOUTS)
        self._layout_index = 0
        self._windows: list[Window] = []
        self._auto_apply = auto_apply

        # Detectar monitor
        if monitor is not None:
            self._monitor = monitor
        else:
            monitors = get_monitors()
            self._monitor = monitors[0] if monitors else None

        log.info(
            "TilingEngine iniciado | layout=%s | monitor=%s | area=%s",
            self.current_layout.name,
            self._monitor.name if self._monitor else "none",
            self.work_area,
        )

    # ------------------------------------------------------------------
    # Propiedades
    # ------------------------------------------------------------------
    @property
    def current_layout(self) -> Layout:
        """Layout activo."""
        return self._layouts[self._layout_index]

    @property
    def layout_name(self) -> str:
        """Nombre del layout activo."""
        return self.current_layout.name

    @property
    def layout_count(self) -> int:
        """Numero de layouts disponibles."""
        return len(self._layouts)

    @property
    def windows(self) -> list[Window]:
        """Lista de ventanas gestionadas (copia)."""
        return list(self._windows)

    @property
    def window_count(self) -> int:
        """Numero de ventanas gestionadas."""
        return len(self._windows)

    @property
    def work_area(self) -> Rect:
        """Area de trabajo del monitor."""
        if self._monitor is not None:
            return self._monitor.work_rect
        # Fallback: intentar detectar
        return get_work_area()

    @property
    def monitor(self) -> Monitor | None:
        """Monitor asociado."""
        return self._monitor

    # ------------------------------------------------------------------
    # Gestion de ventanas
    # ------------------------------------------------------------------
    def add_window(self, window: Window) -> bool:
        """
        Agrega una ventana al tiling.

        La ventana se inserta al final de la lista (como ultima en el stack).
        Si auto_apply esta activo, reorganiza todas las ventanas.

        Args:
            window: Ventana a agregar.

        Returns:
            True si se agrego, False si ya estaba en la lista.
        """
        if window in self._windows:
            log.debug("Ventana ya gestionada: %s", window)
            return False

        self._windows.append(window)
        log.info(
            "TILE ADD [%d/%s] %s",
            len(self._windows),
            self.layout_name,
            window,
        )

        if self._auto_apply:
            self.apply()

        return True

    def remove_window(self, window: Window) -> bool:
        """
        Elimina una ventana del tiling.

        Si auto_apply esta activo, reorganiza las ventanas restantes.

        Args:
            window: Ventana a eliminar.

        Returns:
            True si se elimino, False si no estaba en la lista.
        """
        try:
            self._windows.remove(window)
        except ValueError:
            return False

        log.info(
            "TILE REMOVE [%d/%s] %s",
            len(self._windows),
            self.layout_name,
            window,
        )

        if self._auto_apply:
            self.apply()

        return True

    def contains(self, window: Window) -> bool:
        """True si la ventana esta siendo gestionada por el engine."""
        return window in self._windows

    # ------------------------------------------------------------------
    # Aplicar layout
    # ------------------------------------------------------------------
    def apply(self) -> None:
        """
        Recalcula y aplica el layout activo a todas las ventanas.

        Obtiene el area de trabajo del monitor, pide al layout que
        calcule las coordenadas, y mueve cada ventana a su posicion.
        """
        count = len(self._windows)
        if count == 0:
            log.debug("apply() sin ventanas, nada que hacer")
            return

        area = self.work_area
        layout = self.current_layout

        # Calcular posiciones
        rects = layout.arrange(count, area)

        if len(rects) != count:
            log.error(
                "Layout %s retorno %d rects para %d ventanas",
                layout.name,
                len(rects),
                count,
            )
            return

        # Aplicar posiciones a cada ventana
        for window, rect in zip(self._windows, rects):
            try:
                if not window.is_valid:
                    log.warning("Ventana invalida al aplicar: %s", window)
                    continue

                # Restaurar si esta minimizada/maximizada para poder mover
                if window.is_minimized:
                    window.restore()
                elif window.is_maximized:
                    window.restore()

                window.move_resize(rect.x, rect.y, rect.w, rect.h)
                log.debug(
                    "TILE APPLY %s -> %s",
                    window,
                    rect,
                )
            except Exception:
                log.exception("Error al aplicar tiling a %s", window)

        log.info(
            "Layout aplicado: %s | %d ventanas | area=%s",
            layout.name,
            count,
            area,
        )

    # ------------------------------------------------------------------
    # Cambio de layout
    # ------------------------------------------------------------------
    def next_layout(self) -> Layout:
        """
        Cambia al siguiente layout en la lista circular.

        Returns:
            El nuevo layout activo.
        """
        self._layout_index = (self._layout_index + 1) % len(self._layouts)
        layout = self.current_layout
        log.info("Layout cambiado a: %s", layout.name)

        if self._auto_apply:
            self.apply()

        return layout

    def prev_layout(self) -> Layout:
        """
        Cambia al layout anterior en la lista circular.

        Returns:
            El nuevo layout activo.
        """
        self._layout_index = (self._layout_index - 1) % len(self._layouts)
        layout = self.current_layout
        log.info("Layout cambiado a: %s", layout.name)

        if self._auto_apply:
            self.apply()

        return layout

    def set_layout(self, layout_type: LayoutType) -> bool:
        """
        Cambia a un layout especifico por tipo.

        Args:
            layout_type: Tipo de layout deseado.

        Returns:
            True si se encontro y cambio, False si no esta disponible.
        """
        for i, layout in enumerate(self._layouts):
            if layout.layout_type == layout_type:
                self._layout_index = i
                log.info("Layout establecido: %s", layout.name)
                if self._auto_apply:
                    self.apply()
                return True
        return False

    # ------------------------------------------------------------------
    # Manipulacion del stack de ventanas
    # ------------------------------------------------------------------
    def swap_master(self) -> None:
        """
        Intercambia la ventana enfocada (o la segunda) con el master.

        Si solo hay 0-1 ventanas, no hace nada.
        """
        if len(self._windows) < 2:
            return

        self._windows[0], self._windows[1] = (
            self._windows[1],
            self._windows[0],
        )
        log.info("Swap master: %s <-> %s", self._windows[0], self._windows[1])

        if self._auto_apply:
            self.apply()

    def swap_with_master(self, window: Window) -> None:
        """
        Intercambia una ventana especifica con el master.

        Args:
            window: Ventana a promover a master.
        """
        if window not in self._windows:
            return
        if len(self._windows) < 2:
            return

        idx = self._windows.index(window)
        if idx == 0:
            return  # Ya es master

        self._windows[0], self._windows[idx] = (
            self._windows[idx],
            self._windows[0],
        )
        log.info("Swap to master: %s (era indice %d)", window, idx)

        if self._auto_apply:
            self.apply()

    def rotate_next(self) -> None:
        """
        Rota las ventanas hacia adelante: cada una toma la posicion
        de la siguiente (la ultima pasa a ser master).
        """
        if len(self._windows) < 2:
            return

        last = self._windows.pop()
        self._windows.insert(0, last)
        log.info("Rotate next: nuevo master = %s", self._windows[0])

        if self._auto_apply:
            self.apply()

    def rotate_prev(self) -> None:
        """
        Rota las ventanas hacia atras: cada una toma la posicion
        de la anterior (el master pasa al final).
        """
        if len(self._windows) < 2:
            return

        first = self._windows.pop(0)
        self._windows.append(first)
        log.info("Rotate prev: nuevo master = %s", self._windows[0])

        if self._auto_apply:
            self.apply()

    # ------------------------------------------------------------------
    # Ajustes del layout activo
    # ------------------------------------------------------------------
    def grow_master(self) -> None:
        """Incrementa el ratio del master del layout activo."""
        self.current_layout.grow_master()
        if self._auto_apply:
            self.apply()

    def shrink_master(self) -> None:
        """Reduce el ratio del master del layout activo."""
        self.current_layout.shrink_master()
        if self._auto_apply:
            self.apply()

    def increase_gap(self) -> None:
        """Incrementa el gap del layout activo."""
        self.current_layout.increase_gap()
        if self._auto_apply:
            self.apply()

    def decrease_gap(self) -> None:
        """Reduce el gap del layout activo."""
        self.current_layout.decrease_gap()
        if self._auto_apply:
            self.apply()

    # ------------------------------------------------------------------
    # Informacion / debug
    # ------------------------------------------------------------------
    def dump_state(self) -> str:
        """Retorna un resumen del estado del engine."""
        lines = [
            "=== TilingEngine ===",
            f"    Layout: {self.layout_name} ({self._layout_index + 1}/{len(self._layouts)})",
            f"    Monitor: {self._monitor.name if self._monitor else 'none'}",
            f"    Area: {self.work_area}",
            f"    Ventanas: {len(self._windows)}",
            f"    Master ratio: {self.current_layout.master_ratio:.0%}",
            f"    Gap: {self.current_layout.gap}px",
            "",
        ]
        for i, w in enumerate(self._windows):
            role = "master" if i == 0 else f"stack-{i}"
            lines.append(f"    [{role}] {w}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"TilingEngine("
            f"layout={self.layout_name}, "
            f"windows={len(self._windows)}, "
            f"area={self.work_area})"
        )
