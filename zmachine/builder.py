from .screen import *
from .enums import UIType
from .curses import CursesAdapter
from .graphics import GraphicsAdapter
from .memory import MemoryMap
from .event import EventManager
from .input import InputStreamManager
from .output import OutputStreamManager
from .hotkey import HotkeyHandler
from .protocol import ITerminalAdapter, IScreen
from .quetzal import Quetzal
from .interpreter import ZMachineInterpreter
from .config import ZMachineConfig
from .settings import RuntimeSettings
from .error import ZMachineException
from .constants import INTERPRETER_NUMBER, INTERPRETER_REVISION


class ZMachineBuilder:
    def __init__(self, game_file: str, ui_type: UIType = UIType.TEXT):
        config = ZMachineConfig.from_game_file(game_file)
        event_manager = EventManager()
        memory_map = MemoryMap(config)
        runtime_settings = RuntimeSettings(memory_map)
        terminal_adapter = self._initialize_terminal(ui_type)
        screen = self._initialize_screen(config.version, terminal_adapter, event_manager)
        quetzal = Quetzal(memory_map, terminal_adapter)
        self._initialize_header(memory_map, terminal_adapter, config.version)
        output_stream_manager = OutputStreamManager(screen, memory_map, terminal_adapter, config, runtime_settings, event_manager)
        hotkey_handler = HotkeyHandler(config, runtime_settings, terminal_adapter, output_stream_manager)
        input_stream_manager = InputStreamManager(screen, terminal_adapter, hotkey_handler, event_manager, config)
        self.interpreter = ZMachineInterpreter(
            memory_map, 
            config, 
            runtime_settings, 
            screen, 
            input_stream_manager, 
            output_stream_manager,
            quetzal, 
            event_manager
            )
        
    @staticmethod
    def _initialize_terminal(ui_type: UIType) -> ITerminalAdapter:
        if ui_type == UIType.TEXT:
            return CursesAdapter()
        if ui_type == UIType.GRAPHICS:
            return GraphicsAdapter()
        raise ZMachineException("Unrecognized UI type")

    @staticmethod
    def _initialize_screen(version: int, terminal_adapter: ITerminalAdapter, event_manager: EventManager) -> IScreen:
        if version == 3:
            return ScreenV3(terminal_adapter, event_manager)
        if version == 4:
            return ScreenV4(terminal_adapter, event_manager)
        if version == 5:
            return ScreenV5(terminal_adapter, event_manager)
        raise ZMachineException("Unrecognized configuration")
    
    def _initialize_header(self,
                           memory_map: MemoryMap,
                           terminal_adapter: ITerminalAdapter,
                           version: int) -> None:
        """Write runtime configuration to game memory header.
        
        This must happen after screen initialization but before
        interpreter execution begins. V4+ games need screen dimensions
        and interpreter identification in the header.
        """
        memory_map.write_word(0x1e, INTERPRETER_NUMBER)
        memory_map.write_word(0x32, INTERPRETER_REVISION)
        memory_map.write_byte(0x20, terminal_adapter.height)
        memory_map.write_byte(0x21, terminal_adapter.width)
        if version == 5:
            memory_map.write_word(0x22, terminal_adapter.width)
            memory_map.write_word(0x24, terminal_adapter.height)
            memory_map.write_byte(0x26, 1)
            memory_map.write_byte(0x27, 1)

    def start(self):
        self.interpreter.do_run()