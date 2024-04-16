from memory import MemoryMap
from screen import BaseScreen
from event import EventManager, EventArgs
from error import *
from config import *
import os


class OutputStreamManager:
    def __init__(self, screen: BaseScreen, memory_map: MemoryMap):
        self.screen_stream = ScreenStream(screen)
        self.transcript_stream = TranscriptStream(memory_map)
        self.memory_stream = MemoryStream(memory_map)
        self.event_manager = EventManager()
        self.event_manager.write_to_streams += self.write_to_streams_handler
        self.event_manager.select_output_stream += self.select_stream_handler
        self.streams = {
            1: self.screen_stream,
            2: self.transcript_stream,
            3: self.memory_stream
        }

    def select_stream_handler(self, sender, e: EventArgs):
        stream_id = e.stream_id
        if stream_id == 0:
            return
        if abs(stream_id) not in self.streams.keys():
            raise StreamException(f"Unrecognized stream: {stream_id}")
        if stream_id > 0:
            self.streams[stream_id].open(**e.kwargs())
        else:
            self.streams[-stream_id].close()

    def write_to_streams_handler(self, sender, e: EventArgs):
        text = e.text
        newline = e.get('newline', False)
        if self.memory_stream.is_active:
            self.memory_stream.write(text, newline)
        else:
            self.screen_stream.write(text, newline)
            self.transcript_stream.write(text, newline)


class OutputStream:
    def __init__(self, is_active: bool = False):
        self.is_active = is_active
        self.event_manager = EventManager()
        self.active_window = LOWER_WINDOW
        self.buffer_mode = True
        self.event_manager.set_window += self.set_window_handler
        self.event_manager.set_buffer_mode += self.set_buffer_mode_handler

    def open(self, **kwargs):
        self.is_active = True

    def write(self, text: str, newline: bool):
        raise NotImplementedError('Write operation not supported from base class')

    def close(self):
        self.is_active = False

    def set_window_handler(self, sender, e: EventArgs):
        self.active_window = e.window_id

    def set_buffer_mode_handler(self, sender, e: EventArgs):
        self.buffer_mode = e.mode not in (0, False)


class ScreenStream(OutputStream):
    _BUFFER_LENGTH = 1024

    def __init__(self, screen: BaseScreen):
        super().__init__(True)
        self.screen = screen

    def write(self, text: str, newline: bool):
        if self.is_active:
            if self.buffer_mode and self.active_window == LOWER_WINDOW:
                self.screen.write_to_buffer(text, newline)
            else:
                self.screen.print_to_active_window(text, newline)


class TranscriptStream(OutputStream):
    _BUFFER_LENGTH = 1024

    def __init__(self, memory_map: MemoryMap):
        super().__init__()
        self.buffer = ['\0'] * self._BUFFER_LENGTH
        self.buffer_ptr = 0
        self.script_full_path = None
        self.script_file_mode = 'w'
        self.transcript_full_path = None
        self.memory_map = memory_map
        self.event_manager.pre_read_input += self.pre_read_input_handler
        self.event_manager.post_read_input += self.post_read_input_handler
        self.event_manager.quit += self.quit_handler

    def open(self, **kwargs):
        super().open(**kwargs)
        if self.script_full_path is None:
            self.script_full_path = self.prompt_transcript_file()
        self.memory_map.transcript_active_flag = True

    def write(self, text: str, newline: bool):
        self.is_active = self.memory_map.transcript_active_flag
        if not self.is_active or self.active_window != LOWER_WINDOW:
            return
        if self.script_full_path is None:
            self.script_full_path = self.prompt_transcript_file()
        text_len = len(text)
        while self.buffer_ptr + text_len + 1 >= len(self.buffer):
            self.buffer += ['\0'] * self._BUFFER_LENGTH
        prev_ptr = self.buffer_ptr
        next_ptr = self.buffer_ptr + text_len
        self.buffer[prev_ptr:next_ptr] = text
        if newline:
            self.buffer[next_ptr] = "\n"
            next_ptr += 1
        self.buffer_ptr = next_ptr

    def close(self):
        super().close()
        self.memory_map.transcript_active_flag = False

    def flush_buffer(self):
        # File output is not word wrapped.
        if self.buffer_ptr == 0:
            return
        text = ''.join(self.buffer[:self.buffer_ptr])
        if self.script_full_path is not None:
            with open(self.script_full_path, self.script_file_mode) as s:
                s.write(text)
            self.script_file_mode = 'a'
        self.buffer_ptr = 0

    def prompt_transcript_file(self) -> str:
        # This function should not be called more than once in a game session.
        if self.transcript_full_path is None:
            game_file = CONFIG[GAME_FILE_KEY]
            filepath = os.path.dirname(game_file)
            filename = os.path.basename(game_file)
            base_filename = os.path.splitext(filename)[0]
            default_transcript_file = f'{base_filename}.txt'
            self.interpreter_prompt('Enter a file name.')
            script_file = self.interpreter_input(f'Default is "{default_transcript_file}": ')
            if script_file == '':
                script_file = default_transcript_file
            # If the file already exists and it's a new session, the transcript file will be overwritten.
            self.transcript_full_path = os.path.join(filepath, script_file)
        return self.transcript_full_path

    def interpreter_prompt(self, text):
        self.event_manager.interpreter_prompt.invoke(self, EventArgs(text=text))

    def interpreter_input(self, text):
        event_args = EventArgs(text=text)
        self.event_manager.interpreter_input.invoke(self, event_args)
        return event_args.response

    def pre_read_input_handler(self, sender, e: EventArgs):
        # Write all output in the buffer when with the command prompt.
        self.flush_buffer()

    def post_read_input_handler(self, sender, e: EventArgs):
        self.write(e.command, True)

    def quit_handler(self, sender, e: EventArgs):
        self.flush_buffer()


class MemoryStream(OutputStream):
    def __init__(self, memory_map: MemoryMap):
        super().__init__()
        self.BUFFER_LEN = 256
        self.memory_map = memory_map
        self.table_stack = [(0, 0)] * 16
        self.buffer = [0] * self.BUFFER_LEN
        self.buffer_ptr = 0
        self.stack_ptr = 0

    def open(self, **kwargs):
        self.is_active = True
        table_addr = kwargs['table_addr']
        if self.stack_ptr == len(self.table_stack):
            raise StreamException('Opened too many memory streams')
        self.table_stack[self.stack_ptr] = (table_addr, self.buffer_ptr)
        self.stack_ptr += 1

    def write(self, text: str, newline: bool):
        # Add to the output buffer if necessary.
        if self.buffer_ptr + len(text) >= len(self.buffer):
            self.buffer += [0] * self.BUFFER_LEN
        for c in text:
            zscii_code = ord(c)
            if zscii_code == 10:
                zscii_code = 13
            self.buffer[self.buffer_ptr] = zscii_code
            self.buffer_ptr += 1

    def close(self):
        if not self.is_active:
            raise StreamException("Memory stream is already closed")
        self.stack_ptr -= 1
        table_addr, buffer_start = self.table_stack[self.stack_ptr]
        buffer_len = self.buffer_ptr - buffer_start
        self.memory_map.write_word(table_addr, buffer_len)
        for i in range(buffer_len):
            self.memory_map.write_byte(table_addr + i + 2, self.buffer[buffer_start + i])
        self.buffer_ptr = buffer_start
        if self.stack_ptr == 0:
            self.is_active = False
