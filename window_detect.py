"""
window_detect.py - Deteccion y gestion de ventanas de Windows

Utiliza la API Win32 para enumerar, filtrar y manipular ventanas
del sistema operativo Windows.

Dependencias:
    pip install pywin32 psutil

Autor: Saulieth
Version: 1.0.0
"""

import ctypes
import ctypes.wintypes
from dataclasses import dataclass, field
from typing import Optional

# --- Win32 API constants ---
WM_CLOSE = 0x0010
SW_RESTORE = 9
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_VISIBLE = 0x10000000
WS_MINIMIZE = 0x20000000
WS_MAXIMIZE = 0x01000000
DWMWA_CLOAKED = 14

# --- ctypes function signatures ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(
    ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
)
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
GetClassNameW = user32.GetClassNameW
IsWindowVisible = user32.IsWindowVisible
GetWindowRect = user32.GetWindowRect
GetWindowLongW = user32.GetWindowLongW
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
SetForegroundWindow = user32.SetForegroundWindow
ShowWindow = user32.ShowWindow
PostMessageW = user32.PostMessageW
IsIconic = user32.IsIconic
IsZoomed = user32.IsZoomed

OpenProcess = kernel32.OpenProcess
CloseHandle = kernel32.CloseHandle
GetModuleBaseNameW = psapi.GetModuleBaseNameW

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


# --- Data classes ---
@dataclass
class WindowInfo:
    """Informacion de una ventana de Windows."""

    hwnd: int
    title: str
    class_name: str
    pid: int
    process_name: str
    rect: tuple[int, int, int, int]  # (left, top, right, bottom)
    visible: bool
    minimized: bool
    maximized: bool

    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]

    @property
    def position(self) -> tuple[int, int]:
        return (self.rect[0], self.rect[1])

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    def __str__(self) -> str:
        state = "minimized" if self.minimized else "maximized" if self.maximized else "normal"
        return (
            f"[{self.hwnd:#010x}] {self.title!r} | "
            f"PID: {self.pid} ({self.process_name}) | "
            f"Class: {self.class_name} | "
            f"State: {state} | "
            f"Rect: {self.rect}"
        )


# --- Helper functions ---
def _get_window_text(hwnd: int) -> str:
    """Obtiene el titulo de una ventana."""
    length = GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _get_class_name(hwnd: int) -> str:
    """Obtiene el nombre de clase de una ventana."""
    buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, buf, 256)
    return buf.value


def _get_pid(hwnd: int) -> int:
    """Obtiene el PID del proceso dueno de la ventana."""
    pid = ctypes.wintypes.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _get_process_name(pid: int) -> str:
    """Obtiene el nombre del proceso a partir de su PID."""
    handle = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return "N/A"
    try:
        buf = ctypes.create_unicode_buffer(260)
        result = GetModuleBaseNameW(handle, None, buf, 260)
        return buf.value if result else "N/A"
    finally:
        CloseHandle(handle)


def _get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Obtiene el rectangulo de la ventana (left, top, right, bottom)."""
    rect = ctypes.wintypes.RECT()
    GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)


def _is_real_window(hwnd: int) -> bool:
    """
    Filtra ventanas falsas (tooltips, ventanas ocultas del sistema, etc).
    Retorna True si la ventana es una ventana 'real' del usuario.
    """
    if not IsWindowVisible(hwnd):
        return False

    title = _get_window_text(hwnd)
    if not title or not title.strip():
        return False

    # Filtrar ventanas con tamano cero
    rect = _get_window_rect(hwnd)
    width = rect[2] - rect[0]
    height = rect[3] - rect[1]
    if width <= 0 and height <= 0:
        return False

    # Verificar si la ventana esta cloaked (oculta por DWM, comun en UWP)
    try:
        dwm = ctypes.windll.dwmapi
        cloaked = ctypes.c_int(0)
        hr = dwm.DwmGetWindowAttribute(
            hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
        if hr == 0 and cloaked.value != 0:
            return False
    except (OSError, AttributeError):
        pass

    return True


# --- Core functions ---
def detect_windows(
    filter_title: Optional[str] = None,
    filter_process: Optional[str] = None,
    filter_class: Optional[str] = None,
    only_visible: bool = True,
    include_minimized: bool = True,
) -> list[WindowInfo]:
    """
    Detecta y lista ventanas abiertas en Windows.

    Args:
        filter_title: Substring para filtrar por titulo de ventana (case-insensitive).
        filter_process: Substring para filtrar por nombre de proceso (case-insensitive).
        filter_class: Substring para filtrar por nombre de clase (case-insensitive).
        only_visible: Si True, solo retorna ventanas visibles y reales. Default: True.
        include_minimized: Si True, incluye ventanas minimizadas. Default: True.

    Returns:
        Lista de WindowInfo ordenada alfabeticamente por titulo.
    """
    windows: list[WindowInfo] = []

    def _enum_callback(hwnd: int, _lparam: int) -> bool:
        # Filtro base: ventanas reales
        if only_visible and not _is_real_window(hwnd):
            return True

        # No filtrar por visibilidad
        if not only_visible:
            title = _get_window_text(hwnd)
            if not title:
                return True
        else:
            title = _get_window_text(hwnd)

        minimized = bool(IsIconic(hwnd))

        # Filtro de minimizadas
        if not include_minimized and minimized:
            return True

        # Filtro por titulo
        if filter_title and filter_title.lower() not in title.lower():
            return True

        class_name = _get_class_name(hwnd)

        # Filtro por clase
        if filter_class and filter_class.lower() not in class_name.lower():
            return True

        pid = _get_pid(hwnd)
        process_name = _get_process_name(pid)

        # Filtro por proceso
        if filter_process and filter_process.lower() not in process_name.lower():
            return True

        rect = _get_window_rect(hwnd)
        maximized = bool(IsZoomed(hwnd))

        windows.append(
            WindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                pid=pid,
                process_name=process_name,
                rect=rect,
                visible=bool(IsWindowVisible(hwnd)),
                minimized=minimized,
                maximized=maximized,
            )
        )
        return True

    EnumWindows(EnumWindowsProc(_enum_callback), 0)
    return sorted(windows, key=lambda w: w.title.lower())


def find_window(title: str, exact: bool = False) -> Optional[WindowInfo]:
    """
    Encuentra una ventana por su titulo.

    Args:
        title: Titulo a buscar.
        exact: Si True, busca coincidencia exacta. Si False, busca substring.

    Returns:
        WindowInfo si se encontro, None si no.
    """
    windows = detect_windows(filter_title=None if exact else title)

    if exact:
        for w in windows:
            if w.title == title:
                return w
        return None

    return windows[0] if windows else None


def focus_window(hwnd: int) -> bool:
    """
    Trae una ventana al frente (foreground).

    Args:
        hwnd: Handle de la ventana.

    Returns:
        True si se logro enfocar, False si fallo.
    """
    try:
        if IsIconic(hwnd):
            ShowWindow(hwnd, SW_RESTORE)
        result = SetForegroundWindow(hwnd)
        return bool(result)
    except OSError:
        return False


def close_window(hwnd: int) -> bool:
    """
    Envia un mensaje WM_CLOSE a la ventana (cierre graceful).

    Args:
        hwnd: Handle de la ventana.

    Returns:
        True si se envio el mensaje, False si fallo.
    """
    try:
        result = PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return bool(result)
    except OSError:
        return False


def get_window_info(hwnd: int) -> Optional[WindowInfo]:
    """
    Obtiene informacion detallada de una ventana especifica.

    Args:
        hwnd: Handle de la ventana.

    Returns:
        WindowInfo si la ventana existe, None si no.
    """
    title = _get_window_text(hwnd)
    if not title:
        return None

    return WindowInfo(
        hwnd=hwnd,
        title=title,
        class_name=_get_class_name(hwnd),
        pid=_get_pid(hwnd),
        process_name=_get_process_name(_get_pid(hwnd)),
        rect=_get_window_rect(hwnd),
        visible=bool(IsWindowVisible(hwnd)),
        minimized=bool(IsIconic(hwnd)),
        maximized=bool(IsZoomed(hwnd)),
    )


def print_windows(windows: list[WindowInfo]) -> None:
    """Imprime una tabla formateada de ventanas."""
    import sys

    if not windows:
        print("No se encontraron ventanas.")
        return

    # Header
    print(f"{'HWND':<14} {'PID':<8} {'Process':<25} {'State':<12} {'Title'}")
    print("-" * 100)

    for w in windows:
        state = (
            "minimized" if w.minimized else "maximized" if w.maximized else "normal"
        )
        title_display = w.title[:50] + "..." if len(w.title) > 50 else w.title
        # Encode safely for consoles that don't support all Unicode chars
        title_safe = title_display.encode(
            sys.stdout.encoding or "utf-8", errors="replace"
        ).decode(sys.stdout.encoding or "utf-8", errors="replace")
        print(
            f"{w.hwnd:#010x}     {w.pid:<8} {w.process_name:<25} {state:<12} {title_safe}"
        )

    print(f"\nTotal: {len(windows)} ventana(s)")


# --- Main ---
if __name__ == "__main__":
    print("=== Deteccion de Ventanas de Windows ===\n")

    # Listar todas las ventanas visibles
    print("[*] Listando todas las ventanas visibles...\n")
    all_windows = detect_windows()
    print_windows(all_windows)

    # Ejemplo: buscar ventanas de un proceso especifico
    print("\n[*] Buscando ventanas de 'explorer.exe'...\n")
    explorer_windows = detect_windows(filter_process="explorer")
    print_windows(explorer_windows)
