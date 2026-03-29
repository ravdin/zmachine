from typing import Protocol, Callable, runtime_checkable
from .enums import WindowPosition, InputStreamType

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
class ITerminalAdapter(Protocol):
    """Terminal adapter interface that all terminal adapter implementations must support.
    The terminal adapter provides low-level access to the terminal for 
    the screen logic."""
    @property
    def height(self) -> int:
        """The height of the terminal in characters."""
        ...

    @property
    def width(self) -> int:
        """The width of the terminal in characters."""
        ...

    def refresh(self):
        """Refresh the terminal display."""
        ...

    def set_scrollable_height(self, top: int):
        """Set the scrollable height of the terminal, with the top line of the scroll region at the given y coordinate."""
        ...

    def write_to_screen(self, text: str):
        """Write text directly to the terminal, bypassing the screen's buffering and paging logic."""
        ...

    def get_input_char(self, echo: bool = True) -> int:
        """Get a single input character from the terminal, optionally echoing it to the screen."""
        ...

    def get_escape_sequence(self) -> list[int]:
        """Get a sequence of input characters from the terminal, returning them as a list of character codes."""
        ...

    def get_input_string(self, prompt: str, lowercase: bool) -> str:
        """Get a string of input from the terminal, optionally converting it to lowercase."""
        ...

    def set_timeout(self, timeout_ms: int):
        """Set the input timeout for the terminal in milliseconds."""
        ...

    def get_coordinates(self) -> tuple[int, int]:
        """Get the current cursor coordinates as a 0-indexed (y, x) tuple."""
        ...

    def move_cursor(self, y_pos: int, x_pos: int):
        """Move the cursor to the specified 0-indexed coordinates."""
        ...

    def get_char_at(self, y_pos: int, x_pos: int) -> int:
        """Get the character code at the specified coordinates."""
        ...

    def paint_char_at(self, y_pos: int, x_pos: int, char: int):
        """Paint the specified character code at the given coordinates."""
        ...

    def erase_screen(self):
        """Erase the entire terminal screen."""
        ...

    def erase_window(self, top: int, height: int):
        """Erase a portion of the terminal screen defined by the top coordinate and height."""
        ...

    def clear_to_eol(self):
        """Clear from the current cursor position to the end of the line."""
        ...

    def apply_style_attributes(self, attributes: int):
        """Apply the given text style attributes to subsequent terminal output."""
        ...

    def set_color(self, background_color: int, foreground_color: int):
        """Set the terminal's foreground and background colors for subsequent output."""
        ...

    def sound_effect(self, sound_type: int):
        """Play a sound effect of the specified type."""
        ...

    def shutdown(self):
        """Perform any necessary cleanup of the terminal before exiting."""
        ...

@runtime_checkable
class IInputSource(Protocol):
    """
    Core input source interface that all input source implementations must support.
    
    This is the minimal interface required by the interpreter.
    Version-specific methods (mouse input, touch input) are optional extensions.
    """
    def get_selected_stream_type(self) -> InputStreamType:
        """Get the type of the currently selected input stream."""
        ...

    def select_keyboard_stream(self):
        """Select the keyboard input stream as the active input source."""
        ...

    def select_playback_stream(self, commands: list[str]):
        """Select a playback stream with the given list of commands as the active input source."""
        ...

    def read_input(self,
        timeout_ms: int,
        text_buffer: list[int],
        interrupt_routine_caller: Callable[[int], int],
        interrupt_routine_addr: int,
        echo: bool):
        """Read input with the given timeout and echo settings, storing the result in the provided text buffer."""
        ...

@runtime_checkable
class IOutputStreamManager(Protocol):
    """Output stream handler interface that all output stream handler implementations must support."""

    def open_screen_stream(self):
        ...

    def close_screen_stream(self):
        ...

    def open_transcript_stream(self):
        ...

    def close_transcript_stream(self):
        ...

    def open_memory_stream(self, table_addr: int):
        ...

    def close_memory_stream(self):
        ...

    def open_record_stream(self, record_file_path: str):
        ...

    def close_record_stream(self):
        ...

    def write_to_streams(self, text: str, newline: bool = False):
        """Write the given text to all active output streams."""
        ...


@runtime_checkable
class IHotkeyHandler(Protocol):
    """Hotkey handler interface that all hotkey handler implementations must support.
    This implementation is not core to the Z-Machine protocol and is a convenience for testing."""
    def display_help(self):
        """Display a help message describing the available hotkeys."""
        ...
    def toggle_debug_mode(self):
        """Toggle debug mode on or off."""
        ...
    def set_random_seed(self):
        """Prompt the user to enter a random seed and set it for the random module."""
        ...
    def playback_recorded_input(self, input_source: IInputSource) -> bool:
        """Prompt the user to select a playback file and set the input stream to playback mode with the selected file, returning True if successful."""
        ...
    def open_record_stream(self):
        """Prompt the user to select a file path and open a record stream to that file."""
        ...
    def close_record_stream(self):
        """Close the currently open record stream."""
        ...