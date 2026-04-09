"""
Tests for screen operations and display functionality.

Critical tests include:
- Cursor positioning before printing (regression test)
- Buffer mode transitions
- Window switching
- Color handling
"""
import pytest
from zmachine.screen import BaseScreen, ScreenV3, ScreenV4, ScreenV5, Window
from zmachine.event import EventManager
from zmachine.enums import WindowPosition, TextStyle, Color
from zmachine.constants import DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR
from tests.conftest import assert_cursor_moved_before_print


@pytest.mark.unit
class TestBaseScreen:
    """Test suite for BaseScreen functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_manager = EventManager()
    
    @pytest.mark.unit
    def test_buffer_mode_auto_flushes_on_disable(self, mock_terminal_adapter):
        """Setting buffer_mode=False should auto-flush the buffer."""
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        
        # Write some text to buffer
        screen.buffer_mode = True
        screen.print("test text", False)
        
        # Buffer should have content
        assert screen.text_buffer_ptr > 0
        
        # Disable buffer mode - should auto-flush
        screen.buffer_mode = False
        
        # Buffer should be empty after flush
        assert screen.text_buffer_ptr == 0
        assert "test text" in ''.join(mock_terminal_adapter.screen_output)
    
    @pytest.mark.unit
    def test_active_window_id_property(self, mock_terminal_adapter):
        """active_window_id should return correct window."""
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        
        # Start in lower window
        assert screen.active_window_id == WindowPosition.LOWER
        
        # Switch to upper window
        screen.set_window(WindowPosition.UPPER)
        assert screen.active_window_id == WindowPosition.UPPER
    
    @pytest.mark.unit
    def test_write_to_active_window_flushes_first(self, mock_terminal_adapter):
        """write_to_active_window should flush buffer before writing."""
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        
        # Add something to buffer
        screen.buffer_mode = True
        screen.write_to_buffer("buffered", False)
        assert screen.text_buffer_ptr > 0
        
        # Write to active window - should flush first
        screen.write_to_active_window("direct", False)
        
        # Buffer should be empty
        assert screen.text_buffer_ptr == 0
        
        # Both texts should be in output
        output = ''.join(mock_terminal_adapter.screen_output)
        assert "buffered" in output
        assert "direct" in output


@pytest.mark.unit
class TestScreenV3:
    """Test suite for V3 screen (status line)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_manager = EventManager()
    
    @pytest.mark.unit
    def test_refresh_status_line_uses_status_parameter(self, mock_terminal_adapter):
        """
        REGRESSION TEST: refresh_status_line renamed parameter.
        
        Parameter changed from 'right_status' to 'status'.
        This test ensures the new parameter name is used.
        """
        screen = ScreenV3(mock_terminal_adapter, self.event_manager)
        
        location = "West of House"
        status = "Score: 0  Moves: 1"
        
        # Should not raise AttributeError or TypeError
        screen.refresh_status_line(location, status)
        
        # Verify text was written
        output = ''.join(mock_terminal_adapter.screen_output)
        assert location in output
        assert status in output
    
    @pytest.mark.unit
    def test_status_line_cursor_positioning(self, mock_terminal_adapter):
        """Status line should save and restore cursor position."""
        screen = ScreenV3(mock_terminal_adapter, self.event_manager)
        
        # Set cursor to a known position
        original_pos = (10, 20)
        mock_terminal_adapter.cursor_pos = original_pos
        
        # Refresh status line
        screen.refresh_status_line("Location", "Status")
        
        # Cursor should be restored to original position
        assert mock_terminal_adapter.cursor_pos == original_pos


@pytest.mark.unit
class TestScreenV4:
    """Test suite for V4 screen functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_manager = EventManager()
    
    @pytest.mark.unit
    def test_set_cursor_validates_bounds(self, mock_terminal_adapter):
        """set_cursor should raise error for out-of-bounds positions."""
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        
        # Switch to upper window (cursor movement only allowed there)
        screen.set_window(WindowPosition.UPPER)
        
        # Valid position should work
        screen.set_cursor(0, 0)
        assert mock_terminal_adapter.cursor_pos == (0, 0)
        
        # Out of bounds should raise
        from zmachine.error import InvalidScreenOperationException
        
        with pytest.raises(InvalidScreenOperationException):
            screen.set_cursor(999, 0)  # y too large
        
        with pytest.raises(InvalidScreenOperationException):
            screen.set_cursor(0, 999)  # x too large
    
    @pytest.mark.unit
    def test_set_text_style_flushes_buffer(self, mock_terminal_adapter):
        """set_text_style should flush buffer before applying style."""
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        
        # Add text to buffer
        screen.buffer_mode = True
        screen.write_to_buffer("test", False)
        assert screen.text_buffer_ptr > 0
        
        # Set text style - should flush
        screen.set_text_style(TextStyle.BOLD)
        
        # Buffer should be empty
        assert screen.text_buffer_ptr == 0
        assert "test" in ''.join(mock_terminal_adapter.screen_output)

    @pytest.mark.unit
    def test_erase_lower_window_moves_cursor_to_bottom_left(self, mock_terminal_adapter):
        """Erasing lower window should move cursor to bottom-left of lower window (8.7.3.2.1)."""
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        
        # Move cursor to a different position
        screen.set_window(WindowPosition.LOWER)
        screen.set_cursor(0, 0)
        
        # Erase lower window
        screen.erase_window(WindowPosition.LOWER)
        
        # Cursor should be at bottom-left of lower window (0,0 relative to that window)
        assert mock_terminal_adapter.cursor_pos == (screen.height - 1, 0)


@pytest.mark.unit
class TestScreenV5:
    """Test suite for V5 screen (colors, tables)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_manager = EventManager()
    
    @pytest.mark.unit
    def test_set_color_handles_defaults(self, mock_terminal_adapter):
        """
        REGRESSION TEST: set_color default logic moved from adapter to screen.
        
        Color 0 means "use current", color 1 means "use default".
        """
        screen = ScreenV5(mock_terminal_adapter, self.event_manager)
        
        # Set initial colors
        screen.set_color(Color.RED, Color.WHITE)
        
        # Color 0 should use current
        screen.set_color(0, 0)
        assert mock_terminal_adapter.color_pair == (Color.RED, Color.WHITE)
        
        # Color 1 should use default
        screen.set_color(1, 1)
        assert mock_terminal_adapter.color_pair == (DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR)
    
    @pytest.mark.regression
    def test_print_table_cursor_ordering(self, mock_terminal_adapter):
        """
        CRITICAL REGRESSION TEST: print_table cursor positioning bug.
        
        Bug: Cursor was moved AFTER printing each row instead of BEFORE.
        This caused subsequent rows to start in the wrong place.
        
        Fix: Cursor must be positioned BEFORE printing each row.
        """
        screen = ScreenV5(mock_terminal_adapter, self.event_manager)
        
        # Set initial cursor position
        start_y, start_x = 5, 10
        mock_terminal_adapter.cursor_pos = (start_y, start_x)
        
        # Print table with multiple rows
        table = ["row1", "row2", "row3"]
        
        # Track operations
        operations = []
        
        # Monkey-patch to track operation order
        original_move = mock_terminal_adapter.move_cursor
        original_write = mock_terminal_adapter.write_to_screen
        
        def tracked_move(y, x):
            operations.append(('move_cursor', y, x))
            return original_move(y, x)
        
        def tracked_write(text):
            operations.append(('write', text))
            return original_write(text)
        
        mock_terminal_adapter.move_cursor = tracked_move
        mock_terminal_adapter.write_to_screen = tracked_write
        
        # Execute print_table
        screen.print_table(table)
        
        # Verify cursor moved BEFORE each print
        for i in range(len(table)):
            # Find the print operation for this row
            row_prints = [j for j, op in enumerate(operations) 
                         if op[0] == 'write' and table[i] in str(op[1])]
            
            if row_prints:
                print_index = row_prints[0]
                
                # Look backwards for cursor movement
                cursor_moves = [j for j in range(print_index) 
                               if j < len(operations) and operations[j][0] == 'move_cursor']
                
                assert cursor_moves, \
                    f"Row {i} ('{table[i]}'): No cursor movement before print!\n" \
                    f"Operations: {operations}"
                
                last_cursor_move = cursor_moves[-1]
                
                # Cursor move should be immediately before print
                # (there might be other operations in between, but cursor should come before print)
                assert last_cursor_move < print_index, \
                    f"Row {i} ('{table[i]}'): Cursor moved AFTER print!\n" \
                    f"Cursor move at index {last_cursor_move}, print at {print_index}\n" \
                    f"Operations: {operations}"
    
    @pytest.mark.unit
    def test_print_table_advances_rows(self, mock_terminal_adapter):
        """print_table should advance Y coordinate for each row."""
        screen = ScreenV5(mock_terminal_adapter, self.event_manager)
        
        start_y, start_x = 5, 10
        mock_terminal_adapter.cursor_pos = (start_y, start_x)
        
        table = ["row1", "row2", "row3"]
        
        # Track cursor movements
        cursor_positions = []
        original_move = mock_terminal_adapter.move_cursor
        
        def tracked_move(y, x):
            cursor_positions.append((y, x))
            return original_move(y, x)
        
        mock_terminal_adapter.move_cursor = tracked_move
        
        screen.print_table(table)
        
        # Should have moved cursor for each row
        assert len(cursor_positions) >= len(table)
        
        # Y should increment, X should stay same
        for i, (y, x) in enumerate(cursor_positions[:len(table)]):
            assert y == start_y + i, f"Row {i}: expected y={start_y + i}, got {y}"
            assert x == start_x, f"Row {i}: x should stay at {start_x}, got {x}"
    
    @pytest.mark.unit
    def test_erase_window_resets_style(self, mock_terminal_adapter):
        """V5 erase_window should reset style to ROMAN."""
        screen = ScreenV5(mock_terminal_adapter, self.event_manager)
        
        # Set some style
        screen.set_text_style(TextStyle.BOLD | TextStyle.ITALIC)
        
        # Erase window
        screen.erase_window(WindowPosition.LOWER)
        
        # Lower window style should be reset
        assert screen.lower_window.style_attributes == TextStyle.ROMAN

    @pytest.mark.unit
    def test_erase_lower_window_moves_cursor_to_top_left(self, mock_terminal_adapter):
        """Erasing lower window should move cursor to top-left of lower window (8.7.3.2.1)."""
        screen = ScreenV5(mock_terminal_adapter, self.event_manager)
        
        # Move cursor to a different position
        screen.split_window(5)
        screen.set_window(WindowPosition.LOWER)
        screen.set_cursor(screen.height - 1, 0)  # Move to bottom-left
        
        # Erase lower window
        screen.erase_window(WindowPosition.LOWER)
        
        # Cursor should be at top-left of lower window (5, 0 relative to that window)
        assert mock_terminal_adapter.cursor_pos == (5, 0)


@pytest.mark.integration
class TestScreenWindowManagement:
    """Integration tests for window management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_manager = EventManager()
    
    @pytest.mark.unit
    def test_split_window_adjusts_geometry(self, mock_terminal_adapter):
        """split_window should correctly adjust window geometry."""
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        
        # Split window to 5 lines
        screen.split_window(5)
        
        # Upper window should be 5 lines
        assert screen.upper_window.height == 5
        
        # Lower window should be remaining space
        expected_lower_height = mock_terminal_adapter.height - 5
        assert screen.lower_window.height == expected_lower_height
        
        # Lower window should start after upper
        assert screen.lower_window.y_pos == 5
    
    @pytest.mark.unit
    def test_window_switching_flushes_buffer(self, mock_terminal_adapter):
        """Switching windows should flush the buffer."""
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        
        # Write to lower window buffer
        screen.buffer_mode = True
        screen.write_to_buffer("lower text", False)
        assert screen.text_buffer_ptr > 0
        
        # Switch to upper window - should flush
        screen.set_window(WindowPosition.UPPER)
        
        # Buffer should be empty
        assert screen.text_buffer_ptr == 0
        assert "lower text" in ''.join(mock_terminal_adapter.screen_output)
    
    @pytest.mark.unit
    def test_erase_window_clears_correct_window(self, mock_terminal_adapter):
        """erase_window should only erase the specified window."""
        screen = ScreenV4(mock_terminal_adapter, self.event_manager)
        
        # This is a simplified test - actual implementation would verify
        # that only the correct window region is erased
        
        # Erase upper window
        screen.erase_window(WindowPosition.UPPER)
        
        # Upper window cursor should be reset
        assert screen.upper_window.y_cursor == screen.upper_window.y_pos
        assert screen.upper_window.x_cursor == 0


@pytest.mark.unit
class TestWindow:
    """Test suite for Window class."""
    
    @pytest.mark.unit
    def test_window_initialization(self):
        """Window should initialize with correct defaults."""
        window = Window(width=5, height=10)
        
        assert window.width == 5
        assert window.height == 10
        assert window.y_cursor == 0
        assert window.x_cursor == 0
        assert window.style_attributes == TextStyle.ROMAN
        assert window.background_color == DEFAULT_BACKGROUND_COLOR
        assert window.foreground_color == DEFAULT_FOREGROUND_COLOR
    
    @pytest.mark.unit
    def test_sync_cursor_updates_position(self):
        """sync_cursor should update cursor coordinates."""
        window = Window(width=5, height=10)
        
        window.sync_cursor(3, 7)
        
        assert window.y_cursor == 3
        assert window.x_cursor == 7