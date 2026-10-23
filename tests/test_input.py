import itertools
import pytest
from unittest.mock import Mock

from zmachine.input import InputStreamManager
from zmachine.interpreter import ZMachineInterpreter
from zmachine.settings import RuntimeSettings
from zmachine.event import EventManager

def make_interpreter(test_config, memory_map, input_source):
    interp = ZMachineInterpreter(
        memory_map=memory_map,
        config=test_config,
        runtime_settings=RuntimeSettings(memory_map),
        screen=Mock(),
        input_source=input_source,
        output_manager=Mock(),
        quetzal=Mock(),
        event_manager=EventManager(),
    )
    interp.pc = 0x600
    # The interrupt routine "returns true", which aborts the read.
    interp.do_direct_call = lambda routine_addr: 1
    return interp

def make_input_manager(terminal_adapter, screen, event_manager=None):
    config = Mock()
    config.interrupt_zchars = []
    return InputStreamManager(
        screen=screen,
        terminal_adapter=terminal_adapter,
        hotkey_handler=Mock(),
        event_manager=event_manager or EventManager(),
        config=config,
    )

TIMEOUT = -1  # MockTerminalAdapter returns this from get_input_char on a timeout
 
@pytest.mark.regression
class TestInterruptedTimedRead:
    """User types 'ab', the read times out, and the interrupt routine returns true."""
 
    TEXT_ADDR = 0x200
    PARSE_ADDR = 0x300
 
    def test_input_manager_does_not_crash(self, mock_terminal_adapter, mock_screen):
        mock_terminal_adapter.input_chars = [ord('a'), ord('b'), TIMEOUT]
        manager = make_input_manager(mock_terminal_adapter, mock_screen)
        text_buffer = [0] * 240
 
        # Currently raises IndexError: text_buffer.index(0) == 0, so input_chars is empty.
        manager.read_input(
            timeout_ms=100,
            text_buffer=text_buffer,
            interrupt_routine_caller=lambda addr: 1,
            interrupt_routine_addr=0x1234,
            echo=True,
        )
 
    def test_input_manager_keeps_typed_text(self, mock_terminal_adapter, mock_screen):
        mock_terminal_adapter.input_chars = [ord('a'), ord('b'), TIMEOUT]
        manager = make_input_manager(mock_terminal_adapter, mock_screen)
        text_buffer = [0] * 240
 
        try:
            manager.read_input(
                timeout_ms=100,
                text_buffer=text_buffer,
                interrupt_routine_caller=lambda addr: 1,
                interrupt_routine_addr=0x1234,
                echo=True,
            )
        except IndexError:
            pass  # Covered by the test above; check the buffer contents here.
 
        # Currently [0, ord('b'), 0]: 'a' is overwritten and 'b' is left behind.
        # The typed text should stay in the buffer, followed by a 0 terminator.
        assert text_buffer[:3] == [ord('a'), ord('b'), 0]
 
    @pytest.mark.parametrize('sample_game_data', [5], indirect=True)
    def test_v5_do_read_writes_typed_length(self, test_config, memory_map, mock_terminal_adapter, mock_screen):
        mock_terminal_adapter.input_chars = [ord('a'), ord('b'), TIMEOUT]
        interp = make_interpreter(test_config, memory_map, make_input_manager(mock_terminal_adapter, mock_screen))
        interp.write_byte(self.TEXT_ADDR, 20)      # max chars
        interp.write_byte(self.TEXT_ADDR + 1, 0)   # no initial text
        interp.write_byte(self.PARSE_ADDR, 5)
 
        interp.do_read(self.TEXT_ADDR, self.PARSE_ADDR, time=1, routine=0x100)
 
        # Byte 1 holds the number of characters typed. With the input manager's crash
        # bypassed, do_read currently writes input_len - 1 = -1, stored as 255.
        assert interp.read_byte(self.TEXT_ADDR + 1) == 2
        assert interp.read_byte(self.TEXT_ADDR + 2) == ord('a')
        assert interp.read_byte(self.TEXT_ADDR + 3) == ord('b')
 
    @pytest.mark.parametrize('sample_game_data', [4], indirect=True)
    def test_v4_do_read_preserves_max_length(self, test_config, memory_map, mock_terminal_adapter, mock_screen):
        mock_terminal_adapter.input_chars = [ord('a'), ord('b'), TIMEOUT]
        interp = make_interpreter(test_config, memory_map, make_input_manager(mock_terminal_adapter, mock_screen))
        interp.write_byte(self.TEXT_ADDR, 20)
        interp.write_byte(self.PARSE_ADDR, 5)
 
        interp.do_read(self.TEXT_ADDR, self.PARSE_ADDR, time=1, routine=0x100)
 
        # Byte 0 is the game's max length. do_read currently writes the 0 terminator
        # at text_addr + input_len, which is byte 0 when input_len == 0.
        assert interp.read_byte(self.TEXT_ADDR) == 20
 