from abc import ABC, abstractmethod
from typing import Tuple
from .object_table import ObjectTable
from .enums import RoutineType


class AbstractZMachineInterpreter(ABC):
    """
    Interpreter interface to be referenced by the opcodes.
    """

    @property
    @abstractmethod
    def version(self) -> int:
        pass

    @property
    @abstractmethod
    def object_table(self) -> ObjectTable:
        pass

    @abstractmethod
    def do_branch(self, is_truthy):
        pass

    @abstractmethod
    def do_store(self, value: int):
        pass

    @abstractmethod
    def read_byte(self, addr: int) -> int:
        pass

    @abstractmethod
    def write_byte(self, addr: int, value: int):
        pass

    @abstractmethod
    def read_word(self, addr: int) -> int:
        pass

    @abstractmethod
    def write_word(self, addr: int, value: int):
        pass

    @abstractmethod
    def read_var(self, varnum: int) -> int:
        pass

    @abstractmethod
    def write_var(self, varnum: int, value: int):
        pass

    @abstractmethod
    def unpack_addr(self, packed_addr: int) -> int:
        pass

    @abstractmethod
    def do_routine(self, call_addr: int, args: Tuple[int], routine_type: int = RoutineType.STORE):
        pass

    @abstractmethod
    def do_return(self, retval: int):
        pass

    @abstractmethod
    def get_arg_count(self) -> int:
        pass

    @abstractmethod
    def do_jump(self, offset: int):
        pass

    @abstractmethod
    def do_save(self) -> bool:
        pass

    @abstractmethod
    def do_restore(self) -> bool:
        pass

    @abstractmethod
    def do_save_undo(self):
        pass

    @abstractmethod
    def do_restore_undo(self):
        pass

    @abstractmethod
    def do_restart(self):
        pass

    @abstractmethod
    def do_verify(self) -> bool:
        pass

    @abstractmethod
    def do_quit(self):
        pass

    @abstractmethod
    def do_show_status(self):
        pass

    @abstractmethod
    def stack_push(self, value):
        pass

    @abstractmethod
    def stack_pop(self) -> int:
        pass

    @abstractmethod
    def stack_peek(self) -> int:
        pass

    @abstractmethod
    def get_object_text(self, obj_id: int) -> str:
        pass

    @abstractmethod
    def print_from_pc(self, newline: bool = False):
        pass

    @abstractmethod
    def print_from_addr(self, addr: int, newline: bool = False):
        pass

    @abstractmethod
    def do_print_table(self, addr: int, width: int, height: int, skip: int):
        pass

    def write_to_output_streams(self, text: str, newline: bool = False):
        pass

    @abstractmethod
    def do_read(self, text_buffer_addr: int, parse_buffer_addr: int, time: int = 0, routine: int = 0):
        pass

    @abstractmethod
    def do_read_char(self, time: int = 0, routine: int = 0):
        pass

    @abstractmethod
    def do_tokenize(self, text_addr: int, parse_buffer: int, dictionary_addr: int = 0, flag: int = 0):
        pass

    @abstractmethod
    def do_encode_text(self, text_addr: int, length: int, start: int, coded_buffer: int):
        pass

    @abstractmethod
    def do_split_window(self, lines: int):
        pass

    @abstractmethod
    def do_set_window(self, window_id: int):
        pass

    @abstractmethod
    def do_erase_window(self, window_id: int):
        pass

    @abstractmethod
    def do_set_cursor(self, y: int, x: int):
        pass

    @abstractmethod
    def do_set_text_style(self, style: int):
        pass

    @abstractmethod
    def do_set_buffer_mode(self, mode: bool):
        pass

    @abstractmethod
    def do_select_output_stream(self, stream_id: int, table_addr: int = 0):
        pass

    @abstractmethod
    def do_sound_effect(self, type: int):
        pass

    @abstractmethod
    def do_set_color(self, foreground_color: int, background_color: int):
        pass