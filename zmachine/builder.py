from screen import *
from __curses import CursesAdapter
from memory import MemoryMap
from event import EventManager
from stream import OutputStreamManager
from interpreter import ZMachineInterpreter
from config import ZMachineConfig
from constants import INTERPRETER_NUMBER, INTERPRETER_REVISION


class ZMachineBuilder:
    def __init__(self, game_file: str):
        config = ZMachineConfig.from_game_file(game_file)
        EventManager.initialize_events()
        memory_map = MemoryMap(config)
        screen = self._initialize_screen(config)
        self._initialize_header(memory_map, screen, config.version)
        self.output_stream_manager = OutputStreamManager(screen, memory_map)
        self.interpreter = ZMachineInterpreter(memory_map, config)

    @staticmethod
    def _initialize_screen(config: ZMachineConfig) -> BaseScreen:
        screen_adapter = CursesAdapter(config)
        version = config.version
        if version == 3:
            return ScreenV3(screen_adapter)
        if version == 4:
            return ScreenV4(screen_adapter)
        if version == 5:
            return ScreenV5(screen_adapter)
        raise Exception("Unrecognized configuration")
    
    def _initialize_header(self,
                           memory_map: MemoryMap,
                           screen: BaseScreen,
                           version: int) -> None:
        """Write runtime configuration to game memory header.
        
        This must happen after screen initialization but before
        interpreter execution begins. V4+ games need screen dimensions
        and interpreter identification in the header.
        """
        memory_map.write_word(0x1e, INTERPRETER_NUMBER)
        memory_map.write_word(0x32, INTERPRETER_REVISION)
        memory_map.write_byte(0x20, screen.height)
        memory_map.write_byte(0x21, screen.width)
        if version == 5:
            memory_map.write_word(0x22, screen.width)
            memory_map.write_word(0x24, screen.height)
            memory_map.write_byte(0x26, 1)
            memory_map.write_byte(0x27, 1)

    def start(self):
        self.interpreter.do_run()