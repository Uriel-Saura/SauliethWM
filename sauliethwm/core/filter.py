"""
sauliethwm.core.filter - Window filtering rules.

Decides which windows are *manageable* by the WM (i.e. should be tiled,
tracked, and receive layout commands) versus windows that must be ignored
(taskbar, desktop, system tray, invisible helpers, tool windows, etc.).

The rules here are the single source of truth.  If a window passes
`is_manageable()`, SauliethWM will track it.
"""

from __future__ import annotations

import logging

from sauliethwm.core import win32
from sauliethwm.core.window import Window

log = logging.getLogger(__name__)

# ============================================================================
# Known system class names to ALWAYS ignore
# ============================================================================
IGNORED_CLASSES: frozenset[str] = frozenset({
    # Windows shell / explorer
    "Shell_TrayWnd",            # Taskbar
    "Shell_SecondaryTrayWnd",   # Secondary monitor taskbar
    "Progman",                  # Desktop Program Manager
    "WorkerW",                  # Desktop wallpaper worker
    "DV2ControlHost",           # Start menu
    "Windows.UI.Core.CoreWindow",  # Some UWP overlays

    # System UI
    "NotifyIconOverflowWindow", # System tray overflow
    "TopLevelWindowForOverflowXamlIsland",  # Tray overflow (Win11)
    "Shell_InputSwitchTopLevelWindow",  # Language switcher
    "MultitaskingViewFrame",    # Alt-Tab / Task View
    "TaskListThumbnailWnd",     # Taskbar thumbnails
    "ForegroundStaging",        # Focus transition overlay
    "EdgeUiInputTopWndClass",   # Edge gestures
    "EdgeUiInputWndClass",      # Edge gestures
    "NativeHWNDHost",           # Various Windows host windows

    # Other
    "tooltips_class32",         # Tooltips
    "IME",                      # Input method editor
    "MSCTFIME UI",              # Text input framework
    "#32768",                   # Popup menus
    "#32769",                   # Desktop
    "#32770",                   # Dialog (generic - but we handle this below)
    "TaskManagerWindow",        # Task manager (special handling)
})

# Process names that are always excluded
IGNORED_PROCESSES: frozenset[str] = frozenset({
    "SearchUI.exe",
    "SearchHost.exe",
    "ShellExperienceHost.exe",
    "StartMenuExperienceHost.exe",
    "TextInputHost.exe",
    "LockApp.exe",
    "ScreenClippingHost.exe",
    "GameBar.exe",
    "GameBarFTServer.exe",
})

# ============================================================================
# Window title patterns to ignore (exact match)
# ============================================================================
IGNORED_TITLES: frozenset[str] = frozenset({
    "",
    "Program Manager",
    "Windows Shell Experience Host",
    "Microsoft Text Input Application",
    "Windows Input Experience",
    "NVIDIA GeForce Overlay",
    "Setup",  # Generic installer splash screens with no content
})


# ============================================================================
# Core filter function
# ============================================================================
def is_manageable(window: Window) -> bool:
    """
    Return True if *window* should be managed (tiled / tracked) by the WM.

    This function embodies ALL the heuristics for deciding if a window is
    a regular, user-facing application window versus a system artifact.

    The rules, in order:
        1. Must still exist (valid HWND).
        2. Must be visible and not cloaked.
        3. Must not be a child window.
        4. Class name must not be in the ignore list.
        5. Process name must not be in the ignore list.
        6. Title must not be in the ignore list.
        7. Must not be a tool window (WS_EX_TOOLWINDOW) unless it is also
           marked WS_EX_APPWINDOW.
        8. Must not have WS_EX_NOACTIVATE (non-interactive overlays).
        9. Must have a non-zero size.
       10. Must not be the shell or desktop window.
    """
    hwnd = window.hwnd

    # --- 1. Existence ---
    if not window.is_valid:
        return False

    # --- 2. Visibility ---
    if not window.is_visible:
        return False
    if window.is_cloaked:
        return False

    # --- 3. Not a child ---
    if window.is_child:
        return False

    # --- 4. Class name ---
    cls = window.class_name
    if cls in IGNORED_CLASSES:
        log.debug("Filtered %#010x: ignored class %r", hwnd, cls)
        return False

    # --- 5. Process name ---
    proc = window.process_name
    if proc in IGNORED_PROCESSES:
        log.debug("Filtered %#010x: ignored process %r", hwnd, proc)
        return False

    # --- 6. Title ---
    title = window.title
    if title in IGNORED_TITLES:
        log.debug("Filtered %#010x: ignored title %r", hwnd, title)
        return False

    # --- 7. Tool window vs App window ---
    #   Tool windows (floating palettes, etc.) are excluded UNLESS
    #   they explicitly opt-in via WS_EX_APPWINDOW.
    if window.is_tool_window and not window.is_app_window:
        log.debug("Filtered %#010x: tool window without APPWINDOW", hwnd)
        return False

    # --- 8. Non-interactive overlays ---
    if window.is_no_activate:
        log.debug("Filtered %#010x: WS_EX_NOACTIVATE", hwnd)
        return False

    # --- 9. Non-zero size ---
    if window.width <= 0 and window.height <= 0:
        log.debug("Filtered %#010x: zero size", hwnd)
        return False

    # --- 10. Not the shell/desktop window ---
    shell_hwnd = win32.get_shell_window()
    desktop_hwnd = win32.get_desktop_window()
    if hwnd == shell_hwnd or hwnd == desktop_hwnd:
        log.debug("Filtered %#010x: shell/desktop window", hwnd)
        return False

    return True


# ============================================================================
# Enumeration helpers
# ============================================================================
def enumerate_manageable_windows() -> list[Window]:
    """
    Snapshot: enumerate all current top-level windows and return those
    that pass `is_manageable()`.
    """
    results: list[Window] = []

    def _callback(hwnd: int, _: int) -> bool:
        w = Window(hwnd)
        if is_manageable(w):
            results.append(w)
        return True  # continue enumeration

    win32.enum_windows(_callback)
    return sorted(results, key=lambda w: w.title.lower())



