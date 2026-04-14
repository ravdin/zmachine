"""
Real Interpreter Integration Tests

Tests the actual Interpreter class with mocked dependencies (screen, input, etc.).
These tests verify interpreter-level operations like read and tokenize.
"""
import pytest
from typing import List, Dict, Tuple
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from zmachine.settings import RuntimeSettings
from zmachine.text import TextUtils


# ============================================================================
# Test Data Classes
# ============================================================================

@dataclass
class ReadTestCase:
    """Test case data for read operation."""
    input_text: str
    expected_text: str
    expected_words: List[Tuple[str, int, int]]  # (word, length, position)
    description: str


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_screen():
    """Mock screen that implements IScreen protocol."""
    screen = Mock()
    screen.buffer_mode = True
    screen.pause_enabled = False
    screen.active_window_id = 0
    screen.print = Mock()
    screen.set_window = Mock()
    screen.split_window = Mock()
    screen.erase_window = Mock()
    screen.set_cursor = Mock()
    screen.set_text_style = Mock()
    screen.set_color = Mock()
    screen.print_table = Mock()
    screen.refresh_status_line = Mock()
    screen.reset_output_line_count = Mock()
    screen.sound_effect = Mock()
    return screen


@pytest.fixture
def mock_input_source():
    """Mock input source that provides canned input."""
    input_source = Mock()
    input_source.pending_input = []
    
    def read_input(timeout_ms, text_buffer, interrupt_routine_caller, 
                   interrupt_routine_addr, echo):
        """Simulate reading input and filling text buffer."""
        if input_source.pending_input:
            text = input_source.pending_input.pop(0)
            for i, char in enumerate(text):
                if i >= len(text_buffer):
                    return i
                text_buffer[i] = ord(char)
            text_buffer[len(text)] = 0
            return len(text)
        return 0
    
    input_source.read_input = read_input
    input_source.select_keyboard_stream = Mock()
    input_source.select_playback_stream = Mock()
    return input_source


@pytest.fixture
def mock_output_stream_manager():
    """Mock output stream manager."""
    manager = Mock()
    manager.write_to_streams = Mock()
    return manager


@pytest.fixture
def mock_text_utils(memory_map):
    """Mock text utilities with configurable dictionary."""
    result = Mock()
    result.memory_map = memory_map
    result.separator_chars = [' ', '.', ',']
    result.tokenize = TextUtils.tokenize  # Use real tokenize method
    
    # Dictionary: word -> offset from dictionary base
    # Entries are abritrary, copied from Zork II.
    result.dictionary_entries = {
        "look": 340,
        "go": 246,
        "north": 384,
        "south": 540,
        "east": 174,
        "west": 652,
        "take": 586,
        "drop": 170,
        "inventory": 302,
        "examine": 183,
    }
    
    def lookup_dictionary(text, dictionary_addr=0):
        """Look up word in mock dictionary (case-insensitive)."""
        text = text.lower()
        entry_offset = result.dictionary_entries.get(text, 0)
        if entry_offset == 0:
            return 0
        base_addr = memory_map.config.dictionary_table_addr
        return base_addr + entry_offset
    
    result.lookup_dictionary = lookup_dictionary
    return result

@pytest.fixture
def mock_event_manager():
    """Mock event manager."""
    manager = Mock()
    manager.pre_read_input = MagicMock()
    return manager


@pytest.fixture
def interpreter(test_config, memory_map, mock_screen, mock_input_source, 
                mock_output_stream_manager, mock_text_utils, mock_event_manager):
    """
    Create a real Interpreter instance with mocked dependencies.
    
    This gives us the actual interpreter logic but with controllable I/O.
    """
    from zmachine.interpreter import ZMachineInterpreter
    
    interp = ZMachineInterpreter(
        memory_map=memory_map,
        config=test_config,
        runtime_settings=RuntimeSettings(memory_map),
        screen=mock_screen,
        input_source=mock_input_source,
        output_manager=mock_output_stream_manager,
        quetzal=Mock(),
        event_manager=mock_event_manager
    )
    
    # Replace text utils with mock
    interp.text_utils = mock_text_utils
    interp.pc = 0x600
    
    return interp


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestReadOperation:
    """Integration tests for do_read operation."""
    
    # Test constants
    TEXT_BUFFER_ADDR = 0x0200
    PARSE_BUFFER_ADDR = 0x0300
    DEFAULT_MAX_LENGTH = 20
    DEFAULT_MAX_WORDS = 5
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def setup_buffers(self, interpreter, max_length=None, max_words=None):
        """
        Initialize text and parse buffers.
        
        Returns:
            Tuple of (text_buffer_addr, parse_buffer_addr)
        """
        max_length = max_length or self.DEFAULT_MAX_LENGTH
        max_words = max_words or self.DEFAULT_MAX_WORDS
        
        interpreter.write_byte(self.TEXT_BUFFER_ADDR, max_length)
        interpreter.write_byte(self.PARSE_BUFFER_ADDR, max_words)
        
        return self.TEXT_BUFFER_ADDR, self.PARSE_BUFFER_ADDR
    
    def get_text_from_buffer(self, interpreter, addr, version):
        """
        Extract text from text buffer (handles V4/V5 differences).
        
        Args:
            interpreter: Interpreter instance
            addr: Text buffer address
            version: Z-Machine version
            
        Returns:
            String extracted from buffer
        """
        chars = []
        offset = 1 if version <= 4 else 2
        i = 0
        while True:
            char = interpreter.read_byte(addr + offset + i)
            if char == 0:
                break
            chars.append(chr(char))
            i += 1
        return ''.join(chars)
    
    def get_parsed_words(self, interpreter, parse_addr):
        """
        Extract word entries from parse buffer.
        
        Args:
            interpreter: Interpreter instance
            parse_addr: Parse buffer address
            
        Returns:
            List of dicts with keys: dict_addr, length, position
        """
        num_words = interpreter.read_byte(parse_addr + 1)
        words = []
        
        for i in range(num_words):
            base = parse_addr + 2 + (i * 4)
            word_entry = {
                'dict_addr': interpreter.read_word(base),
                'length': interpreter.read_byte(base + 2),
                'position': interpreter.read_byte(base + 3)
            }
            words.append(word_entry)
        
        return words
    
    def verify_word_entry(self, word, expected_length, expected_position, 
                         word_name="word"):
        """
        Verify a word entry has expected values.
        
        Args:
            word: Word entry dict from get_parsed_words
            expected_length: Expected word length
            expected_position: Expected position in buffer
            word_name: Name for error messages
        """
        assert word['length'] == expected_length, \
            f"{word_name}: expected length {expected_length}, got {word['length']}"
        assert word['position'] == expected_position, \
            f"{word_name}: expected position {expected_position}, got {word['position']}"
        assert word['dict_addr'] >= 0, \
            f"{word_name}: invalid dictionary address {word['dict_addr']}"
    
    # ========================================================================
    # V4 Tests
    # ========================================================================
    
    class TestV4:
        """V4-specific read tests."""
        
        # Test data
        V4_TEST_CASES = [
            ReadTestCase(
                input_text="look\r",
                expected_text="look",
                expected_words=[("look", 4, 1)],
                description="single_word"
            ),
            ReadTestCase(
                input_text="go north\r",
                expected_text="go north",
                expected_words=[("go", 2, 1), ("north", 5, 4)],
                description="two_words"
            ),
            ReadTestCase(
                input_text="take red ball\r",
                expected_text="take red ball",
                expected_words=[("take", 4, 1), ("red", 3, 6), ("ball", 4, 10)],
                description="three_words"
            ),
        ]
        
        @pytest.mark.parametrize('sample_game_data', [4], indirect=True)
        @pytest.mark.parametrize('test_case', V4_TEST_CASES, 
                                ids=lambda tc: tc.description)
        def test_v4_read_cases(self, interpreter, mock_input_source, test_case):
            """
            Test V4 do_read with various inputs.
            
            V4 text buffer format:
            [0]: max length (includes terminator)
            [1+]: characters
            [...]: null terminator
            
            V4 parse buffer format:
            [0]: max words
            [1]: actual words parsed
            [2+]: word entries (4 bytes each)
            
            Word entry:
            [0-1]: dictionary address (big-endian)
            [2]: word length
            [3]: position (offset from byte 1)
            """
            parent = TestReadOperation()
            mock_input_source.pending_input = [test_case.input_text]
            
            # Setup buffers
            text_addr, parse_addr = parent.setup_buffers(interpreter)
            
            # Call real do_read
            interpreter.do_read(text_addr, parse_addr)
            
            # Verify text buffer
            text = parent.get_text_from_buffer(interpreter, text_addr, version=4)
            assert text == test_case.expected_text, \
                f"Expected '{test_case.expected_text}', got '{text}'"
            
            # Verify parse buffer
            words = parent.get_parsed_words(interpreter, parse_addr)
            assert len(words) == len(test_case.expected_words), \
                f"Expected {len(test_case.expected_words)} words, got {len(words)}"
            
            # Verify each word entry
            for i, (actual, (_, exp_length, exp_position)) in enumerate(
                zip(words, test_case.expected_words)
            ):
                parent.verify_word_entry(
                    actual, exp_length, exp_position,
                    word_name=f"word {i+1}"
                )
        
        @pytest.mark.parametrize('sample_game_data', [4], indirect=True)
        def test_v4_respects_max_length(self, interpreter, mock_input_source):
            """Test that V4 do_read truncates input to max buffer length."""
            parent = TestReadOperation()
            
            # Input longer than buffer
            mock_input_source.pending_input = ["verylongcommandthatexceedsbuffer\r"]
            
            # Small buffer: max 10 chars (includes terminator)
            text_addr, parse_addr = parent.setup_buffers(
                interpreter, max_length=10
            )
            
            interpreter.do_read(text_addr, parse_addr)
            
            # Count characters written
            char_count = 0
            for i in range(1, 11):
                char = interpreter.read_byte(text_addr + i)
                if char == 0:
                    break
                char_count += 1
            
            # Should be truncated
            assert char_count < 10, \
                f"Expected truncation, but got {char_count} chars"
            
            # Must have terminator
            found_terminator = False
            for i in range(1, 11):
                if interpreter.read_byte(text_addr + i) == 0:
                    found_terminator = True
                    break
            assert found_terminator, "Missing null terminator"

        @pytest.mark.parametrize('sample_game_data', [4], indirect=True)
        def test_v4_buffer_size_semantics(self, interpreter, mock_input_source):
            """
            Test V4 buffer size semantics.
            
            V4: text_buffer[0] = max chars INCLUDING terminator
            V5: text_buffer[0] = max chars EXCLUDING terminator
            """
            parent = TestReadOperation()
            mock_input_source.pending_input = ["12345\r"]  # 5 chars
            
            text_addr = 0x0200
            parse_addr = 0x0300
            
            # V4: Set buffer size to 6 (5 chars + terminator)
            interpreter.write_byte(text_addr, 6)
            interpreter.write_byte(parse_addr, 5)
            
            interpreter.do_read(text_addr, parse_addr)
            
            # Should fit exactly
            text = parent.get_text_from_buffer(interpreter, text_addr, version=4)
            assert text == "12345"
        
        @pytest.mark.parametrize('sample_game_data', [4], indirect=True)
        def test_v4_empty_input(self, interpreter, mock_input_source):
            """Test V4 do_read with empty input (just Enter)."""
            parent = TestReadOperation()
            mock_input_source.pending_input = ["\r"]
            
            text_addr, parse_addr = parent.setup_buffers(interpreter)
            
            interpreter.do_read(text_addr, parse_addr)
            
            # First character should be terminator
            assert interpreter.read_byte(text_addr + 1) == 0, \
                "Expected null terminator at byte 1"
            
            # No words parsed
            num_words = interpreter.read_byte(parse_addr + 1)
            assert num_words == 0, \
                f"Expected 0 words, got {num_words}"
        
        @pytest.mark.parametrize('sample_game_data', [4], indirect=True)
        def test_v4_punctuation_handling(self, interpreter, mock_input_source):
            """Test V4 do_read with punctuation."""
            parent = TestReadOperation()
            
            # Input with comma separator
            mock_input_source.pending_input = ["look, go\r"]
            
            text_addr, parse_addr = parent.setup_buffers(interpreter)
            
            interpreter.do_read(text_addr, parse_addr)
            
            # Verify text stored correctly
            text = parent.get_text_from_buffer(interpreter, text_addr, version=4)
            assert text == "look, go"
            
            # Verify words parsed (comma might be separate word or ignored)
            words = parent.get_parsed_words(interpreter, parse_addr)
            
            # At minimum, should have "look" and "go"
            # Comma handling depends on separator configuration
            assert len(words) >= 2, \
                f"Expected at least 2 words, got {len(words)}"
    
    # ========================================================================
    # V5 Tests
    # ========================================================================
    
    class TestV5:
        """V5-specific read tests."""
        
        @pytest.mark.parametrize('sample_game_data', [5], indirect=True)
        def test_v5_buffer_format(self, interpreter, mock_input_source):
            """
            Test V5 buffer format differences.
            
            V5 text buffer format:
            [0]: max length (excludes terminator)
            [1]: chars read (written by do_read)
            [2+]: characters
            [...]: null terminator
            """
            parent = TestReadOperation()
            mock_input_source.pending_input = ["look\r"]
            
            text_addr, parse_addr = parent.setup_buffers(interpreter)
            
            interpreter.do_read(text_addr, parse_addr)
            
            # V5: Byte 1 contains character count
            chars_read = interpreter.read_byte(text_addr + 1)
            assert chars_read == 4, \
                f"Expected 4 chars read, got {chars_read}"
            
            # V5: Characters start at byte 2
            assert interpreter.read_byte(text_addr + 2) == ord('l')
            assert interpreter.read_byte(text_addr + 3) == ord('o')
            assert interpreter.read_byte(text_addr + 4) == ord('o')
            assert interpreter.read_byte(text_addr + 5) == ord('k')
        
        @pytest.mark.parametrize('sample_game_data', [5], indirect=True)
        def test_v5_parse_buffer_positions(self, interpreter, mock_input_source):
            """
            Test V5 parse buffer position offsets.
            
            V5 positions are offset from byte 2 (not byte 1 like V4).
            """
            parent = TestReadOperation()
            mock_input_source.pending_input = ["go north\r"]
            
            text_addr, parse_addr = parent.setup_buffers(interpreter)
            
            interpreter.do_read(text_addr, parse_addr)
            
            words = parent.get_parsed_words(interpreter, parse_addr)
            assert len(words) == 2
            
            # V5: First word at position 2 (offset from start of buffer)
            assert words[0]['position'] == 2, \
                f"V5: Expected position 2 for first word, got {words[0]['position']}"
            
            # V5: Second word at position 5 (after "go ")
            assert words[1]['position'] == 5, \
                f"V5: Expected position 5 for second word, got {words[1]['position']}"
    
    # ========================================================================
    # Version-Agnostic Tests
    # ========================================================================
    
    class TestAllVersions:
        """Tests that work across all versions."""
        
        @pytest.mark.parametrize('sample_game_data', [3, 4, 5], indirect=True)
        def test_handles_empty_input(self, interpreter, mock_input_source):
            """Test all versions handle empty input correctly."""
            parent = TestReadOperation()
            mock_input_source.pending_input = ["\r"]
            
            text_addr, parse_addr = parent.setup_buffers(interpreter)
            
            interpreter.do_read(text_addr, parse_addr)
            
            # Should have no words
            num_words = interpreter.read_byte(parse_addr + 1)
            assert num_words == 0, \
                f"V{interpreter.version}: Expected 0 words, got {num_words}"
        
        @pytest.mark.parametrize('sample_game_data', [3, 4, 5], indirect=True)
        def test_handles_whitespace_only(self, interpreter, mock_input_source):
            """Test all versions handle whitespace-only input."""
            parent = TestReadOperation()
            mock_input_source.pending_input = ["   \r"]
            
            text_addr, parse_addr = parent.setup_buffers(interpreter)
            
            interpreter.do_read(text_addr, parse_addr)
            
            # Should have no words (just spaces)
            num_words = interpreter.read_byte(parse_addr + 1)
            assert num_words == 0, \
                f"V{interpreter.version}: Expected 0 words from whitespace, got {num_words}"
        
        @pytest.mark.parametrize('sample_game_data', [4, 5], indirect=True)
        def test_respects_max_words(self, interpreter, mock_input_source):
            """Test that parsing respects max words limit."""
            parent = TestReadOperation()
            
            # Input with many words
            mock_input_source.pending_input = ["take the red round ball now\r"]
            
            # Parse buffer allows max 3 words
            text_addr, parse_addr = parent.setup_buffers(
                interpreter, max_words=3, max_length=50
            )
            
            interpreter.do_read(text_addr, parse_addr)
            
            # Verify num_words is clamped to max
            num_words = interpreter.read_byte(parse_addr + 1)
            assert num_words == 3, f"Expected num_words=3, got {num_words}"

            # Verify exactly 3 word entries exist (not more)
            words = parent.get_parsed_words(interpreter, parse_addr)
            assert len(words) == 3, f"Expected 3 word entries, got {len(words)}"

            # Verify the 4th word slot is uninitialized (or zeros)
            # This ensures we didn't write beyond max_words
            fourth_word_addr = parse_addr + 2 + (3 * 4)
            assert interpreter.read_word(fourth_word_addr) == 0
            # Could check that this memory is still zeroed or uninitialized


# ============================================================================
# Future Test Classes
# ============================================================================

# TODO: Add these test classes as you expand coverage
#
# @pytest.mark.integration
# class TestTokenizeOperation:
#     """Tests for standalone do_tokenize operation."""
#     pass
#
# @pytest.mark.integration
# class TestReadThenTokenize:
#     """Tests for complete read → tokenize workflow."""
#     pass
#
# @pytest.mark.integration
# class TestTimedInput:
#     """Tests for timed input (V4+)."""
#     pass
#
# @pytest.mark.integration
# class TestInputInterrupts:
#     """Tests for input interrupts (V5+)."""
#     pass