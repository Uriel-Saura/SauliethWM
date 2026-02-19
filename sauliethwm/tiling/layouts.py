"""
sauliethwm.tiling.layouts - Layouts de tiling para organizar ventanas.

Cada layout es una clase que implementa la interfaz base `Layout`.
Recibe una lista de ventanas (como HWNDs) y el area disponible,
y calcula las coordenadas exactas donde debe ir cada una.

Layouts disponibles:
    - TallLayout       : Master a la izquierda, stack a la derecha (estilo dwm)
    - WideLayout       : Master arriba, stack abajo
    - MonocleLayout    : Una ventana ocupa toda el area
    - ThreeColumnLayout: Tres columnas (izquierda, centro master, derecha)
"""

from __future__ import annotations

import abc
import enum
import logging
from dataclasses import dataclass, field

from sauliethwm.tiling.rect import Rect

log = logging.getLogger(__name__)


# ============================================================================
# LayoutType enum
# ============================================================================
class LayoutType(enum.Enum):
    """Identificador de cada tipo de layout."""
    TALL = "tall"
    WIDE = "wide"
    MONOCLE = "monocle"
    THREE_COLUMN = "three_column"


# ============================================================================
# Layout (clase base abstracta)
# ============================================================================
class Layout(abc.ABC):
    """
    Interfaz abstracta para un layout de tiling.

    Un layout recibe N ventanas y un area disponible, y retorna
    una lista de N rectángulos indicando donde debe posicionarse
    cada ventana. La correspondencia es por indice: el rectangulo[i]
    es la posicion para la ventana[i].

    Parametros ajustables comunes:
        - master_ratio: Fraccion del area para la ventana master (0.0 - 1.0).
        - gap: Pixeles de separacion entre ventanas.
    """

    def __init__(
        self,
        master_ratio: float = 0.55,
        gap: int = 4,
    ) -> None:
        self._master_ratio = max(0.1, min(0.9, master_ratio))
        self._gap = max(0, gap)

    # ------------------------------------------------------------------
    # Propiedades
    # ------------------------------------------------------------------
    @property
    def master_ratio(self) -> float:
        return self._master_ratio

    @master_ratio.setter
    def master_ratio(self, value: float) -> None:
        self._master_ratio = max(0.1, min(0.9, value))

    @property
    def gap(self) -> int:
        return self._gap

    @gap.setter
    def gap(self, value: int) -> None:
        self._gap = max(0, value)

    # ------------------------------------------------------------------
    # Interfaz abstracta
    # ------------------------------------------------------------------
    @property
    @abc.abstractmethod
    def layout_type(self) -> LayoutType:
        """Retorna el tipo de layout."""
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Nombre legible del layout."""
        ...

    @abc.abstractmethod
    def arrange(self, count: int, area: Rect) -> list[Rect]:
        """
        Calcula las posiciones para *count* ventanas dentro de *area*.

        Args:
            count: Numero de ventanas a organizar.
            area:  Area disponible del monitor.

        Returns:
            Lista de Rect con exactamente *count* elementos.
            Cada Rect indica donde posicionar la ventana correspondiente.
        """
        ...

    # ------------------------------------------------------------------
    # Ajustes interactivos
    # ------------------------------------------------------------------
    def grow_master(self, step: float = 0.05) -> None:
        """Incrementa el ratio del master."""
        self.master_ratio = self._master_ratio + step

    def shrink_master(self, step: float = 0.05) -> None:
        """Reduce el ratio del master."""
        self.master_ratio = self._master_ratio - step

    def increase_gap(self, step: int = 2) -> None:
        """Incrementa el gap entre ventanas."""
        self.gap = self._gap + step

    def decrease_gap(self, step: int = 2) -> None:
        """Reduce el gap entre ventanas."""
        self.gap = self._gap - step

    # ------------------------------------------------------------------
    # Representacion
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"master_ratio={self._master_ratio:.2f}, "
            f"gap={self._gap})"
        )


# ============================================================================
# TallLayout - Master a la izquierda, stack a la derecha (estilo dwm)
# ============================================================================
class TallLayout(Layout):
    """
    Layout tipo 'tall' (master-stack vertical).

    Con 1 ventana: ocupa toda el area.
    Con 2+ ventanas: la primera (master) ocupa la columna izquierda
    segun master_ratio, y las demas se apilan en la columna derecha.

    Esquema (3 ventanas):
        +----------+------+
        |          |  2   |
        |    1     +------+
        | (master) |  3   |
        +----------+------+
    """

    @property
    def layout_type(self) -> LayoutType:
        return LayoutType.TALL

    @property
    def name(self) -> str:
        return "Tall"

    def arrange(self, count: int, area: Rect) -> list[Rect]:
        """
        Calcula posiciones para un layout tall (master-stack).

        Args:
            count: Numero de ventanas.
            area:  Area disponible del monitor.

        Returns:
            Lista de Rect con las posiciones calculadas.
        """
        if count <= 0:
            return []

        gap = self._gap

        # Una sola ventana: ocupa todo con gap exterior
        if count == 1:
            return [area.pad(gap)]

        # Dividir en master (izquierda) y stack (derecha)
        master_area, stack_area = area.split_horizontal(self._master_ratio)

        # Aplicar gap al master
        master_rect = Rect(
            x=master_area.x + gap,
            y=master_area.y + gap,
            w=master_area.w - gap - gap // 2,
            h=master_area.h - 2 * gap,
        )

        # Dividir el stack en filas iguales
        stack_count = count - 1
        stack_rows = stack_area.slice_rows(stack_count)

        # Aplicar gap a cada fila del stack
        stack_rects: list[Rect] = []
        for i, row in enumerate(stack_rows):
            top_gap = gap if i == 0 else gap // 2
            bottom_gap = gap if i == stack_count - 1 else gap // 2
            r = Rect(
                x=row.x + gap // 2,
                y=row.y + top_gap,
                w=row.w - gap - gap // 2,
                h=row.h - top_gap - bottom_gap,
            )
            stack_rects.append(r)

        return [master_rect] + stack_rects


# ============================================================================
# WideLayout - Master arriba, stack abajo
# ============================================================================
class WideLayout(Layout):
    """
    Layout tipo 'wide' (master-stack horizontal).

    Con 1 ventana: ocupa toda el area.
    Con 2+ ventanas: la primera (master) ocupa la fila superior
    segun master_ratio, y las demas se reparten en columnas abajo.

    Esquema (3 ventanas):
        +------------------+
        |    1 (master)    |
        +--------+---------+
        |   2    |    3    |
        +--------+---------+
    """

    @property
    def layout_type(self) -> LayoutType:
        return LayoutType.WIDE

    @property
    def name(self) -> str:
        return "Wide"

    def arrange(self, count: int, area: Rect) -> list[Rect]:
        """
        Calcula posiciones para un layout wide (master arriba, stack abajo).

        Args:
            count: Numero de ventanas.
            area:  Area disponible del monitor.

        Returns:
            Lista de Rect con las posiciones calculadas.
        """
        if count <= 0:
            return []

        gap = self._gap

        # Una sola ventana: ocupa todo con gap exterior
        if count == 1:
            return [area.pad(gap)]

        # Dividir en master (arriba) y stack (abajo)
        master_area, stack_area = area.split_vertical(self._master_ratio)

        # Aplicar gap al master
        master_rect = Rect(
            x=master_area.x + gap,
            y=master_area.y + gap,
            w=master_area.w - 2 * gap,
            h=master_area.h - gap - gap // 2,
        )

        # Dividir el stack en columnas iguales
        stack_count = count - 1
        stack_cols = stack_area.slice_columns(stack_count)

        # Aplicar gap a cada columna del stack
        stack_rects: list[Rect] = []
        for i, col in enumerate(stack_cols):
            left_gap = gap if i == 0 else gap // 2
            right_gap = gap if i == stack_count - 1 else gap // 2
            r = Rect(
                x=col.x + left_gap,
                y=col.y + gap // 2,
                w=col.w - left_gap - right_gap,
                h=col.h - gap - gap // 2,
            )
            stack_rects.append(r)

        return [master_rect] + stack_rects


# ============================================================================
# MonocleLayout - Una ventana ocupa toda el area
# ============================================================================
class MonocleLayout(Layout):
    """
    Layout tipo 'monocle' (pantalla completa).

    Todas las ventanas reciben el mismo rectangulo (el area completa),
    de modo que se apilan una sobre otra. Solo la ventana con foco
    es visible en la practica.

    Esquema:
        +------------------+
        |                  |
        |    1 (activa)    |
        |                  |
        +------------------+
        (2, 3, ... detras)
    """

    @property
    def layout_type(self) -> LayoutType:
        return LayoutType.MONOCLE

    @property
    def name(self) -> str:
        return "Monocle"

    def arrange(self, count: int, area: Rect) -> list[Rect]:
        """
        Calcula posiciones para un layout monocle.

        Todas las ventanas reciben la misma posicion: el area completa
        con gap exterior aplicado.

        Args:
            count: Numero de ventanas.
            area:  Area disponible del monitor.

        Returns:
            Lista de Rect identicos, uno por ventana.
        """
        if count <= 0:
            return []

        full = area.pad(self._gap)
        return [full] * count


# ============================================================================
# ThreeColumnLayout - Tres columnas (izquierda, centro master, derecha)
# ============================================================================
class ThreeColumnLayout(Layout):
    """
    Layout de tres columnas.

    La ventana master ocupa la columna central. Las ventanas secundarias
    se reparten alternando entre la columna izquierda y la derecha.

    Con 1 ventana: ocupa todo el area.
    Con 2 ventanas: master izquierda, segunda derecha (se comporta como Tall).
    Con 3+ ventanas: tres columnas con master en el centro.

    Esquema (5 ventanas):
        +------+----------+------+
        |  2   |          |  3   |
        +------+  1       +------+
        |  4   | (master) |  5   |
        +------+----------+------+
    """

    def __init__(
        self,
        master_ratio: float = 0.50,
        gap: int = 4,
    ) -> None:
        super().__init__(master_ratio=master_ratio, gap=gap)

    @property
    def layout_type(self) -> LayoutType:
        return LayoutType.THREE_COLUMN

    @property
    def name(self) -> str:
        return "ThreeColumn"

    def arrange(self, count: int, area: Rect) -> list[Rect]:
        """
        Calcula posiciones para un layout de tres columnas.

        Args:
            count: Numero de ventanas.
            area:  Area disponible del monitor.

        Returns:
            Lista de Rect con las posiciones calculadas.
        """
        if count <= 0:
            return []

        gap = self._gap

        # Una sola ventana: ocupa todo
        if count == 1:
            return [area.pad(gap)]

        # Dos ventanas: master izquierda, segunda derecha (como Tall)
        if count == 2:
            left, right = area.split_horizontal(self._master_ratio)
            master_rect = Rect(
                x=left.x + gap,
                y=left.y + gap,
                w=left.w - gap - gap // 2,
                h=left.h - 2 * gap,
            )
            second_rect = Rect(
                x=right.x + gap // 2,
                y=right.y + gap,
                w=right.w - gap - gap // 2,
                h=right.h - 2 * gap,
            )
            return [master_rect, second_rect]

        # 3+ ventanas: tres columnas
        # Calcular anchos: laterales iguales, centro segun master_ratio
        side_ratio = (1.0 - self._master_ratio) / 2.0
        left_w = int(area.w * side_ratio)
        center_w = int(area.w * self._master_ratio)
        right_w = area.w - left_w - center_w

        left_area = Rect(area.x, area.y, left_w, area.h)
        center_area = Rect(area.x + left_w, area.y, center_w, area.h)
        right_area = Rect(area.x + left_w + center_w, area.y, right_w, area.h)

        # Master en el centro
        master_rect = Rect(
            x=center_area.x + gap // 2,
            y=center_area.y + gap,
            w=center_area.w - gap,
            h=center_area.h - 2 * gap,
        )

        # Distribuir ventanas secundarias alternando izquierda/derecha
        left_windows: list[int] = []
        right_windows: list[int] = []
        for i in range(1, count):
            if i % 2 == 1:
                left_windows.append(i)
            else:
                right_windows.append(i)

        # Si no hay ventanas en un lado, redistribuir
        if not right_windows and len(left_windows) > 1:
            half = len(left_windows) // 2
            right_windows = left_windows[half:]
            left_windows = left_windows[:half]

        results: list[Rect] = [master_rect]  # indice 0 = master

        # Crear slots vacios para todas las ventanas
        slots: list[Rect | None] = [None] * count
        slots[0] = master_rect

        # Apilar ventanas en la columna izquierda
        if left_windows:
            left_rows = left_area.slice_rows(len(left_windows))
            for idx, win_idx in enumerate(left_windows):
                row = left_rows[idx]
                top_gap = gap if idx == 0 else gap // 2
                bottom_gap = gap if idx == len(left_windows) - 1 else gap // 2
                slots[win_idx] = Rect(
                    x=row.x + gap,
                    y=row.y + top_gap,
                    w=row.w - gap - gap // 2,
                    h=row.h - top_gap - bottom_gap,
                )

        # Apilar ventanas en la columna derecha
        if right_windows:
            right_rows = right_area.slice_rows(len(right_windows))
            for idx, win_idx in enumerate(right_windows):
                row = right_rows[idx]
                top_gap = gap if idx == 0 else gap // 2
                bottom_gap = gap if idx == len(right_windows) - 1 else gap // 2
                slots[win_idx] = Rect(
                    x=row.x + gap // 2,
                    y=row.y + top_gap,
                    w=row.w - gap - gap // 2,
                    h=row.h - top_gap - bottom_gap,
                )

        # Retornar en orden, filtrando None (no deberia haber)
        return [s for s in slots if s is not None]
