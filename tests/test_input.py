import pytest
from unittest.mock import Mock

from zmachine.input import InputStreamManager
from zmachine.interpreter import ZMachineInterpreter
from zmachine.settings import RuntimeSettings
from zmachine.event import EventManager, PostReadInputEventArgs

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

@pytest.fixture(params=['mock', 'integrated'])
def input_source_factory(request, mock_terminal_adapter, mock_input_source):
    if request.param == 'mock':
        source = mock_input_source
        feed = lambda keys: setattr(source, 'input_chars', keys)
    else:
        source = make_input_manager(mock_terminal_adapter, screen=Mock())
        feed = lambda keys: setattr(mock_terminal_adapter, 'input_chars', keys)
    return source, feed

TIMEOUT = -1  # MockTerminalAdapter returns this from get_input_char on a timeout
 
@pytest.mark.regression
class TestInterruptedTimedRead:
    """User types 'ab', the read times out, and the interrupt routine returns true."""
 
    TEXT_ADDR = 0x200
    PARSE_ADDR = 0x300
 
    def test_input_manager_clears_text_buffer_on_timeout(self, mock_terminal_adapter):
        mock_terminal_adapter.input_chars = [ord('a'), ord('b'), TIMEOUT]
        manager = make_input_manager(mock_terminal_adapter, screen=Mock())
        text_buffer = [0] * 240
 
        manager.read_input(
            timeout_ms=100,
            text_buffer=text_buffer,
            interrupt_routine_caller=lambda addr: 1,
            interrupt_routine_addr=0x1234,
            echo=True,
        )
 
        # On timeout, the read process should terminate at once and clear the text buffer.
        assert text_buffer[:3] == [0, 0, 0]

    def test_input_manager_invokes_post_read_event(self, mock_terminal_adapter):
        mock_terminal_adapter.input_chars = [ord('l'), ord('o'), ord('o'), ord('k'), 13]
        text_buffer = [0] * 240
        def post_read_handler(*args):
            _, event_args = args
            assert event_args.command == 'look'
            assert event_args.terminating_char == 13
        mock_post_read_handler = Mock(side_effect=post_read_handler)
        event_manager = EventManager()
        event_manager.post_read_input += mock_post_read_handler
        input_manager = make_input_manager(mock_terminal_adapter, screen=Mock(), event_manager=event_manager)

        input_manager.read_input(
            timeout_ms=0,
            text_buffer=text_buffer,
            interrupt_routine_caller=lambda addr: 0,
            interrupt_routine_addr=0,
            echo=True
        )
        mock_post_read_handler.assert_called_once()
 
    @pytest.mark.parametrize('sample_game_data', [5], indirect=True)
    def test_v5_do_read_writes_typed_length(self, test_config, memory_map, input_source_factory):
        input_source, feed = input_source_factory
        feed([ord('a'), ord('b'), TIMEOUT])
        interp = make_interpreter(test_config, memory_map, input_source)
        interp.write_byte(self.TEXT_ADDR, 20)      # max chars
        interp.write_byte(self.TEXT_ADDR + 1, 0)   # no initial text
        interp.write_byte(self.PARSE_ADDR, 5)
 
        interp.do_read(self.TEXT_ADDR, self.PARSE_ADDR, time=1, routine=0x100)
 
        # Byte 1 holds the number of characters typed. Since the interrupt callback returns 1,
        # the text buffer in the mock input source is cleared, so do_read should store zero characters
        # typed.
        assert interp.read_byte(self.TEXT_ADDR + 1) == 0
 
    @pytest.mark.parametrize('sample_game_data', [4], indirect=True)
    def test_v4_do_read_preserves_max_length(self, test_config, memory_map, input_source_factory):
        input_source, feed = input_source_factory
        feed([ord('a'), ord('b'), TIMEOUT])
        interp = make_interpreter(test_config, memory_map, input_source)
        interp.write_byte(self.TEXT_ADDR, 20)
        interp.write_byte(self.PARSE_ADDR, 5)
 
        interp.do_read(self.TEXT_ADDR, self.PARSE_ADDR, time=1, routine=0x100)
 
        # Verify that when a timeout interrupts the read, the max length of the
        # text buffer is preserved.
        assert interp.read_byte(self.TEXT_ADDR) == 20
