"""
sauliethwm.core.win32 - Low-level Win32 API bindings via ctypes.

Centralizes all Win32 API calls used by the window manager so that
no other module needs to import ctypes directly.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Callable

# ============================================================================
# DLL handles
# ============================================================================
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
dwmapi = ctypes.windll.dwmapi
ole32 = ctypes.windll.ole32

# ============================================================================
# Constants
# ============================================================================

# Window messages
WM_CLOSE = 0x0010

# ShowWindow commands
SW_HIDE = 0
SW_NORMAL = 1
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9

# GetWindowLong indices
GWL_STYLE = -16
GWL_EXSTYLE = -20

# Window styles
WS_VISIBLE = 0x10000000
WS_MINIMIZE = 0x20000000
WS_MAXIMIZE = 0x01000000
WS_CAPTION = 0x00C00000
WS_CHILD = 0x40000000
WS_DISABLED = 0x08000000
WS_POPUP = 0x80000000
WS_THICKFRAME = 0x00040000
WS_OVERLAPPEDWINDOW = 0x00CF0000

# Extended window styles
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

# DWM attributes
DWMWA_CLOAKED = 14

# Process access rights
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

# WinEvent constants
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_OBJECT_CREATE = 0x8000  # Misnamed in some docs - this is EVENT_OBJECT_SHOW for our purpose
EVENT_OBJECT_DESTROY = 0x8001
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_HIDE = 0x8003
EVENT_OBJECT_FOCUS = 0x8005
EVENT_SYSTEM_MINIMIZESTART = 0x0016
EVENT_SYSTEM_MINIMIZEEND = 0x0017
EVENT_OBJECT_LOCATIONCHANGE = 0x800B
EVENT_OBJECT_NAMECHANGE = 0x800C
EVENT_SYSTEM_MOVESIZESTART = 0x000A
EVENT_SYSTEM_MOVESIZEEND = 0x000B

# For SetWinEventHook range - capture everything we need
EVENT_MIN = 0x0003  # EVENT_SYSTEM_FOREGROUND
EVENT_MAX = 0x800C  # EVENT_OBJECT_NAMECHANGE

# Object identifiers
OBJID_WINDOW = 0
CHILDID_SELF = 0

# SetWindowPos flags
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
HWND_TOP = 0
HWND_NOTOPMOST = -2

# ============================================================================
# Callback types
# ============================================================================
EnumWindowsProc = ctypes.WINFUNCTYPE(
    ctypes.c_bool,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LPARAM,
)

# WinEventProc: void callback(HWINEVENTHOOK, DWORD, HWND, LONG, LONG, DWORD, DWORD)
WinEventProc = ctypes.WINFUNCTYPE(
    None,
    ctypes.wintypes.HANDLE,   # hWinEventHook
    ctypes.wintypes.DWORD,    # event
    ctypes.wintypes.HWND,     # hwnd
    ctypes.c_long,            # idObject
    ctypes.c_long,            # idChild
    ctypes.wintypes.DWORD,    # idEventThread
    ctypes.wintypes.DWORD,    # dwmsEventTime
)

# ============================================================================
# Wrapped API functions
# ============================================================================

def enum_windows(callback: Callable[[int, int], bool]) -> None:
    """Enumerate all top-level windows."""
    _cb = EnumWindowsProc(callback)
    user32.EnumWindows(_cb, 0)


def get_window_text(hwnd: int) -> str:
    """Get the title bar text of a window."""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def get_class_name(hwnd: int) -> str:
    """Get the window class name."""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def get_window_pid(hwnd: int) -> int:
    """Get the PID of the process that owns a window."""
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def get_process_name(pid: int) -> str:
    """Get the executable name of a process by PID."""
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid
    )
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(260)
        if psapi.GetModuleBaseNameW(handle, None, buf, 260):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) of the window."""
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)


def get_window_style(hwnd: int) -> int:
    """Return the WS_* style bits."""
    return user32.GetWindowLongW(hwnd, GWL_STYLE)


def get_window_ex_style(hwnd: int) -> int:
    """Return the WS_EX_* extended style bits."""
    return user32.GetWindowLongW(hwnd, GWL_EXSTYLE)


def is_window_visible(hwnd: int) -> bool:
    return bool(user32.IsWindowVisible(hwnd))


def is_window_iconic(hwnd: int) -> bool:
    """True if the window is minimized."""
    return bool(user32.IsIconic(hwnd))


def is_window_zoomed(hwnd: int) -> bool:
    """True if the window is maximized."""
    return bool(user32.IsZoomed(hwnd))


def is_window_valid(hwnd: int) -> bool:
    """True if the window handle is still valid."""
    return bool(user32.IsWindow(hwnd))


def is_window_cloaked(hwnd: int) -> bool:
    """
    True if the window is cloaked by DWM.
    UWP apps and virtual-desktop-hidden windows are cloaked.
    """
    cloaked = ctypes.c_int(0)
    hr = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return hr == 0 and cloaked.value != 0


def get_foreground_window() -> int:
    """Return the HWND of the current foreground window."""
    return user32.GetForegroundWindow()


def set_foreground_window(hwnd: int) -> bool:
    return bool(user32.SetForegroundWindow(hwnd))


def show_window(hwnd: int, cmd: int) -> bool:
    return bool(user32.ShowWindow(hwnd, cmd))


def post_message(hwnd: int, msg: int, wparam: int = 0, lparam: int = 0) -> bool:
    return bool(user32.PostMessageW(hwnd, msg, wparam, lparam))


def set_window_pos(
    hwnd: int,
    x: int,
    y: int,
    width: int,
    height: int,
    flags: int = SWP_NOZORDER | SWP_NOACTIVATE,
    insert_after: int = HWND_TOP,
) -> bool:
    """Move and resize a window."""
    return bool(
        user32.SetWindowPos(hwnd, insert_after, x, y, width, height, flags)
    )


def get_shell_window() -> int:
    """Return the HWND of the desktop (shell) window."""
    return user32.GetShellWindow()


def get_desktop_window() -> int:
    """Return the HWND of the desktop window."""
    return user32.GetDesktopWindow()


# ============================================================================
# WinEvent hook
# ============================================================================

def set_win_event_hook(
    event_min: int,
    event_max: int,
    callback: WinEventProc,  # type: ignore[type-arg]
    pid: int = 0,
    thread_id: int = 0,
    flags: int = WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
) -> int:
    """
    Install a WinEvent hook.  Returns a hook handle (0 on failure).
    The *callback* must be stored (prevent GC) for the lifetime of the hook.
    """
    return user32.SetWinEventHook(
        event_min, event_max, 0, callback, pid, thread_id, flags
    )


def unhook_win_event(hook_handle: int) -> bool:
    return bool(user32.UnhookWinEvent(hook_handle))


# ============================================================================
# Message loop helpers
# ============================================================================

def get_message() -> tuple[bool, ctypes.wintypes.MSG]:
    """
    Blocking call that retrieves one message from the thread queue.
    Returns (got_message, msg).  got_message is False on WM_QUIT.
    """
    msg = ctypes.wintypes.MSG()
    result = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
    return (result > 0, msg)


def translate_and_dispatch(msg: ctypes.wintypes.MSG) -> None:
    user32.TranslateMessage(ctypes.byref(msg))
    user32.DispatchMessageW(ctypes.byref(msg))


def post_quit_message(exit_code: int = 0) -> None:
    user32.PostQuitMessage(exit_code)


WM_QUIT = 0x0012


def post_thread_message(thread_id: int, msg: int, wparam: int = 0, lparam: int = 0) -> bool:
    """Post a message to a specific thread's message queue (cross-thread safe)."""
    return bool(user32.PostThreadMessageW(thread_id, msg, wparam, lparam))


def get_current_thread_id() -> int:
    """Get the current OS thread ID."""
    return kernel32.GetCurrentThreadId()


def co_initialize() -> None:
    """Initialize COM for this thread (needed for some shell interactions)."""
    ole32.CoInitialize(0)


def co_uninitialize() -> None:
    ole32.CoUninitialize()
