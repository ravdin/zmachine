from abc import ABC, abstractmethod
from typing import Tuple
from event import EventManager
from object_table import ObjectTable


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

    @property
    @abstractmethod
    def event_manager(self) -> EventManager:
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
    def do_routine(self, call_addr: int, args: Tuple[int], discard_result: bool = False):
        pass

    @abstractmethod
    def do_return(self, retval: int):
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

    def write_to_output_streams(self, text: str, newline: bool = False):
        pass

    @abstractmethod
    def do_read(self, text_buffer: int, parser_buffer: int):
        pass
