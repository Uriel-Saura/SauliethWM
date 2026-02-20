"""
sauliethwm.core.combo_parser - Parser de combos de teclado.

Convierte strings legibles como "win+shift+q" en los argumentos
(modifiers, vk) que necesita RegisterHotKey / HotkeyManager.register().

Caracteristicas:
    - Aliases: win = super = windows, ctrl = control, alt = menu.
    - Case-insensitive: "Win+Shift+Q" == "win+shift+q".
    - Validacion: error claro si el combo es invalido.
    - Deteccion de duplicados via HotkeyManager.find_by_combo().
"""

from __future__ import annotations

import logging

from sauliethwm.core import win32

log = logging.getLogger(__name__)


# ============================================================================
# Modifier aliases -> modifier flag
# ============================================================================
_MODIFIER_MAP: dict[str, int] = {
    "alt": win32.MOD_ALT,
    "menu": win32.MOD_ALT,
    "ctrl": win32.MOD_CONTROL,
    "control": win32.MOD_CONTROL,
    "shift": win32.MOD_SHIFT,
    "win": win32.MOD_WIN,
    "super": win32.MOD_WIN,
    "windows": win32.MOD_WIN,
    "mod": win32.MOD_WIN,
}


# ============================================================================
# Virtual key name -> VK code
# ============================================================================
_VK_MAP: dict[str, int] = {}


def _build_vk_map() -> None:
    """Populate the VK name map on first use."""
    if _VK_MAP:
        return

    # Letters A-Z (VK 0x41 - 0x5A)
    for i in range(26):
        ch = chr(ord("a") + i)
        _VK_MAP[ch] = 0x41 + i

    # Digits 0-9 (VK 0x30 - 0x39)
    for i in range(10):
        _VK_MAP[str(i)] = 0x30 + i

    # Function keys F1-F24
    for i in range(1, 25):
        _VK_MAP[f"f{i}"] = 0x70 + (i - 1)  # VK_F1 = 0x70

    # Special keys
    _VK_MAP.update(
        {
            "return": 0x0D,
            "enter": 0x0D,
            "escape": 0x1B,
            "esc": 0x1B,
            "space": 0x20,
            "tab": 0x09,
            "backspace": 0x08,
            "delete": 0x2E,
            "del": 0x2E,
            "insert": 0x2D,
            "ins": 0x2D,
            "home": 0x24,
            "end": 0x23,
            "pageup": 0x21,
            "pgup": 0x21,
            "pagedown": 0x22,
            "pgdn": 0x22,
            # Arrow keys
            "left": 0x25,
            "up": 0x26,
            "right": 0x27,
            "down": 0x28,
            # Numpad
            "numpad0": 0x60,
            "numpad1": 0x61,
            "numpad2": 0x62,
            "numpad3": 0x63,
            "numpad4": 0x64,
            "numpad5": 0x65,
            "numpad6": 0x66,
            "numpad7": 0x67,
            "numpad8": 0x68,
            "numpad9": 0x69,
            "multiply": 0x6A,
            "add": 0x6B,
            "subtract": 0x6D,
            "decimal": 0x6E,
            "divide": 0x6F,
            # OEM keys
            "semicolon": 0xBA,
            "equals": 0xBB,
            "comma": 0xBC,
            "minus": 0xBD,
            "period": 0xBE,
            "slash": 0xBF,
            "backquote": 0xC0,
            "tilde": 0xC0,
            "bracketleft": 0xDB,
            "backslash": 0xDC,
            "bracketright": 0xDD,
            "quote": 0xDE,
            # Media / browser
            "volumemute": 0xAD,
            "volumedown": 0xAE,
            "volumeup": 0xAF,
            "printscreen": 0x2C,
            "print": 0x2C,
            "pause": 0x13,
            "capslock": 0x14,
            "numlock": 0x90,
            "scrolllock": 0x91,
        }
    )


# ============================================================================
# Public API
# ============================================================================

class ComboParseError(ValueError):
    """Raised when a combo string cannot be parsed."""
    pass


def parse_combo(combo: str) -> tuple[int, int]:
    """
    Parse a keyboard combo string into (modifiers, vk) for RegisterHotKey.

    Args:
        combo: Human-readable combo like "win+shift+q", "alt+1",
               "ctrl+alt+delete". Case-insensitive. Parts separated by '+'.

    Returns:
        Tuple of (modifiers_flags, virtual_key_code).

    Raises:
        ComboParseError: If the combo is empty, has no key part, contains
                         unknown tokens, or has duplicate modifiers.
    """
    _build_vk_map()

    if not combo or not combo.strip():
        raise ComboParseError("Empty combo string")

    parts = [p.strip().lower() for p in combo.split("+")]
    parts = [p for p in parts if p]  # remove empty from "win + + q"

    if not parts:
        raise ComboParseError(f"No valid parts in combo: {combo!r}")

    modifiers = 0
    vk: int | None = None
    seen_mods: set[str] = set()

    for part in parts:
        if part in _MODIFIER_MAP:
            # It's a modifier
            canonical = _get_canonical_modifier(part)
            if canonical in seen_mods:
                raise ComboParseError(
                    f"Duplicate modifier {part!r} in combo: {combo!r}"
                )
            seen_mods.add(canonical)
            modifiers |= _MODIFIER_MAP[part]
        elif part in _VK_MAP:
            # It's a key
            if vk is not None:
                raise ComboParseError(
                    f"Multiple key parts in combo: {combo!r}. "
                    f"Only one non-modifier key is allowed."
                )
            vk = _VK_MAP[part]
        else:
            raise ComboParseError(
                f"Unknown key or modifier: {part!r} in combo: {combo!r}"
            )

    if vk is None:
        raise ComboParseError(
            f"No key found in combo: {combo!r}. "
            f"A combo must have exactly one non-modifier key."
        )

    return modifiers, vk


def combo_to_str(modifiers: int, vk: int) -> str:
    """
    Convert (modifiers, vk) back to a human-readable string.

    Useful for logging and error messages.
    """
    _build_vk_map()

    parts: list[str] = []
    if modifiers & win32.MOD_WIN:
        parts.append("Win")
    if modifiers & win32.MOD_CONTROL:
        parts.append("Ctrl")
    if modifiers & win32.MOD_ALT:
        parts.append("Alt")
    if modifiers & win32.MOD_SHIFT:
        parts.append("Shift")

    # Reverse-lookup VK name
    vk_name = None
    for name, code in _VK_MAP.items():
        if code == vk:
            vk_name = name.upper() if len(name) == 1 else name.capitalize()
            break

    if vk_name is None:
        vk_name = f"0x{vk:02X}"

    parts.append(vk_name)
    return "+".join(parts)


def is_valid_combo(combo: str) -> bool:
    """Check if a combo string is valid without raising."""
    try:
        parse_combo(combo)
        return True
    except ComboParseError:
        return False


# ============================================================================
# Internal helpers
# ============================================================================

def _get_canonical_modifier(alias: str) -> str:
    """
    Map a modifier alias to its canonical name for duplicate detection.

    e.g. "ctrl", "control" -> "control"
         "win", "super", "windows" -> "win"
    """
    flag = _MODIFIER_MAP.get(alias.lower(), 0)
    if flag == win32.MOD_ALT:
        return "alt"
    if flag == win32.MOD_CONTROL:
        return "control"
    if flag == win32.MOD_SHIFT:
        return "shift"
    if flag == win32.MOD_WIN:
        return "win"
    return alias
