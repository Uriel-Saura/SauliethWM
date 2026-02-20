"""
sauliethwm.config.hotkeys - Definicion de hotkeys para el WM.

Define y registra todos los keybindings:
    Workspaces:
        Alt + 1..9          -> Cambiar al workspace 1..9
        Alt + Shift + 1..9  -> Mover ventana enfocada al workspace 1..9

    Foco direccional (estilo vim):
        Alt + H             -> Foco a la izquierda
        Alt + J             -> Foco abajo
        Alt + K             -> Foco arriba
        Alt + L             -> Foco a la derecha

    Mover ventana (estilo vim):
        Alt + Shift + H     -> Mover ventana a la izquierda
        Alt + Shift + J     -> Mover ventana abajo
        Alt + Shift + K     -> Mover ventana arriba
        Alt + Shift + L     -> Mover ventana a la derecha

    Ventana:
        Alt + Shift + C     -> Cerrar ventana enfocada
        Alt + Shift + M     -> Swap con master

    Layout:
        Alt + Space         -> Siguiente layout
        Alt + Shift + Space -> Layout anterior

    Resize:
        Alt + =             -> Crecer master
        Alt + -             -> Encoger master
        Alt + Shift + =     -> Aumentar gap
        Alt + Shift + -     -> Disminuir gap
        Alt + R             -> Entrar en modo resize interactivo

    Spawn:
        Alt + Return        -> Abrir terminal (wt.exe)
        Alt + E             -> Abrir explorador

    WM:
        Alt + Shift + Q     -> Cerrar SauliethWM
        Alt + Shift + R     -> Retilear todo
"""

from __future__ import annotations

import logging

from sauliethwm.core import win32
from sauliethwm.core.keybinds import (
    HotkeyManager,
    MOD_ALT,
    MOD_SHIFT,
)
from sauliethwm.core.commands import CommandDispatcher
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


def register_all_hotkeys(
    hk_manager: HotkeyManager,
    dispatcher: CommandDispatcher,
) -> int:
    """
    Registra todos los hotkeys del WM, vinculando cada combinacion
    de teclas a un comando del dispatcher.

    Args:
        hk_manager: El gestor de hotkeys donde registrar.
        dispatcher: El dispatcher de comandos con todos los comandos ya registrados.

    Returns:
        Numero de hotkeys registrados exitosamente.
    """
    registered = 0

    def _bind(modifiers: int, vk: int, command: str, desc: str) -> None:
        nonlocal registered
        cmd = dispatcher.get(command)
        if cmd is None:
            log.warning("Hotkey bind: command %r not found, skipping", command)
            return
        result = hk_manager.register(
            modifiers=modifiers,
            vk=vk,
            callback=cmd.fn,
            description=desc,
        )
        if result is not None:
            registered += 1

    # ------------------------------------------------------------------
    # Alt + 1..9: Cambiar al workspace N
    # ------------------------------------------------------------------
    for ws_id, vk in _WS_VK_MAP.items():
        _bind(MOD_ALT, vk, f"switch_workspace_{ws_id}", f"Switch to workspace {ws_id}")

    # ------------------------------------------------------------------
    # Alt + Shift + 1..9: Mover ventana enfocada al workspace N
    # ------------------------------------------------------------------
    for ws_id, vk in _WS_VK_MAP.items():
        _bind(MOD_ALT | MOD_SHIFT, vk, f"move_to_workspace_{ws_id}", f"Move window to workspace {ws_id}")

    # ------------------------------------------------------------------
    # Foco direccional (vim-style: H/J/K/L)
    # ------------------------------------------------------------------
    _bind(MOD_ALT, win32.VK_H, "focus_left", "Focus left")
    _bind(MOD_ALT, win32.VK_J, "focus_down", "Focus down")
    _bind(MOD_ALT, win32.VK_K, "focus_up", "Focus up")
    _bind(MOD_ALT, win32.VK_L, "focus_right", "Focus right")

    # ------------------------------------------------------------------
    # Mover ventana (vim-style: Shift + H/J/K/L)
    # ------------------------------------------------------------------
    _bind(MOD_ALT | MOD_SHIFT, win32.VK_H, "move_window_left", "Move window left")
    _bind(MOD_ALT | MOD_SHIFT, win32.VK_J, "move_window_down", "Move window down")
    _bind(MOD_ALT | MOD_SHIFT, win32.VK_K, "move_window_up", "Move window up")
    _bind(MOD_ALT | MOD_SHIFT, win32.VK_L, "move_window_right", "Move window right")

    # ------------------------------------------------------------------
    # Ventana
    # ------------------------------------------------------------------
    _bind(MOD_ALT | MOD_SHIFT, win32.VK_C, "close_window", "Close focused window")
    _bind(MOD_ALT | MOD_SHIFT, win32.VK_M, "swap_master", "Swap with master")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    _bind(MOD_ALT, win32.VK_SPACE, "next_layout", "Next layout")
    _bind(MOD_ALT | MOD_SHIFT, win32.VK_SPACE, "prev_layout", "Previous layout")

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------
    _bind(MOD_ALT, 0xBB, "grow_master", "Grow master (=)")       # VK_OEM_PLUS (=)
    _bind(MOD_ALT, 0xBD, "shrink_master", "Shrink master (-)")   # VK_OEM_MINUS (-)
    _bind(MOD_ALT | MOD_SHIFT, 0xBB, "increase_gap", "Increase gap (+)")
    _bind(MOD_ALT | MOD_SHIFT, 0xBD, "decrease_gap", "Decrease gap (_)")
    _bind(MOD_ALT, win32.VK_R, "enter_resize_mode", "Enter resize mode")

    # ------------------------------------------------------------------
    # Spawn
    # ------------------------------------------------------------------
    _bind(MOD_ALT, win32.VK_RETURN, "spawn_terminal", "Launch terminal")
    _bind(MOD_ALT, win32.VK_E, "spawn_explorer", "Launch explorer")

    # ------------------------------------------------------------------
    # WM lifecycle
    # ------------------------------------------------------------------
    _bind(MOD_ALT | MOD_SHIFT, win32.VK_Q, "quit_wm", "Quit SauliethWM")
    _bind(MOD_ALT | MOD_SHIFT, win32.VK_R, "retile_all", "Retile all workspaces")

    log.info("Hotkeys registered: %d", registered)

    return registered
