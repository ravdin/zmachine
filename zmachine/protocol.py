from typing import Protocol, Callable, runtime_checkable
from .enums import WindowPosition

@runtime_checkable
class IScreen(Protocol):
    """
    Core screen interface that all screen implementations must support.
    
    This is the minimal interface required by the interpreter.
    Version-specific methods (colors, graphics) are optional extensions.
    """
    @property
    def buffer_mode(self) -> bool:
        """Whether the screen is in buffered mode."""
        ...

    @buffer_mode.setter
    def buffer_mode(self, value: bool) -> None:
        """Set the screen's buffered mode."""
        ...

    @property
    def pause_enabled(self) -> bool:
        """Whether the screen should pause after printing a full page of text."""
        ...

    @pause_enabled.setter
    def pause_enabled(self, value: bool) -> None:
        """Set whether the screen should pause after printing a full page of text."""
        ...

    @property
    def active_window_id(self) -> 'WindowPosition':
        """The currently active window."""
        ...

    def refresh_status_line(self, location: str, status: str) -> None:
        """Refresh the status line with the given text (v3 only)."""
        ...

    def print(self, text: str, newline: bool = False) -> None: 
        """Print text to the active window."""
        ...

    def reset_output_line_count(self) -> None:
        """Reset the count of output lines printed since the last read or pause."""
        ...
        
    def set_window(self, window_id: int) -> None:
        """Set the active window."""
        ...
        
    def split_window(self, lines: int) -> None: 
        """Split screen with the upper window of given height."""
        ...

    def erase_window(self, window_id: int) -> None: 
        """Erase the contents of the specified window.
        If -1, unsplit the screen and erase the entire display, if -2, erase the screen without unsplitting."""
        ...

    def sound_effect(self, type: int) -> None: 
        """Play a sound effect of the specified type."""
        ...

    def set_cursor(self, y_pos: int, x_pos: int) -> None:
        """Set the cursor position."""
        ...

    def set_text_style(self, style: int) -> None:
        """Set the text style (reverse background, underline, bold)."""
        ...

    def set_color(self, background_color: int, foreground_color: int) -> None:
        """Set the colors of the active window."""
        ...

    def print_table(self, table: list[str]) -> None:
        """Print a table from the print_table op."""
        ...

@runtime_checkable
class IInputSource(Protocol):
    """
    Core input source interface that all input source implementations must support.
    
    This is the minimal interface required by the interpreter.
    Version-specific methods (mouse input, touch input) are optional extensions.
    """
    def read_input(self,
        timeout_ms: int,
        text_buffer: list[int],
        interrupt_routine_caller: Callable[[int], int],
        interrupt_routine_addr: int,
        echo: bool):
        """Read input with the given timeout and echo settings, storing the result in the provided text buffer."""
        ...