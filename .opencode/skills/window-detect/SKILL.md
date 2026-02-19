---
name: window-detect
description: > Detects, lists, and manages Windows windows using Python and the Win32 API. Trigger: When the user needs to find, list, filter, or manipulate open windows on Windows OS.
license: Apache-2.0
metadata:
  author: Saulieth
  version: "1.0.0"
  auto_invoke:
    - "Detecting windows"
    - "Listing open windows"
    - "Finding a specific window"
    - "Window management"
---

## Critical Rules

- ALWAYS use the `win32gui` and `win32process` APIs from `pywin32` for window detection
- ALWAYS handle cases where windows may close between enumeration and access
- ALWAYS filter out invisible and zero-size windows by default
- NEVER forcefully close or kill windows unless the user explicitly requests it
- NEVER modify window state (minimize, maximize, move) without user confirmation
- ALWAYS report window title, handle (HWND), PID, and visibility status

---

## Capabilities

| Capability | Description |
|------------|-------------|
| `list` | List all visible windows with title, HWND, and PID |
| `find` | Find windows by title substring or exact match |
| `filter` | Filter windows by process name, visibility, or class name |
| `info` | Get detailed info about a specific window (size, position, state) |
| `focus` | Bring a specific window to the foreground |
| `close` | Send a close message to a window (requires confirmation) |

---

## Dependencies

```
pywin32
```

Install with:
```bash
pip install pywin32
```

---

## Workflow

1. **Enumerate windows**
   - Use `win32gui.EnumWindows()` to iterate over all top-level windows
   - Filter out invisible windows (`win32gui.IsWindowVisible`)
   - Filter out windows with empty titles

2. **Collect window information**
   - HWND (window handle)
   - Window title (`win32gui.GetWindowText`)
   - Window class (`win32gui.GetClassName`)
   - Process ID (`win32process.GetWindowThreadProcessId`)
   - Window rect/position (`win32gui.GetWindowRect`)
   - Visibility and state

3. **Present results to user**
   - Display as a formatted table
   - Include HWND, Title, PID, Class, and Visibility
   - Sort by title alphabetically by default

4. **Perform actions if requested**
   - Focus: `win32gui.SetForegroundWindow(hwnd)`
   - Close: `win32gui.PostMessage(hwnd, WM_CLOSE, 0, 0)`
   - Get info: `win32gui.GetWindowRect(hwnd)`

---

## Decision Tree

```
User wants to see windows?
+-- Yes -> List all visible windows with details
+-- No
    +-- User wants to find a specific window?
    |   +-- By title -> Use find with title substring
    |   +-- By process -> Use filter with process name
    +-- User wants to act on a window?
        +-- Focus -> Bring to foreground
        +-- Close -> Confirm first, then send WM_CLOSE
        +-- Info -> Show position, size, state
```

---

## Python Function Reference

```python
import win32gui
import win32process
import psutil

def detect_windows(filter_title=None, only_visible=True):
    """
    Detect and list Windows windows.
    
    Args:
        filter_title: Optional substring to filter window titles
        only_visible: If True, only return visible windows (default: True)
    
    Returns:
        List of dicts with keys: hwnd, title, class_name, pid, process_name, rect, visible
    """
    windows = []
    
    def enum_callback(hwnd, _):
        if only_visible and not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        if filter_title and filter_title.lower() not in title.lower():
            return
        
        class_name = win32gui.GetClassName(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        try:
            process_name = psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "N/A"
        
        rect = win32gui.GetWindowRect(hwnd)
        
        windows.append({
            "hwnd": hwnd,
            "title": title,
            "class_name": class_name,
            "pid": pid,
            "process_name": process_name,
            "rect": rect,
            "visible": win32gui.IsWindowVisible(hwnd)
        })
    
    win32gui.EnumWindows(enum_callback, None)
    return sorted(windows, key=lambda w: w["title"].lower())
```

---

## Commands

```python
# List all visible windows
windows = detect_windows()

# Find windows by title
windows = detect_windows(filter_title="Chrome")

# Focus a window
win32gui.SetForegroundWindow(hwnd)

# Close a window (gracefully)
import win32con
win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)

# Get window position and size
left, top, right, bottom = win32gui.GetWindowRect(hwnd)
width = right - left
height = bottom - top
```
