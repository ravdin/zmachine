from typing import Protocol, Callable, runtime_checkable
from .enums import WindowPosition, RoutineType

@runtime_checkable
class ISerializable(Protocol):
    """Interface for objects that can be serialized to and deserialized from a byte representation."""
    def serialize(self) -> bytes:
        """Serialize the object to a byte representation."""
        ...

    def deserialize(self, data: bytes):
        """Deserialize the object from a byte representation, overwriting the current state."""
        ...

@runtime_checkable
class IQuetzal(Protocol):
    def do_save(self, pc: int, call_stack: ISerializable) -> bool:
        """Saves the game state. Returns true if successful."""
        ...

    def do_restore(self, call_stack: ISerializable) -> tuple[int, bool]:
        """
        Restores the game state.
        
        Returns:
            Tuple of (pc, success) where:
            - pc: Program counter from save file (only valid if success=True)
            - success: True if restore succeeded, False otherwise
        """
        ...

@runtime_checkable
class IObjectTable(Protocol):
    """Object table interface that all object table implementations must support."""
    def get_attribute_flag(self, obj_id: int, attr_num: int) -> bool:
        """Return the value of the specified attribute for the given object number."""
        ...

    def set_attribute_flag(self, obj_id: int, attr_num: int, value: bool):
        """Set the value of the specified attribute for the given object number."""
        ...
    
    def insert_object(self, obj_id: int, parent_id: int):
        """Insert the object with the given object number as a child of the specified parent object."""
        ...

    def get_property_data(self, obj_id: int, prop_id: int) -> int:
        """Return the value of the specified property for the given object number."""
        ...

    def set_property_data(self, obj_id: int, prop_id: int, value: int):
        """Set the value of the specified property for the given object number."""
        ...

    def get_property_addr(self, obj_id: int, prop_id: int) -> int | None:
        """Return the address of the specified property for the given object number, or None if the property does not exist."""
        ...

    def get_next_property_num(self, obj_id: int, prop_id: int) -> int:
        """Return the property number of the next property after the specified property for the given object number, or 0 if there are no more properties."""
        ...

    def get_property_data_len(self, prop_addr: int) -> int:
        """Return the length in bytes of the property data at the given property address."""
        ...

    def get_object_parent_id(self, obj_id: int) -> int:
        """Return the object number of the parent of the given object number."""
        ...

    def get_object_sibling_id(self, obj_id: int) -> int:
        """Return the object number of the sibling of the given object number."""
        ...

    def get_object_child_id(self, obj_id: int) -> int:
        """Return the object number of the first child of the given object number."""
        ...

    def orphan_object(self, obj_id: int):
        """Remove the object with the given object number from its current parent and siblings. Its children, if any, are unaffected."""
        ...

    def get_object_text_zchars(self, obj_id: int) -> list[int]:
        """Return the text of the given object number as a list of Z-characters."""
        ...

@runtime_checkable
class IZMachineInterpreter(Protocol):
    """
    Interpreter interface to be referenced by the opcodes.
    """

    @property
    def version(self) -> int:
        ...

    @property
    def object_table(self) -> IObjectTable:
        ...

    def do_branch(self, is_truthy: int):
        ...

    def do_store(self, value: int):
        ...

    def read_byte(self, addr: int) -> int:
        ...

    def write_byte(self, addr: int, value: int):
        pass

    def read_word(self, addr: int) -> int:
        ...

    def write_word(self, addr: int, value: int):
        ...

    def read_var(self, varnum: int) -> int:
        ...

    def write_var(self, varnum: int, value: int):
        ...

    def unpack_addr(self, packed_addr: int) -> int:
        ...

    def do_routine(self, call_addr: int, args: tuple[int, ...], routine_type: int = RoutineType.STORE):
        ...

    def do_return(self, retval: int):
        ...

    def get_arg_count(self) -> int:
        ...

    def do_jump(self, offset: int):
        ...

    def do_save(self) -> bool:
        ...

    def do_restore(self) -> bool:
        ...

    def do_save_undo(self):
        ...

    def do_restore_undo(self):
        ...

    def do_restart(self):
        ...

    def do_verify(self) -> bool:
        ...

    def do_quit(self):
        ...

    def do_show_status(self):
        ...

    def stack_push(self, value):
        ...

    def stack_pop(self) -> int:
        ...

    def stack_peek(self) -> int:
        ...

    def get_object_text(self, obj_id: int) -> str:
        ...

    def print_from_pc(self, newline: bool = False):
        ...

    def print_from_addr(self, addr: int, newline: bool = False):
        ...

    def do_print_table(self, addr: int, width: int, height: int, skip: int):
        ...

    def write_to_output_streams(self, text: str, newline: bool = False):
        ...

    def do_read(self, text_buffer_addr: int, parse_buffer_addr: int, time: int = 0, routine: int = 0):
        ...

    def do_read_char(self, time: int = 0, routine: int = 0):
        ...

    def do_tokenize(self, text_addr: int, parse_buffer: int, dictionary_addr: int = 0, flag: int = 0):
        ...

    def do_encode_text(self, text_addr: int, length: int, start: int, coded_buffer: int):
        ...

    def do_split_window(self, lines: int):
        ...

    def do_set_window(self, window_id: int):
        ...

    def do_erase_window(self, window_id: int):
        ...

    def do_set_cursor(self, y: int, x: int):
        ...

    def do_set_text_style(self, style: int):
        ...

    def do_set_buffer_mode(self, mode: bool):
        ...

    def do_select_output_stream(self, stream_id: int, table_addr: int = 0):
        ...

    def do_sound_effect(self, type: int):
        ...

    def do_set_color(self, foreground_color: int, background_color: int):
        ...

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
class IBaseOutputStream(Protocol):
    """Output stream interface that all output stream implementations must support."""
    @property
    def is_active(self) -> bool:
        """Return true the output stream is currently active, false otherwise."""
        ...

    def write(self, text: str, newline: bool):
        """Write the given text to the output stream, optionally adding a newline."""
        ...

    def close(self):
        """Close the output stream."""
        ...

@runtime_checkable
class IOutputStream(IBaseOutputStream, Protocol):
    """Output stream interface that implements the open method with no arguments, for streams that don't require additional parameters to open."""
    def open(self):
        """Open the output stream."""
        ...

@runtime_checkable
class IMemoryOutputStream(IBaseOutputStream, Protocol):
    """Memory output stream interface that extends the base output stream with a method for opening with a table address."""
    def open(self, table_addr: int):
        """Open the memory output stream with the given table address."""
        ...

@runtime_checkable
class IRecordOutputStream(IBaseOutputStream, Protocol):
    """Record output stream interface that extends the base output stream with a method for opening with a file path."""
    def open(self, record_file_path: str):
        """Open the record output stream with the given file path."""
        ...

@runtime_checkable
class IOutputStreamManager(Protocol):
    """Output stream handler interface that all output stream handler implementations must support."""

    @property
    def screen_stream(self) -> IOutputStream:
        """The output stream for writing to the screen."""
        ...

    @property
    def transcript_stream(self) -> IOutputStream:
        """The output stream for writing to the transcript file."""
        ...

    @property
    def memory_stream(self) -> IMemoryOutputStream:
        """The output stream for writing to memory."""
        ...

    @property
    def record_stream(self) -> IRecordOutputStream:
        """The output stream for writing to a record file."""
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
    def set_random_seed(self):
        """Prompt the user to enter a random seed and set it for the random module."""
        ...
    def playback_recorded_input(self, input_source: IInputSource) -> bool:
        """Prompt the user to select a playback file and set the input stream to playback mode with the selected file, returning True if successful."""
        ...
    def toggle_record_stream(self):
        """Toggle the record stream on or off, prompting the user to select a file when turning on."""
        ...