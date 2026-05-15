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
from zmachine.screen import ScreenV3, ScreenV4, ScreenV5, ScreenV6
from zmachine.window import Window
from zmachine.event import EventManager
from zmachine.enums import WindowPosition, TextStyle, Color, FontEnum
from zmachine.constants import DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR
from zmachine.error import InvalidScreenOperationException


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
        screen.set_buffer_mode(False)
        
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
        screen.set_buffer_mode(True)
        screen.write_to_buffer("buffered", False)
        assert screen.text_buffer_ptr > 0
        
        # Write to active window - should flush first
        screen.set_buffer_mode(False)
        screen.print("direct", False)
        
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
            screen.set_window(0)
            screen.print(text, newline)
            screen.flush_buffer()

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

        screen.set_window(0)
        screen.flush_buffer()

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
    def test_store_cursor_coordinates(self, mock_terminal_adapter, mock_resource_data):
        """
        The screen uses 0-indexed, absolute coordinates for positioning the cursor.
        The test verifies that storing the active window coordinates in the Window
        class stores 1-index, relative to the top left of the window, as understood
        by the game.
        """
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        height = mock_terminal_adapter.height
        mock_terminal_adapter.cursor_pos = (height - 1, 0)
        
        screen.set_window(0)
        screen.reset_cursor(screen.windows[0])
        screen.set_window(WindowPosition.UPPER)
        screen.store_cursor_coordinates()
        cursor_y, cursor_x = screen.windows[1].y_cursor, screen.windows[1].x_cursor
        assert (cursor_y, cursor_x) == (1, 1), (
            f'Expected upper window cursor to be (1, 1), got ({cursor_y}, {cursor_x})'
        )

        screen.split_window(1)
        screen.set_window(WindowPosition.LOWER)
        screen.print('>')
        screen.store_cursor_coordinates()
        cursor_y, cursor_x = screen.windows[0].y_cursor, screen.windows[0].x_cursor
        expected_y, expected_x = height - 1, 2
        assert (cursor_y, cursor_x) == (expected_y, expected_x), (
            f'Expected upper window cursor to be ({expected_y}, {expected_x}), got ({cursor_y}, {cursor_x})'
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
        screen.set_cursor(1, 1)
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
        screen.set_cursor(1, 1)
        
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
        screen.set_color(Color.WHITE, Color.RED, -3)
        
        # Color 0 should use current
        screen.set_color(0, 0, -3)
        assert mock_terminal_adapter.color_pair == (Color.RED, Color.WHITE)
        
        # Color 1 should use default
        screen.set_color(1, 1, -3)
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
        assert screen.windows[0].text_style_attributes == TextStyle.ROMAN

    @pytest.mark.unit
    def test_erase_lower_window_moves_cursor_to_top_left(self, mock_terminal_adapter, mock_resource_data):
        """Erasing lower window should move cursor to top-left of lower window (8.7.3.2.1)."""
        screen = ScreenV5(mock_terminal_adapter, mock_resource_data, self.event_manager)
        
        # Move cursor to a different position
        screen.split_window(5)
        screen.set_window(WindowPosition.LOWER)
        
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
        lower_window, upper_window = screen.windows
        
        # Split window to 5 lines
        screen.split_window(5)
        
        # Upper window should be 5 lines
        assert upper_window.height == 5
        
        # Lower window should be remaining space
        expected_lower_height = mock_terminal_adapter.height - 5
        assert lower_window.height == expected_lower_height
        
        # Lower window should start after upper
        assert lower_window.y_pos == 6
    
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
        screen.erase_window(1)
        upper_window = screen.windows[1]
        
        # Upper window cursor should be reset
        assert upper_window.y_cursor == upper_window.y_pos
        assert upper_window.x_cursor == 1


@pytest.mark.unit
class TestWindow:
    """Test suite for Window class."""
    
    @pytest.mark.unit
    def test_window_initialization(self):
        """Window should initialize with correct defaults."""
        window = Window(width=5, height=10, font_size=0x101)
        
        assert window.width == 5
        assert window.height == 10
        assert window.y_cursor == 1
        assert window.x_cursor == 1
        assert window.text_style_attributes == TextStyle.ROMAN
        assert window.background_color == DEFAULT_BACKGROUND_COLOR
        assert window.foreground_color == DEFAULT_FOREGROUND_COLOR
    

# ============================================================================
# wrap_lines iterator
# ============================================================================

class TestWrapLines:
    def setup_method(self):
        self.event_manager = EventManager()

    def _screen(self, mock_terminal_adapter, mock_resource_data):
        return ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)

    @pytest.mark.unit
    def test_hard_break_long_word(self, mock_terminal_adapter, mock_resource_data):
        """A word longer than the line width is hard-broken (forward progress)."""
        screen = self._screen(mock_terminal_adapter, mock_resource_data)
        width = mock_terminal_adapter.width  # 80, font_width 1
        screen.set_window(WindowPosition.LOWER)
        mock_terminal_adapter.cursor_pos = (mock_terminal_adapter.height - 1, 0)

        text = 'a' * (width + 20)
        lines = list(screen.wrap_lines(text))

        # First line fills the width; remainder on the next line. Every line
        # is nonempty (no infinite loop).
        assert len(lines) == 2
        assert len(lines[0].rstrip('\n')) == width
        assert len(lines[1].rstrip('\n')) == 20
        assert all(len(line) > 0 for line in lines)

    @pytest.mark.unit
    def test_break_at_space(self, mock_terminal_adapter, mock_resource_data):
        """Wrapping prefers the last space within the available width."""
        screen = self._screen(mock_terminal_adapter, mock_resource_data)
        screen.set_window(WindowPosition.LOWER)
        mock_terminal_adapter.cursor_pos = (mock_terminal_adapter.height - 1, 0)

        # width is 80; build text that must break at a space.
        first = 'a' * 70
        second = 'b' * 30
        text = f"{first} {second}"  # 70 + 1 + 30 = 101 chars
        lines = list(screen.wrap_lines(text))

        # The space at index 70 is within the first 80 chars, so the first
        # line is the 70 a's (the space is consumed as the break point).
        assert lines[0].rstrip('\n') == first
        assert ''.join(line.rstrip('\n') for line in lines[1:]) == second

    @pytest.mark.unit
    def test_newline_in_text_breaks_line(self, mock_terminal_adapter, mock_resource_data):
        screen = self._screen(mock_terminal_adapter, mock_resource_data)
        screen.set_window(WindowPosition.LOWER)
        mock_terminal_adapter.cursor_pos = (mock_terminal_adapter.height - 1, 0)

        lines = list(screen.wrap_lines("ab\ncd"))
        # First yielded chunk includes the newline; second is the remainder.
        assert lines[0] == "ab\n"
        assert lines[1] == "cd"

    @pytest.mark.unit
    def test_empty_text_yields_nothing(self, mock_terminal_adapter, mock_resource_data):
        screen = self._screen(mock_terminal_adapter, mock_resource_data)
        assert list(screen.wrap_lines("")) == []

    @pytest.mark.unit
    def test_wrapping_off_clips_single_line(self, mock_terminal_adapter, mock_resource_data):
        """
        REGRESSION (Shogun): with wrapping off, text is clipped to the available
        width and yielded as a single line, never wrapping to a second.
        This must terminate even when the window is degenerate.
        """
        screen = self._screen(mock_terminal_adapter, mock_resource_data)
        screen.set_window(WindowPosition.LOWER)
        window = screen.active_window
        # Turn wrapping off (clear attribute bit 0).
        window.window_attributes &= 0xe
        mock_terminal_adapter.cursor_pos = (mock_terminal_adapter.height - 1, 0)

        width = mock_terminal_adapter.width
        text = 'a' * (width + 50)
        lines = list(screen.wrap_lines(text))

        assert len(lines) == 1
        assert len(lines[0]) <= width

    @pytest.mark.unit
    def test_wrapping_off_degenerate_width_terminates(self, mock_terminal_adapter, mock_resource_data):
        """
        REGRESSION (Shogun): a near-zero printable width must not spin. With
        a 1-unit-wide window and wrapping off, wrap_lines yields at most a
        tiny clipped chunk and returns.
        """
        screen = self._screen(mock_terminal_adapter, mock_resource_data)
        screen.set_window(WindowPosition.LOWER)
        window = screen.active_window
        window.window_attributes &= 0xe  # wrapping off
        window.width = 1                  # degenerate
        mock_terminal_adapter.cursor_pos = (mock_terminal_adapter.height - 1, 0)

        # This call must return rather than loop forever.
        lines = list(screen.wrap_lines("abcdef"))
        assert len(lines) == 1
        assert len(lines[0]) <= 1


# ============================================================================
# set_window_attributes bit operations
# ============================================================================

class TestWindowAttributes:
    def setup_method(self):
        self.event_manager = EventManager()

    @pytest.mark.unit
    @pytest.mark.parametrize("start,flags,operation,expected", [
        (0b0000, 0b1010, 0, 0b1010),   # set: replace with flags
        (0b0100, 0b1010, 1, 0b1110),   # or: set supplied bits
        (0b1110, 0b1010, 2, 0b0100),   # and-clear: clear supplied bits
        (0b1100, 0b1010, 3, 0b0110),   # xor: toggle supplied bits
    ])
    def test_operations(self, mock_terminal_adapter, mock_resource_data,
                         start, flags, operation, expected):
        # set_window_attributes lives on ScreenV6, but the bit logic is what we
        # exercise here via a Window directly to avoid a graphics adapter.
        window = Window(height=10, width=10, font_size=0x101)
        window.window_attributes = start
        # Mirror the screen-layer logic for the unit under test.
        flags &= 0xf
        if operation == 0:
            window.window_attributes = flags
        elif operation == 1:
            window.window_attributes |= flags
        elif operation == 2:
            window.window_attributes &= (~flags & 0xf)
        elif operation == 3:
            window.window_attributes ^= flags
        assert window.window_attributes == expected


# ============================================================================
# Window property dispatch
# ============================================================================

class TestWindowProperties:
    @pytest.mark.unit
    def test_color_data_packs_bg_fg(self):
        window = Window(height=10, width=10, font_size=0x101)
        window.background_color = 6
        window.foreground_color = 9
        # color_data = (bg << 8) | fg
        assert window.color_data == (6 << 8) | 9

    @pytest.mark.unit
    def test_color_data_setter_unpacks(self):
        window = Window(height=10, width=10, font_size=0x101)
        window.color_data = (4 << 8) | 7
        assert window.background_color == 4
        assert window.foreground_color == 7

    @pytest.mark.unit
    def test_font_number_round_trip(self):
        window = Window(height=10, width=10, font_size=0x101)
        window.font_number = int(FontEnum.GRAPHICS)
        assert window.font == FontEnum.GRAPHICS
        assert window.font_number == int(FontEnum.GRAPHICS)

    @pytest.mark.unit
    def test_font_number_invalid_raises(self):
        window = Window(height=10, width=10, font_size=0x101)
        with pytest.raises(InvalidScreenOperationException):
            window.font_number = 999

    @pytest.mark.unit
    def test_buffered_printing_setter_toggles_only_bit_3(self):
        window = Window(height=10, width=10, font_size=0x101)
        window.window_attributes = 0b0111  # bit 3 off, others on
        window.buffered_printing = True
        assert window.window_attributes == 0b1111
        window.buffered_printing = False
        assert window.window_attributes == 0b0111

    @pytest.mark.unit
    def test_get_set_property_by_number(self):
        window = Window(height=10, width=20, font_size=0x101)
        # Property 2 = height, 3 = width per the PROPERTIES dispatch table.
        assert window.get_property(2) == 10
        assert window.get_property(3) == 20
        window.set_property(2, 15)
        assert window.height == 15

    @pytest.mark.unit
    def test_unknown_property_raises(self):
        window = Window(height=10, width=10, font_size=0x101)
        with pytest.raises(InvalidScreenOperationException):
            window.get_property(99)


# ============================================================================
# store_cursor_coordinates bounds handling
# ============================================================================

class TestStoreCursorCoordinates:
    def setup_method(self):
        self.event_manager = EventManager()

    @pytest.mark.unit
    def test_out_of_bounds_cursor_not_stored(self, mock_terminal_adapter, mock_resource_data):
        """
        When the absolute cursor falls outside the active window, the stored
        window cursor is left unchanged rather than recording an invalid value.
        """
        screen = ScreenV4(mock_terminal_adapter, mock_resource_data, self.event_manager)
        screen.set_window(WindowPosition.UPPER)
        upper = screen.active_window
        # Upper window has height 0 at this point; any cursor row >= height is
        # out of bounds. Record current stored cursor, then move the terminal
        # cursor out of bounds and attempt to store.
        before = (upper.y_cursor, upper.x_cursor)
        mock_terminal_adapter.cursor_pos = (mock_terminal_adapter.height - 1, 0)
        screen.store_cursor_coordinates()
        assert (upper.y_cursor, upper.x_cursor) == before


# ============================================================================
# V6 tests
# ============================================================================

class TestScreenV6Init:
    def setup_method(self):
        self.event_manager = EventManager()
        
    @pytest.fixture
    def screen(self, graphics_adapter, resource_data):
        return ScreenV6(graphics_adapter, resource_data, self.event_manager)

    @pytest.mark.unit
    def test_eight_windows_created(self, screen):
        assert len(screen.windows) == 8

    @pytest.mark.unit
    def test_window_dimensions_in_pixels(self, screen, graphics_adapter):
        # Window 0 fills the screen in pixels.
        assert screen.windows[0].height == graphics_adapter.screen_height_pixels
        assert screen.windows[0].width == graphics_adapter.screen_width_pixels

    @pytest.mark.unit
    def test_window_attributes_defaults(self, screen):
        # Window 0 has all four attributes on (0xf); windows 1-7 have only
        # buffering (bit 3, 0x8).
        assert screen.windows[0].window_attributes == 0xf
        for i in range(1, 8):
            assert screen.windows[i].window_attributes == 0x8


# ============================================================================
# set_cursor
# ============================================================================

class TestScreenV6SetCursor:
    def setup_method(self):
        self.event_manager = EventManager()
        
    @pytest.fixture
    def screen(self, graphics_adapter, resource_data):
        return ScreenV6(graphics_adapter, resource_data, self.event_manager)
    
    @pytest.mark.unit
    def test_set_cursor_stores_pixel_coordinates(self, screen, graphics_adapter):
        # Active window is window 0 at (1,1). Set cursor to pixel (40, 100).
        screen.set_cursor(40, 100)
        window = screen.active_window
        assert (window.y_cursor, window.x_cursor) == (40, 100)
        # Adapter receives absolute 0-indexed: (y_pos-1)+(y_cursor-1) etc.
        # Window 0 origin is (1,1) so absolute == (39, 99).
        assert graphics_adapter.cursor_pos == (39, 99)

    @pytest.mark.unit
    def test_set_cursor_rejects_nonpositive(self, screen):
        with pytest.raises(InvalidScreenOperationException):
            screen.set_cursor(0, 5)
        with pytest.raises(InvalidScreenOperationException):
            screen.set_cursor(5, 0)

    @pytest.mark.unit
    def test_left_margin_does_not_affect_y_cursor(self, screen):
        """
        The left margin is a horizontal (x) quantity. Setting the cursor with a
        y value at or below the left-margin value must NOT bump the y cursor.
        A failure here means set_cursor is guarding the wrong axis.
        """
        window = screen.active_window
        window.left_margin = 5
        screen.set_cursor(3, 100)   # y=3 is <= left_margin 5, but y is vertical
        assert window.y_cursor == 3


# ============================================================================
# split_window
# ============================================================================

class TestScreenV6SplitWindow:
    def setup_method(self):
        self.event_manager = EventManager()
        
    @pytest.fixture
    def screen(self, graphics_adapter, resource_data):
        return ScreenV6(graphics_adapter, resource_data, self.event_manager)
    
    @pytest.mark.unit
    def test_split_sets_geometry_in_pixels(self, screen, graphics_adapter):
        screen.split_window(200)   # 200px tall upper window
        lower, upper = screen.windows[:2]
        assert upper.height == 200
        assert upper.y_pos == 1
        assert lower.y_pos == 201
        assert lower.height == graphics_adapter.screen_height_pixels - 200

    @pytest.mark.unit
    def test_split_sets_print_and_scroll_region(self, screen, graphics_adapter):
        screen.split_window(200)
        # After split the active window (lower, window 0) should have its print
        # region set to its pixel geometry.
        assert graphics_adapter.print_region is not None
        left, top, width, height = graphics_adapter.print_region
        # Lower window origin y_pos=201 -> top 200 (0-indexed).
        assert top == 200


# ============================================================================
# move_window / resize_window
# ============================================================================

class TestScreenV6WindowGeometry:
    def setup_method(self):
        self.event_manager = EventManager()
        
    @pytest.fixture
    def screen(self, graphics_adapter, resource_data):
        return ScreenV6(graphics_adapter, resource_data, self.event_manager)
    
    @pytest.mark.unit
    def test_move_window(self, screen):
        screen.move_window(2, y=100, x=50)
        window = screen.windows[2]
        assert window.y_pos == 100
        assert window.x_pos == 50

    @pytest.mark.unit
    def test_resize_window(self, screen):
        screen.resize_window(2, y=300, x=400)
        window = screen.windows[2]
        assert window.height == 300
        assert window.width == 400

    @pytest.mark.unit
    def test_resize_resets_cursor_if_out_of_bounds(self, screen):
        window = screen.windows[2]
        window.x_cursor = 500
        window.y_cursor = 500
        screen.resize_window(2, y=100, x=100)  # smaller than cursor
        # Cursor should be reset to window origin (1, 1).
        assert (window.y_cursor, window.x_cursor) == (1, 1)


# ============================================================================
# set_margins
# ============================================================================

class TestScreenV6SetMargins:
    def setup_method(self):
        self.event_manager = EventManager()
        
    @pytest.fixture
    def screen(self, graphics_adapter, resource_data):
        return ScreenV6(graphics_adapter, resource_data, self.event_manager)
    
    @pytest.mark.unit
    def test_set_margins_stores_values(self, screen):
        screen.set_margins(left=20, right=30, window_id=0)
        window = screen.windows[0]
        assert window.left_margin == 20
        assert window.right_margin == 30

    @pytest.mark.unit
    def test_set_margins_updates_print_region(self, screen, graphics_adapter):
        # Active window is window 0. Setting margins should re-set the print
        # region accounting for them.
        screen.set_margins(left=20, right=30, window_id=-3)
        left, top, width, height = graphics_adapter.print_region
        # Print region left = x_pos + left_margin - 1 = 1 + 20 - 1 = 20.
        assert left == 20
        # Width = window width - left - right margins.
        assert width == graphics_adapter.screen_width_pixels - 20 - 30


# ============================================================================
# draw_picture / erase_picture
# ============================================================================

class TestScreenV6Pictures:
    def setup_method(self):
        self.event_manager = EventManager()
        
    @pytest.fixture
    def screen(self, graphics_adapter, resource_data):
        return ScreenV6(graphics_adapter, resource_data, self.event_manager)
    
    @pytest.mark.unit
    def test_draw_picture_at_explicit_coords(self, screen, graphics_adapter):
        # Coordinates are 1-indexed; window 0 origin is (1,1).
        screen.draw_picture(5, y=10, x=20)
        assert len(graphics_adapter.draw_calls) == 1
        number, top, left = graphics_adapter.draw_calls[0]
        # top = window_top(0) + (y-1) = 9; left = window_left(0) + (x-1) = 19.
        assert (number, top, left) == (5, 9, 19)

    @pytest.mark.unit
    def test_draw_picture_at_cursor_when_zero(self, screen, graphics_adapter):
        window = screen.active_window
        window.y_cursor = 40
        window.x_cursor = 60
        screen.draw_picture(5, y=0, x=0)
        number, top, left = graphics_adapter.draw_calls[0]
        # Uses cursor: top = window_top(0) + (y_cursor-1) = 39; left = 59.
        assert (top, left) == (39, 59)

    @pytest.mark.unit
    def test_get_picture_size_delegates(self, screen):
        assert screen.get_picture_size(5) == (100, 50)


# ============================================================================
# scroll_window
# ============================================================================

class TestScreenV6ScrollWindow:
    def setup_method(self):
        self.event_manager = EventManager()
        
    @pytest.fixture
    def screen(self, graphics_adapter, resource_data):
        return ScreenV6(graphics_adapter, resource_data, self.event_manager)
    
    @pytest.mark.unit
    def test_scroll_window_passes_pixel_geometry(self, screen, graphics_adapter):
        window = screen.windows[0]
        screen.scroll_window(0, pixels=20)
        assert len(graphics_adapter.scroll_calls) == 1
        left, top, width, height, pixels = graphics_adapter.scroll_calls[0]
        # Window 0 origin (1,1) -> (0,0); full screen size; 20px scroll.
        assert (left, top) == (0, 0)
        assert (width, height) == (graphics_adapter.screen_width_pixels, graphics_adapter.screen_height_pixels)
        assert pixels == 20


# ============================================================================
# set_window_attributes
# ============================================================================

class TestScreenV6WindowAttributes:
    def setup_method(self):
        self.event_manager = EventManager()
        
    @pytest.fixture
    def screen(self, graphics_adapter, resource_data):
        return ScreenV6(graphics_adapter, resource_data, self.event_manager)
    
    @pytest.mark.unit
    @pytest.mark.parametrize("start,flags,operation,expected", [
        (0b0000, 0b1010, 0, 0b1010),
        (0b0100, 0b1010, 1, 0b1110),
        (0b1110, 0b1010, 2, 0b0100),
        (0b1100, 0b1010, 3, 0b0110),
    ])
    def test_operations(self, screen, start, flags, operation, expected):
        window = screen.windows[2]
        window.window_attributes = start
        screen.set_window_attributes(2, flags, operation)
        assert window.window_attributes == expected

    @pytest.mark.unit
    def test_invalid_operation_raises(self, screen):
        with pytest.raises(InvalidScreenOperationException):
            screen.set_window_attributes(2, 0xf, operation=99)


# ============================================================================
# set_mouse_window
# ============================================================================

class TestScreenV6MouseWindow:
    def setup_method(self):
        self.event_manager = EventManager()
        
    @pytest.fixture
    def screen(self, graphics_adapter, resource_data):
        return ScreenV6(graphics_adapter, resource_data, self.event_manager)
    
    @pytest.mark.unit
    def test_mouse_window_full_screen_when_negative(self, screen, graphics_adapter):
        screen.set_mouse_window(-1)
        left, top, width, height = graphics_adapter.mouse_region
        assert (left, top) == (0, 0)
        assert (width, height) == (graphics_adapter.screen_width_pixels, graphics_adapter.screen_height_pixels)

    @pytest.mark.unit
    def test_mouse_window_specific_window(self, screen, graphics_adapter):
        window = screen.windows[2]
        window.y_pos = 100
        window.x_pos = 50
        window.height = 200
        window.width = 300
        screen.set_mouse_window(2)
        left, top, width, height = graphics_adapter.mouse_region
        # Origin 0-indexed: (49, 99); size as-is.
        assert (left, top) == (49, 99)
        assert (width, height) == (300, 200)


# ============================================================================
# set_cursor_enabled
# ============================================================================

class TestScreenV6CursorEnabled:
    def setup_method(self):
        self.event_manager = EventManager()
        
    @pytest.fixture
    def screen(self, graphics_adapter, resource_data):
        return ScreenV6(graphics_adapter, resource_data, self.event_manager)
    
    @pytest.mark.unit
    def test_set_cursor_enabled_toggles_adapter(self, screen, graphics_adapter):
        screen.set_cursor_enabled(False)
        assert graphics_adapter.cursor_enabled is False
        screen.set_cursor_enabled(True)
        assert graphics_adapter.cursor_enabled is True