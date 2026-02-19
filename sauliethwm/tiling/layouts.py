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
