"""
sauliethwm.core.win_suppress - Supresion de la tecla Win del sistema.

Cuando se registran hotkeys que usan la tecla Win (como win+1),
Windows por defecto tambien ejecuta la accion nativa (abrir el menu
inicio al soltar Win, etc.). RegisterHotKey suprime la combinacion
win+X, pero no suprime el "tap" de Win sola.

Este modulo instala un low-level keyboard hook (WH_KEYBOARD_LL) que:
    1. Detecta cuando la tecla Win es presionada.
    2. Si Win se presiona junto con otra tecla (parte de un hotkey),
       marca el evento como "consumed" para evitar que Windows
       interprete el release de Win como "abrir menu inicio".
    3. Si Win se presiona y suelta sola sin otro hotkey, tambien
       suprime el menu inicio (configurable).

El hook es global y funciona con el message loop del WindowManager.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
from typing import Optional

log = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

VK_LWIN = 0x5B
VK_RWIN = 0x5C

# KBDLLHOOKSTRUCT
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


# Low-level keyboard hook callback type
# LRESULT CALLBACK LowLevelKeyboardProc(int nCode, WPARAM wParam, LPARAM lParam)
LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    ctypes.c_long,         # LRESULT
    ctypes.c_int,          # nCode
    ctypes.wintypes.WPARAM,  # wParam
    ctypes.wintypes.LPARAM,  # lParam
)

user32 = ctypes.windll.user32


class WinKeySuppressor:
    """
    Suppresses the Windows Start menu from opening when Win key is
    used as a modifier in WM hotkeys.

    The strategy:
        - Install a WH_KEYBOARD_LL hook.
        - Track Win key press/release state.
        - When Win is pressed down, set a flag.
        - When any other key is pressed while Win is held, mark Win
          as "used in combo" (suppress the standalone Win action).
        - When Win is released: if it was used in a combo, eat the
          key-up to prevent Start menu from opening.

    This approach allows Win+X combinations to work via RegisterHotKey
    while preventing the standalone Win tap from triggering the Start menu.
    """

    def __init__(self, suppress_standalone: bool = True) -> None:
        """
        Args:
            suppress_standalone: If True, also suppress Win-only taps
                                (pressing and releasing Win without any
                                other key). If False, only suppress Win
                                release after a combo was used.
        """
        self._suppress_standalone = suppress_standalone
        self._hook_handle: int = 0
        self._hook_proc: Optional[LowLevelKeyboardProc] = None
        self._win_pressed: bool = False
        self._win_used_in_combo: bool = False
        self._installed: bool = False

    @property
    def is_installed(self) -> bool:
        return self._installed

    def install(self) -> bool:
        """
        Install the low-level keyboard hook.

        Must be called from the same thread that runs the message loop.

        Returns:
            True if the hook was installed successfully.
        """
        if self._installed:
            log.debug("WinKeySuppressor: already installed")
            return True

        # Create the callback (prevent GC)
        self._hook_proc = LowLevelKeyboardProc(self._hook_callback)

        self._hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc,
            None,  # hInstance (None for global hook)
            0,     # dwThreadId (0 for all threads)
        )

        if not self._hook_handle:
            log.error("WinKeySuppressor: SetWindowsHookExW failed")
            self._hook_proc = None
            return False

        self._installed = True
        log.info("WinKeySuppressor: low-level keyboard hook installed")
        return True

    def uninstall(self) -> None:
        """Remove the low-level keyboard hook."""
        if not self._installed:
            return

        if self._hook_handle:
            user32.UnhookWindowsHookEx(self._hook_handle)
            self._hook_handle = 0

        self._hook_proc = None
        self._installed = False
        self._win_pressed = False
        self._win_used_in_combo = False
        log.info("WinKeySuppressor: keyboard hook removed")

    def _hook_callback(
        self, nCode: int, wParam: int, lParam: int
    ) -> int:
        """
        Low-level keyboard hook callback.

        Called for every keyboard event system-wide.
        """
        if nCode < 0:
            return user32.CallNextHookEx(0, nCode, wParam, lParam)

        # Cast lParam to KBDLLHOOKSTRUCT pointer
        kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        vk = kb.vkCode

        is_win_key = vk in (VK_LWIN, VK_RWIN)

        if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            if is_win_key:
                # Win key pressed
                if not self._win_pressed:
                    self._win_pressed = True
                    self._win_used_in_combo = False
            else:
                # Another key pressed while Win is held
                if self._win_pressed:
                    self._win_used_in_combo = True

        elif wParam in (WM_KEYUP, WM_SYSKEYUP):
            if is_win_key:
                # Win key released
                should_suppress = False

                if self._win_used_in_combo:
                    # Win was used as modifier in a combo -> suppress
                    should_suppress = True
                elif self._suppress_standalone:
                    # Standalone Win tap -> suppress if configured
                    should_suppress = True

                self._win_pressed = False
                self._win_used_in_combo = False

                if should_suppress:
                    # Eat the key-up event to prevent Start menu
                    log.debug(
                        "WinKeySuppressor: suppressed Win key-up (vk=0x%02X)",
                        vk,
                    )
                    return 1  # Non-zero = swallow the event

        # Pass through
        return user32.CallNextHookEx(0, nCode, wParam, lParam)
