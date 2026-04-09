"""
Shared pytest fixtures and test utilities for Z-Machine tests.

This module provides common fixtures that can be used across all test modules.
"""
import pytest
import os
from typing import Protocol, Tuple
from zmachine.config import ZMachineConfig
from zmachine.memory import MemoryMap
from zmachine.enums import RoutineType, WindowPosition
from zmachine.protocol import IZMachineInterpreter, IObjectTable

# Color enum will be added in PR #10
try:
    from zmachine.enums import Color
except ImportError:
    # Create placeholder for pre-PR#10 testing
    class Color:
        BLACK = 2
        RED = 3
        GREEN = 4
        YELLOW = 5
        BLUE = 6
        MAGENTA = 7
        CYAN = 8
        WHITE = 9


# ============================================================================
# Mock Implementations
# ============================================================================

class MockTerminalAdapter:
    """Mock terminal adapter for testing without curses dependency."""
    
    def __init__(self, width: int = 80, height: int = 24):
        self._width = width
        self._height = height
        self.screen_output = []
        self.cursor_pos = (0, 0)
        self.input_chars = []
        self.input_strings = []
        self.style_attributes = 0
        self.color_pair = (Color.BLACK, Color.WHITE)
        self.scrollable_height = height
        self.timeout_ms = -1
        self.shutdown_called = False
        
    @property
    def height(self) -> int:
        return self._height
    
    @property
    def width(self) -> int:
        return self._width
    
    def refresh(self):
        pass
    
    def set_scrollable_height(self, top: int):
        self.scrollable_height = top
    
    def write_to_screen(self, text: str):
        self.screen_output.append(text)
    
    def get_input_char(self, echo: bool = True) -> int:
        if self.input_chars:
            return self.input_chars.pop(0)
        return ord('\n')
    
    def get_escape_sequence(self) -> list[int]:
        return []
    
    def get_input_string(self, prompt: str, lowercase: bool) -> str:
        if self.input_strings:
            result = self.input_strings.pop(0)
            return result.lower() if lowercase else result
        return ""
    
    def set_timeout(self, timeout_ms: int):
        self.timeout_ms = timeout_ms
    
    def get_coordinates(self) -> tuple[int, int]:
        return self.cursor_pos
    
    def move_cursor(self, y_pos: int, x_pos: int):
        self.cursor_pos = (y_pos, x_pos)
    
    def get_char_at(self, y_pos: int, x_pos: int) -> int:
        return ord(' ')
    
    def paint_char_at(self, y_pos: int, x_pos: int, char_and_attr: int):
        pass
    
    def erase_screen(self):
        self.screen_output.clear()
    
    def erase_window(self, top: int, height: int):
        pass
    
    def clear_to_eol(self):
        pass
    
    def apply_style_attributes(self, attributes: int):
        self.style_attributes = attributes
    
    def set_color(self, background_color: int, foreground_color: int):
        self.color_pair = (background_color, foreground_color)
    
    def sound_effect(self, sound_type: int):
        pass
    
    def shutdown(self):
        self.shutdown_called = True


class MockScreen:
    """Mock screen for testing without terminal dependencies."""
    
    def __init__(self, width: int = 80, height: int = 24):
        self.width = width
        self.height = height
        self.buffer_mode = True
        self.active_window_id = WindowPosition.LOWER
        self.operations = []  # Track method calls
        
    def print(self, text: str, newline: bool = False):
        self.operations.append(('print', text, newline))
    
    def write_to_active_window(self, text: str, newline: bool = False):
        self.operations.append(('write_to_active_window', text, newline))
    
    def set_window(self, window_id: int):
        self.operations.append(('set_window', window_id))
        self.active_window_id = window_id
    
    def split_window(self, lines: int):
        self.operations.append(('split_window', lines))
    
    def erase_window(self, window_id: int):
        self.operations.append(('erase_window', window_id))
    
    def set_cursor(self, y_pos: int, x_pos: int):
        self.operations.append(('set_cursor', y_pos, x_pos))
    
    def set_text_style(self, style: int):
        self.operations.append(('set_text_style', style))
    
    def set_color(self, background_color: int, foreground_color: int):
        self.operations.append(('set_color', background_color, foreground_color))
    
    def print_table(self, table: list[str]):
        self.operations.append(('print_table', table))
    
    def refresh_status_line(self, location: str, status: str):
        self.operations.append(('refresh_status_line', location, status))
    
    def sound_effect(self, type: int):
        self.operations.append(('sound_effect', type))


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_terminal_adapter():
    """Provide a mock terminal adapter for testing."""
    return MockTerminalAdapter()


@pytest.fixture
def mock_screen():
    """Provide a mock screen for testing."""
    return MockScreen()


@pytest.fixture
def sample_game_data():
    """Provide minimal valid Z-Machine V5 game data."""
    # Create minimal valid Z-Machine file header
    # Need at least 64KB for a proper Z-Machine file
    data = bytearray(0x1000)  # 4KB minimum
    data[0] = 5  # Version 5
    data[1:3] = b'\x00\x01'  # Release number
    data[4:10] = b'840726'  # Serial number
    data[0x0E:0x10] = b'\x00\x40'  # Static memory base = 0x0040 (after dynamic memory)
    data[0x1C:0x1E] = b'\x12\x34'  # Checksum
    return bytes(data)


@pytest.fixture
def test_config(tmp_path, sample_game_data):
    """Provide a test Z-Machine configuration."""
    # Create temporary game file
    game_file = tmp_path / "test.z5"
    game_file.write_bytes(sample_game_data)
    
    return ZMachineConfig.from_game_file(str(game_file))


@pytest.fixture
def memory_map(test_config):
    """Provide a test memory map."""
    return MemoryMap(test_config)


@pytest.fixture
def temp_save_file(tmp_path):
    """Provide a temporary save file path."""
    return tmp_path / "test_save.sav"


# ============================================================================
# Test Utilities
# ============================================================================

def create_valid_quetzal_save(pc: int, release: bytes, serial: bytes, checksum: int) -> bytes:
    """
    Create a valid Quetzal save file for testing.
    
    Args:
        pc: Program counter value
        release: 2-byte release number
        serial: 6-byte serial number
        checksum: 2-byte checksum
    
    Returns:
        Valid Quetzal save file bytes
    """
    from io import BytesIO
    
    # Build IFhd chunk (header)
    ifhd_data = (
        release +
        serial +
        checksum.to_bytes(2, 'big') +
        pc.to_bytes(3, 'big')
    )
    
    # Build CMem chunk (compressed memory) - minimal
    cmem_data = b'\x00' * 16  # Simplified for testing
    
    # Build Stks chunk (call stack) - minimal
    stks_data = b''  # Empty stack
    
    # Assemble chunks
    chunks = []
    
    # IFhd chunk
    chunks.append(b'IFhd')
    chunks.append(len(ifhd_data).to_bytes(4, 'big'))
    chunks.append(ifhd_data)
    if len(ifhd_data) % 2:
        chunks.append(b'\x00')  # Padding
    
    # CMem chunk
    chunks.append(b'CMem')
    chunks.append(len(cmem_data).to_bytes(4, 'big'))
    chunks.append(cmem_data)
    
    # Stks chunk
    chunks.append(b'Stks')
    chunks.append(len(stks_data).to_bytes(4, 'big'))
    chunks.append(stks_data)
    
    # Assemble FORM
    chunk_data = b''.join(chunks)
    form_data = b'IFZS' + chunk_data
    
    result = (
        b'FORM' +
        len(form_data).to_bytes(4, 'big') +
        form_data
    )
    
    return result


def assert_cursor_moved_before_print(operations: list, start_index: int = 0):
    """
    Assert that cursor movement happens before printing.
    
    This is a regression test for the print_table bug where cursor
    was moved AFTER printing instead of BEFORE.
    
    Args:
        operations: List of (operation_name, *args) tuples
        start_index: Index to start checking from
    """
    for i in range(start_index, len(operations) - 1):
        op_name, *args = operations[i]
        next_op_name, *next_args = operations[i + 1]
        
        # If we see a print operation
        if 'print' in next_op_name.lower():
            # The previous operation should be cursor movement (if any cursor ops exist)
            if 'cursor' in op_name.lower() or 'move' in op_name.lower():
                # This is correct - cursor moved before print
                continue
            # If previous op wasn't cursor movement, that's okay too
            # But if we see cursor movement AFTER print, that's wrong
        
        # Check for the BAD pattern: print followed by cursor movement
        if 'print' in op_name.lower() and ('cursor' in next_op_name.lower() or 'move' in next_op_name.lower()):
            raise AssertionError(
                f"Cursor movement after print detected at index {i}:\n"
                f"  Operation {i}: {operations[i]}\n"
                f"  Operation {i+1}: {operations[i+1]}\n"
                f"  Cursor MUST be moved BEFORE printing, not after!"
            )
        
# ============================================================================
# Mock Interpreter for Opcode Testing
# ============================================================================
 
class MockInterpreter:
    """
    Mock interpreter for testing opcodes in isolation.
    
    Provides minimal implementation of IZMachineInterpreter to support
    opcode execution tests without needing a full story file or game state.
    """
    
    def __init__(self, version: int = 5):
        self._version = version
        self._memory = bytearray(0x10000)  # 64KB memory
        self._stack = []  # Simple stack for testing
        self._locals = []  # Local variables
        self._globals_start = 0x100  # Globals at 0x100
        self._pc = 0x1000  # Program counter
        self._branch_taken = False
        self._stored_value = None
        self._object_table = None 
        self._output = []
        
        # Initialize globals area (240 bytes = 120 words)
        for i in range(240):
            self._memory[self._globals_start + i] = 0
    
    @property
    def version(self) -> int:
        return self._version
    
    @property
    def object_table(self) -> IObjectTable:
        # Lazy initialization if needed
        if self._object_table is None:
            self._object_table = MockObjectTable()
        return self._object_table
    
    @property
    def pc(self) -> int:
        return self._pc
    
    @pc.setter
    def pc(self, value: int):
        self._pc = value
    
    @property
    def branch_taken(self) -> bool:
        """Check if last branch was taken."""
        return self._branch_taken
    
    @property
    def stored_value(self) -> int:
        """Get last stored value."""
        return self._stored_value
    
    def do_branch(self, is_truthy: int):
        """Record whether branch was taken."""
        self._branch_taken = bool(is_truthy)
    
    def do_store(self, value: int):
        """Store result of operation."""
        self._stored_value = value & 0xFFFF  # Store as 16-bit value
    
    def read_byte(self, addr: int) -> int:
        """Read byte from memory."""
        return self._memory[addr & 0xFFFF]
    
    def write_byte(self, addr: int, value: int):
        """Write byte to memory."""
        self._memory[addr & 0xFFFF] = value & 0xFF
    
    def read_word(self, addr: int) -> int:
        """Read word from memory (big-endian, signed)."""
        addr = addr & 0xFFFF
        high = self._memory[addr]
        low = self._memory[addr + 1]
        value = (high << 8) | low
        # Convert to signed
        if value > 32767:
            value -= 65536
        return value
    
    def write_word(self, addr: int, value: int):
        """Write word to memory (big-endian)."""
        addr = addr & 0xFFFF
        # Convert to unsigned for storage
        if value < 0:
            value = 65536 + value
        self._memory[addr] = (value >> 8) & 0xFF
        self._memory[addr + 1] = value & 0xFF
    
    def read_var(self, varnum: int) -> int:
        """Read variable: 0=stack, 1-15=locals, 16+=globals."""
        if varnum == 0:
            return self.stack_pop()
        elif varnum <= 15:
            return self._locals[varnum - 1] if varnum <= len(self._locals) else 0
        else:
            # Globals: stored as words starting at _globals_start
            global_index = varnum - 16
            addr = self._globals_start + (global_index * 2)
            return self.read_word(addr)
    
    def write_var(self, varnum: int, value: int):
        """Write variable: 0=stack, 1-15=locals, 16+=globals."""
        if varnum == 0:
            self.stack_push(value)
        elif varnum <= 15:
            # Extend locals list if needed
            while len(self._locals) < varnum:
                self._locals.append(0)
            self._locals[varnum - 1] = value
        else:
            # Globals
            global_index = varnum - 16
            addr = self._globals_start + (global_index * 2)
            self.write_word(addr, value)
    
    def unpack_addr(self, packed_addr: int) -> int:
        """Unpack routine/string address."""
        if self._version <= 3:
            return packed_addr * 2
        elif self._version <= 5:
            return packed_addr * 4
        elif self._version <= 7:
            return packed_addr * 4  # V6-7 use offsets
        else:
            return packed_addr * 8
    
    def do_routine(self, call_addr: int, args: Tuple[int], routine_type: int = RoutineType.STORE):
        """Minimal routine call for testing."""
        pass
    
    def do_return(self, retval: int):
        """Minimal return for testing."""
        pass
    
    def get_arg_count(self) -> int:
        """Get argument count of current routine."""
        return len(self._locals)
    
    def do_jump(self, offset: int):
        """Jump by offset."""
        self._pc += offset
    
    def do_save(self) -> bool:
        return True
    
    def do_restore(self) -> bool:
        return True
    
    def do_save_undo(self):
        pass
    
    def do_restore_undo(self):
        pass
    
    def do_restart(self):
        pass
    
    def do_verify(self) -> bool:
        return True
    
    def do_quit(self):
        pass
    
    def do_show_status(self):
        pass
    
    def stack_push(self, value):
        """Push value onto stack."""
        self._stack.append(value & 0xFFFF)  # Store as 16-bit value
    
    def stack_pop(self) -> int:
        """Pop value from stack."""
        if not self._stack:
            return 0
        return self._stack.pop()
    
    def stack_peek(self) -> int:
        """Peek at top of stack without popping."""
        if not self._stack:
            return 0
        return self._stack[-1]
    
    def get_object_text(self, obj_id: int) -> str:
        return ""
    
    def print_from_pc(self, newline: bool = False):
        pass
    
    def print_from_addr(self, addr: int, newline: bool = False):
        pass
    
    def do_print_table(self, addr: int, width: int, height: int, skip: int):
        pass
    
    def write_to_output_streams(self, text: str, newline: bool = False):
        self._output.append(text)
    
    def do_read(self, text_buffer_addr: int, parse_buffer_addr: int, time: int = 0, routine: int = 0):
        pass
    
    def do_read_char(self, time: int = 0, routine: int = 0):
        pass
    
    def do_tokenize(self, text_addr: int, parse_buffer: int, dictionary_addr: int = 0, flag: int = 0):
        pass
    
    def do_encode_text(self, text_addr: int, length: int, start: int, coded_buffer: int):
        pass
    
    def do_split_window(self, lines: int):
        pass
    
    def do_set_window(self, window_id: int):
        pass
    
    def do_erase_window(self, window_id: int):
        pass
    
    def do_set_cursor(self, y: int, x: int):
        pass
    
    def do_set_text_style(self, style: int):
        pass
    
    def do_set_buffer_mode(self, mode: bool):
        pass
    
    def do_select_output_stream(self, stream_id: int, table_addr: int = 0):
        pass
    
    def do_sound_effect(self, type: int):
        pass
    
    def do_set_color(self, foreground_color: int, background_color: int):
        pass

class MockObjectTable:
    """Mock object table for testing."""
    
    def __init__(self):
        self._attributes = {}
        self._properties = {}
        self._parents = {}
        self._siblings = {}
        self._children = {}
    
    def get_attribute_flag(self, obj_id: int, attr_num: int) -> bool:
        return self._attributes.get((obj_id, attr_num), False)
    
    def set_attribute_flag(self, obj_id: int, attr_num: int, value: bool):
        self._attributes[(obj_id, attr_num)] = value
    
    def insert_object(self, obj_id: int, parent_id: int):
        self._parents[obj_id] = parent_id
    
    def get_property_data(self, obj_id: int, prop_id: int) -> int:
        return self._properties.get((obj_id, prop_id), 0)
    
    def set_property_data(self, obj_id: int, prop_id: int, value: int):
        self._properties[(obj_id, prop_id)] = value
    
    def get_property_addr(self, obj_id: int, prop_id: int) -> int | None:
        if (obj_id, prop_id) in self._properties:
            return 0x1000  # Dummy address
        return None
    
    def get_next_property_num(self, obj_id: int, prop_id: int) -> int:
        return 0
    
    def get_property_data_len(self, prop_addr: int) -> int:
        return 2
    
    def get_object_parent_id(self, obj_id: int) -> int:
        return self._parents.get(obj_id, 0)
    
    def get_object_sibling_id(self, obj_id: int) -> int:
        return self._siblings.get(obj_id, 0)
    
    def get_object_child_id(self, obj_id: int) -> int:
        return self._children.get(obj_id, 0)
    
    def orphan_object(self, obj_id: int):
        if obj_id in self._parents:
            del self._parents[obj_id]
    
    def get_object_text_zchars(self, obj_id: int) -> list[int]:
        return []
 
 
@pytest.fixture
def mock_interpreter():
    """Fixture providing a mock interpreter for opcode testing."""
    return MockInterpreter(version=5)
 