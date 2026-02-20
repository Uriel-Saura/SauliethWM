"""
sauliethwm.core.spawn - Lanzar aplicaciones desde el WM.

Proporciona una funcion spawn() que ejecuta un programa usando
subprocess.Popen. Si el ejecutable no existe o falla el lanzamiento,
se muestra una notificacion toast de Windows en lugar de crashear.

Uso tipico (desde config):
    "win+return" = "spawn wt.exe"
    "win+d"      = "spawn explorer.exe"

La notificacion toast usa la API nativa de Windows via ctypes
para no depender de paquetes externos.
"""

from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
import threading
from typing import Optional

from sauliethwm.core import win32

log = logging.getLogger(__name__)


def spawn(command: str) -> Optional[subprocess.Popen]:
    """
    Launch an application from the WM.

    The command string is split using shell lexing rules:
        "wt.exe"           -> ["wt.exe"]
        "code ."           -> ["code", "."]
        'explorer "C:\\foo"' -> ["explorer", "C:\\foo"]

    If the executable is not found on PATH or the process fails to
    start, a Windows toast notification is shown and None is returned.

    Args:
        command: The command string to execute.

    Returns:
        The Popen object if launched successfully, None on failure.
    """
    if not command or not command.strip():
        log.warning("spawn: empty command")
        _show_toast("SauliethWM", "spawn: empty command")
        return None

    try:
        args = shlex.split(command, posix=False)
    except ValueError as e:
        log.error("spawn: failed to parse command %r: %s", command, e)
        _show_toast("SauliethWM", f"Invalid command: {command}")
        return None

    if not args:
        log.warning("spawn: no arguments after parsing %r", command)
        _show_toast("SauliethWM", f"Empty command: {command}")
        return None

    executable = args[0]

    # Check if executable exists on PATH (best-effort)
    resolved = shutil.which(executable)
    if resolved is None:
        log.error("spawn: executable not found: %r", executable)
        _show_toast(
            "SauliethWM",
            f"Executable not found: {executable}",
        )
        return None

    try:
        proc = subprocess.Popen(
            args,
            # Detach from our console so the child survives WM restart
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
            # Don't inherit our stdin/stdout/stderr
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info("spawn: launched %r (PID %d)", command, proc.pid)
        return proc

    except OSError as e:
        log.error("spawn: failed to launch %r: %s", command, e)
        _show_toast("SauliethWM", f"Failed to launch: {executable}\n{e}")
        return None
    except Exception as e:
        log.exception("spawn: unexpected error launching %r", command)
        _show_toast("SauliethWM", f"Error launching: {executable}\n{e}")
        return None


def spawn_async(command: str) -> None:
    """
    Launch an application in a background thread.

    This is the preferred entry point for hotkey callbacks, as it
    avoids blocking the message loop during process creation.
    """
    thread = threading.Thread(
        target=spawn,
        args=(command,),
        daemon=True,
        name=f"spawn-{command}",
    )
    thread.start()


# ============================================================================
# Toast notification (Windows native)
# ============================================================================

def _show_toast(title: str, message: str) -> None:
    """
    Show a Windows balloon/toast notification.

    Uses the Shell_NotifyIcon API via ctypes for a lightweight
    notification without external dependencies. Falls back to
    log-only if the notification fails.
    """
    try:
        _show_balloon_notification(title, message)
    except Exception:
        # Fallback: just log it (don't crash the WM over a notification)
        log.warning("Toast notification failed: %s - %s", title, message)


def _show_balloon_notification(title: str, message: str) -> None:
    """
    Show a system tray balloon notification using Shell_NotifyIconW.

    This creates a temporary invisible tray icon, shows the balloon,
    and removes the icon after a short delay.
    """
    import ctypes
    import ctypes.wintypes
    import time

    # Shell_NotifyIcon constants
    NIM_ADD = 0x00000000
    NIM_MODIFY = 0x00000001
    NIM_DELETE = 0x00000002
    NIF_ICON = 0x00000002
    NIF_TIP = 0x00000004
    NIF_INFO = 0x00000010
    NIIF_INFO = 0x00000001

    shell32 = ctypes.windll.shell32

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.DWORD),
            ("hWnd", ctypes.wintypes.HWND),
            ("uID", ctypes.wintypes.UINT),
            ("uFlags", ctypes.wintypes.UINT),
            ("uCallbackMessage", ctypes.wintypes.UINT),
            ("hIcon", ctypes.wintypes.HICON),
            ("szTip", ctypes.c_wchar * 128),
            ("dwState", ctypes.wintypes.DWORD),
            ("dwStateMask", ctypes.wintypes.DWORD),
            ("szInfo", ctypes.c_wchar * 256),
            ("uVersion", ctypes.wintypes.UINT),
            ("szInfoTitle", ctypes.c_wchar * 64),
            ("dwInfoFlags", ctypes.wintypes.DWORD),
        ]

    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = 0
    nid.uID = 99999  # Unique ID for our notifications
    nid.uFlags = NIF_ICON | NIF_TIP | NIF_INFO
    nid.hIcon = ctypes.windll.user32.LoadIconW(0, 32516)  # IDI_WARNING
    nid.szTip = "SauliethWM"
    nid.szInfo = message[:255]
    nid.szInfoTitle = title[:63]
    nid.dwInfoFlags = NIIF_INFO

    # Add icon (creates it)
    shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    # Show balloon
    shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    # Remove after a short delay (in a thread to not block)
    def _cleanup():
        time.sleep(5)
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

    cleanup_thread = threading.Thread(target=_cleanup, daemon=True)
    cleanup_thread.start()
