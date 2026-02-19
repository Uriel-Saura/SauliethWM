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
