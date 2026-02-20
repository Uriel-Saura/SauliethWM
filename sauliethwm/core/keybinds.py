"""
sauliethwm.core.keybinds - Sistema de hotkeys globales.

Gestiona el registro de hotkeys globales via la Win32 API RegisterHotKey.
Los hotkeys se despachan a traves del message loop existente (WM_HOTKEY).

El HotkeyManager:
    1. Permite registrar combinaciones de teclas con callbacks.
    2. Se integra con el message loop del WindowManager.
    3. Limpia todos los hotkeys al detenerse.

Uso tipico:
    hk = HotkeyManager()
    hk.register(MOD_ALT, VK_1, mi_callback)
    # ... el message loop procesa WM_HOTKEY automaticamente ...
    hk.unregister_all()
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from sauliethwm.core import win32

log = logging.getLogger(__name__)


# Re-export modifier constants for convenience
MOD_ALT = win32.MOD_ALT
MOD_CONTROL = win32.MOD_CONTROL
MOD_SHIFT = win32.MOD_SHIFT
MOD_WIN = win32.MOD_WIN
MOD_NOREPEAT = win32.MOD_NOREPEAT


# Type for hotkey callbacks: called with no arguments
HotkeyCallback = Callable[[], None]


@dataclass(frozen=True, slots=True)
class Hotkey:
    """Represents a registered hotkey binding."""

    id: int
    modifiers: int
    vk: int
    callback: HotkeyCallback
    description: str


class HotkeyManager:
    """
    Gestiona hotkeys globales del sistema.

    Cada hotkey se registra con un ID unico via RegisterHotKey.
    Cuando el message loop recibe WM_HOTKEY, dispatch() busca el ID
    y ejecuta el callback correspondiente.
    """

    def __init__(self) -> None:
        # hotkey_id -> Hotkey
        self._hotkeys: dict[int, Hotkey] = {}
        # Auto-incrementing ID counter (starting at 1)
        self._next_id: int = 1

    @property
    def count(self) -> int:
        """Number of registered hotkeys."""
        return len(self._hotkeys)

    @property
    def hotkeys(self) -> list[Hotkey]:
        """List of all registered hotkeys."""
        return list(self._hotkeys.values())

    def register(
        self,
        modifiers: int,
        vk: int,
        callback: HotkeyCallback,
        description: str = "",
    ) -> int | None:
        """
        Register a global hotkey.

        Args:
            modifiers:   Combination of MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN.
            vk:          Virtual key code.
            callback:    Function to call when the hotkey is pressed.
            description: Human-readable description for logging/debug.

        Returns:
            The hotkey ID if registered successfully, None on failure.
        """
        hotkey_id = self._next_id

        if not win32.register_hotkey(hotkey_id, modifiers, vk):
            mod_str = self._modifiers_to_str(modifiers)
            log.error(
                "Failed to register hotkey: %s+0x%02X (%s)",
                mod_str,
                vk,
                description,
            )
            return None

        hotkey = Hotkey(
            id=hotkey_id,
            modifiers=modifiers,
            vk=vk,
            callback=callback,
            description=description,
        )
        self._hotkeys[hotkey_id] = hotkey
        self._next_id += 1

        mod_str = self._modifiers_to_str(modifiers)
        log.info(
            "Hotkey registered: id=%d %s+0x%02X  %s",
            hotkey_id,
            mod_str,
            vk,
            description,
        )

        return hotkey_id

    def replace(
        self,
        hotkey_id: int,
        modifiers: int,
        vk: int,
        callback: HotkeyCallback,
        description: str = "",
    ) -> int | None:
        """
        Replace an existing hotkey in-place (hot-reload friendly).

        Unregisters the old hotkey and registers a new one with the same
        or different combo/callback.  If registration fails the old hotkey
        is already gone (caller should handle gracefully).

        Args:
            hotkey_id:   ID of the hotkey to replace.
            modifiers:   New modifier flags.
            vk:          New virtual key code.
            callback:    New callback function.
            description: New human-readable description.

        Returns:
            The new hotkey ID if replaced successfully, None on failure.
        """
        old = self._hotkeys.get(hotkey_id)
        if old is None:
            log.warning("replace: hotkey id=%d not found", hotkey_id)
            return None

        # Unregister the old hotkey from the OS
        win32.unregister_hotkey(hotkey_id)
        del self._hotkeys[hotkey_id]

        # Register the new one (gets a fresh ID)
        new_id = self.register(modifiers, vk, callback, description)
        if new_id is not None:
            log.info(
                "Hotkey replaced: old_id=%d -> new_id=%d  %s",
                hotkey_id,
                new_id,
                description,
            )
        else:
            log.error(
                "Hotkey replace failed: old_id=%d was unregistered but "
                "new combo could not be registered (%s)",
                hotkey_id,
                description,
            )
        return new_id

    def find_by_combo(self, modifiers: int, vk: int) -> Hotkey | None:
        """
        Find a registered hotkey by its modifier+VK combination.

        Useful for hot-reload: look up the existing hotkey before replacing.

        Returns:
            The Hotkey dataclass if found, None otherwise.
        """
        for hk in self._hotkeys.values():
            if hk.modifiers == modifiers and hk.vk == vk:
                return hk
        return None

    def unregister(self, hotkey_id: int) -> bool:
        """Unregister a hotkey by its ID."""
        hotkey = self._hotkeys.pop(hotkey_id, None)
        if hotkey is None:
            return False

        win32.unregister_hotkey(hotkey_id)
        log.info("Hotkey unregistered: id=%d %s", hotkey_id, hotkey.description)
        return True

    def unregister_all(self) -> None:
        """Unregister all hotkeys. Call this on shutdown."""
        for hotkey_id in list(self._hotkeys.keys()):
            win32.unregister_hotkey(hotkey_id)
        count = len(self._hotkeys)
        self._hotkeys.clear()
        log.info("All hotkeys unregistered (%d total)", count)

    def dispatch(self, hotkey_id: int) -> bool:
        """
        Dispatch a WM_HOTKEY event to the appropriate callback.

        Called by the message loop when it receives a WM_HOTKEY message.

        Args:
            hotkey_id: The wParam from WM_HOTKEY (the registered ID).

        Returns:
            True if a callback was found and executed.
        """
        hotkey = self._hotkeys.get(hotkey_id)
        if hotkey is None:
            log.warning("Unknown hotkey id: %d", hotkey_id)
            return False

        log.debug("Hotkey dispatched: %s", hotkey.description)
        try:
            hotkey.callback()
        except Exception:
            log.exception(
                "Error in hotkey callback: %s", hotkey.description
            )

        return True

    def dump_state(self) -> str:
        """Return a formatted string of all registered hotkeys."""
        lines = [
            f"=== HotkeyManager: {len(self._hotkeys)} hotkeys ===",
            "",
        ]
        for hk in self._hotkeys.values():
            mod_str = self._modifiers_to_str(hk.modifiers)
            lines.append(
                f"  id={hk.id:3d}  {mod_str}+0x{hk.vk:02X}  {hk.description}"
            )
        return "\n".join(lines)

    @staticmethod
    def _modifiers_to_str(modifiers: int) -> str:
        """Convert modifier flags to a human-readable string."""
        parts: list[str] = []
        if modifiers & MOD_WIN:
            parts.append("Win")
        if modifiers & MOD_CONTROL:
            parts.append("Ctrl")
        if modifiers & MOD_ALT:
            parts.append("Alt")
        if modifiers & MOD_SHIFT:
            parts.append("Shift")
        return "+".join(parts) if parts else "None"
