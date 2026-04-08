import re
from abc import ABC, abstractmethod
from typing import Callable
from .enums import TerminalEscape, InputStreamType, Hotkey
from .config import ZMachineConfig
from .constants import ESCAPE_CHAR
from .event import EventManager, EventArgs, PostReadInputEventArgs
from .protocol import IScreen, ITerminalAdapter, IInputSource, IHotkeyHandler

class KeyboardInputParser:
    def __init__(self, terminal_adapter: ITerminalAdapter):
        self.terminal_adapter = terminal_adapter

    def set_timeout(self, timeout_ms: int):
        self.terminal_adapter.set_timeout(timeout_ms)

    def get_next_char(self, echo: bool = True) -> int:
        c = self.terminal_adapter.get_input_char(echo)
        if c == ESCAPE_CHAR:
            # Escape sequence.
            # For special characters (arrows, function keys), the remaining characters
            # will be in the keyboard input stream.
            escape_sequence = self.terminal_adapter.get_escape_sequence()
            terminal_mapping = TerminalEscape.lookup_sequence(tuple(escape_sequence))
            if terminal_mapping is None:
                return ESCAPE_CHAR
            else:
                return terminal_mapping.zscii_char
        return c
    
    def backspace(self, backspace_chars: int = 1):
        y, x = self.terminal_adapter.get_coordinates()
        if backspace_chars > 0 and x > backspace_chars:
            self.terminal_adapter.move_cursor(y, x - backspace_chars)
            self.terminal_adapter.clear_to_eol()

class InputStreamManager:
    def __init__(self, 
                 screen: IScreen,
                 terminal_adapter: ITerminalAdapter, 
                 hotkey_handler: IHotkeyHandler,
                 event_manager: EventManager,
                 config: ZMachineConfig
                ):
        self.screen = screen
        self.event_manager = event_manager
        self.keyboard_input_stream = KeyboardInputStream(terminal_adapter, self, screen, hotkey_handler, config)
        self.playback_input_stream = PlaybackInputStream(terminal_adapter, self)
        self.active_stream: InputStream = self.keyboard_input_stream

    def select_playback_stream(self, commands: list[str]):
        self.playback_input_stream.open(commands)
        self.screen.pause_enabled = False
        self.active_stream = self.playback_input_stream

    def select_keyboard_stream(self):
        self.screen.pause_enabled = True
        self.active_stream = self.keyboard_input_stream

    def read_input(self,
        timeout_ms: int,
        text_buffer: list[int],
        interrupt_routine_caller: Callable[[int], int],
        interrupt_routine_addr: int,
        echo: bool
    ):
        self.event_manager.pre_read_input.invoke(self, EventArgs())
        self.active_stream.read_input(timeout_ms=timeout_ms,
                                      text_buffer=text_buffer,
                                      interrupt_routine_caller=interrupt_routine_caller,
                                      interrupt_routine_addr=interrupt_routine_addr,
                                      echo=echo)
        input_len = 1 if len(text_buffer) == 1 else text_buffer.index(0)
        input_chars = text_buffer[:input_len]
        terminating_char = input_chars[-1]
        command = None if input_len <= 1 else bytearray(input_chars[:-1]).decode()
        post_input_event_args = PostReadInputEventArgs(command=command, terminating_char=terminating_char)
        self.event_manager.post_read_input.invoke(self, post_input_event_args)


class InputStream(ABC):
    """Base class for input sources"""
    def __init__(self, terminal_adapter: ITerminalAdapter, input_source: IInputSource):
        self.terminal_adapter = terminal_adapter
        self.input_source = input_source

    @abstractmethod
    def read_input(self,
        timeout_ms: int,
        text_buffer: list[int],
        interrupt_routine_caller: Callable[[int], int],
        interrupt_routine_addr: int,
        echo: bool
    ):
        pass
        
class KeyboardInputStream(InputStream):
    def __init__(self, 
                 terminal_adapter: ITerminalAdapter, 
                 input_source: IInputSource, 
                 screen: IScreen, 
                 hotkey_handler: IHotkeyHandler, 
                 config: ZMachineConfig
        ):
        super().__init__(terminal_adapter, input_source)
        self.screen = screen
        self.hotkey_handler = hotkey_handler
        self.config = config
        self.keyboard_input_parser = KeyboardInputParser(terminal_adapter)

    def read_input(self,
        timeout_ms: int,
        text_buffer: list[int],
        interrupt_routine_caller: Callable[[int], int],
        interrupt_routine_addr: int,
        echo: bool = True
    ):
        self.keyboard_input_parser.set_timeout(timeout_ms)
        start_buffer_pos = 0
        while start_buffer_pos < len(text_buffer) and text_buffer[start_buffer_pos] != 0:
            start_buffer_pos += 1
        buffer_pos = start_buffer_pos
        while buffer_pos < len(text_buffer):
            c = self.keyboard_input_parser.get_next_char(echo)
            if c == ESCAPE_CHAR:
                # Unrecognized escape sequence. Ignore.
                continue
            if c in TerminalEscape.values():
                # If the special key is recognized as an interrupt character, write it to the buffer and stop here.
                # If the input buffer length is 1 (read_char), write the character to the buffer.
                # Otherwise, ignore the character.
                if c in Hotkey:
                    # Recognized hotkey.
                    # Clear the input buffer before processing the hotkey.
                    self.keyboard_input_parser.backspace(buffer_pos - start_buffer_pos)
                    buffer_pos = start_buffer_pos
                    text_buffer[buffer_pos] = 0
                    if c == Hotkey.HELP:
                        self.hotkey_handler.display_help()
                    elif c == Hotkey.SEED:
                        self.hotkey_handler.set_random_seed()
                    elif c == Hotkey.PLAYBACK:
                        if self.hotkey_handler.playback_recorded_input(self.input_source):
                            # If opening the playback stream, read the first command immediately.
                            # Otherwise, continue reading input from the keyboard.
                            self.input_source.read_input(timeout_ms=timeout_ms,
                                                         text_buffer=text_buffer,
                                                         interrupt_routine_caller=interrupt_routine_caller,
                                                         interrupt_routine_addr=interrupt_routine_addr,
                                                         echo=echo)
                            return
                    elif c == Hotkey.RECORD:
                        self.hotkey_handler.toggle_record_stream()
                    elif c == Hotkey.DEBUG:
                        self.hotkey_handler.toggle_debug_mode()
                    continue
                if c in self.config.interrupt_zchars:
                    text_buffer[buffer_pos] = c
                    break
                if len(text_buffer) == 1:
                    text_buffer[0] = c
                    break
                continue
            if c == -1:
                # Timed out.
                if interrupt_routine_caller(interrupt_routine_addr) != 0:
                    text_buffer[0] = 0
                    return
                continue
            elif c in (8, 127):
                # Delete and backspace; will treat as backspace.
                if len(text_buffer) == 1:
                    text_buffer[0] = 8
                    break
                if buffer_pos > 0:
                    buffer_pos -= 1
                    text_buffer[buffer_pos] = 0
                    self.keyboard_input_parser.backspace()
                continue
            elif c in (10, 13):
                # Newline; will treat as end of input.
                if echo:
                    self.screen.reset_output_line_count()
                text_buffer[buffer_pos] = 13
                break
            elif c < 32 or c > 126:
                # Non-printable character, ignore.
                continue
            if ord('A') <= c <= ord('Z'):
                c += 32 # Convert to lowercase.
            text_buffer[buffer_pos] = c
            buffer_pos += 1
        self.keyboard_input_parser.set_timeout(0)


class PlaybackInputStream(InputStream):
    def __init__(self, terminal_adapter: ITerminalAdapter, input_source: IInputSource):
        super().__init__(terminal_adapter, input_source)
        self.commands: list[str] = []
        self.command_index = 0

    def open(self, commands: list[str]):
        self.commands = commands
        self.command_index = 0
    
    def read_input(self,
        timeout_ms: int,
        text_buffer: list[int],
        interrupt_routine_caller: Callable[[int], int],
        interrupt_routine_addr: int,
        echo: bool = True
    ):
        buffer_pos = 0
        while buffer_pos < len(text_buffer) and text_buffer[buffer_pos] != 0:
            buffer_pos += 1
        command = self.commands[self.command_index].strip()
        if command == '':
            text_buffer[buffer_pos] = 13
        # If the text buffer length is 1 (read_char), the command should be a single character.
        # If not, the playback file is out of sync and playback will stop here.
        elif len(text_buffer) == 1:
            matches = re.match(r'^\[(\d+)\]$', command)
            if matches is None:
                self.terminal_adapter.write_to_screen(f"Invalid command in playback file: {self.command_index}: {command}\n")
                text_buffer[0] = 13
                self.input_source.select_keyboard_stream()
            else:
                zscii_code = int(matches.groups()[0])
                text_buffer[0] = zscii_code
                if echo and 32 <= zscii_code <= 126:
                    self.terminal_adapter.write_to_screen(chr(zscii_code))
        else:
            # Parse format: "command text" or "command text[terminating_char]"
            matches = re.match(r'^(.+?)(?:\[(\d+)\])?$', command)
            if matches is None:
                self.terminal_adapter.write_to_screen(f"Invalid command in playback file: {self.command_index}: {command}\n")
                text_buffer[buffer_pos] = 13
                self.input_source.select_keyboard_stream()
                return
            groups = matches.groups()
            command_text = groups[0]
            if echo:
                self.terminal_adapter.write_to_screen(command_text.upper() + '\n')
            if len(groups) > 1 and groups[1] is not None:
                terminating_char = int(groups[1])
                if terminating_char == 0:
                    if interrupt_routine_caller(interrupt_routine_addr) != 0:
                        text_buffer[0] = 0
                        return
            else:
                terminating_char = 13
            for c in command_text:
                text_buffer[buffer_pos] = ord(c)
                buffer_pos += 1
            text_buffer[buffer_pos] = terminating_char
        self.command_index += 1
        if self.command_index == len(self.commands):
            self.input_source.select_keyboard_stream()