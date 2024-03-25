from screen import Screen
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
        self.output_stream_manager = OutputStreamManager(memory_map)
        self.interpreter = ZMachineInterpreter(memory_map)
        self.screen = Screen(self.version, self.output_stream_manager.screen_stream)
        event_manager.post_init.invoke(self, EventArgs())

    def start(self):
        self.interpreter.do_run()
