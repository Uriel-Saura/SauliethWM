"""
sauliethwm.config.hotkeys - Definicion de hotkeys para el WM.

Define y registra todos los keybindings:
    Workspaces:
        Win + 1..9          -> Cambiar al workspace 1..9
        Win + Shift + 1..9  -> Mover ventana enfocada al workspace 1..9

    Foco direccional (estilo vim):
        Win + H             -> Foco a la izquierda
        Win + J             -> Foco abajo
        Win + K             -> Foco arriba
        Win + L             -> Foco a la derecha

    Mover ventana (estilo vim):
        Win + Shift + H     -> Mover ventana a la izquierda
        Win + Shift + J     -> Mover ventana abajo
        Win + Shift + K     -> Mover ventana arriba
        Win + Shift + L     -> Mover ventana a la derecha

    Ventana:
        Win + Shift + C     -> Cerrar ventana enfocada
        Win + Shift + M     -> Swap con master

    Layout:
        Win + Space         -> Siguiente layout
        Win + Shift + Space -> Layout anterior

    Resize:
        Win + =             -> Crecer master
        Win + -             -> Encoger master
        Win + Shift + =     -> Aumentar gap
        Win + Shift + -     -> Disminuir gap
        Win + R             -> Entrar en modo resize interactivo

    Spawn:
        Win + Return        -> Abrir terminal (wt.exe)
        Win + E             -> Abrir explorador

    WM:
        Win + Shift + Q     -> Cerrar SauliethWM
        Win + Shift + R     -> Retilear todo
"""

from __future__ import annotations

import logging

from sauliethwm.core import win32
from sauliethwm.core.keybinds import (
    HotkeyManager,
    MOD_SHIFT,
    MOD_WIN,
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
    # Win + 1..9: Cambiar al workspace N
    # ------------------------------------------------------------------
    for ws_id, vk in _WS_VK_MAP.items():
        _bind(MOD_WIN, vk, f"switch_workspace_{ws_id}", f"Switch to workspace {ws_id}")

    # ------------------------------------------------------------------
    # Win + Shift + 1..9: Mover ventana enfocada al workspace N
    # ------------------------------------------------------------------
    for ws_id, vk in _WS_VK_MAP.items():
        _bind(MOD_WIN | MOD_SHIFT, vk, f"move_to_workspace_{ws_id}", f"Move window to workspace {ws_id}")

    # ------------------------------------------------------------------
    # Foco direccional (vim-style: H/J/K/L)
    # ------------------------------------------------------------------
    _bind(MOD_WIN, win32.VK_H, "focus_left", "Focus left")
    _bind(MOD_WIN, win32.VK_J, "focus_down", "Focus down")
    _bind(MOD_WIN, win32.VK_K, "focus_up", "Focus up")
    _bind(MOD_WIN, win32.VK_L, "focus_right", "Focus right")

    # ------------------------------------------------------------------
    # Mover ventana (vim-style: Shift + H/J/K/L)
    # ------------------------------------------------------------------
    _bind(MOD_WIN | MOD_SHIFT, win32.VK_H, "move_window_left", "Move window left")
    _bind(MOD_WIN | MOD_SHIFT, win32.VK_J, "move_window_down", "Move window down")
    _bind(MOD_WIN | MOD_SHIFT, win32.VK_K, "move_window_up", "Move window up")
    _bind(MOD_WIN | MOD_SHIFT, win32.VK_L, "move_window_right", "Move window right")

    # ------------------------------------------------------------------
    # Ventana
    # ------------------------------------------------------------------
    _bind(MOD_WIN | MOD_SHIFT, win32.VK_C, "close_window", "Close focused window")
    _bind(MOD_WIN | MOD_SHIFT, win32.VK_M, "swap_master", "Swap with master")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    _bind(MOD_WIN, win32.VK_SPACE, "next_layout", "Next layout")
    _bind(MOD_WIN | MOD_SHIFT, win32.VK_SPACE, "prev_layout", "Previous layout")

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------
    _bind(MOD_WIN, 0xBB, "grow_master", "Grow master (=)")       # VK_OEM_PLUS (=)
    _bind(MOD_WIN, 0xBD, "shrink_master", "Shrink master (-)")   # VK_OEM_MINUS (-)
    _bind(MOD_WIN | MOD_SHIFT, 0xBB, "increase_gap", "Increase gap (+)")
    _bind(MOD_WIN | MOD_SHIFT, 0xBD, "decrease_gap", "Decrease gap (_)")
    _bind(MOD_WIN, win32.VK_R, "enter_resize_mode", "Enter resize mode")

    # ------------------------------------------------------------------
    # Spawn
    # ------------------------------------------------------------------
    _bind(MOD_WIN, win32.VK_RETURN, "spawn_terminal", "Launch terminal")
    _bind(MOD_WIN, win32.VK_E, "spawn_explorer", "Launch explorer")

    # ------------------------------------------------------------------
    # WM lifecycle
    # ------------------------------------------------------------------
    _bind(MOD_WIN | MOD_SHIFT, win32.VK_Q, "quit_wm", "Quit SauliethWM")
    _bind(MOD_WIN | MOD_SHIFT, win32.VK_R, "retile_all", "Retile all workspaces")

    log.info("Hotkeys registered: %d", registered)

    return registered
