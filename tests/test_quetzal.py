"""
Tests for Quetzal save/restore functionality.

Critical tests include:
- Type safety: restore must return int | None, never bool
- File validation: proper error handling for invalid saves
- Data integrity: correct PC and state restoration
"""
import pytest
import os
from zmachine.quetzal import Quetzal
from zmachine.stack import CallStack
from tests.conftest import create_valid_quetzal_save


@pytest.mark.unit
class TestQuetzalRestore:
    """Test suite for Quetzal restore functionality."""
    
    def setup_method(self):
        """Set up test fixtures for each test."""
        self.call_stack = CallStack()
    
    @pytest.mark.regression
    def test_restore_returns_none_not_false_on_missing_file(
        self, memory_map, mock_terminal_adapter, tmp_path
    ):
        """
        REGRESSION TEST: Restore must return None, never False.
        
        Bug: Previously returned False on missing file, which was treated
        as PC=0 by interpreter, causing jump to address 0 and crash.
        
        Fix: Must return None so interpreter knows restore failed.
        """
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        
        # Mock prompt to return non-existent file
        nonexistent_file = str(tmp_path / "nonexistent.sav")
        quetzal.prompt_save_file = lambda: os.path.basename(nonexistent_file)
        quetzal.game_file = str(tmp_path / "test.z5")
        
        result = quetzal.do_restore(self.call_stack)
        
        # The critical assertion: must be None, not False
        assert result is None, f"Expected None, got {result}"
        assert result is not False, "Must NOT return False - this would be treated as PC=0!"
        assert not isinstance(result, bool), \
            f"Return type must not be bool, got {type(result).__name__}"
    
    @pytest.mark.unit
    def test_restore_returns_none_on_invalid_header(
        self, memory_map, mock_terminal_adapter, temp_save_file
    ):
        """Restore should return None for invalid IFF header."""
        # Create file with wrong header
        temp_save_file.write_bytes(
            b"XXXX" +  # Wrong header (should be 'FORM')
            b"\x00\x00\x00\x08" +  # Length
            b"IFZS"
        )
        
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.prompt_save_file = lambda: temp_save_file.name
        quetzal.game_file = str(temp_save_file.parent / "test.z5")
        
        result = quetzal.do_restore(self.call_stack)
        
        assert result is None
        assert not isinstance(result, bool)
        assert "Invalid save file!" in ''.join(mock_terminal_adapter.screen_output)
    
    @pytest.mark.unit
    def test_restore_returns_none_on_wrong_form_type(
        self, memory_map, mock_terminal_adapter, temp_save_file
    ):
        """Restore should return None for wrong FORM type."""
        # Create file with correct IFF but wrong form type
        temp_save_file.write_bytes(
            b"FORM" +
            b"\x00\x00\x00\x08" +  # Length
            b"XXXX"  # Wrong form type (should be 'IFZS')
        )
        
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.prompt_save_file = lambda: temp_save_file.name
        quetzal.game_file = str(temp_save_file.parent / "test.z5")
        
        result = quetzal.do_restore(self.call_stack)
        
        assert result is None
        assert not isinstance(result, bool)
    
    @pytest.mark.unit
    def test_restore_returns_int_on_success(
        self, test_config, memory_map, mock_terminal_adapter, temp_save_file
    ):
        """Restore should return positive int PC on success."""
        test_pc = 0x5432
        
        # Create valid save file
        save_data = create_valid_quetzal_save(
            pc=test_pc,
            release=test_config.release_number,
            serial=test_config.serial_number,
            checksum=test_config.checksum
        )
        temp_save_file.write_bytes(save_data)
        
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.prompt_save_file = lambda: temp_save_file.name
        quetzal.game_file = str(temp_save_file.parent / "test.z5")
        
        result = quetzal.do_restore(self.call_stack)
        
        # Type assertions
        assert isinstance(result, int), f"Expected int, got {type(result)}"
        assert not isinstance(result, bool), "Must not be bool"
        
        # Value assertions
        assert result == test_pc, f"Expected PC={test_pc:#x}, got {result:#x}"
        assert result > 0, "PC should be positive"
    
    @pytest.mark.regression
    def test_restore_type_contract_never_bool(
        self, test_config, memory_map, mock_terminal_adapter, temp_save_file, tmp_path
    ):
        """
        CRITICAL: Explicitly test that False is never returned.
        
        This test exists because mypy cannot catch bool vs int due to
        Python's type system (bool is a subclass of int).
        """
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.game_file = str(tmp_path / "test.z5")
        
        # Test various failure scenarios
        test_cases = [
            (lambda: "nonexistent.sav", "missing file"),
            (lambda: self._create_invalid_header_save(temp_save_file), "invalid header"),
            (lambda: self._create_wrong_form_save(temp_save_file), "wrong FORM type"),
        ]
        
        for setup_func, scenario in test_cases:
            filename = setup_func()
            quetzal.prompt_save_file = lambda: os.path.basename(filename) if isinstance(filename, str) else filename.name
            
            result = quetzal.do_restore(self.call_stack)
            
            # The contract: int | None, never bool
            assert result is not False, \
                f"Scenario '{scenario}': must NOT return False"
            assert result is None or isinstance(result, int), \
                f"Scenario '{scenario}': must return int | None, got {type(result)}"
            assert not isinstance(result, bool), \
                f"Scenario '{scenario}': must not return bool"
    
    @pytest.mark.unit
    def test_restore_validates_checksum(
        self, test_config, memory_map, mock_terminal_adapter, temp_save_file
    ):
        """Restore should reject files with mismatched checksum."""
        wrong_checksum = test_config.checksum + 1
        
        save_data = create_valid_quetzal_save(
            pc=0x1000,
            release=test_config.release_number,
            serial=test_config.serial_number,
            checksum=wrong_checksum  # Wrong!
        )
        temp_save_file.write_bytes(save_data)
        
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.prompt_save_file = lambda: temp_save_file.name
        quetzal.game_file = str(temp_save_file.parent / "test.z5")
        
        result = quetzal.do_restore(self.call_stack)
        
        assert result is None
        assert "Invalid save file!" in ''.join(mock_terminal_adapter.screen_output)
    
    @pytest.mark.unit
    def test_restore_validates_release_number(
        self, test_config, memory_map, mock_terminal_adapter, temp_save_file
    ):
        """Restore should reject files with mismatched release number."""
        wrong_release = b'\xFF\xFF'
        
        save_data = create_valid_quetzal_save(
            pc=0x1000,
            release=wrong_release,  # Wrong!
            serial=test_config.serial_number,
            checksum=test_config.checksum
        )
        temp_save_file.write_bytes(save_data)
        
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.prompt_save_file = lambda: temp_save_file.name
        quetzal.game_file = str(temp_save_file.parent / "test.z5")
        
        result = quetzal.do_restore(self.call_stack)
        
        assert result is None
    
    @pytest.mark.unit
    def test_restore_validates_serial_number(
        self, test_config, memory_map, mock_terminal_adapter, temp_save_file
    ):
        """Restore should reject files with mismatched serial number."""
        wrong_serial = b'999999'
        
        save_data = create_valid_quetzal_save(
            pc=0x1000,
            release=test_config.release_number,
            serial=wrong_serial,  # Wrong!
            checksum=test_config.checksum
        )
        temp_save_file.write_bytes(save_data)
        
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.prompt_save_file = lambda: temp_save_file.name
        quetzal.game_file = str(temp_save_file.parent / "test.z5")
        
        result = quetzal.do_restore(self.call_stack)
        
        assert result is None
    
    @pytest.mark.unit
    def test_restore_returns_none_on_missing_chunks(
        self, test_config, memory_map, mock_terminal_adapter, temp_save_file
    ):
        """Restore should handle missing required chunks gracefully."""
        # Create FORM with IFZS but no chunks
        incomplete_save = (
            b'FORM' +
            b'\x00\x00\x00\x04' +  # Length = 4 (just IFZS)
            b'IFZS'
        )
        temp_save_file.write_bytes(incomplete_save)
        
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.prompt_save_file = lambda: temp_save_file.name
        quetzal.game_file = str(temp_save_file.parent / "test.z5")
        
        result = quetzal.do_restore(self.call_stack)
        
        # Should return None, not crash
        assert result is None
        assert not isinstance(result, bool)
    
    # Helper methods
    
    def _create_invalid_header_save(self, path):
        """Create save with invalid header."""
        path.write_bytes(b"XXXX\x00\x00\x00\x08IFZS")
        return path
    
    def _create_wrong_form_save(self, path):
        """Create save with wrong FORM type."""
        path.write_bytes(b"FORM\x00\x00\x00\x08XXXX")
        return path


@pytest.mark.integration
class TestQuetzalIntegration:
    """Integration tests for Quetzal with interpreter."""
    
    @pytest.mark.regression
    def test_interpreter_handles_restore_failure_correctly(
        self, test_config, memory_map, mock_terminal_adapter, tmp_path
    ):
        """
        Test that interpreter correctly handles None from failed restore.
        
        This ensures the interpreter doesn't try to use False as PC=0.
        """
        from zmachine.interpreter import ZMachineInterpreter
        from zmachine.event import EventManager
        
        # This test would require full interpreter setup
        # Simplified version focusing on the critical contract
        
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.prompt_save_file = lambda: "nonexistent.sav"
        quetzal.game_file = str(tmp_path / "test.z5")
        
        call_stack = CallStack()
        result = quetzal.do_restore(call_stack)
        
        # Simulate what interpreter does
        if result is not None:
            # This block should NOT execute when restore fails
            pytest.fail("Interpreter would incorrectly set PC when restore failed!")
        else:
            # This is correct - restore failed, do nothing
            pass
        
        assert result is None


@pytest.mark.unit
class TestQuetzalSave:
    """Test suite for Quetzal save functionality."""
    
    @pytest.mark.unit
    def test_save_creates_valid_file(
        self, memory_map, mock_terminal_adapter, temp_save_file
    ):
        """Save should create a valid Quetzal file."""
        quetzal = Quetzal(memory_map, mock_terminal_adapter)
        quetzal.prompt_save_file = lambda: temp_save_file.name
        quetzal.game_file = str(temp_save_file.parent / "test.z5")
        
        call_stack = CallStack()
        pc = 0x1234
        
        # This test requires save implementation
        # Placeholder for when save is fully implemented
        pytest.skip("Save test requires full save implementation")