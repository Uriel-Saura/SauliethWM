# SauliethWM

Un **tiling window manager** para Windows construido desde cero usando la Win32 API via ctypes.

## Caracteristicas

- **Deteccion automatica de ventanas**: Rastrea ventanas manejables en tiempo real, excluyendo automaticamente taskbar, desktop, system tray, UWP overlays, tooltips, y otras ventanas del sistema
- **Event loop basado en WinEventHook**: Recibe notificaciones en tiempo real cuando ventanas son creadas, destruidas, enfocadas, movidas, minimizadas o cambian de titulo
- **Arquitectura modular**: Sistema de eventos/callbacks para que modulos de alto nivel (layouts, keybindings, IPC) reaccionen sin conocer Win32
- **Sin dependencias externas**: Solo usa ctypes (standard library)

## Estado actual

**v0.1.0** - Nucleo del WM completado:
- ✅ Estructura `Window` con propiedades en vivo
- ✅ Filtrado avanzado de ventanas manejables
- ✅ `WindowManager` con event loop WinEventHook
- ✅ Sistema de callbacks para 7 tipos de eventos
- ✅ Pruebas de captura de eventos en tiempo real

## Como ejecutar

### Requisitos

- Python 3.10+ (usa `match`/`case` y type hints modernos)
- Windows 10/11
- Solo standard library (ctypes)

### Ejecucion

#### 1. Modo interactivo (con logging completo)

```bash
python -m sauliethwm
```

Esto iniciara el event loop principal y mostrara:
- Estado inicial de ventanas detectadas
- Logs de todos los eventos en tiempo real (focus, minimize, restore, title change, etc.)
- Presiona `Ctrl+C` para detener

**Ejemplo de salida:**

```
=== WindowManager: 6 managed windows ===
    Focused: [0x011704a8] 'Windows Terminal' ...

============================================================
  SauliethWM event loop running. Press Ctrl+C to stop.
============================================================

04:00:15.123 [INFO] MANAGE  [0x00020240] 'Firefox' ...
04:00:17.456 [DEBUG] FOCUS -> [0x00020476] 'Discord' ...
04:00:20.789 [DEBUG] TITLE [0x00020240] 'New Tab - Firefox' ...
```

#### 2. Test de eventos (8 segundos con auto-stop)

```bash
python test_events.py
```

Ejecuta el event loop por 8 segundos, captura eventos, y se detiene automaticamente. Util para verificar que el sistema funciona correctamente sin tener que detenerlo manualmente.

**Ejemplo de salida:**

```
  Event                      | HWND         | Title
  ----------------------------------------------------------------------
  [04:00:15] focus_changed        | 0x00020240 | Firefox
  [04:00:17] title_changed        | 0x00020240 | New Tab - Firefox
  [04:00:20] window_minimized     | 0x00020476 | Discord

  [Timer] 8 seconds elapsed, stopping...

  Final state: 6 managed windows
  Done.
```

#### 3. Listado de ventanas (sin event loop)

```python
from sauliethwm.core import WindowManager

# Enumera ventanas manejables sin iniciar el loop
windows = WindowManager.list_windows()

for w in windows:
    print(f"{w.hwnd:#010x} | {w.title} | {w.process_name} | {w.state.value}")
```

## Arquitectura

```
sauliethwm/
├── core/
│   ├── win32.py      # Bindings Win32 API (ctypes)
│   ├── window.py     # Estructura Window (propiedades en vivo)
│   ├── filter.py     # Reglas de filtrado de ventanas manejables
│   └── manager.py    # WindowManager + event loop WinEventHook
├── __init__.py
└── __main__.py       # Entry point
```

### Componentes principales

#### `Window` (window.py)
Envuelve un HWND. Todas las propiedades (`title`, `rect`, `state`, `style`) son **lecturas en vivo** contra Win32 API. Acciones: `focus()`, `minimize()`, `maximize()`, `restore()`, `close()`, `move_resize()`.

#### `filter.py`
Funcion `is_manageable()` con 10 reglas para decidir si una ventana debe gestionarse:
- **Excluye**: Taskbar, Desktop, System Tray, UWP overlays, tooltips, IME, ventanas tool, ventanas hijo, ventanas cloaked, procesos del sistema
- **Incluye**: Ventanas visibles, con titulo, tamano > 0, top-level, activables

#### `WindowManager` (manager.py)
Corazon del WM:
- `start()`: Escanea ventanas existentes → instala `SetWinEventHook` → entra al message loop
- **Eventos capturados**: `SHOW`, `DESTROY`, `HIDE`, `FOREGROUND`, `FOCUS`, `MINIMIZE`, `MOVESIZE`, `NAMECHANGE`
- **Sistema de callbacks**: 7 tipos de evento para que otros modulos reaccionen
- `stop()`: Cross-thread safe via `PostThreadMessage(WM_QUIT)`

## Eventos soportados

| Evento | Descripcion |
|--------|-------------|
| `WINDOW_ADDED` | Una nueva ventana manejable aparecio |
| `WINDOW_REMOVED` | Una ventana fue destruida o se volvio no-manejable |
| `FOCUS_CHANGED` | La ventana con foco cambio |
| `WINDOW_MINIMIZED` | Una ventana fue minimizada |
| `WINDOW_RESTORED` | Una ventana fue restaurada |
| `WINDOW_MOVED` | Una ventana fue movida o redimensionada |
| `TITLE_CHANGED` | El titulo de una ventana cambio |

## Uso programatico

```python
from sauliethwm.core import WindowManager, WMEvent

def on_focus_change(event, window, wm):
    print(f"Nueva ventana enfocada: {window.title}")

def on_window_added(event, window, wm):
    print(f"Ventana nueva detectada: {window}")

wm = WindowManager()

# Suscribirse a eventos especificos
wm.on(WMEvent.FOCUS_CHANGED, on_focus_change)
wm.on(WMEvent.WINDOW_ADDED, on_window_added)

# O suscribirse a todos los eventos
wm.on_all(lambda event, window, wm: print(f"Evento: {event.value}"))

# Iniciar el event loop (bloquea hasta wm.stop())
wm.start()
```

## Proximos pasos

- [ ] Motor de layouts (tiling, floating, monocle)
- [ ] Sistema de keybindings (hotkeys globales)
- [ ] Configuracion via archivo TOML
- [ ] IPC para comunicacion con scripts externos
- [ ] Workspace/tags virtuales
- [ ] Status bar integration

## Licencia

Apache-2.0

## Autor

Saulieth
