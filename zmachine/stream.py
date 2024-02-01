from memory import MemoryMap
from event import EventManager, EventArgs
from transcript import TranscriptUtils
from error import *
from constants import *


class OutputStreamManager:
    def __init__(self, memory_map: MemoryMap, transcript_utils: TranscriptUtils):
        self.screen_stream = ScreenStream()
        self.transcript_stream = TranscriptStream(memory_map, transcript_utils)
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

    def __init__(self):
        super().__init__(True)
        self.buffer = ['\0'] * self._BUFFER_LENGTH
        self.buffer_ptr = 0

    def write(self, text: str, newline: bool):
        if self.is_active:
            if self.buffer_mode and self.active_window == LOWER_WINDOW:
                self.write_to_buffer(text, newline)
            else:
                self.write_to_screen(text, newline)

    def write_to_buffer(self, text: str, newline: bool):
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

    def write_to_screen(self, text: str, newline: bool):
        event_args = EventArgs(text=text, newline=newline)
        self.event_manager.print_to_active_window.invoke(self, event_args)

    def flush_buffer(self) -> str:
        text = ''.join(self.buffer[:self.buffer_ptr])
        self.buffer_ptr = 0
        return text

    def has_buffer(self):
        return self.buffer_ptr > 0


class TranscriptStream(OutputStream):
    _BUFFER_LENGTH = 1024

    def __init__(self, memory_map: MemoryMap, transcript_utils: TranscriptUtils):
        super().__init__()
        self.buffer = ['\0'] * self._BUFFER_LENGTH
        self.buffer_ptr = 0
        self.script_full_path = None
        self.script_file_mode = 'w'
        self.memory_map = memory_map
        self.transcript_utils = transcript_utils
        self.event_manager.pre_read_input += self.pre_read_input_handler
        self.event_manager.post_read_input += self.post_read_input_handler

    def open(self, **kwargs):
        super().open(**kwargs)
        if self.script_full_path is None:
            self.script_full_path = self.transcript_utils.prompt_transcript_file()
        self.memory_map.transcript_active_flag = True

    def write(self, text: str, newline: bool):
        self.is_active = self.memory_map.transcript_active_flag
        if not self.is_active or self.active_window != LOWER_WINDOW:
            return
        if self.script_full_path is None:
            self.script_full_path = self.transcript_utils.prompt_transcript_file()
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

    def pre_read_input_handler(self, sender, e: EventArgs):
        # Write all output in the buffer when with the command prompt.
        # File output is not word wrapped.
        if self.buffer_ptr == 0:
            return
        text = ''.join(self.buffer[:self.buffer_ptr])
        if self.script_full_path is not None:
            with open(self.script_full_path, self.script_file_mode) as s:
                s.write(text)
            self.script_file_mode = 'a'
        self.buffer_ptr = 0

    def post_read_input_handler(self, sender, e: EventArgs):
        self.write(e.command, True)


class MemoryStream(OutputStream):
    def __init__(self, memory_map: MemoryMap):
        super().__init__()
        self.memory_map = memory_map
        self.table_stack = [(0, 0)] * 16
        self.buffer = [0] * 256
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
