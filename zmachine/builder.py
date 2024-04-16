from screen import *
from __curses import CursesAdapter
from memory import MemoryMap
from event import EventManager, EventArgs
from stream import OutputStreamManager
from interpreter import ZMachineInterpreter
from config import *


class ZMachineBuilder:
    def __init__(self, game_file: str):
        with open(game_file, 'rb') as s:
            game_data = bytearray(s.read())
        self.version = game_data[0]
        if self.version not in SUPPORTED_VERSIONS:
            if 0 < self.version <= 6:
                print(f"Unsupported zmachine version: v{self.version}")
            else:
                print("Unrecognized zmachine file")
            exit(0)
        CONFIG[GAME_FILE_KEY] = game_file
        event_manager = EventManager.initialize_events()
        memory_map = MemoryMap(game_data)
        screen = self.initialize_screen(self.version)
        self.output_stream_manager = OutputStreamManager(screen, memory_map)
        self.interpreter = ZMachineInterpreter(memory_map)
        event_manager.post_init.invoke(self, EventArgs())

    @staticmethod
    def initialize_screen(version: int) -> BaseScreen:
        screen_adapter = CursesAdapter()
        if version == 3:
            return ScreenV3(screen_adapter)
        if version == 4:
            return ScreenV4(screen_adapter)
        if version == 5:
            return ScreenV5(screen_adapter)

    def start(self):
        self.interpreter.do_run()
