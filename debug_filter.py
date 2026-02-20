"""
Diagnostic script: enumerate all visible top-level windows and show
why each one is accepted or rejected by the WM filter.

Run with:  python debug_filter.py
"""

import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

# Constants
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
DWMWA_CLOAKED = 14
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

from sauliethwm.core.filter import IGNORED_CLASSES, IGNORED_PROCESSES, IGNORED_TITLES


def get_text(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def get_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def get_pid(hwnd):
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def get_process_name(pid):
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        return "<unknown>"
    buf = ctypes.create_unicode_buffer(260)
    psapi.GetModuleBaseNameW(h, None, buf, 260)
    kernel32.CloseHandle(h)
    return buf.value


def is_cloaked(hwnd):
    val = ctypes.c_int(0)
    hr = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(val), ctypes.sizeof(val))
    return hr == 0 and val.value != 0


def get_rect(hwnd):
    r = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def diagnose(hwnd):
    """Return (accepted: bool, reason: str, info: dict)"""
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    exstyle = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    title = get_text(hwnd)
    cls = get_class(hwnd)
    pid = get_pid(hwnd)
    proc = get_process_name(pid)
    left, top, right, bottom = get_rect(hwnd)
    w = right - left
    h = bottom - top

    info = {
        "hwnd": f"0x{hwnd:08X}",
        "title": title,
        "class": cls,
        "process": proc,
        "pid": pid,
        "size": f"{w}x{h}",
        "pos": f"{left},{top}",
        "style": f"0x{style:08X}",
        "exstyle": f"0x{exstyle:08X}",
        "flags": [],
    }

    # Decode relevant flags
    if style & WS_VISIBLE: info["flags"].append("VISIBLE")
    if style & WS_CHILD: info["flags"].append("CHILD")
    if style & WS_CAPTION: info["flags"].append("CAPTION")
    if style & WS_THICKFRAME: info["flags"].append("THICKFRAME")
    if exstyle & WS_EX_TOOLWINDOW: info["flags"].append("TOOLWINDOW")
    if exstyle & WS_EX_APPWINDOW: info["flags"].append("APPWINDOW")
    if exstyle & WS_EX_NOACTIVATE: info["flags"].append("NOACTIVATE")
    if exstyle & WS_EX_TOPMOST: info["flags"].append("TOPMOST")

    # --- Apply filter pipeline ---
    if not user32.IsWindow(hwnd):
        return False, "INVALID", info

    if not (style & WS_VISIBLE):
        return False, "NOT_VISIBLE", info

    if is_cloaked(hwnd):
        return False, "CLOAKED", info

    if style & WS_CHILD:
        return False, "CHILD_WINDOW", info

    if cls in IGNORED_CLASSES:
        return False, f"IGNORED_CLASS({cls})", info

    if proc in IGNORED_PROCESSES:
        return False, f"IGNORED_PROCESS({proc})", info

    if title in IGNORED_TITLES:
        return False, f"IGNORED_TITLE({title!r})", info

    if (exstyle & WS_EX_TOOLWINDOW) and not (exstyle & WS_EX_APPWINDOW):
        return False, "TOOLWINDOW_NO_APPWINDOW", info

    if exstyle & WS_EX_NOACTIVATE:
        return False, "NOACTIVATE", info

    if w <= 0 and h <= 0:
        return False, "ZERO_SIZE", info

    shell = user32.GetShellWindow()
    desktop = user32.GetDesktopWindow()
    if hwnd == shell or hwnd == desktop:
        return False, "SHELL_OR_DESKTOP", info

    return True, "ACCEPTED", info


def main():
    hwnds = []

    def callback(hwnd, _):
        hwnds.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(callback), 0)

    accepted = []
    rejected = []

    for hwnd in hwnds:
        ok, reason, info = diagnose(hwnd)
        # Skip invisible and system noise
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        if not (style & WS_VISIBLE):
            continue
        if ok:
            accepted.append((reason, info))
        else:
            rejected.append((reason, info))

    print("=" * 80)
    print(f"  ACCEPTED WINDOWS ({len(accepted)})")
    print("=" * 80)
    for reason, info in accepted:
        print(f"  [{reason}] {info['process']:30s} | {info['title'][:50]}")
        print(f"           class={info['class']!r}  size={info['size']}  flags={','.join(info['flags'])}")
        print()

    print()
    print("=" * 80)
    print(f"  REJECTED VISIBLE WINDOWS ({len(rejected)})")
    print("=" * 80)
    for reason, info in rejected:
        print(f"  [{reason}] {info['process']:30s} | {info['title'][:50]}")
        print(f"           class={info['class']!r}  size={info['size']}  flags={','.join(info['flags'])}")
        print(f"           style={info['style']}  exstyle={info['exstyle']}")
        print()


if __name__ == "__main__":
    main()
