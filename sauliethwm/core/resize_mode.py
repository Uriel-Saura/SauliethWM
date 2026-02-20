"""
sauliethwm.core.resize_mode - Modo de resize interactivo.

Implementa un modo especial (similar al resize mode de i3) donde:
    1. Se activa con un hotkey (por defecto Alt+R).
    2. Las teclas direccionales ajustan el tamano de la ventana activa.
    3. Se sale del modo con Escape o Enter.

Internamente, al entrar en resize mode:
    - Se registran hotkeys temporales para Left/Right/Up/Down/Esc/Enter.
    - Cada pulsacion ajusta el master ratio o gap.
    - Al salir, se desregistran los hotkeys temporales.

Esto evita tener que combinar modificadores para resize.
"""

from __future__ import annotations

import logging
from typing import Optional

from sauliethwm.core.keybinds import HotkeyManager
from sauliethwm.core import win32

log = logging.getLogger(__name__)

# VK codes for resize mode keys
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_ESCAPE = 0x1B
VK_RETURN = 0x0D


class ResizeMode:
    """
    Interactive resize mode for the window manager.

    When activated, arrow keys resize the active window's area.
    Press Escape or Enter to exit.

    Usage:
        resize_mode = ResizeMode(hk_manager, on_resize, on_exit)
        resize_mode.enter()    # registers temporary hotkeys
        # ... user presses arrow keys ...
        resize_mode.exit()     # unregisters temporary hotkeys

    The on_resize callback receives a direction string:
    "wider", "narrower", "taller", "shorter".
    """

    def __init__(
        self,
        hk_manager: HotkeyManager,
        on_resize: callable,
        on_exit: Optional[callable] = None,
    ) -> None:
        """
        Args:
            hk_manager: The HotkeyManager for registering temporary hotkeys.
            on_resize:  Called with direction string when an arrow key is pressed.
                        Signature: on_resize(direction: str) -> None
                        direction is one of: "wider", "narrower", "taller", "shorter"
            on_exit:    Optional callback when exiting resize mode.
        """
        self._hk_manager = hk_manager
        self._on_resize = on_resize
        self._on_exit = on_exit
        self._active = False
        self._temp_hotkey_ids: list[int] = []

    @property
    def is_active(self) -> bool:
        """True if currently in resize mode."""
        return self._active

    def enter(self) -> bool:
        """
        Enter resize mode.

        Registers temporary hotkeys for arrow keys and Escape/Enter.
        These use no modifiers so that raw arrow presses are captured.

        Returns:
            True if entered successfully.
        """
        if self._active:
            log.debug("ResizeMode: already active")
            return False

        log.info("ResizeMode: ENTERING resize mode")
        self._active = True
        self._temp_hotkey_ids = []

        # Register arrow keys (no modifiers)
        bindings = [
            (0, VK_RIGHT, "wider", "ResizeMode: wider (Right)"),
            (0, VK_LEFT, "narrower", "ResizeMode: narrower (Left)"),
            (0, VK_UP, "taller", "ResizeMode: taller (Up)"),
            (0, VK_DOWN, "shorter", "ResizeMode: shorter (Down)"),
        ]

        for mods, vk, direction, desc in bindings:
            def _make_handler(d: str):
                def _handler():
                    if self._active:
                        self._on_resize(d)
                return _handler

            hk_id = self._hk_manager.register(mods, vk, _make_handler(direction), desc)
            if hk_id is not None:
                self._temp_hotkey_ids.append(hk_id)

        # Register Escape and Enter to exit
        esc_id = self._hk_manager.register(
            0, VK_ESCAPE, self.exit, "ResizeMode: exit (Escape)"
        )
        if esc_id is not None:
            self._temp_hotkey_ids.append(esc_id)

        enter_id = self._hk_manager.register(
            0, VK_RETURN, self.exit, "ResizeMode: exit (Enter)"
        )
        if enter_id is not None:
            self._temp_hotkey_ids.append(enter_id)

        log.info(
            "ResizeMode: %d temporary hotkeys registered",
            len(self._temp_hotkey_ids),
        )
        return True

    def exit(self) -> None:
        """
        Exit resize mode.

        Unregisters all temporary hotkeys and restores normal operation.
        """
        if not self._active:
            return

        log.info("ResizeMode: EXITING resize mode")
        self._active = False

        # Unregister all temporary hotkeys
        for hk_id in self._temp_hotkey_ids:
            self._hk_manager.unregister(hk_id)

        count = len(self._temp_hotkey_ids)
        self._temp_hotkey_ids.clear()

        log.info("ResizeMode: %d temporary hotkeys unregistered", count)

        if self._on_exit is not None:
            try:
                self._on_exit()
            except Exception:
                log.exception("ResizeMode: error in on_exit callback")

    def toggle(self) -> None:
        """Toggle resize mode on/off."""
        if self._active:
            self.exit()
        else:
            self.enter()
