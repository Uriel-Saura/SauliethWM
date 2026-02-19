"""
sauliethwm.core.window - The Window data structure.

Each Window instance is a lightweight, live handle to a real Win32 window.
Properties read from the OS on demand so the data is always fresh.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional

from sauliethwm.core import win32


# ============================================================================
# WindowState enum
# ============================================================================
class WindowState(enum.Enum):
    """Observable state of a window."""
    NORMAL = "normal"
    MINIMIZED = "minimized"
    MAXIMIZED = "maximized"
    HIDDEN = "hidden"       # Invisible or cloaked


# ============================================================================
# Window
# ============================================================================
class Window:
    """
    Represents a single top-level window on the system.

    This is the fundamental data structure of SauliethWM.  It wraps an HWND
    and exposes all queryable properties as live reads against the Win32 API
    so the information is never stale.

    Equality and hashing are based solely on the HWND value, so a Window can
    be safely used in sets and as dict keys.
    """

    __slots__ = ("_hwnd",)

    def __init__(self, hwnd: int) -> None:
        self._hwnd = hwnd

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    @property
    def hwnd(self) -> int:
        return self._hwnd

    @property
    def is_valid(self) -> bool:
        """True if the underlying OS window still exists."""
        return win32.is_window_valid(self._hwnd)

    # ------------------------------------------------------------------
    # Descriptors (read live from OS)
    # ------------------------------------------------------------------
    @property
    def title(self) -> str:
        return win32.get_window_text(self._hwnd)

    @property
    def class_name(self) -> str:
        return win32.get_class_name(self._hwnd)

    @property
    def pid(self) -> int:
        return win32.get_window_pid(self._hwnd)

    @property
    def process_name(self) -> str:
        return win32.get_process_name(self.pid)

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------
    @property
    def rect(self) -> tuple[int, int, int, int]:
        """(left, top, right, bottom)"""
        return win32.get_window_rect(self._hwnd)

    @property
    def x(self) -> int:
        return self.rect[0]

    @property
    def y(self) -> int:
        return self.rect[1]

    @property
    def width(self) -> int:
        r = self.rect
        return r[2] - r[0]

    @property
    def height(self) -> int:
        r = self.rect
        return r[3] - r[1]

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    @property
    def position(self) -> tuple[int, int]:
        return (self.x, self.y)

    # ------------------------------------------------------------------
    # Style flags
    # ------------------------------------------------------------------
    @property
    def style(self) -> int:
        return win32.get_window_style(self._hwnd)

    @property
    def ex_style(self) -> int:
        return win32.get_window_ex_style(self._hwnd)

    @property
    def is_visible(self) -> bool:
        return win32.is_window_visible(self._hwnd)

    @property
    def is_cloaked(self) -> bool:
        return win32.is_window_cloaked(self._hwnd)

    @property
    def is_minimized(self) -> bool:
        return win32.is_window_iconic(self._hwnd)

    @property
    def is_maximized(self) -> bool:
        return win32.is_window_zoomed(self._hwnd)

    @property
    def is_child(self) -> bool:
        return bool(self.style & win32.WS_CHILD)

    @property
    def is_popup(self) -> bool:
        return bool(self.style & win32.WS_POPUP)

    @property
    def is_tool_window(self) -> bool:
        return bool(self.ex_style & win32.WS_EX_TOOLWINDOW)

    @property
    def is_app_window(self) -> bool:
        return bool(self.ex_style & win32.WS_EX_APPWINDOW)

    @property
    def is_topmost(self) -> bool:
        return bool(self.ex_style & win32.WS_EX_TOPMOST)

    @property
    def is_no_activate(self) -> bool:
        return bool(self.ex_style & win32.WS_EX_NOACTIVATE)

    @property
    def has_caption(self) -> bool:
        return bool(self.style & win32.WS_CAPTION)

    @property
    def has_thick_frame(self) -> bool:
        """True if the window has a resizable border."""
        return bool(self.style & win32.WS_THICKFRAME)

    # ------------------------------------------------------------------
    # Derived state
    # ------------------------------------------------------------------
    @property
    def state(self) -> WindowState:
        if not self.is_visible or self.is_cloaked:
            return WindowState.HIDDEN
        if self.is_minimized:
            return WindowState.MINIMIZED
        if self.is_maximized:
            return WindowState.MAXIMIZED
        return WindowState.NORMAL

    @property
    def is_focused(self) -> bool:
        return win32.get_foreground_window() == self._hwnd

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def focus(self) -> bool:
        """Bring window to the foreground, restoring if minimized."""
        if self.is_minimized:
            win32.show_window(self._hwnd, win32.SW_RESTORE)
        return win32.set_foreground_window(self._hwnd)

    def minimize(self) -> bool:
        return win32.show_window(self._hwnd, win32.SW_MINIMIZE)

    def maximize(self) -> bool:
        return win32.show_window(self._hwnd, win32.SW_MAXIMIZE)

    def restore(self) -> bool:
        return win32.show_window(self._hwnd, win32.SW_RESTORE)

    def close(self) -> bool:
        """Send WM_CLOSE (graceful close request)."""
        return win32.post_message(self._hwnd, win32.WM_CLOSE)

    def move_resize(self, x: int, y: int, width: int, height: int) -> bool:
        """Reposition and resize the window."""
        return win32.set_window_pos(self._hwnd, x, y, width, height)

    def move(self, x: int, y: int) -> bool:
        """Move without changing size."""
        return win32.set_window_pos(
            self._hwnd, x, y, 0, 0,
            flags=win32.SWP_NOSIZE | win32.SWP_NOZORDER | win32.SWP_NOACTIVATE,
        )

    def resize(self, width: int, height: int) -> bool:
        """Resize without moving."""
        return win32.set_window_pos(
            self._hwnd, 0, 0, width, height,
            flags=win32.SWP_NOMOVE | win32.SWP_NOZORDER | win32.SWP_NOACTIVATE,
        )

    # ------------------------------------------------------------------
    # Snapshot (for logging / debugging)
    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        """Return a dict of all current properties (one-time read)."""
        return {
            "hwnd": self._hwnd,
            "title": self.title,
            "class_name": self.class_name,
            "pid": self.pid,
            "process_name": self.process_name,
            "rect": self.rect,
            "state": self.state.value,
            "is_focused": self.is_focused,
            "style": hex(self.style),
            "ex_style": hex(self.ex_style),
        }

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Window):
            return self._hwnd == other._hwnd
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._hwnd)

    def __repr__(self) -> str:
        title = self.title if self.is_valid else "<destroyed>"
        return f"Window(hwnd={self._hwnd:#010x}, title={title!r})"

    def __str__(self) -> str:
        if not self.is_valid:
            return f"[{self._hwnd:#010x}] <destroyed>"
        return (
            f"[{self._hwnd:#010x}] {self.title!r} | "
            f"PID:{self.pid} ({self.process_name}) | "
            f"{self.state.value} | "
            f"{self.width}x{self.height}+{self.x}+{self.y}"
        )
