"""
sauliethwm.core.window - The Window data structure.

Each Window instance is a lightweight, live handle to a real Win32 window.
Properties read from the OS on demand so the data is always fresh.
"""

from __future__ import annotations

import enum
import logging

from sauliethwm.core import win32

log = logging.getLogger(__name__)


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

    __slots__ = (
        "_hwnd",
        "_fullscreen",
        "_saved_style",
        "_saved_ex_style",
        "_saved_rect",
    )

    def __init__(self, hwnd: int) -> None:
        self._hwnd = hwnd
        self._fullscreen: bool = False
        self._saved_style: int = 0
        self._saved_ex_style: int = 0
        self._saved_rect: tuple[int, int, int, int] = (0, 0, 0, 0)

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
    # Fullscreen management
    # ------------------------------------------------------------------
    # Mask of style bits removed when entering fullscreen
    _FS_STYLE_MASK = win32.WS_CAPTION | win32.WS_THICKFRAME

    # Mask of extended style bits removed when entering fullscreen
    _FS_EX_STYLE_MASK = (
        win32.WS_EX_DLGMODALFRAME
        | win32.WS_EX_WINDOWEDGE
        | win32.WS_EX_CLIENTEDGE
        | win32.WS_EX_STATICEDGE
    )

    @property
    def is_fullscreen(self) -> bool:
        """True if the window is in WM-managed fullscreen mode."""
        return self._fullscreen

    def enter_fullscreen(
        self, monitor_x: int, monitor_y: int, monitor_w: int, monitor_h: int,
    ) -> bool:
        """
        Put the window into borderless fullscreen mode.

        Saves current styles and rect, removes decorations, and positions
        the window to cover the entire monitor area (including taskbar).

        Args:
            monitor_x/y/w/h: Full monitor rectangle (not work area).

        Returns:
            True if the operation succeeded.
        """
        if self._fullscreen:
            return False

        if not self.is_valid:
            return False

        # Save original state for restoration
        self._saved_style = self.style
        self._saved_ex_style = self.ex_style
        self._saved_rect = self.rect

        # Restore from minimized/maximized before style change
        if self.is_minimized or self.is_maximized:
            self.restore()

        # Remove decorations from style
        new_style = self._saved_style & ~self._FS_STYLE_MASK
        win32.set_window_style(self._hwnd, new_style)

        # Remove extended decorations
        new_ex = self._saved_ex_style & ~self._FS_EX_STYLE_MASK
        win32.set_window_ex_style(self._hwnd, new_ex)

        # Apply style changes and reposition to full monitor
        win32.set_window_pos(
            self._hwnd,
            monitor_x, monitor_y, monitor_w, monitor_h,
            flags=(
                win32.SWP_NOZORDER
                | win32.SWP_NOACTIVATE
                | win32.SWP_FRAMECHANGED
            ),
        )

        self._fullscreen = True
        log.info("FULLSCREEN ON  %s", self)
        return True

    def exit_fullscreen(self) -> bool:
        """
        Restore the window from borderless fullscreen to its original state.

        Restores the saved styles and repositions the window to its
        previous rect.

        Returns:
            True if the operation succeeded.
        """
        if not self._fullscreen:
            return False

        if not self.is_valid:
            self._fullscreen = False
            return False

        # Restore original styles
        win32.set_window_style(self._hwnd, self._saved_style)
        win32.set_window_ex_style(self._hwnd, self._saved_ex_style)

        # Restore position with FRAMECHANGED to apply style change
        left, top, right, bottom = self._saved_rect
        w = right - left
        h = bottom - top
        win32.set_window_pos(
            self._hwnd,
            left, top, w, h,
            flags=(
                win32.SWP_NOZORDER
                | win32.SWP_NOACTIVATE
                | win32.SWP_FRAMECHANGED
            ),
        )

        self._fullscreen = False
        log.info("FULLSCREEN OFF %s", self)
        return True

    def toggle_fullscreen(
        self, monitor_x: int, monitor_y: int, monitor_w: int, monitor_h: int,
    ) -> bool:
        """
        Toggle between fullscreen and normal state.

        Args:
            monitor_x/y/w/h: Full monitor rectangle (used for enter).

        Returns:
            True if the operation succeeded.
        """
        if self._fullscreen:
            return self.exit_fullscreen()
        return self.enter_fullscreen(monitor_x, monitor_y, monitor_w, monitor_h)

    def suspend_fullscreen(self) -> bool:
        """
        Force-hide a fullscreen borderless window for workspace switch.

        Normal ShowWindow(SW_HIDE) may not reliably hide a borderless
        window that covers the whole monitor.  This method:
          1. Clears WS_VISIBLE directly from the style bits.
          2. Moves the window off-screen with SetWindowPos + SWP_HIDEWINDOW.
        The _fullscreen flag is preserved so reapply_fullscreen() can
        restore the window when the workspace becomes active again.

        Returns:
            True if the operation was performed.
        """
        if not self._fullscreen:
            return False
        if not self.is_valid:
            return False

        # 1. Strip WS_VISIBLE from style bits directly
        cur_style = win32.get_window_style(self._hwnd)
        win32.set_window_style(self._hwnd, cur_style & ~win32.WS_VISIBLE)

        # 2. Move off-screen and request hide via SetWindowPos
        win32.set_window_pos(
            self._hwnd,
            -32000, -32000, 1, 1,
            flags=(
                win32.SWP_NOZORDER
                | win32.SWP_NOACTIVATE
                | win32.SWP_HIDEWINDOW
            ),
        )
        log.debug("FULLSCREEN SUSPENDED %s", self)
        return True

    def reapply_fullscreen(
        self, monitor_x: int, monitor_y: int, monitor_w: int, monitor_h: int,
    ) -> bool:
        """
        Re-apply fullscreen styles and reposition the window to cover
        the given monitor rectangle.

        This is used after show_all_windows() to re-enter fullscreen
        for windows that were suspended, and also when a fullscreen
        window is moved to another workspace on a different monitor.

        Args:
            monitor_x/y/w/h: Full monitor rectangle to cover.

        Returns:
            True if repositioned, False if not in fullscreen.
        """
        if not self._fullscreen:
            return False
        if not self.is_valid:
            return False

        # Ensure decorations are stripped (suspend may have altered them)
        cur_style = win32.get_window_style(self._hwnd)
        cur_ex = win32.get_window_ex_style(self._hwnd)

        new_style = cur_style & ~self._FS_STYLE_MASK
        new_ex = cur_ex & ~self._FS_EX_STYLE_MASK

        if new_style != cur_style:
            win32.set_window_style(self._hwnd, new_style)
        if new_ex != cur_ex:
            win32.set_window_ex_style(self._hwnd, new_ex)

        # Reposition to cover the full monitor; also SWP_SHOWWINDOW to
        # ensure visibility in case suspend_fullscreen cleared WS_VISIBLE.
        win32.set_window_pos(
            self._hwnd,
            monitor_x, monitor_y, monitor_w, monitor_h,
            flags=(
                win32.SWP_NOZORDER
                | win32.SWP_NOACTIVATE
                | win32.SWP_FRAMECHANGED
                | win32.SWP_SHOWWINDOW
            ),
        )
        return True

    def is_native_fullscreen(
        self, monitor_x: int, monitor_y: int, monitor_w: int, monitor_h: int,
    ) -> bool:
        """
        Detect if the window is already in a native fullscreen state
        (e.g. a game or video player). A window is considered native
        fullscreen if it has no caption/thick frame and covers the
        entire monitor rectangle.

        Args:
            monitor_x/y/w/h: Full monitor rectangle to check against.

        Returns:
            True if the window appears to be natively fullscreen.
        """
        if not self.is_valid:
            return False

        # Must not have decorations
        style = self.style
        if style & win32.WS_CAPTION or style & win32.WS_THICKFRAME:
            return False

        # Must cover the monitor (with a small tolerance of 5px)
        left, top, right, bottom = self.rect
        tolerance = 5
        if (
            left <= monitor_x + tolerance
            and top <= monitor_y + tolerance
            and right >= monitor_x + monitor_w - tolerance
            and bottom >= monitor_y + monitor_h - tolerance
        ):
            return True

        return False

    def mark_as_fullscreen(self) -> None:
        """
        Mark this window as fullscreen without modifying its styles.

        Used for windows detected as natively fullscreen. Saves the
        current state so exit_fullscreen() can restore it if needed.
        """
        if self._fullscreen:
            return
        self._saved_style = self.style
        self._saved_ex_style = self.ex_style
        self._saved_rect = self.rect
        self._fullscreen = True
        log.info("NATIVE FULLSCREEN DETECTED %s", self)

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
            "is_fullscreen": self._fullscreen,
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
