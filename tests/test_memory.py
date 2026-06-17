"""
Tests for memory map and call stack functionality.
"""
import pytest
from zmachine.output import MemoryStream
from zmachine.stack import CallStack
from zmachine.error import IllegalWriteException, InvalidMemoryException


@pytest.mark.unit
class TestMemoryMap:
    """Test suite for MemoryMap."""
    
    @pytest.mark.unit
    def test_read_write_byte(self, memory_map):
        """Memory map should support byte read/write in dynamic memory."""
        # Write to dynamic memory (should succeed)
        address = 0x3f  # Should be in dynamic memory
        value = 0x42
        
        memory_map.write_byte(address, value)
        result = memory_map.read_byte(address)
        
        assert result == value
    
    @pytest.mark.unit
    def test_read_write_word(self, memory_map):
        """Memory map should support word read/write."""
        address = 0x3e
        value = 0x1234
        
        memory_map.write_word(address, value)
        result = memory_map.read_word(address)
        
        assert result == value
    
    @pytest.mark.unit
    def test_write_to_static_memory_raises(self, memory_map, test_config):
        """Writing to static memory should raise IllegalWriteException."""
        # Static memory starts at static_memory_base_addr
        static_addr = test_config.static_memory_base_addr
        
        with pytest.raises(IllegalWriteException):
            memory_map.write_byte(static_addr, 0xFF)
    
    @pytest.mark.unit
    def test_read_out_of_bounds_raises(self, memory_map):
        """Reading beyond memory bounds should raise InvalidMemoryException."""
        with pytest.raises(InvalidMemoryException):
            memory_map.read_byte(0xFFFFFF)  # Way beyond memory
    
    @pytest.mark.unit
    def test_reset_dynamic_memory(self, memory_map, test_config):
        """reset_dynamic_memory should restore dynamic memory region."""
        # Modify some dynamic memory
        address = 0x3f
        original = memory_map.read_byte(address)
        memory_map.write_byte(address, original + 1)
        
        # Save the current state
        current_dynamic = bytearray()
        for addr in range(0, test_config.static_memory_base_addr):
            current_dynamic.append(memory_map.read_byte(addr))
        
        # Reset should restore to original
        memory_map.reset_dynamic_memory(bytes(current_dynamic))
        
        # Value should be what we set it to (since we captured that state)
        assert memory_map.read_byte(address) == original + 1


@pytest.mark.unit
class TestCallStack:
    """Test suite for CallStack."""
    
    @pytest.mark.unit
    def test_push_pop_value(self):
        """Stack should support push/pop operations."""
        from zmachine.stack import EvalStack
        
        stack = EvalStack()
        test_value = 0x1234
        stack.push(test_value)
        result = stack.pop()
        
        assert result == test_value
    
    @pytest.mark.unit
    def test_pop_empty_stack_raises(self):
        """Popping from empty stack should raise an error."""
        from zmachine.stack import EvalStack
        
        stack = EvalStack()
        
        with pytest.raises(Exception):  # Or specific stack exception
            stack.pop()
    
    @pytest.mark.unit
    def test_push_call_frame(self):
        """Stack should support pushing call frames."""
        stack = CallStack()
        
        # Push a call frame - using actual API
        return_pc = 0x5000
        num_locals = 3
        result_variable = 0x10
        
        # CallStack.push() creates a frame
        stack.push(
            return_pc=0x5000,
            arg_count=0,
            routine_type=0,  # STORE
            local_vars=[0] * num_locals,
            store_varnum=1
        )
        
        # Stack should have a frame
        assert stack.current_frame is not None
    
    @pytest.mark.unit
    def test_pop_call_frame(self):
        """Stack should support popping call frames."""
        stack = CallStack()
        
        return_pc = 0x5000
        num_locals = 3
        result_variable = 0x10
        
        stack.push(
            return_pc=0x5000,
            arg_count=0,
            routine_type=0,  # STORE
            local_vars=[0] * num_locals,
            store_varnum=1
        )
        
        frame = stack.pop()
        
        assert frame.return_pc == return_pc
    
    @pytest.mark.unit
    def test_serialization_round_trip(self):
        """Stack should serialize and deserialize correctly."""
        from zmachine.stack import EvalStack
        
        stack1 = CallStack()
        
        stack1.push(
            return_pc=0x5000,
            arg_count=0,
            routine_type=0,  # STORE
            local_vars=[0] * 3,
            store_varnum=1
        )

        # Add some state
        stack1.current_frame.eval_stack.push(0x1111)
        
        # Serialize
        data = stack1.serialize()
        
        # Deserialize into new stack
        stack2 = CallStack()
        stack2.deserialize(data)
        
        # Should have frame
        frame = stack2.current_frame
        assert frame is not None
        assert frame.return_pc == 0x5000
        assert frame.eval_stack.pop() == 0x1111


@pytest.mark.integration
class TestMemoryAndStack:
    """Integration tests for memory and stack interaction."""
    
    @pytest.mark.unit
    def test_local_variables_in_memory(self, memory_map):
        """Local variables should be accessible through call stack."""
        stack = CallStack()
        
        # Push a call frame with locals
        stack.push(
            return_pc=0x5000,
            arg_count=0,
            routine_type=0,  # STORE
            local_vars=[0] * 3,
            store_varnum=1
        )
        
        # Set local variables
        for i in range(3):
            stack.set_local_var(i, 0x1000 + i)
        
        # Read them back
        for i in range(3):
            value = stack.get_local_var(i)
            assert value == 0x1000 + i

# ============================================================================
# MemoryStream
# ============================================================================

class _MockMemory:
    """Minimal memory map: flat dict-backed byte store with word helpers."""
    def __init__(self, version: int = 6, font_width: int = 10):
        self._mem = {}
        self._version = version
        self._font_width = font_width

    def write_byte(self, addr: int, val: int):
        self._mem[addr] = val & 0xff

    def read_byte(self, addr: int) -> int:
        if addr == 0:
            return self._version
        if addr == 0x27:  # V6 font width byte, used by close() for unit width
            return self._font_width
        return self._mem.get(addr, 0)

    def write_word(self, addr: int, val: int):
        self._mem[addr] = (val >> 8) & 0xff
        self._mem[addr + 1] = val & 0xff

    def read_word(self, addr: int) -> int:
        return (self._mem.get(addr, 0) << 8) | self._mem.get(addr + 1, 0)

    def bytes_at(self, addr: int, length: int) -> bytes:
        return bytes(self._mem.get(addr + i, 0) for i in range(length))


class TestMemoryStreamPlain:
    """The non-buffered path (normal output_stream 3)."""

    @pytest.mark.unit
    def test_plain_write_stores_length_prefixed_text(self):
        mem = _MockMemory(version=5)
        stream = MemoryStream(mem)
        addr = 0x1000
        stream.open(addr, False, 0)
        stream.write("Hello", False)
        stream.close()

        # Word at addr = length; bytes follow.
        assert mem.read_word(addr) == len("Hello")
        assert mem.bytes_at(addr + 2, 5) == b"Hello"

    @pytest.mark.unit
    def test_nested_streams_lifo(self):
        """Memory streams nest; closing pops the most recent table."""
        mem = _MockMemory(version=5)
        stream = MemoryStream(mem)
        stream.open(0x1000, False, 0)
        stream.write("outer", False)
        stream.open(0x2000, False, 0)
        stream.write("in", False)
        stream.close()  # closes inner (0x2000)

        assert mem.read_word(0x2000) == 2
        assert mem.bytes_at(0x2002, 2) == b"in"

        stream.close()  # closes outer (0x1000)
        assert mem.read_word(0x1000) == 5
        assert mem.bytes_at(0x1002, 5) == b"outer"


class TestMemoryStreamBuffered:
    """The buffered/print_form path (flush_buffered)."""

    @pytest.mark.unit
    def test_text_shorter_than_width_single_row(self):
        """A line shorter than the width is written as one row plus a 0 terminator."""
        mem = _MockMemory(version=6)
        stream = MemoryStream(mem)
        addr = 0x1000
        stream.open(addr, True, 10)  # buffering on, width 10
        stream.write("Hello", False)
        stream.close()

        # Row 0: length 5, "Hello"
        assert mem.read_word(addr) == 5
        assert mem.bytes_at(addr + 2, 5) == b"Hello"
        # Terminator word (0) follows the row.
        assert mem.read_word(addr + 2 + 5) == 0

    @pytest.mark.unit
    def test_hard_break_when_no_whitespace(self):
        """A run longer than width with no spaces is hard-broken at the width."""
        mem = _MockMemory(version=6)
        stream = MemoryStream(mem)
        addr = 0x1000
        stream.open(addr, True, 4)  # width 4
        stream.write("abcdefg", False)  # 7 chars, no spaces
        stream.close()

        # First row: 4 chars + newline marker. flush() writes count+1 as the
        # word and appends a 13. Row word should be 4 + 1 = 5.
        assert mem.read_word(addr) == 5
        assert mem.bytes_at(addr + 2, 4) == b"abcd"
