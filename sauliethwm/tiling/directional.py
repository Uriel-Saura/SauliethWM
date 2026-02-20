"""
sauliethwm.tiling.directional - Operaciones direccionales sobre ventanas.

Implementa la logica geometrica para:
    - Foco direccional (focus_left/right/up/down): encontrar la ventana
      mas cercana en una direccion respecto a la ventana enfocada.
    - Movimiento direccional (move_window_left/right/up/down): intercambiar
      la posicion de la ventana enfocada con la adyacente en esa direccion.

El calculo se basa en comparar los centros de los rectangulos de cada
ventana y elegir la mas cercana en el eje correspondiente, con un
filtro angular para evitar seleccionar ventanas que estan en diagonal.
"""

from __future__ import annotations

import enum
import logging
import math
from typing import Optional

from sauliethwm.core.window import Window
from sauliethwm.tiling.rect import Rect

log = logging.getLogger(__name__)


class Direction(enum.Enum):
    """Cardinal directions for focus/move operations."""
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


def _get_window_center(window: Window) -> tuple[int, int]:
    """Get the center point of a window's rectangle."""
    if not window.is_valid:
        return (0, 0)
    left, top, right, bottom = window.rect
    cx = (left + right) // 2
    cy = (top + bottom) // 2
    return cx, cy


def find_nearest_window(
    focused: Window,
    candidates: list[Window],
    direction: Direction,
) -> Optional[Window]:
    """
    Find the nearest window in a given direction from the focused window.

    The algorithm:
        1. Compute the center of the focused window.
        2. For each candidate, compute its center.
        3. Filter candidates that are in the correct direction
           (e.g. for LEFT, candidate.cx < focused.cx).
        4. Among those, pick the closest by distance on the primary axis,
           with secondary axis distance as tiebreaker.

    Args:
        focused:    The currently focused window.
        candidates: List of all tiled windows to consider.
        direction:  The direction to search.

    Returns:
        The nearest Window in that direction, or None if no candidate.
    """
    if not focused.is_valid:
        return None

    fx, fy = _get_window_center(focused)
    best: Optional[Window] = None
    best_primary: float = float("inf")
    best_secondary: float = float("inf")

    for candidate in candidates:
        if candidate == focused:
            continue
        if not candidate.is_valid:
            continue

        cx, cy = _get_window_center(candidate)
        dx = cx - fx
        dy = cy - fy

        # Check if candidate is in the correct direction
        in_direction = False
        primary_dist: float = 0
        secondary_dist: float = 0

        if direction == Direction.LEFT:
            if dx < 0:
                in_direction = True
                primary_dist = abs(dx)
                secondary_dist = abs(dy)

        elif direction == Direction.RIGHT:
            if dx > 0:
                in_direction = True
                primary_dist = abs(dx)
                secondary_dist = abs(dy)

        elif direction == Direction.UP:
            if dy < 0:
                in_direction = True
                primary_dist = abs(dy)
                secondary_dist = abs(dx)

        elif direction == Direction.DOWN:
            if dy > 0:
                in_direction = True
                primary_dist = abs(dy)
                secondary_dist = abs(dx)

        if not in_direction:
            continue

        # Select by closest primary, then closest secondary
        if (primary_dist < best_primary) or (
            primary_dist == best_primary and secondary_dist < best_secondary
        ):
            best = candidate
            best_primary = primary_dist
            best_secondary = secondary_dist

    return best


def focus_direction(
    focused: Window,
    tiled_windows: list[Window],
    direction: Direction,
) -> Optional[Window]:
    """
    Focus the nearest window in the given direction.

    Args:
        focused:       The currently focused window.
        tiled_windows: All tiled windows in the active workspace.
        direction:     Direction to move focus.

    Returns:
        The window that was focused, or None if no target found.
    """
    target = find_nearest_window(focused, tiled_windows, direction)
    if target is None:
        log.debug("focus_%s: no window found in that direction", direction.value)
        return None

    target.focus()
    log.info("focus_%s: %s -> %s", direction.value, focused, target)
    return target


def swap_direction(
    focused: Window,
    tiled_windows: list[Window],
    direction: Direction,
) -> Optional[tuple[int, int]]:
    """
    Swap the focused window's position with the nearest window in the
    given direction within the tiled window list.

    This modifies the list IN PLACE (swaps the two elements).
    The caller should retile after this operation.

    Args:
        focused:       The currently focused window.
        tiled_windows: The internal _tiled_windows list (mutable).
        direction:     Direction to swap.

    Returns:
        Tuple of (source_index, target_index) if swap occurred, None otherwise.
    """
    target = find_nearest_window(focused, tiled_windows, direction)
    if target is None:
        log.debug("move_window_%s: no window found in that direction", direction.value)
        return None

    try:
        src_idx = tiled_windows.index(focused)
        tgt_idx = tiled_windows.index(target)
    except ValueError:
        log.warning("move_window_%s: window not in tiled list", direction.value)
        return None

    # Swap positions in the list
    tiled_windows[src_idx], tiled_windows[tgt_idx] = (
        tiled_windows[tgt_idx],
        tiled_windows[src_idx],
    )

    log.info(
        "move_window_%s: swapped [%d]%s <-> [%d]%s",
        direction.value,
        src_idx,
        focused,
        tgt_idx,
        target,
    )

    return src_idx, tgt_idx
