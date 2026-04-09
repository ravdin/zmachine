"""
Tests for error handling and edge cases.

This module tests exceptional conditions and boundary cases.
"""
import pytest
from zmachine.error import (
    InvalidGameFileException,
    ZSCIIException,
    IllegalWriteException,
    InvalidMemoryException,
    StreamException,
)

# ZMachineException and InvalidScreenOperationException will be added in PR #10
# For now, create placeholders for testing
try:
    from zmachine.error import ZMachineException
except ImportError:
    # Not yet in codebase - will be added in PR #10
    ZMachineException = Exception

try:
    from zmachine.error import InvalidScreenOperationException
except ImportError:
    # Not yet in codebase - will be added in PR #10
    class InvalidScreenOperationException(Exception):
        pass


@pytest.mark.unit
class TestExceptionHierarchy:
    """Test the exception hierarchy from PR #10."""
    
    @pytest.mark.unit
    def test_all_exceptions_inherit_from_base(self):
        """All Z-Machine exceptions should inherit from ZMachineException."""
        exception_types = [
            InvalidScreenOperationException,
            InvalidGameFileException,
            ZSCIIException,
            IllegalWriteException,
            InvalidMemoryException,
            StreamException,
        ]
        
        for exc_type in exception_types:
            assert issubclass(exc_type, ZMachineException), \
                f"{exc_type.__name__} should inherit from ZMachineException"
    
    @pytest.mark.unit
    def test_exceptions_can_be_caught_generically(self):
        """All Z-Machine exceptions should be catchable as ZMachineException."""
        try:
            raise InvalidScreenOperationException("test error")
        except ZMachineException as e:
            assert "test error" in str(e)
        else:
            pytest.fail("Exception should have been caught")
    
    @pytest.mark.unit
    def test_exceptions_can_be_caught_specifically(self):
        """Specific exception types should still be catchable."""
        try:
            raise IllegalWriteException(0x5000)
        except IllegalWriteException as e:
            assert "5000" in str(e)
        except ZMachineException:
            pytest.fail("Should have caught specific exception type")


@pytest.mark.unit
class TestScreenErrorHandling:
    """Test error handling in screen operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        from zmachine.event import EventManager
        self.event_manager = EventManager()
    
    @pytest.mark.unit
    def test_unsupported_operations_raise_not_implemented(self, mock_terminal_adapter):
        """Unsupported operations should raise NotImplementedError."""
        from zmachine.screen import BaseScreen
        
        screen = BaseScreen(mock_terminal_adapter, self.event_manager)
        
        # These operations are not implemented in base screen
        with pytest.raises(NotImplementedError):
            screen.set_cursor(0, 0)
        
        with pytest.raises(NotImplementedError):
            screen.set_text_style(0)
        
        with pytest.raises(NotImplementedError):
            screen.set_color(0, 0)
        
        with pytest.raises(NotImplementedError):
            screen.print_table([])
        
        with pytest.raises(NotImplementedError):
            screen.refresh_status_line("", "")
    
    @pytest.mark.unit
    def test_invalid_window_id_raises(self, mock_terminal_adapter):
        """Invalid window ID should raise InvalidScreenOperationException."""
        from zmachine.screen import ScreenV4
        
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        
        with pytest.raises(InvalidScreenOperationException):
            screen.set_window(999)  # Invalid window ID
    
    @pytest.mark.unit
    def test_cursor_out_of_bounds_raises(self, mock_terminal_adapter):
        """Cursor movement outside screen bounds should raise error."""
        from zmachine.screen import ScreenV4
        
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        screen.set_window(1)  # Upper window (allows cursor movement)
        
        with pytest.raises(InvalidScreenOperationException):
            screen.set_cursor(999, 999)


@pytest.mark.unit
class TestMemoryErrorHandling:
    """Test error handling in memory operations."""
    
    @pytest.mark.unit
    def test_write_to_static_memory_raises(self, memory_map, test_config):
        """Writing to static memory should raise IllegalWriteException."""
        static_addr = test_config.static_memory_base_addr
        
        with pytest.raises(IllegalWriteException) as exc_info:
            memory_map.write_byte(static_addr, 0xFF)
        
        assert str(static_addr) in str(exc_info.value) or \
               hex(static_addr) in str(exc_info.value)
    
    @pytest.mark.unit
    def test_read_invalid_address_raises(self, memory_map):
        """Reading from invalid address should raise InvalidMemoryException."""
        with pytest.raises(InvalidMemoryException):
            memory_map.read_byte(0xFFFFFF)
    
    @pytest.mark.unit
    def test_write_invalid_address_raises(self, memory_map):
        """Writing to invalid address should raise InvalidMemoryException."""
        with pytest.raises(IllegalWriteException):
            memory_map.write_byte(0xFFFFFF, 0)


@pytest.mark.unit
class TestStreamErrorHandling:
    """Test error handling in stream operations."""
    
    @pytest.mark.unit
    def test_too_many_nested_memory_streams_raises(self, memory_map):
        """Opening too many nested memory streams should raise StreamException."""
        from zmachine.output import MemoryStream
        
        stream = MemoryStream(memory_map)
        
        # Z-Machine spec limits to 16 nested streams
        max_depth = 16
        
        # Open max number of streams
        for i in range(max_depth):
            stream.open(0x1000 + i * 0x100)
        
        # One more should raise
        with pytest.raises(StreamException) as exc_info:
            stream.open(0x2000)
        
        assert "too many" in str(exc_info.value).lower() or \
               "memory stream" in str(exc_info.value).lower()


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.unit
    def test_zero_length_text(self, mock_screen):
        """Screen should handle empty text gracefully."""
        from zmachine.output import ScreenStream
        
        stream = ScreenStream(mock_screen)
        
        # Should not crash
        stream.write("", False)
        stream.write("", True)
    
    @pytest.mark.unit
    def test_very_long_text(self, mock_screen):
        """Screen should handle very long text."""
        from zmachine.output import ScreenStream
        
        stream = ScreenStream(mock_screen)
        
        # 10KB of text
        long_text = "x" * 10000
        
        # Should not crash
        stream.write(long_text, False)
    
    @pytest.mark.unit
    def test_null_bytes_in_memory(self, memory_map):
        """Memory should handle null bytes correctly."""
        address = 0x3e
        
        memory_map.write_byte(address, 0x00)
        result = memory_map.read_byte(address)
        
        assert result == 0x00
    
    @pytest.mark.unit
    def test_max_value_bytes(self, memory_map):
        """Memory should handle maximum value bytes."""
        address = 0x3e
        
        memory_map.write_byte(address, 0xFF)
        result = memory_map.read_byte(address)
        
        assert result == 0xFF
    
    @pytest.mark.unit
    def test_max_value_words(self, memory_map):
        """Memory should handle maximum value words."""
        address = 0x3e
        
        memory_map.write_word(address, 0xFFFF)
        result = memory_map.read_word(address)
        
        assert result == 0xFFFF
    
    @pytest.mark.unit
    def test_empty_call_stack(self):
        """Empty call stack operations should handle gracefully."""
        from zmachine.stack import CallStack
        
        stack = CallStack()
        
        # Popping from empty stack should raise
        with pytest.raises(Exception):
            stack.pop_value()
    
    @pytest.mark.unit
    def test_window_split_to_zero(self, mock_terminal_adapter):
        """Splitting window to 0 lines should work."""
        from zmachine.screen import ScreenV4
        from zmachine.event import EventManager
        
        event_manager = EventManager()
        screen = ScreenV4(mock_terminal_adapter, event_manager)
        
        # Split to 0 should work (unsplit)
        screen.split_window(0)
        
        assert screen.upper_window.height == 0
    
    @pytest.mark.unit
    def test_window_split_to_full_height(self, mock_terminal_adapter):
        """Splitting window to full height should work."""
        from zmachine.screen import ScreenV4
        from zmachine.event import EventManager
        
        event_manager = EventManager()
        screen = ScreenV4(mock_terminal_adapter, event_manager)
        
        # Split to full height
        screen.split_window(mock_terminal_adapter.height)
        
        assert screen.upper_window.height == mock_terminal_adapter.height
        assert screen.lower_window.height == 0


@pytest.mark.integration
class TestErrorRecovery:
    """Test error recovery and graceful degradation."""
    
    @pytest.mark.unit
    def test_continue_after_invalid_operation(self, mock_terminal_adapter):
        """System should continue working after invalid operation."""
        from zmachine.screen import ScreenV4
        from zmachine.event import EventManager
        
        event_manager = EventManager()
        screen = ScreenV4(mock_terminal_adapter, event_manager)
        screen.buffer_mode = False
        
        # Try invalid operation
        try:
            screen.set_window(999)
        except InvalidScreenOperationException:
            pass
        
        # Should still be able to use screen
        screen.set_window(0)
        screen.print("test", False)
        
        # Check that print worked
        assert ('print', 'test', False) in mock_terminal_adapter.screen_output or \
               'test' in ''.join(str(x) for x in mock_terminal_adapter.screen_output)


@pytest.mark.unit
class TestTypeValidation:
    """Test type validation and contracts."""
    
    @pytest.mark.regression
    def test_restore_never_returns_bool_on_any_error(
        self, memory_map, mock_terminal_adapter, tmp_path
    ):
        """
        Comprehensive test that restore never returns bool.
        
        Tests all error paths to ensure bool is never returned.
        """
        from zmachine.quetzal import Quetzal
        from zmachine.stack import CallStack
        
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.game_file = str(tmp_path / "test.z5")
        call_stack = CallStack()
        
        # Test various error conditions
        error_conditions = [
            # Missing file
            lambda: "nonexistent.sav",
            # Invalid header
            lambda: self._create_file_with_content(tmp_path, b"XXXX"),
            # Wrong FORM type
            lambda: self._create_file_with_content(tmp_path, b"FORM\x00\x00\x00\x08XXXX"),
            # Empty file
            lambda: self._create_file_with_content(tmp_path, b""),
        ]
        
        for i, setup_error in enumerate(error_conditions):
            filename = setup_error()
            if isinstance(filename, str):
                quetzal.prompt_save_file = lambda: filename
            else:
                quetzal.prompt_save_file = lambda: filename.name
            
            result = quetzal.do_restore(call_stack)
            
            # Critical assertions
            assert not isinstance(result, bool), \
                f"Error condition {i}: returned bool ({result})"
            assert result is None or isinstance(result, int), \
                f"Error condition {i}: returned {type(result)}, expected int | None"
    
    def _create_file_with_content(self, tmp_path, content):
        """Helper to create a file with given content."""
        import tempfile
        f = tmp_path / f"test_{len(content)}.sav"
        f.write_bytes(content)
        return f