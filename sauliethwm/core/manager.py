"""
sauliethwm.core.manager - WindowManager: the central event loop and state.

This is the heart of SauliethWM.  WindowManager:

  1. On startup, enumerates all existing manageable windows.
  2. Installs a WinEventHook to receive real-time notifications when
     windows are created, destroyed, shown, hidden, moved, resized,
     focused, minimized, or maximized.
  3. Maintains a live set of managed Window objects.
  4. Exposes an event/callback system so that higher-level modules
     (layout engine, keybindings, IPC) can react to window events
     without knowing anything about Win32.
"""

from __future__ import annotations

import enum
import logging
import signal
from collections.abc import Callable
from typing import Optional

from sauliethwm.core import win32
from sauliethwm.core.window import Window
from sauliethwm.core.filter import is_manageable, enumerate_manageable_windows
from sauliethwm.core.keybinds import HotkeyManager

log = logging.getLogger(__name__)


# ============================================================================
# Event types emitted by WindowManager
# ============================================================================
class WMEvent(enum.Enum):
    """Events that the WindowManager can emit to subscribers."""

    # A new manageable window appeared (created or became visible).
    WINDOW_ADDED = "window_added"

    # A managed window was destroyed or became unmanageable.
    WINDOW_REMOVED = "window_removed"

    # The foreground (focused) window changed.
    FOCUS_CHANGED = "focus_changed"

    # A managed window was minimized.
    WINDOW_MINIMIZED = "window_minimized"

    # A managed window was restored from minimized/maximized.
    WINDOW_RESTORED = "window_restored"

    # A managed window was moved or resized (externally, not by us).
    WINDOW_MOVED = "window_moved"

    # A managed window's title changed.
    TITLE_CHANGED = "title_changed"


# Type alias for event callbacks.
# All callbacks receive (event, window, manager).
EventCallback = Callable[["WMEvent", Optional[Window], "WindowManager"], None]


# ============================================================================
# WindowManager
# ============================================================================
class WindowManager:
    """
    Central manager that tracks all manageable windows and dispatches events.

    Usage:
        wm = WindowManager()
        wm.on(WMEvent.WINDOW_ADDED, my_callback)
        wm.start()   # blocks in the Win32 message loop
    """

    def __init__(self) -> None:
        # Managed windows indexed by HWND for O(1) lookup
        self._windows: dict[int, Window] = {}

        # Currently focused managed window (or None)
        self._focused: Optional[Window] = None

        # Event subscribers: event -> list of callbacks
        self._subscribers: dict[WMEvent, list[EventCallback]] = {
            ev: [] for ev in WMEvent
        }

        # WinEvent hook handle (set when running)
        self._hook_handle: int = 0

        # Must prevent GC of the ctypes callback
        self._hook_proc: Optional[win32.WinEventProc] = None

        # Flag to request stop
        self._running: bool = False

        # Suppression flag: when True, hide/show events are ignored
        # to prevent feedback loops during workspace switching.
        self._suppress_hide_show: bool = False

        # Set of HWNDs whose hide/show events should be ignored even
        # after _suppress_hide_show is turned off.  Cleared explicitly
        # via clear_suppressed_hwnds().  This handles the race where
        # WinEvents arrive asynchronously after resume_events().
        self._suppressed_hwnds: set[int] = set()

        # Thread ID of the message loop (needed for cross-thread stop)
        self._loop_thread_id: int = 0

        # Optional hotkey manager for global keybindings
        self._hotkey_manager: Optional[HotkeyManager] = None

    # ------------------------------------------------------------------
    # Public: window access
    # ------------------------------------------------------------------
    @property
    def windows(self) -> list[Window]:
        """Return a sorted list of all currently managed windows."""
        return sorted(self._windows.values(), key=lambda w: w.title.lower())

    @property
    def focused(self) -> Optional[Window]:
        return self._focused

    def get(self, hwnd: int) -> Optional[Window]:
        """Get a managed window by its HWND, or None."""
        return self._windows.get(hwnd)

    @property
    def count(self) -> int:
        return len(self._windows)

    # ------------------------------------------------------------------
    # Public: event subscription
    # ------------------------------------------------------------------
    def on(self, event: WMEvent, callback: EventCallback) -> None:
        """Register a callback for a specific event."""
        self._subscribers[event].append(callback)

    def off(self, event: WMEvent, callback: EventCallback) -> None:
        """Unregister a callback."""
        try:
            self._subscribers[event].remove(callback)
        except ValueError:
            pass

    def on_all(self, callback: EventCallback) -> None:
        """Register a callback for ALL events."""
        for ev in WMEvent:
            self._subscribers[ev].append(callback)

    def set_hotkey_manager(self, hk_manager: HotkeyManager) -> None:
        """
        Attach a HotkeyManager so WM_HOTKEY messages are dispatched.

        Must be called before start().
        """
        self._hotkey_manager = hk_manager

    def suppress_events(self) -> None:
        """
        Start suppressing hide/show events.

        Call this before programmatically hiding/showing windows
        (e.g. workspace switch) to prevent the WinEventHook from
        unmanaging/re-managing windows that are being hidden/shown
        intentionally by the workspace manager.
        """
        self._suppress_hide_show = True

    def resume_events(self) -> None:
        """Stop suppressing hide/show events."""
        self._suppress_hide_show = False

    def add_suppressed_hwnds(self, hwnds: set[int]) -> None:
        """
        Register HWNDs that were just hidden/shown programmatically.

        Late-arriving WinEvents for these HWNDs will be ignored even
        after the global suppression flag is turned off.
        """
        self._suppressed_hwnds.update(hwnds)

    def clear_suppressed_hwnds(self) -> None:
        """Clear the per-HWND suppression set after events have settled."""
        self._suppressed_hwnds.clear()

    # ------------------------------------------------------------------
    # Internal: emit events
    # ------------------------------------------------------------------
    def _emit(self, event: WMEvent, window: Optional[Window] = None) -> None:
        for cb in self._subscribers[event]:
            try:
                cb(event, window, self)
            except Exception:
                log.exception(
                    "Error in event callback for %s on %s", event.value, window
                )

    # ------------------------------------------------------------------
    # Internal: manage / unmanage
    # ------------------------------------------------------------------
    def _manage(self, hwnd: int) -> Optional[Window]:
        """
        Start managing a window.  Returns the Window if newly added, or
        None if it was already managed or is not manageable.
        """
        if hwnd in self._windows:
            return None

        window = Window(hwnd)
        if not is_manageable(window):
            return None

        self._windows[hwnd] = window
        log.info("MANAGE  %s", window)
        self._emit(WMEvent.WINDOW_ADDED, window)
        return window

    def _unmanage(self, hwnd: int) -> Optional[Window]:
        """
        Stop managing a window.  Returns the Window if it was managed,
        or None if it wasn't.
        """
        window = self._windows.pop(hwnd, None)
        if window is None:
            return None

        log.info("UNMANAGE  %s", window)

        if self._focused is not None and self._focused.hwnd == hwnd:
            self._focused = None

        self._emit(WMEvent.WINDOW_REMOVED, window)
        return window

    # ------------------------------------------------------------------
    # Internal: initial scan
    # ------------------------------------------------------------------
    def _scan_existing(self) -> None:
        """Enumerate all currently-open manageable windows."""
        for w in enumerate_manageable_windows():
            self._windows[w.hwnd] = w
            log.info("INITIAL %s", w)
            self._emit(WMEvent.WINDOW_ADDED, w)

        # Set current focus
        fg_hwnd = win32.get_foreground_window()
        if fg_hwnd in self._windows:
            self._focused = self._windows[fg_hwnd]

        log.info(
            "Initial scan complete: %d managed windows, focused: %s",
            len(self._windows),
            self._focused,
        )

    # ------------------------------------------------------------------
    # Internal: WinEvent callback
    # ------------------------------------------------------------------
    def _on_win_event(
        self,
        hook: int,
        event: int,
        hwnd: int,
        id_object: int,
        id_child: int,
        event_thread: int,
        event_time: int,
    ) -> None:
        """
        Raw WinEvent callback dispatched by the OS.

        We only care about events on top-level windows (id_object == OBJID_WINDOW
        and id_child == CHILDID_SELF).  Everything else is discarded.
        """
        # Filter: only top-level window events
        if id_object != win32.OBJID_WINDOW:
            return
        if id_child != win32.CHILDID_SELF:
            return
        if hwnd == 0:
            return

        # Dispatch by event type
        try:
            if event == win32.EVENT_OBJECT_SHOW:
                self._handle_show(hwnd)

            elif event == win32.EVENT_OBJECT_DESTROY:
                self._handle_destroy(hwnd)

            elif event == win32.EVENT_OBJECT_HIDE:
                self._handle_hide(hwnd)

            elif event == win32.EVENT_SYSTEM_FOREGROUND:
                self._handle_foreground(hwnd)

            elif event == win32.EVENT_OBJECT_FOCUS:
                # Usually redundant with FOREGROUND but captures more cases
                self._handle_foreground(hwnd)

            elif event == win32.EVENT_SYSTEM_MINIMIZESTART:
                self._handle_minimize(hwnd)

            elif event == win32.EVENT_SYSTEM_MINIMIZEEND:
                self._handle_restore(hwnd)

            elif event == win32.EVENT_SYSTEM_MOVESIZEEND:
                self._handle_movesize(hwnd)

            elif event == win32.EVENT_OBJECT_NAMECHANGE:
                self._handle_title_change(hwnd)

        except Exception:
            log.exception("Error handling event %#06x for hwnd %#010x", event, hwnd)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _handle_show(self, hwnd: int) -> None:
        """A window became visible - check if it should be managed."""
        if self._suppress_hide_show:
            return
        if hwnd in self._suppressed_hwnds:
            self._suppressed_hwnds.discard(hwnd)
            return
        self._manage(hwnd)

    def _handle_destroy(self, hwnd: int) -> None:
        """A window was destroyed."""
        self._suppressed_hwnds.discard(hwnd)
        if self._suppress_hide_show:
            # During workspace switching, only remove from the internal
            # tracking dict but do NOT emit WINDOW_REMOVED so the
            # workspace handler doesn't try to retile mid-switch.
            window = self._windows.pop(hwnd, None)
            if window is not None:
                log.debug("DESTROY (suppressed) %s", window)
                if self._focused is not None and self._focused.hwnd == hwnd:
                    self._focused = None
            return
        self._unmanage(hwnd)

    def _handle_hide(self, hwnd: int) -> None:
        """A window became invisible - unmanage it (unless suppressed)."""
        if self._suppress_hide_show:
            return
        if hwnd in self._suppressed_hwnds:
            self._suppressed_hwnds.discard(hwnd)
            return
        self._unmanage(hwnd)

    def _handle_foreground(self, hwnd: int) -> None:
        """The foreground window changed."""
        # During workspace switching, ignore foreground changes to avoid
        # re-managing windows from inactive workspaces.
        if self._suppress_hide_show:
            return
        if hwnd in self._suppressed_hwnds:
            return

        # If it's a new window we haven't seen, try to manage it
        if hwnd not in self._windows:
            self._manage(hwnd)

        window = self._windows.get(hwnd)
        if window is not None and window != self._focused:
            self._focused = window
            log.debug("FOCUS -> %s", window)
            self._emit(WMEvent.FOCUS_CHANGED, window)

    def _handle_minimize(self, hwnd: int) -> None:
        """A window was minimized."""
        # During workspace switching we use SW_MINIMIZE before SW_HIDE
        # to force-hide stubborn windows.  Ignore the resulting
        # MINIMIZESTART events so the workspace handler doesn't
        # remove windows from their workspaces mid-switch.
        if self._suppress_hide_show:
            return
        if hwnd in self._suppressed_hwnds:
            self._suppressed_hwnds.discard(hwnd)
            return
        window = self._windows.get(hwnd)
        if window is not None:
            log.debug("MINIMIZE %s", window)
            self._emit(WMEvent.WINDOW_MINIMIZED, window)

    def _handle_restore(self, hwnd: int) -> None:
        """A window was restored from minimized state."""
        if self._suppress_hide_show:
            return
        if hwnd in self._suppressed_hwnds:
            self._suppressed_hwnds.discard(hwnd)
            return
        # It might be new to us
        if hwnd not in self._windows:
            self._manage(hwnd)
        window = self._windows.get(hwnd)
        if window is not None:
            log.debug("RESTORE %s", window)
            self._emit(WMEvent.WINDOW_RESTORED, window)

    def _handle_movesize(self, hwnd: int) -> None:
        """A window finished a move/resize operation."""
        window = self._windows.get(hwnd)
        if window is not None:
            log.debug("MOVESIZE %s", window)
            self._emit(WMEvent.WINDOW_MOVED, window)

    def _handle_title_change(self, hwnd: int) -> None:
        """A window title changed."""
        window = self._windows.get(hwnd)
        if window is not None:
            log.debug("TITLE %s", window)
            self._emit(WMEvent.TITLE_CHANGED, window)

    # ------------------------------------------------------------------
    # Public: lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """
        Start the window manager.

        1. Enumerates existing windows.
        2. Installs the WinEvent hook.
        3. Enters the Win32 message loop (blocks until stop() is called
           or a SIGINT/SIGTERM is received).
        """
        log.info("SauliethWM starting...")

        # COM initialization (needed for some shell interactions)
        win32.co_initialize()

        # Phase 1: enumerate existing windows
        self._scan_existing()

        # Phase 2: install WinEvent hook
        self._hook_proc = win32.WinEventProc(self._on_win_event)
        self._hook_handle = win32.set_win_event_hook(
            event_min=win32.EVENT_MIN,
            event_max=win32.EVENT_MAX,
            callback=self._hook_proc,
        )

        if not self._hook_handle:
            log.error("Failed to install WinEvent hook!")
            win32.co_uninitialize()
            raise RuntimeError("SetWinEventHook failed")

        log.info("WinEvent hook installed (handle=%#x)", self._hook_handle)

        # Handle Ctrl+C gracefully
        def _signal_handler(sig: int, frame: object) -> None:
            log.info("Signal %d received, stopping...", sig)
            self.stop()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        # Phase 3: message loop
        self._running = True
        self._loop_thread_id = win32.get_current_thread_id()
        log.info(
            "Entering message loop (%d managed windows)", len(self._windows)
        )

        while self._running:
            got_msg, msg = win32.get_message()
            if not got_msg:
                break

            # Intercept WM_HOTKEY for the keybind system
            if msg.message == win32.WM_HOTKEY and self._hotkey_manager is not None:
                hotkey_id = msg.wParam
                self._hotkey_manager.dispatch(hotkey_id)
                continue

            win32.translate_and_dispatch(msg)

        # Cleanup
        self._cleanup()
        log.info("SauliethWM stopped.")

    def stop(self) -> None:
        """
        Request the event loop to stop.
        Safe to call from any thread or from within a callback.
        """
        self._running = False
        # PostThreadMessage with WM_QUIT to wake up GetMessage from any thread
        if self._loop_thread_id:
            win32.post_thread_message(
                self._loop_thread_id, win32.WM_QUIT, 0, 0
            )
        else:
            win32.post_quit_message(0)

    def _cleanup(self) -> None:
        """Unhook and release resources."""
        # Unregister all hotkeys
        if self._hotkey_manager is not None:
            self._hotkey_manager.unregister_all()

        if self._hook_handle:
            win32.unhook_win_event(self._hook_handle)
            self._hook_handle = 0
            log.info("WinEvent hook removed")

        self._hook_proc = None
        win32.co_uninitialize()

    # ------------------------------------------------------------------
    # Convenience: one-shot enumeration (no event loop)
    # ------------------------------------------------------------------
    @staticmethod
    def list_windows() -> list[Window]:
        """
        Enumerate all manageable windows right now, without starting
        the event loop.  Useful for debugging and scripting.
        """
        return enumerate_manageable_windows()

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------
    def dump_state(self) -> str:
        """Return a formatted string of all managed windows."""
        lines = [
            f"=== WindowManager: {len(self._windows)} managed windows ===",
            f"    Focused: {self._focused}",
            "",
        ]
        for w in self.windows:
            marker = " >> " if w == self._focused else "    "
            lines.append(f"{marker}{w}")
        return "\n".join(lines)
