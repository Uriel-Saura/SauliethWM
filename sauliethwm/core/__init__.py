"""
sauliethwm.core - Core window detection and control subsystem.

This package contains:
    - win32 : Low-level Win32 API bindings via ctypes
    - window : The Window data structure representing a managed window
    - filter : Logic to decide which windows are manageable
    - manager : WindowManager class - the central event loop and state
    - keybinds : Global hotkey registration and dispatch
"""

from sauliethwm.core.window import Window, WindowState
from sauliethwm.core.manager import WindowManager
from sauliethwm.core.keybinds import HotkeyManager, Hotkey

__all__ = [
    "Window", "WindowState", "WindowManager",
    "HotkeyManager", "Hotkey",
]
