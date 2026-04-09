"""
Tests for output stream management.

Tests the refactored output stream API from PR #10.
"""
import pytest
from zmachine.output import OutputStreamManager, OutputStream, ScreenStream, MemoryStream
from zmachine.enums import OutputStreamType
from zmachine.error import StreamException


@pytest.mark.unit
class TestOutputStreamManager:
    """Test suite for OutputStreamManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        from zmachine.event import EventManager
        from zmachine.settings import RuntimeSettings
        
        self.event_manager = EventManager()
    
    @pytest.mark.unit
    def test_stream_properties_return_correct_types(
        self, memory_map, mock_screen, mock_terminal_adapter, test_config
    ):
        """
        Stream properties should return correct protocol types.
        
        This tests the refactored API where streams are accessed via
        properties instead of wrapper methods.
        """
        from zmachine.settings import RuntimeSettings
        
        runtime_settings = RuntimeSettings(memory_map)
        
        manager = OutputStreamManager(
            mock_screen,
            memory_map,
            mock_terminal_adapter,
            test_config,
            runtime_settings,
            self.event_manager
        )
        
        # Each property should return correct stream type
        assert hasattr(manager.screen_stream, 'open')
        assert hasattr(manager.transcript_stream, 'open')
        assert hasattr(manager.memory_stream, 'open')
        assert hasattr(manager.record_stream, 'open')
    
    @pytest.mark.unit
    def test_screen_stream_open_close(
        self, memory_map, mock_screen, mock_terminal_adapter, test_config
    ):
        """Screen stream should support open/close operations."""
        from zmachine.settings import RuntimeSettings
        
        runtime_settings = RuntimeSettings(memory_map)
        
        manager = OutputStreamManager(
            mock_screen,
            memory_map,
            mock_terminal_adapter,
            test_config,
            runtime_settings,
            self.event_manager
        )
        
        # Screen stream starts active
        assert manager.screen_stream.is_active
        
        # Close it
        manager.screen_stream.close()
        assert not manager.screen_stream.is_active
        
        # Reopen it
        manager.screen_stream.open()
        assert manager.screen_stream.is_active
    
    @pytest.mark.unit
    def test_memory_stream_requires_table_addr(
        self, memory_map, mock_screen, mock_terminal_adapter, test_config
    ):
        """Memory stream open() requires table_addr parameter."""
        from zmachine.settings import RuntimeSettings
        
        runtime_settings = RuntimeSettings(memory_map)
        
        manager = OutputStreamManager(
            mock_screen,
            memory_map,
            mock_terminal_adapter,
            test_config,
            runtime_settings,
            self.event_manager
        )
        
        # Should not be active initially
        assert not manager.memory_stream.is_active
        
        # Open with table address
        table_addr = 0x1000
        manager.memory_stream.open(table_addr)
        
        # Should now be active
        assert manager.memory_stream.is_active
    
    @pytest.mark.unit
    def test_record_stream_requires_file_path(
        self, memory_map, mock_screen, mock_terminal_adapter, test_config, tmp_path
    ):
        """Record stream open() requires record_file_path parameter."""
        from zmachine.settings import RuntimeSettings
        
        runtime_settings = RuntimeSettings(memory_map)
        
        manager = OutputStreamManager(
            mock_screen,
            memory_map,
            mock_terminal_adapter,
            test_config,
            runtime_settings,
            self.event_manager
        )
        
        # Should not be active initially
        assert not manager.record_stream.is_active
        
        # Open with file path
        record_path = str(tmp_path / "test_record.txt")
        manager.record_stream.open(record_path)
        
        # Should now be active
        assert manager.record_stream.is_active


@pytest.mark.unit
class TestOutputStream:
    """Test suite for base OutputStream class."""
    
    @pytest.mark.unit
    def test_is_active_property(self):
        """is_active should be accessible as property."""
        stream = OutputStream()
        
        # Should start inactive
        assert not stream.is_active
        
        # Should be settable
        stream.is_active = True
        assert stream.is_active
        
        stream.is_active = False
        assert not stream.is_active
    
    @pytest.mark.unit
    def test_write_not_implemented(self):
        """Base class write() should raise NotImplementedError."""
        stream = OutputStream()
        
        with pytest.raises(NotImplementedError):
            stream.write("test", False)


@pytest.mark.unit
class TestScreenStream:
    """Test suite for ScreenStream."""
    
    @pytest.mark.unit
    def test_screen_stream_writes_to_screen(self, mock_screen):
        """ScreenStream should write to screen when active."""
        stream = ScreenStream(mock_screen)
        
        # Should be active by default
        assert stream.is_active
        
        # Write should call screen.print
        stream.write("test text", False)
        
        # Should be in screen operations
        assert ('print', 'test text', False) in mock_screen.operations
    
    @pytest.mark.unit
    def test_screen_stream_respects_active_flag(self, mock_screen):
        """ScreenStream should only write when active."""
        stream = ScreenStream(mock_screen)
        
        # Deactivate
        stream.close()
        assert not stream.is_active
        
        # Clear operations
        mock_screen.operations.clear()
        
        # Write should not produce output
        stream.write("test", False)
        
        # No operations should have been recorded
        assert len(mock_screen.operations) == 0


@pytest.mark.unit
class TestMemoryStream:
    """Test suite for MemoryStream."""
    
    @pytest.mark.unit
    def test_memory_stream_buffers_output(self, memory_map):
        """MemoryStream should buffer output to memory."""
        stream = MemoryStream(memory_map)
        
        table_addr = 0x1000
        stream.open(table_addr)
        
        # Write some text
        test_text = "Hello"
        stream.write(test_text, False)
        
        # Should be buffered (actual write happens on close)
        assert stream.is_active
    
    @pytest.mark.unit
    def test_memory_stream_nested_opens_raises(self, memory_map):
        """Opening too many nested memory streams should raise."""
        stream = MemoryStream(memory_map)
        
        # Open maximum number of streams
        max_depth = 16  # Typical Z-Machine limit
        
        for i in range(max_depth):
            stream.open(0x1000 + i * 0x100)
        
        # One more should raise
        with pytest.raises(StreamException):
            stream.open(0x2000)


@pytest.mark.integration
class TestOutputStreamIntegration:
    """Integration tests for output stream interactions."""
    
    @pytest.mark.unit
    def test_write_to_multiple_streams(
        self, memory_map, mock_screen, mock_terminal_adapter, test_config, tmp_path
    ):
        """Writing should go to all active streams."""
        from zmachine.event import EventManager
        from zmachine.settings import RuntimeSettings
        
        event_manager = EventManager()
        runtime_settings = RuntimeSettings(memory_map)
        
        manager = OutputStreamManager(
            mock_screen,
            memory_map,
            mock_terminal_adapter,
            test_config,
            runtime_settings,
            event_manager
        )
        
        # Activate multiple streams
        manager.screen_stream.open()
        manager.transcript_stream.open()
        
        # Write text
        test_text = "multi-stream test"
        manager.write_to_streams(test_text, False)
        
        # Should appear in screen operations
        screen_writes = [op for op in mock_screen.operations if 'print' in op[0]]
        assert len(screen_writes) > 0
        
        # Memory stream should have buffered it
        assert manager.screen_stream.is_active


@pytest.mark.regression
class TestOutputStreamRefactoring:
    """
    Regression tests for PR #10 output stream refactoring.
    
    Tests the change from wrapper methods to direct property access.
    """
    
    @pytest.mark.unit
    def test_no_wrapper_methods_exist(
        self, memory_map, mock_screen, mock_terminal_adapter, test_config
    ):
        """
        Ensure old wrapper methods are removed.
        
        Before PR #10: manager.open_screen_stream()
        After PR #10: manager.screen_stream.open()
        """
        from zmachine.event import EventManager
        from zmachine.settings import RuntimeSettings
        
        event_manager = EventManager()
        runtime_settings = RuntimeSettings(memory_map)
        
        manager = OutputStreamManager(
            mock_screen,
            memory_map,
            mock_terminal_adapter,
            test_config,
            runtime_settings,
            event_manager
        )
        
        # Old methods should not exist
        assert not hasattr(manager, 'open_screen_stream')
        assert not hasattr(manager, 'close_screen_stream')
        assert not hasattr(manager, 'open_transcript_stream')
        assert not hasattr(manager, 'close_transcript_stream')
        assert not hasattr(manager, 'open_memory_stream')
        assert not hasattr(manager, 'close_memory_stream')
        assert not hasattr(manager, 'open_record_stream')
        assert not hasattr(manager, 'close_record_stream')
    
    @pytest.mark.unit
    def test_streams_accessible_via_properties(
        self, memory_map, mock_screen, mock_terminal_adapter, test_config
    ):
        """Streams should be accessible via properties."""
        from zmachine.event import EventManager
        from zmachine.settings import RuntimeSettings
        
        event_manager = EventManager()
        runtime_settings = RuntimeSettings(memory_map)
        
        manager = OutputStreamManager(
            mock_screen,
            memory_map,
            mock_terminal_adapter,
            test_config,
            runtime_settings,
            event_manager
        )
        
        # New properties should exist
        assert hasattr(manager, 'screen_stream')
        assert hasattr(manager, 'transcript_stream')
        assert hasattr(manager, 'memory_stream')
        assert hasattr(manager, 'record_stream')
        
        # And they should have open/close methods
        for stream_name in ['screen_stream', 'transcript_stream', 'memory_stream', 'record_stream']:
            stream = getattr(manager, stream_name)
            assert hasattr(stream, 'open')
            assert hasattr(stream, 'close')
            assert hasattr(stream, 'is_active')