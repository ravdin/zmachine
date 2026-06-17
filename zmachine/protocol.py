from typing import Protocol, Callable, runtime_checkable
from .enums import Color, RoutineType, FontEnum, PackedAddressType

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
class IResourceData(Protocol):
    """
    Interface for external resource files containing data such as sounds and pictures.
    """
    @property
    def release_number(self) -> int:
        ...
    
    @property
    def picture_count(self) -> int:
        ...

    def get_scaling_ratio(self, number: int, window_width: int, window_height: int) -> float:
        """Calculate a scaling factor when rendering images in a window."""
        ...

    def is_valid_picture(self, number: int) -> bool:
        ...

    def is_adaptive_picture(self, number: int) -> bool:
        ...

    def get_picture_data(self, number: int) -> bytes:
        ...

    def get_sound_data(self, number: int) -> bytes:
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

    @property
    def screen(self) -> 'IScreen':
        ...

    def do_branch(self, is_truthy: int):
        ...

    def do_store(self, value: int):
        ...

    def read_byte(self, addr: int) -> int:
        ...

    def write_byte(self, addr: int, value: int):
        ...

    def read_word(self, addr: int) -> int:
        ...

    def write_word(self, addr: int, value: int):
        ...

    def read_var(self, varnum: int) -> int:
        ...

    def write_var(self, varnum: int, value: int):
        ...

    def unpack_addr(self, packed_addr: int, addr_type: int = PackedAddressType.ROUTINE) -> int:
        ...

    def do_routine(self, routine_addr: int, args: tuple[int, ...], routine_type: int = RoutineType.STORE):
        ...

    def do_return(self, retval: int):
        ...

    def get_arg_count(self) -> int:
        ...

    def do_catch(self):
        ...
    
    def do_throw(self, return_value: int, frame_id: int):
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

    def do_select_output_stream(self, stream_id: int, table_addr: int = 0, buffering: bool = False, width: int = 0):
        ...

    def do_sound_effect(self, number: int, effect: int = 0, volume: int = 0, routine: int = 0):
        ...

    def do_get_picture_data(self, number: int, array: int):
        ...


@runtime_checkable
class IScreen(Protocol):
    """
    Core screen interface that all screen implementations must support.
    
    This is the minimal interface required by the interpreter.
    Version-specific methods (colors, graphics) are optional extensions.
    """
    def set_buffer_mode(self, value: bool):
        """Buffer text for delayed output."""
        ...

    @property
    def pause_enabled(self) -> bool:
        """Whether the screen should pause after printing a full page of text."""
        ...

    @pause_enabled.setter
    def pause_enabled(self, value: bool):
        """Set whether the screen should pause after printing a full page of text."""
        ...

    @property
    def transcript_output_enabled(self) -> bool:
        """Indicates that output to the currently active window will write to the transcript stream,
        if the transcript stream is enabled."""
        ...

    @property
    def resource_data(self) -> IResourceData:
        """Expose the underlying resources for reading."""
        ...

    def restart_screen(self):
        """Re-initialize screen settings on a restart."""

    def refresh_status_line(self, location: str, status: str):
        """Refresh the status line with the given text (v3 only)."""
        ...

    def print(self, text: str, newline: bool = False): 
        """Print text to the active window."""
        ...

    def reset_output_line_count(self):
        """Reset the count of output lines printed since the last read or pause."""
        ...
        
    def set_window(self, window_id: int):
        """Set the active window."""
        ...
        
    def split_window(self, lines: int): 
        """Split screen with the upper window of given height."""
        ...

    def erase_window(self, window_id: int): 
        """Erase the contents of the specified window.
        If -1, unsplit the screen and erase the entire display, if -2, erase the screen without unsplitting."""
        ...

    def erase_line(self, value: int):
        """V4/V5: Erase from the cursor to the end of the line, if the value is 1.
        V6: Erase the given number of pixels, or to the end of the line if the value is 1."""
        ...

    def sound_effect(self, number: int, effect: int, volume: int, repeats: int, routine: int): 
        """Play a sound effect of the specified type."""
        ...

    def get_cursor(self) -> tuple[int, int]:
        """Get the current cursor row and column."""
        ...

    def set_cursor(self, y_cursor: int, x_cursor: int, window_id = -3):
        """Set the cursor position."""
        ...

    def set_text_style(self, style: int):
        """Set the text style (reverse background, underline, bold)."""
        ...

    def set_color(self, foreground_color: int, background_color: int, window_id: int = -3):
        """Set the colors of the active window."""
        ...

    def set_font(self, font_id: int, window_id: int = -3) -> int:
        """Set the font of the output character."""
        ...

    def print_table(self, table: list[str]):
        """Print a table from the print_table op."""
        ...

    def get_window_property(self, window_id: int, property_number: int) -> int:
        """Read the given property of the given window."""
        ...

    def put_window_property(self, window_id: int, property_number: int, value: int):
        """Write a window property."""
        ...

    def get_picture_size(self, number: int) -> tuple[int, int]:
        """Get a picture resource width and height."""
        ...

    def draw_picture(self, number: int, y: int = 0, x: int = 0):
        """Draw a picture from the resource data."""
        ...

    def erase_picture(self, number: int, y: int = 0, x: int = 0):
        """Paint the appropriate region of the screen to the background color."""

    def set_mouse_window(self, window_id: int):
        """Restrict mouse input to the boundaries of the given window."""
        ...

    def set_cursor_enabled(self, value: bool):
        """Enable or disable the cursor."""
        ...

    def set_margins(self, left: int, right: int, window_id: int = -3):
        """Set the left and right margin positions for a window."""
        ...

    def move_window(self, window_id: int, y: int, x: int):
        """Move a window position."""
        ...

    def resize_window(self, window_id: int, y: int, x: int):
        """Resize a window."""
        ...

    def scroll_window(self, window_id: int, pixels: int):
        """Scroll a window by a given number of pixels."""
        ...

    def set_window_attributes(self, window_id: int, flags: int, operation: int = 0):
        """Set attributes for a given window."""
        ...

@runtime_checkable
class ITerminalAdapter(Protocol):
    """Terminal adapter interface that all terminal adapter implementations must support.
    The terminal adapter provides low-level access to the terminal for 
    the screen logic."""
    @property
    def height(self) -> int:
        """The height of the terminal in units."""
        ...

    @property
    def width(self) -> int:
        """The width of the terminal in units."""
        ...

    @property
    def font_size(self) -> int:
        """Return font height (upper bytes) and font width (lower bytes) in units."""
        ...

    @property
    def at_wrap_boundary(self) -> bool:
        """Indicates that the output text of the last line has reached the edge of the screen."""
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

    def move_cursor_to_line_start(self):
        """Move the cursor to the left margin of the current line."""
        ...

    def cache_current_line(self):
        """Cache the current line for later retrieval."""
        ...

    def uncache_current_line(self):
        """Restore a cached line."""
        ...

    def erase_screen(self, background_color: int = Color.BLACK):
        """Erase the entire terminal screen."""
        ...

    def erase_window(self, left: int, top: int, width: int, height: int, background_color: int = Color.BLACK):
        """Erase a portion of the terminal screen defined by the top coordinate and height."""
        ...

    def clear_to_eol(self):
        """Clear from the current cursor position to the end of the line."""
        ...

    def apply_style_attributes(self, attributes: int):
        """Apply the given text style attributes to subsequent terminal output."""
        ...

    def apply_color_settings(self, background_color: int, foreground_color: int):
        """Set the terminal's foreground and background colors for subsequent output."""
        ...

    def beep(self):
        """Emit a beep."""
        ...

    def shutdown(self):
        """Perform any necessary cleanup of the terminal before exiting."""
        ...

@runtime_checkable
class IGraphicsAdapter(Protocol):
    """
    Defines additional methods for display beyond TerminalAdapter.
    """
    @property
    def cursor_enabled(self) -> bool:
        ...
    
    @cursor_enabled.setter
    def cursor_enabled(self, value: bool):
        ...
    
    @property
    def scrolling_enabled(self) -> bool:
        ...
    
    @scrolling_enabled.setter
    def scrolling_enabled(self, value: bool):
        ...

    def is_font_supported(self, font_id: int) -> bool:
        """Return true if the terminal output supports the font setting, false otherwise."""
        ...

    def apply_font(self, font: FontEnum):
        """Set the character font for output."""
        ...

    def erase_line(self, width: int):
        """Erase the given width in pixels from the cursor position."""
        ...

    def get_picture_size(self, number: int, resource_data: IResourceData) -> tuple[int, int]:
        """Get the width and height of a picture resource."""
        ...

    def draw_picture(self, number: int, top: int, left: int, resource_data: IResourceData):
        """Draw a picture."""
        ...

    def erase_picture(self, number: int, top: int, left: int, resource_data: IResourceData):
        """Paint the appropriate region of the screen to the background color."""

    def load_sound_effect(self, number: int, sound_data: bytes):
        """Prepare a sound effect to be played."""
        ...

    def play_sound_effect(self, number: int, sound_data: bytes, volume: int, repeats: int, routine: int):
        """Play a sound effect of the specified type."""
        ...

    def interrupt_sound_effect(self, number: int):
        """Interrupt the given sound effect."""
        ...

    def unload_sound_effect(self, number: int):
        """Unload a sound effect from memory."""
        ...

    def scroll_window(self, left: int, top: int, width: int, height: int, pixels: int):
        """Scroll a region by a given number of pixels."""
        ...

    def set_print_region(self, left: int, top: int, width: int, height: int):
        """Set a region of the window for printing."""
        ...

    def set_scrollable_region(self, left: int, top: int, width: int, height: int):
        """Set a region of the window to be scrollable."""
        ...

    def set_mouse_region(self, left: int, top: int, width: int, height: int):
        """Restrict mouse input to the boundaries of a window."""
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
    def open(self, table_addr: int, buffering: bool, width: int):
        """Open the memory output stream with the given table address.
        V6: Option to include line buffering and output width, for print_form.
        """
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