"""
sauliethwm.config.hotkeys - Definicion de hotkeys para workspaces.

Define y registra todos los keybindings relacionados con:
    - Navegacion entre workspaces (Alt+1..9)
    - Mover ventana a workspace (Alt+Shift+1..9)
    - Mover ventana al siguiente monitor (Alt+Shift+M)

Esquema de teclas (estilo i3/dwm):
    Alt + 1..9          -> Cambiar al workspace 1..9
    Alt + Shift + 1..9  -> Mover ventana enfocada al workspace 1..9
"""

from __future__ import annotations

import logging

from sauliethwm.core import win32
from sauliethwm.core.keybinds import (
    HotkeyManager,
    MOD_ALT,
    MOD_SHIFT,
)
from sauliethwm.core.manager import WindowManager
from sauliethwm.tiling.workspace_manager import WorkspaceManager

log = logging.getLogger(__name__)


# Mapeo de workspace IDs (1-9) a virtual key codes
_WS_VK_MAP: dict[int, int] = {
    1: win32.VK_1,
    2: win32.VK_2,
    3: win32.VK_3,
    4: win32.VK_4,
    5: win32.VK_5,
    6: win32.VK_6,
    7: win32.VK_7,
    8: win32.VK_8,
    9: win32.VK_9,
}


def register_workspace_hotkeys(
    hk_manager: HotkeyManager,
    ws_manager: WorkspaceManager,
    wm: WindowManager,
) -> int:
    """
    Registra todos los hotkeys de navegacion y movimiento de workspaces.

    Hotkeys registrados:
        Alt + 1..9          : switch_workspace(N) en monitor 0
        Alt + Shift + 1..9  : move_window_to_workspace(focused, N)

    Args:
        hk_manager: El gestor de hotkeys donde registrar.
        ws_manager: El gestor de workspaces para ejecutar acciones.
        wm:         El WindowManager para obtener la ventana enfocada.

    Returns:
        Numero de hotkeys registrados exitosamente.
    """
    registered = 0

    # ------------------------------------------------------------------
    # Alt + 1..9: Cambiar al workspace N
    # ------------------------------------------------------------------
    for ws_id, vk in _WS_VK_MAP.items():
        # Closure trick: capture ws_id by default argument
        def _make_switch(target_id: int):
            def _switch():
                ws_manager.switch_workspace(target_id, monitor_index=0)
            return _switch

        result = hk_manager.register(
            modifiers=MOD_ALT,
            vk=vk,
            callback=_make_switch(ws_id),
            description=f"Switch to workspace {ws_id}",
        )
        if result is not None:
            registered += 1

    # ------------------------------------------------------------------
    # Alt + Shift + 1..9: Mover ventana enfocada al workspace N
    # ------------------------------------------------------------------
    for ws_id, vk in _WS_VK_MAP.items():
        def _make_move(target_id: int):
            def _move():
                focused = wm.focused
                if focused is None:
                    log.debug("Move to ws %d: no focused window", target_id)
                    return
                ws_manager.move_window_to_workspace(focused, target_id)
            return _move

        result = hk_manager.register(
            modifiers=MOD_ALT | MOD_SHIFT,
            vk=vk,
            callback=_make_move(ws_id),
            description=f"Move window to workspace {ws_id}",
        )
        if result is not None:
            registered += 1

    log.info(
        "Workspace hotkeys registered: %d of %d",
        registered,
        len(_WS_VK_MAP) * 2,
    )

    return registered
