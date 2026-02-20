"""
sauliethwm.core.commands - Dispatcher de comandos internos.

Mapea nombres de comandos en string a metodos del WM, permitiendo
que archivos de configuracion usen strings como "close_window" o
"next_layout" sin hardcodear la relacion en multiples lugares.

El CommandDispatcher es el registro central:
    dispatcher = CommandDispatcher()
    dispatcher.register("close_window", wm_close_focused)
    dispatcher.register("next_layout", ws_next_layout)
    dispatcher.execute("close_window")

Tambien se puede usar como decorador:
    @dispatcher.command("close_window")
    def close_window():
        ...
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


# Type for command functions: called with no arguments
CommandFn = Callable[[], None]


@dataclass(frozen=True, slots=True)
class Command:
    """Metadata for a registered command."""

    name: str
    fn: CommandFn
    description: str
    category: str


class CommandDispatcher:
    """
    Registry that maps command name strings to callable functions.

    This decouples config files from the actual WM methods: the config
    uses "close_window" and the dispatcher resolves it at runtime.
    """

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    @property
    def count(self) -> int:
        return len(self._commands)

    @property
    def command_names(self) -> list[str]:
        """All registered command names, sorted."""
        return sorted(self._commands.keys())

    def register(
        self,
        name: str,
        fn: CommandFn,
        description: str = "",
        category: str = "general",
    ) -> None:
        """
        Register a command by name.

        If a command with the same name already exists, it is replaced
        (useful for hot-reload).

        Args:
            name:        Unique command name (e.g. "close_window").
            fn:          The callable to invoke.
            description: Human-readable description.
            category:    Grouping category (e.g. "focus", "layout", "window").
        """
        if name in self._commands:
            log.info("Command replaced: %s", name)

        self._commands[name] = Command(
            name=name,
            fn=fn,
            description=description,
            category=category,
        )
        log.debug("Command registered: %s (%s)", name, category)

    def unregister(self, name: str) -> bool:
        """Remove a command by name. Returns True if it existed."""
        cmd = self._commands.pop(name, None)
        if cmd is not None:
            log.debug("Command unregistered: %s", name)
            return True
        return False

    def execute(self, name: str) -> bool:
        """
        Execute a command by name.

        Args:
            name: The command name to execute.

        Returns:
            True if the command was found and executed successfully.
        """
        cmd = self._commands.get(name)
        if cmd is None:
            log.warning("Unknown command: %s", name)
            return False

        log.debug("Executing command: %s", name)
        try:
            cmd.fn()
        except Exception:
            log.exception("Error executing command: %s", name)
            return False

        return True

    def get(self, name: str) -> Command | None:
        """Look up a command by name."""
        return self._commands.get(name)

    def has(self, name: str) -> bool:
        """Check if a command is registered."""
        return name in self._commands

    def command(
        self,
        name: str,
        description: str = "",
        category: str = "general",
    ) -> Callable[[CommandFn], CommandFn]:
        """
        Decorator to register a function as a command.

        Usage:
            @dispatcher.command("close_window", category="window")
            def close_window():
                ...
        """

        def decorator(fn: CommandFn) -> CommandFn:
            self.register(name, fn, description=description, category=category)
            return fn

        return decorator

    def list_commands(self, category: str | None = None) -> list[Command]:
        """
        List all registered commands, optionally filtered by category.

        Args:
            category: If given, only return commands in this category.

        Returns:
            Sorted list of Command objects.
        """
        commands = list(self._commands.values())
        if category is not None:
            commands = [c for c in commands if c.category == category]
        return sorted(commands, key=lambda c: c.name)

    def dump_state(self) -> str:
        """Return a formatted string of all commands for debugging."""
        lines = [
            f"=== CommandDispatcher: {len(self._commands)} commands ===",
            "",
        ]
        for cmd in self.list_commands():
            desc = f"  {cmd.description}" if cmd.description else ""
            lines.append(f"  [{cmd.category}] {cmd.name}{desc}")
        return "\n".join(lines)


def build_default_commands(
    dispatcher: CommandDispatcher,
    wm: object,
    ws_manager: object,
) -> None:
    """
    Register all built-in commands into the dispatcher.

    This is the single place that maps command name strings to actual
    WM/WorkspaceManager methods. Called during startup.

    Args:
        dispatcher:  The CommandDispatcher to populate.
        wm:          The WindowManager instance.
        ws_manager:  The WorkspaceManager instance.
    """
    from sauliethwm.core.manager import WindowManager
    from sauliethwm.tiling.workspace_manager import WorkspaceManager

    assert isinstance(wm, WindowManager)
    assert isinstance(ws_manager, WorkspaceManager)

    # -- Window commands -----------------------------------------------
    @dispatcher.command("close_window", description="Close focused window", category="window")
    def close_window() -> None:
        focused = wm.focused
        if focused is not None:
            focused.close()

    @dispatcher.command("minimize_window", description="Minimize focused window", category="window")
    def minimize_window() -> None:
        focused = wm.focused
        if focused is not None:
            focused.minimize()

    @dispatcher.command("maximize_window", description="Maximize focused window", category="window")
    def maximize_window() -> None:
        focused = wm.focused
        if focused is not None:
            focused.maximize()

    @dispatcher.command("restore_window", description="Restore focused window", category="window")
    def restore_window() -> None:
        focused = wm.focused
        if focused is not None:
            focused.restore()

    # -- Layout commands -----------------------------------------------
    @dispatcher.command("next_layout", description="Switch to next layout", category="layout")
    def next_layout() -> None:
        ws = ws_manager.get_active_workspace()
        ws.next_layout()
        ws_manager.retile()

    @dispatcher.command("prev_layout", description="Switch to previous layout", category="layout")
    def prev_layout() -> None:
        ws = ws_manager.get_active_workspace()
        ws.prev_layout()
        ws_manager.retile()

    # -- Stack commands ------------------------------------------------
    @dispatcher.command("swap_master", description="Swap focused with master", category="stack")
    def swap_master() -> None:
        focused = wm.focused
        if focused is None:
            return
        ws = ws_manager.find_window_workspace(focused)
        if ws is None:
            return
        ws.swap_with_master(focused)
        mi = ws_manager.get_monitor_for_workspace(ws.id)
        if mi is not None:
            ws_manager.retile(mi)

    @dispatcher.command("rotate_next", description="Rotate window stack forward", category="stack")
    def rotate_next() -> None:
        ws = ws_manager.get_active_workspace()
        ws.rotate_next()
        ws_manager.retile()

    @dispatcher.command("rotate_prev", description="Rotate window stack backward", category="stack")
    def rotate_prev() -> None:
        ws = ws_manager.get_active_workspace()
        ws.rotate_prev()
        ws_manager.retile()

    # -- Resize commands -----------------------------------------------
    @dispatcher.command("grow_master", description="Increase master area ratio", category="resize")
    def grow_master() -> None:
        ws = ws_manager.get_active_workspace()
        ws.grow_master()
        ws_manager.retile()

    @dispatcher.command("shrink_master", description="Decrease master area ratio", category="resize")
    def shrink_master() -> None:
        ws = ws_manager.get_active_workspace()
        ws.shrink_master()
        ws_manager.retile()

    @dispatcher.command("increase_gap", description="Increase gap between windows", category="resize")
    def increase_gap() -> None:
        ws = ws_manager.get_active_workspace()
        ws.increase_gap()
        ws_manager.retile()

    @dispatcher.command("decrease_gap", description="Decrease gap between windows", category="resize")
    def decrease_gap() -> None:
        ws = ws_manager.get_active_workspace()
        ws.decrease_gap()
        ws_manager.retile()

    # -- Workspace switch commands (1-9) --------------------------------
    for i in range(1, 10):
        def _make_switch(ws_id: int) -> CommandFn:
            def _switch() -> None:
                ws_manager.switch_workspace(ws_id, monitor_index=0)
            return _switch

        dispatcher.register(
            f"switch_workspace_{i}",
            _make_switch(i),
            description=f"Switch to workspace {i}",
            category="workspace",
        )

    # -- Move window to workspace (1-9) --------------------------------
    for i in range(1, 10):
        def _make_move(ws_id: int) -> CommandFn:
            def _move() -> None:
                focused = wm.focused
                if focused is not None:
                    ws_manager.move_window_to_workspace(focused, ws_id)
            return _move

        dispatcher.register(
            f"move_to_workspace_{i}",
            _make_move(i),
            description=f"Move focused window to workspace {i}",
            category="workspace",
        )

    # -- Monitor commands ----------------------------------------------
    @dispatcher.command("move_to_next_monitor", description="Move window to next monitor", category="monitor")
    def move_to_next_monitor() -> None:
        focused = wm.focused
        if focused is not None:
            ws_manager.move_window_to_next_monitor(focused)

    # -- WM lifecycle --------------------------------------------------
    @dispatcher.command("quit_wm", description="Quit SauliethWM", category="wm")
    def quit_wm() -> None:
        log.info("Command: quit_wm")
        print("\n" + ws_manager.get_status_summary())
        wm.stop()

    @dispatcher.command("retile", description="Force retile active workspace", category="wm")
    def retile() -> None:
        ws_manager.retile()

    @dispatcher.command("retile_all", description="Force retile all workspaces", category="wm")
    def retile_all() -> None:
        ws_manager.retile_all()

    log.info("Default commands registered: %d", dispatcher.count)
