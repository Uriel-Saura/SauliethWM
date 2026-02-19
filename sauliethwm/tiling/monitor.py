"""
sauliethwm.tiling.monitor - Deteccion del area disponible del monitor.

Usa win32api/win32gui de pywin32 para obtener el area de trabajo
(work area) de cada monitor, descontando la taskbar y otras barras
del sistema.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import win32api
import win32con

from sauliethwm.tiling.rect import Rect

log = logging.getLogger(__name__)


# ============================================================================
# Monitor
# ============================================================================
@dataclass(frozen=True, slots=True)
class Monitor:
    """
    Representa un monitor fisico conectado al sistema.

    Atributos:
        name:      Nombre del dispositivo (ej. r'\\\\.\\DISPLAY1').
        full_rect: Area total del monitor (resolucion completa).
        work_rect: Area de trabajo (descontando taskbar y barras).
        is_primary: True si es el monitor principal.
    """

    name: str
    full_rect: Rect
    work_rect: Rect
    is_primary: bool = False

    @property
    def width(self) -> int:
        """Ancho del area de trabajo."""
        return self.work_rect.w

    @property
    def height(self) -> int:
        """Alto del area de trabajo."""
        return self.work_rect.h


# ============================================================================
# Funciones de deteccion
# ============================================================================

def get_monitors() -> list[Monitor]:
    """
    Enumera todos los monitores conectados al sistema.

    Usa win32api.EnumDisplayMonitors para obtener cada monitor y
    win32api.GetMonitorInfo para extraer el area de trabajo.

    Returns:
        Lista de Monitor ordenada: el primario primero, luego por nombre.
    """
    monitors: list[Monitor] = []

    for hmonitor, _hdc, _rect in win32api.EnumDisplayMonitors(None, None):
        try:
            info = win32api.GetMonitorInfo(hmonitor)
        except Exception:
            log.warning("No se pudo obtener info del monitor %s", hmonitor)
            continue

        # info['Monitor'] = (left, top, right, bottom) - area total
        # info['Work']    = (left, top, right, bottom) - area de trabajo
        # info['Device']  = nombre del dispositivo
        # info['Flags']   = 1 si es primario

        full = info["Monitor"]
        work = info["Work"]
        device = info["Device"]
        is_primary = bool(info["Flags"] & win32con.MONITORINFOF_PRIMARY)

        monitor = Monitor(
            name=device,
            full_rect=Rect.from_ltrb(*full),
            work_rect=Rect.from_ltrb(*work),
            is_primary=is_primary,
        )

        monitors.append(monitor)
        log.debug(
            "Monitor detectado: %s | total=%s | trabajo=%s | primario=%s",
            device,
            monitor.full_rect,
            monitor.work_rect,
            is_primary,
        )

    # Ordenar: primario primero, luego por nombre
    monitors.sort(key=lambda m: (not m.is_primary, m.name))

    log.info("Monitores detectados: %d", len(monitors))
    return monitors


def get_primary_monitor() -> Monitor:
    """
    Retorna el monitor primario.

    Raises:
        RuntimeError: Si no se detecta ningun monitor.
    """
    monitors = get_monitors()
    if not monitors:
        raise RuntimeError("No se detectaron monitores en el sistema")

    # El primero siempre es el primario (por el sort anterior)
    return monitors[0]


def get_work_area() -> Rect:
    """
    Atajo: retorna el area de trabajo del monitor primario.

    Esta es la funcion mas comun para un WM de un solo monitor.
    """
    return get_primary_monitor().work_rect
