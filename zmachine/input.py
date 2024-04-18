import re
from config import *
from error import *
from screen import BaseScreen
from typing import Callable, Dict
from event import EventManager, EventArgs


class InputStreamManager:
    def __init__(self, screen: BaseScreen):
        self.event_manager = EventManager()
        self.event_manager.read_input += self.read_input_handler
        self.event_manager.select_input_stream += self.select_input_stream_handler
        self.input_streams: Dict[int, InputStream] = {
            INPUT_STREAM_KEYBOARD: KeyboardInputStream(screen),
            INPUT_STREAM_PLAYBACK: PlaybackInputStream(screen)
        }

    def select_input_stream_handler(self, sender, e: EventArgs):
        stream_id: int = e.stream_id
        if stream_id not in self.input_streams:
            raise StreamException(f"Unrecognized input stream: {stream_id}")
        CONFIG[ACTIVE_INPUT_STREAM_KEY] = stream_id
        self.input_streams[stream_id].open(**e.kwargs())

    def read_input_handler(self, sender, e: EventArgs):
        active_stream_id = CONFIG[ACTIVE_INPUT_STREAM_KEY]
        self.input_streams[active_stream_id].read(**e.kwargs())


class InputStream:
    def __init__(self, screen: BaseScreen):
        self.event_manager = EventManager()
        self.screen = screen

    def open(self, **kwargs):
        pass

    def read(
        self,
        text_buffer: list[int],
        timeout_ms: int,
        interrupt_routine_caller: Callable[[int], int],
        interrupt_routine_addr: int,
        echo: bool = True
    ):
        raise NotImplementedError("Read operation not supported from base class")


class KeyboardInputStream(InputStream):
    def __init__(self, screen: BaseScreen):
        super().__init__(screen)

    def read(
        self,
        text_buffer: list[int],
        timeout_ms: int,
        interrupt_routine_caller: Callable[[int], int],
        interrupt_routine_addr: int,
        echo: bool = True
    ):
        self.screen.read_keyboard_input(
            text_buffer,
            timeout_ms,
            interrupt_routine_caller,
            interrupt_routine_addr,
            echo
        )


class PlaybackInputStream(InputStream):
    def __init__(self, screen: BaseScreen):
        super().__init__(screen)
        self.commands: list[str] = []
        self.command_ptr = 0

    def open(self, **kwargs):
        record_file = kwargs['record_full_path']
        with open(record_file, 'r') as s:
            self.commands = s.readlines()
        if len(self.commands) == 0:
            CONFIG[ACTIVE_INPUT_STREAM_KEY] = INPUT_STREAM_KEYBOARD
        self.command_ptr = 0

    def read(
            self,
            text_buffer: list[int],
            timeout_ms: int,
            interrupt_routine_caller: Callable[[int], int],
            interrupt_routine_addr: int,
            echo: bool = True
    ):
        text_buffer_ptr = 0
        for i in range(len(text_buffer)):
            if text_buffer[i] == 0:
                break
            text_buffer_ptr += 1
        command = self.commands[self.command_ptr].strip()
        matches = re.match(r'((?:\w|\s|[.,"])*)([(\d+)])?', command)
        groups = matches.groups()
        command_text = groups[0]
        if echo:
            self.screen.write_to_screen(command_text.upper() + "\n")
        if groups[1] is not None:
            terminating_char = int(groups[1])
            if terminating_char == 0:
                if interrupt_routine_caller(interrupt_routine_addr) != 0:
                    text_buffer[0] = 0
                    return
        else:
            terminating_char = 13
        for ch in command_text:
            text_buffer[text_buffer_ptr] = ord(ch)
            text_buffer_ptr += 1
        text_buffer[text_buffer_ptr] = terminating_char
        self.command_ptr += 1
        if self.command_ptr == len(self.commands):
            CONFIG[ACTIVE_INPUT_STREAM_KEY] = INPUT_STREAM_KEYBOARD
