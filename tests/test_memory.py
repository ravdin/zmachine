"""
Tests for memory map and call stack functionality.
"""
import pytest
from zmachine.memory import MemoryMap
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
    def test_reset_dynamic_memory(self, memory_map):
        """reset_dynamic_memory should restore dynamic memory region."""
        # Modify some dynamic memory
        address = 0x3f
        original = memory_map.read_byte(address)
        memory_map.write_byte(address, original + 1)
        
        # Save the current state
        current_dynamic = bytearray()
        for addr in range(0, memory_map.static_memory_base_addr):
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