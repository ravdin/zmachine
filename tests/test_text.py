"""
Text Utility Unit Tests

Tests for Z-character encoding/decoding (ZSCII) functionality.
These are foundational for read/tokenize operations.

Z-character encoding is used to compress text in Z-Machine games.
"""
import pytest


@pytest.mark.unit
class TestZCharDecoding:
    """
    Test Z-character to ZSCII decoding.
    
    Z-characters are 5-bit values (0-31) that encode text.
    They're packed 3 per 16-bit word.
    """
    
    @pytest.mark.unit
    def test_decode_simple_word(self, text_utils):
        """
        Test decoding a simple word: "look"
        
        From CZECH or Z-Machine spec examples.
        """
        # TODO: Get actual Z-character encoding for "look"
        # Example format (this is illustrative):
        # zchars = [17, 20, 20, 16, 5, 5]  # "look" encoded
    
        
        # Test basic decoding
        zchars = [20, 21, 10, 19, 5, 5] 
        result = text_utils.zscii_decode(zchars)
        assert result == "open"
    
    @pytest.mark.unit
    def test_decode_alphabet_shift(self, text_utils):
        """
        Test alphabet shifts (A0, A1, A2).
        
        Z-machine has 3 alphabets:
        A0: a-z (lowercase)
        A1: A-Z (uppercase)  
        A2: symbols and punctuation
        """
        
        # Shift to A1 for uppercase
        # zchars for "LOOK" would use alphabet shift
        zchars = [4, 17, 4, 20, 4, 20, 4, 16, 5, 5, 5, 5]
        result = text_utils.zscii_decode(zchars)
        assert result == "LOOK"
    
    @pytest.mark.unit
    def test_decode_with_abbreviations(self, text_utils):
        """
        Test decoding with abbreviations (Z-chars 1-3).
        
        Z-chars 1, 2, 3 are special - they reference abbreviation table.
        """
        # TODO: Test abbreviation expansion
        zchars = [2, 25]
        result = text_utils.zscii_decode(zchars)
        assert result == "doesn't "

        zchars[1] = 19
        result = text_utils.zscii_decode(zchars)
        assert result == "Frobozz "
    
    @pytest.mark.unit  
    def test_decode_special_characters(self, text_utils):
        """
        Test decoding special ZSCII characters.
        
        Characters like newline (13), quotes, etc.
        """
        
        # TODO: Test special characters
        # Newline, quotes, punctuation
        pass
    
    @pytest.mark.unit
    def test_decode_multibyte_zscii(self, text_utils):
        """
        Test decoding multi-byte ZSCII sequences.
        
        Z-char 6 in A2 followed by two Z-chars gives a 10-bit ZSCII code.
        """
        # TODO: Test multi-byte ZSCII
        pass

@pytest.mark.unit
class TestReadZChar:
    """
    Test reading Z-characters from memory.
    
    This involves reading packed 16-bit words and unpacking into Z-chars.
    """
    def setup_method(self, text_utils):
        # Setup a memory map with known Z-character data
        #memory_map = text_utils.memory_map
        pass
        
    
    @pytest.mark.unit
    def test_read_zchars(self, text_utils):
        """
        Test reading Z-chars from memory.
        
        Should read words until a word with high bit set is found.
        """
        pass


@pytest.mark.unit
class TestZCharEncoding:
    """
    Test ZSCII to Z-character encoding.
    
    Used by tokenize and other text processing operations.
    """
    
    @pytest.mark.unit
    def test_encode_simple_word(self, text_utils):
        """Test encoding a simple lowercase word."""
        
        result = text_utils.zscii_encode("look")
        # TODO: Verify correct Z-character sequence
        # Should produce specific 5-bit values
        assert len(result) > 0
        assert result == [0x46, 0x94, 0xC0, 0xA5]


# TODO: Add tests for:
# - Abbreviation table lookup
# - Unicode table (V5+)
# - Different alphabet tables (V1-V4 vs V5+)
# - Case-insensitive comparison
# - Terminating characters (V5+)
# - Maximum word lengths by version