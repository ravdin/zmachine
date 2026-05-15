import os
from .config import ZMachineConfig
from .settings import RuntimeSettings
from .memory import MemoryMap
from .protocol import IScreen, ITerminalAdapter, IOutputStream, IMemoryOutputStream, IRecordOutputStream
from .event import EventManager, EventArgs, PostReadInputEventArgs
from .error import StreamException
from .logging import output_logger as logger


class OutputStreamManager:
    def __init__(self, 
                 screen: IScreen,
                 memory_map: MemoryMap,
                 terminal_adapter: ITerminalAdapter, 
                 config: ZMachineConfig,
                 runtime_settings: RuntimeSettings,
                 event_manager: EventManager
                ):
        self.config = config
        self.memory_map = memory_map

        self._screen_stream = ScreenStream(screen)
        self._transcript_stream = TranscriptStream(config, runtime_settings, screen, terminal_adapter)
        self._memory_stream = MemoryStream(memory_map)
        self._record_stream = RecordStream()

        self._transcript_stream.register_delegates(event_manager)
        self._record_stream.register_delegates(event_manager)

    @property
    def screen_stream(self) -> IOutputStream:
        """The output stream for writing to the screen."""
        return self._screen_stream

    @property
    def transcript_stream(self) -> IOutputStream:
        """The output stream for writing to the transcript file."""
        return self._transcript_stream

    @property
    def memory_stream(self) -> IMemoryOutputStream:
        """The output stream for writing to memory."""
        return self._memory_stream

    @property
    def record_stream(self) -> IRecordOutputStream:
        """The output stream for writing to a record file."""
        return self._record_stream

    def write_to_streams(self, text: str, newline: bool = False):
        if self.memory_stream.is_active:
            self.memory_stream.write(text, newline)
        else:
            self.screen_stream.write(text, newline)
            self.transcript_stream.write(text, newline)


class OutputStream:
    def __init__(self, is_active: bool = False):
        self._is_active = is_active

    @property
    def is_active(self) -> bool:
        return self._is_active
    
    @is_active.setter
    def is_active(self, value: bool):
        if value:
            logger.info(f"Opening {self.__class__.__name__}")
        self._is_active = value

    def write(self, text: str, newline: bool):
        raise NotImplementedError('Write operation not supported from base class')

    def close(self):
        logger.info(f"Closing {self.__class__.__name__}")
        self.is_active = False


class ScreenStream(OutputStream):
    def __init__(self, screen: IScreen):
        super().__init__(True)
        self.screen = screen

    def open(self):
        self.is_active = True

    def write(self, text: str, newline: bool):
        if self.is_active:
            self.screen.print(text, newline)


class TranscriptStream(OutputStream):
    _BUFFER_LENGTH = 1024

    def __init__(self, config: ZMachineConfig, runtime_settings: RuntimeSettings, screen: IScreen, terminal_adapter: ITerminalAdapter):
        super().__init__()
        self.config = config
        self.runtime_settings = runtime_settings
        self.screen = screen
        self.terminal_adapter = terminal_adapter
        self.buffer: list[str] = ['\0'] * self._BUFFER_LENGTH
        self.buffer_ptr: int = 0
        self.script_full_path: str | None = None
        self.script_file_mode: str = 'w'
        self.transcript_full_path: str | None = None

    def open(self):
        self.is_active = True
        if self.script_full_path is None:
            self.script_full_path = self.prompt_transcript_file()
        self.runtime_settings.transcript_active_flag = True

    def write(self, text: str, newline: bool):
        self.is_active = self.runtime_settings.transcript_active_flag
        if not (self.is_active and self.screen.transcript_output_enabled):
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
        self.runtime_settings.transcript_active_flag = False

    def register_delegates(self, event_manager):
        event_manager.pre_read_input += self.pre_read_input_handler
        event_manager.post_read_input += self.post_read_input_handler
        event_manager.on_quit += self.on_quit_handler

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
            game_file = self.config.game_file
            filepath = os.path.dirname(game_file)
            filename = os.path.basename(game_file)
            base_filename = os.path.splitext(filename)[0]
            default_transcript_file = f'{base_filename}.txt'
            self.terminal_adapter.write_to_screen('Enter a file name.\n')
            script_file = self.terminal_adapter.get_input_string(f'Default is "{default_transcript_file}": ', False)
            if script_file == '':
                script_file = default_transcript_file
            # If the file already exists and it's a new session, the transcript file will be overwritten.
            self.transcript_full_path = os.path.join(filepath, script_file)
        return self.transcript_full_path

    def pre_read_input_handler(self, sender, e: EventArgs):
        self.flush_buffer()

    def post_read_input_handler(self, sender, e: PostReadInputEventArgs):
        if e.command is None:
            return
        if e.terminating_char == 13:
            self.write(e.command, True)

    def on_quit_handler(self, sender, e: EventArgs):
        self.flush_buffer()


class MemoryStream(OutputStream):
    def __init__(self, memory_map: MemoryMap):
        super().__init__()
        self.BUFFER_LEN = 256
        self.memory_map = memory_map
        self.table_stack = [(0, 0, 0, 0)] * 16
        self.buffer = [0] * self.BUFFER_LEN
        self.buffer_ptr = 0
        self.stack_ptr = 0

    def open(self, table_addr: int, buffering: bool, width: int):
        self.is_active = True
        logger.info(f"Opening memory stream for table at address {table_addr:x}")
        if buffering:
            logger.info(f"Memory stream output buffered with width {width}")
        if self.stack_ptr == len(self.table_stack):
            raise StreamException('Opened too many memory streams')
        self.table_stack[self.stack_ptr] = (table_addr, int(buffering), width, self.buffer_ptr)
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
        table_addr, buffering, width, buffer_start = self.table_stack[self.stack_ptr]
        buffer_len = self.buffer_ptr - buffer_start
        if buffering:
            self.flush_buffered(table_addr, buffer_start, width)
        else:
            self.flush(table_addr, buffer_start, buffer_len)
        version = self.memory_map.read_byte(0)
        if version == 6:
            font_width = self.memory_map.read_byte(0x27)
            output_width = width if buffering else buffer_len
            self.memory_map.write_word(0x30, output_width * font_width)
        self.buffer_ptr = buffer_start
        if self.stack_ptr == 0:
            self.is_active = False

    def flush(self, table_addr: int, buffer_start: int, buffer_len: int, newline: bool = False) -> int:
        self.memory_map.write_word(table_addr, buffer_len + int(newline))
        for i in range(buffer_len):
            self.memory_map.write_byte(table_addr + i + 2, self.buffer[buffer_start + i])
        if newline:
            self.memory_map.write_byte(table_addr + buffer_len + 2, 13)
        return table_addr + buffer_len + int(newline) + 2

    def flush_buffered(self, table_addr: int, buffer_start: int, width: int):
        pos = buffer_start
        while pos < self.buffer_ptr:
            buffer_len = self.buffer_ptr - pos
            remaining_buffer = self.buffer[pos:]
            nl_index = remaining_buffer.index(13) if 13 in remaining_buffer else -1
            if 0 <= nl_index < width:
                table_addr = self.flush(table_addr, pos, min(width, nl_index + 1))
                pos += nl_index + 1
                continue
            if buffer_len <= width:
                table_addr = self.flush(table_addr, pos, buffer_len)
                break
            if 32 in remaining_buffer[:width + 1]:
                space_index = width - 1 - remaining_buffer[:width + 1:-1].index(32)
                table_addr = self.flush(table_addr, pos, space_index, space_index < width)
                pos += space_index + 1
                continue
            # This means there is no whitespace in the output characters.
            newline = width < len(remaining_buffer)
            table_addr = self.flush(table_addr, pos, width, newline)
            pos += width
        self.memory_map.write_word(table_addr, 0)


class RecordStream(OutputStream):
    def __init__(self):
        super().__init__()
        self.record_full_path = ''

    def register_delegates(self, event_manager: EventManager):
        event_manager.post_read_input += self.post_read_input_handler

    def open(self, record_file_path: str):
        self.is_active = True
        self.record_full_path = record_file_path

    def post_read_input_handler(self, sender, e: PostReadInputEventArgs):
        if not self.is_active:
            return
        with open(self.record_full_path, 'a') as s:
            if e.command is not None:
                s.write(e.command)
            if e.command is None or e.terminating_char != 13:
                s.write(f'[{e.terminating_char}]')
            s.write("\n")