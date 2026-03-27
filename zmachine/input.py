import re
import os
from abc import ABC, abstractmethod
from typing import Callable
from .enums import TerminalEscape, InputStreamType, Hotkey, WindowPosition
from .config import ZMachineConfig
from .constants import ESCAPE_CHAR
from .screen import BaseScreen, TerminalAdapter
from .event import EventManager, EventArgs

class KeyboardInputParser:
    def __init__(self, terminal_adapter: TerminalAdapter):
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
    def __init__(self, screen: BaseScreen, event_manager: EventManager, config: ZMachineConfig):
        self.screen = screen
        self.keyboard_input_stream = KeyboardInputStream(screen, event_manager, config)
        self.playback_input_stream = PlaybackInputStream(screen, event_manager)
        self.active_stream: InputStream = self.keyboard_input_stream
        self.register_delegates(event_manager)

    def register_delegates(self, event_manager: EventManager):
        event_manager.read_input += self.read_input_handler
        event_manager.select_input_stream += self.select_input_stream_handler

    def open_playback_stream(self, playback_file_path: str):
        if not os.path.exists(playback_file_path):
            return
        with open(playback_file_path, 'r') as playback_file:
            commands = playback_file.readlines()

    def select_input_stream_handler(self, sender, e: EventArgs):
        input_stream_type = e.input_stream_type
        if input_stream_type == InputStreamType.KEYBOARD:
            self.screen.pause_enabled = True
            self.active_stream = self.keyboard_input_stream
        elif input_stream_type == InputStreamType.PLAYBACK:
            commands = e.get('commands', None)
            if commands is not None:
                self.playback_input_stream.open(e.commands)
                self.screen.pause_enabled = False
                self.active_stream = self.playback_input_stream

    def read_input_handler(self, sender, event_args: EventArgs):
        timeout_ms: int = event_args.timeout_ms
        text_buffer: list[int] = event_args.text_buffer
        interrupt_routine_caller: Callable[[int], int] = event_args.interrupt_routine_caller
        interrupt_routine_addr: int = event_args.interrupt_routine_addr
        echo = event_args.get('echo', True)
        self.active_stream.read_input(timeout_ms=timeout_ms,
                                      text_buffer=text_buffer,
                                      interrupt_routine_caller=interrupt_routine_caller,
                                      interrupt_routine_addr=interrupt_routine_addr,
                                      echo=echo)

class InputStream(ABC):
    """Base class for input sources"""
    def __init__(self, screen: BaseScreen, event_manager: EventManager):
        self.screen = screen
        self.event_manager = event_manager

    @abstractmethod
    def read_input(self,
        timeout_ms: int,
        text_buffer: list[int],
        interrupt_routine_caller: Callable[[int], int],
        interrupt_routine_addr: int,
        echo: bool):
        pass
        
class KeyboardInputStream(InputStream):
    def __init__(self, screen: BaseScreen, event_manager: EventManager, config: ZMachineConfig):
        super().__init__(screen, event_manager)
        self.config = config
        self.keyboard_input_parser = KeyboardInputParser(screen.terminal_adapter)

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
                    # Clear the input buffer and invoke the hotkey event handler.
                    self.keyboard_input_parser.backspace(buffer_pos - start_buffer_pos)
                    buffer_pos = start_buffer_pos
                    text_buffer[buffer_pos] = 0
                    hotkey_event_args = EventArgs(hotkey=c)
                    self.event_manager.activate_hotkey.invoke(self, hotkey_event_args)
                    # For the playback hotkey, if the hotkey event handler switched to the playback input stream,
                    # invoke the first command from the playback stream immediately.
                    # Otherwise, continue reading input from the keyboard.
                    if c == Hotkey.PLAYBACK and hotkey_event_args.get('playback_open', False):
                        read_event_args = EventArgs(timeout_ms=timeout_ms,
                                                   text_buffer=text_buffer,
                                                   interrupt_routine_caller=interrupt_routine_caller,
                                                   interrupt_routine_addr=interrupt_routine_addr,
                                                   echo=echo)
                        self.event_manager.read_input.invoke(self, read_event_args)
                        return
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
    def __init__(self, screen: BaseScreen, event_manager: EventManager):
        super().__init__(screen, event_manager)
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
                self.screen.write_to_screen(f"Invalid command in playback file: {self.command_index}: {command}\n")
                text_buffer[0] = 13
                self.event_manager.select_input_stream.invoke(self, EventArgs(input_stream_type=InputStreamType.KEYBOARD))
            else:
                zscii_code = int(matches.groups()[0])
                text_buffer[0] = zscii_code
                if echo and 32 <= zscii_code <= 126:
                    self.screen.write_to_screen(chr(zscii_code))
        else:
            # Parse format: "command text" or "command text[terminating_char]"
            matches = re.match(r'^(.+?)(?:\[(\d+)\])?$', command)
            if matches is None:
                self.screen.write_to_screen(f"Invalid command in playback file: {self.command_index}: {command}\n")
                text_buffer[buffer_pos] = 13
                self.event_manager.select_input_stream.invoke(self, EventArgs(input_stream_type=InputStreamType.KEYBOARD))
                return
            groups = matches.groups()
            command_text = groups[0]
            if echo:
                self.screen.write_to_screen(command_text.upper() + '\n')
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
            self.event_manager.select_input_stream.invoke(self, EventArgs(input_stream_type=InputStreamType.KEYBOARD))