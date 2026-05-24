"""
Tests for screen operations and display functionality.

Critical tests include:
- Cursor positioning before printing (regression test)
- Buffer mode transitions
- Window switching
- Color handling
"""
import pytest
from unittest.mock import MagicMock
from zmachine.screen import ScreenV3, ScreenV4, ScreenV5
from zmachine.window import Window
from zmachine.event import EventManager
from zmachine.enums import WindowPosition, TextStyle, Color
from zmachine.constants import DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR


@pytest.mark.unit
class TestBaseScreen:
    """Test suite for BaseScreen functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_manager = EventManager()
    
    @pytest.mark.unit
    def test_buffer_mode_auto_flushes_on_disable(self, mock_terminal_adapter, mock_resource_data):
        """Setting buffer_mode=False should auto-flush the buffer."""
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_active_window_id_property(self, mock_terminal_adapter, mock_resource_data):
        """active_window_id should return correct window."""
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
        # Start in lower window
        assert screen.active_window == screen.windows[WindowPosition.LOWER]
        
        # Switch to upper window
        screen.set_window(WindowPosition.UPPER)
        assert screen.active_window == screen.windows[WindowPosition.UPPER]
    
    @pytest.mark.unit
    def test_write_to_active_window_flushes_first(self, mock_terminal_adapter, mock_resource_data):
        """write_to_active_window should flush buffer before writing."""
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_wrap_boundary_not_treated_as_indent(self, mock_terminal_adapter, mock_resource_data):
        """
        REGRESSION TEST: A space at the start of a line caused by word wrapping
        at the exact screen width must not be treated as an intentional indent. 
        If there are multiple screen flushes the output must be the same as if
        the screen buffer had been flushed once.

        Scenario:
        1. Flush text shorter than screen width, ending with a space.
        2. Flush text with no leading/trailing spaces that exactly fills
            the remaining screen width. Cursor is now at the right edge,
            setting a wrap boundary.
        3. Flush text that starts with a space (intentional indent).

        Expected:
        - Two lines written to the screen.
        - Line 1 exactly fills the screen width (flush 1 + flush 2 combined).
        - Line 2 does not start with a space (word wrapping across screen flushes
            is preserved).
        """
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        width = mock_terminal_adapter.width

        # Flush 1: text shorter than screen width, ending with a space.
        prefix = "The runes "
        assert len(prefix) < width

        # Flush 2: no leading/trailing spaces, exactly fills remaining width.
        remaining = width - len(prefix)
        middle = "a" * remaining
        assert len(prefix) + len(middle) == width

        # Flush 3: intentional indent - starts with a space.
        indent_text = " are inscribed across the top."

        def buffer_and_flush(text, newline = False):
            screen.print(text, newline)
            screen.flush_buffer(screen.lower_window)

        buffer_and_flush(prefix)
        buffer_and_flush(middle)
        buffer_and_flush(indent_text, True)

        # Inspect what was written to the adapter
        lines = mock_terminal_adapter.screen_output

        assert len(lines) >= 2, \
            f"Expected at least 2 lines, got: {lines!r}"

        assert lines[0] == prefix + middle, \
            f"Expected line 1 to be exactly {(prefix + middle)!r}, got: {lines[0]!r}"

        assert lines[1] == indent_text[1:], \
            f"Expected line 2 not to start with a space, " \
            f"got: {lines[1]!r}"
        
    @pytest.mark.unit
    def test_pause_line_count_with_full_width_lines(self, mock_terminal_adapter, mock_resource_data):
        """
        REGRESSION TEST: When a line of text exactly fills the screen width,
        the output line counter must still increment correctly so that the
        pause-after-page logic triggers at the right time.

        The bug: if cursor_x == width after a write, get_coordinates() returns
        x != 0 on the NEXT call, so flush_buffer's line count check
        (which looks for x == 0 after each write) would miss the increment.
        This caused the screen to scroll too far before pausing.

        Scenario:
        - Screen height is H lines. Pause threshold is H - 1 (upper window height).
        - Write H lines of text, each exactly filling the screen width.
        - After the last flush, output_line_count should equal H.
        """
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        width = mock_terminal_adapter.width
        height = mock_terminal_adapter.height

        # Set up a split screen with 1 line upper window so the
        # pause threshold is height - 1.
        screen.split_window(1)
        screen.set_window(WindowPosition.LOWER)

        # Each line exactly fills the screen width with no spaces,
        # so word wrap doesn't intervene - each flush produces exactly one line.
        full_line_text = "a" * width

        # Enable pause so output_line_count is actively tracked.
        screen.pause_enabled = True

        mock_terminal_adapter.get_input_char = MagicMock(return_value=13)

        screen.print('First line', True)
        screen.print(full_line_text, False)
        screen.print(' wrap to third line', True)

        # Write enough lines to fill the lower window completely.
        # The lower window is (height - 1) lines tall after the split.
        lower_height = height - 1
        for _ in range(lower_height - 3):
            screen.print('\n', False)

        screen.flush_buffer(screen.lower_window)

        mock_terminal_adapter.get_input_char.assert_called_with(False)
        mock_terminal_adapter.get_input_char.assert_called_once()

        expected_line_count = 1
        actual_line_count = screen.active_window.line_count
        assert actual_line_count == expected_line_count, (
            f"Expected output_line_count to be {expected_line_count} after writing "
            f"{lower_height} full-width lines, but got {actual_line_count}. "
            f"This indicates the line counter is not incrementing when text "
            f"exactly fills the screen width."
        )


@pytest.mark.unit
class TestScreenV3:
    """Test suite for V3 screen (status line)."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_manager = EventManager()
    
    @pytest.mark.unit
    def test_refresh_status_line_uses_status_parameter(self, mock_terminal_adapter, mock_resource_data):
        """
        REGRESSION TEST: refresh_status_line renamed parameter.
        
        Parameter changed from 'right_status' to 'status'.
        This test ensures the new parameter name is used.
        """
        screen = ScreenV3(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
        location = "West of House"
        status = "Score: 0  Moves: 1"
        
        # Should not raise AttributeError or TypeError
        screen.refresh_status_line(location, status)
        
        # Verify text was written
        output = ''.join(mock_terminal_adapter.screen_output)
        assert location in output
        assert status in output
    
    @pytest.mark.unit
    def test_status_line_cursor_positioning(self, mock_terminal_adapter, mock_resource_data):
        """Status line should save and restore cursor position."""
        screen = ScreenV3(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_set_cursor_validates_bounds(self, mock_terminal_adapter, mock_resource_data):
        """set_cursor should raise error for out-of-bounds positions."""
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_set_text_style_flushes_buffer(self, mock_terminal_adapter, mock_resource_data):
        """set_text_style should flush buffer before applying style."""
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_erase_lower_window_moves_cursor_to_bottom_left(self, mock_terminal_adapter, mock_resource_data):
        """Erasing lower window should move cursor to bottom-left of lower window (8.7.3.2.1)."""
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_set_color_handles_defaults(self, mock_terminal_adapter, mock_resource_data):
        """
        REGRESSION TEST: set_color default logic moved from adapter to screen.
        
        Color 0 means "use current", color 1 means "use default".
        """
        screen = ScreenV5(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
        # Set initial colors
        screen.set_color(Color.RED, Color.WHITE, -1)
        
        # Color 0 should use current
        screen.set_color(0, 0, -1)
        assert mock_terminal_adapter.color_pair == (Color.RED, Color.WHITE)
        
        # Color 1 should use default
        screen.set_color(1, 1, -1)
        assert mock_terminal_adapter.color_pair == (DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR)
    
    @pytest.mark.regression
    def test_print_table_cursor_ordering(self, mock_terminal_adapter, mock_resource_data):
        """
        CRITICAL REGRESSION TEST: print_table cursor positioning bug.
        
        Bug: Cursor was moved AFTER printing each row instead of BEFORE.
        This caused subsequent rows to start in the wrong place.
        
        Fix: Cursor must be positioned BEFORE printing each row.
        """
        screen = ScreenV5(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_print_table_advances_rows(self, mock_terminal_adapter, mock_resource_data):
        """print_table should advance Y coordinate for each row."""
        screen = ScreenV5(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_erase_window_resets_style(self, mock_terminal_adapter, mock_resource_data):
        """V5 erase_window should reset style to ROMAN."""
        screen = ScreenV5(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
        # Set some style
        screen.set_text_style(TextStyle.BOLD | TextStyle.ITALIC)
        
        # Erase window
        screen.erase_window(WindowPosition.LOWER)
        
        # Lower window style should be reset
        assert screen.lower_window.text_style_attributes == TextStyle.ROMAN

    @pytest.mark.unit
    def test_erase_lower_window_moves_cursor_to_top_left(self, mock_terminal_adapter, mock_resource_data):
        """Erasing lower window should move cursor to top-left of lower window (8.7.3.2.1)."""
        screen = ScreenV5(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_split_window_adjusts_geometry(self, mock_terminal_adapter, mock_resource_data):
        """split_window should correctly adjust window geometry."""
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_window_switching_flushes_buffer(self, mock_terminal_adapter, mock_resource_data):
        """Switching windows should flush the buffer."""
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
    def test_erase_window_clears_correct_window(self, mock_terminal_adapter, mock_resource_data):
        """erase_window should only erase the specified window."""
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
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
        window = Window(width=5, height=10, font_size=0x101)
        
        assert window.width == 5
        assert window.height == 10
        assert window.y_cursor == 0
        assert window.x_cursor == 0
        assert window.text_style_attributes == TextStyle.ROMAN
        assert window.background_color == DEFAULT_BACKGROUND_COLOR
        assert window.foreground_color == DEFAULT_FOREGROUND_COLOR
    
    @pytest.mark.unit
    def test_sync_cursor_updates_position(self):
        """sync_cursor should update cursor coordinates."""
        window = Window(width=5, height=10, font_size=0x101)
        
        window.sync_cursor(3, 7)
        
        assert window.y_cursor == 3
        assert window.x_cursor == 7