"""
sauliethwm.tiling - Motor de tiling (organizacion automatica de ventanas).

Este paquete contiene:
    - rect    : Estructura Rect para geometria de areas
    - monitor : Deteccion del area disponible del monitor
    - layouts : Layouts de tiling (Tall, Wide, Monocle, ThreeColumn)
    - engine  : TilingEngine - motor principal de organizacion
"""

from sauliethwm.tiling.rect import Rect
from sauliethwm.tiling.monitor import Monitor, get_monitors, get_work_area
from sauliethwm.tiling.layouts import (
    Layout,
    LayoutType,
    TallLayout,
    WideLayout,
    MonocleLayout,
    ThreeColumnLayout,
)
from sauliethwm.tiling.engine import TilingEngine

__all__ = [
    "Rect",
    "Monitor",
    "get_monitors",
    "get_work_area",
    "Layout",
    "LayoutType",
    "TallLayout",
    "WideLayout",
    "MonocleLayout",
    "ThreeColumnLayout",
    "TilingEngine",
]
