from constants import *
from screen import Screen
from memory import MemoryMap
from event import EventManager
from stream import OutputStreamManager
from transcript import TranscriptUtils
from interpreter import ZMachineInterpreter


class ZMachineBuilder:
    def __init__(self, game_file: str):
        self.game_file = game_file
        with open(game_file, 'rb') as s:
            game_data = bytearray(s.read())
        self.version = game_data[0]
        if self.version not in SUPPORTED_VERSIONS:
            if 0 < self.version <= 6:
                print(f"Unsupported zmachine version: v{self.version}")
            else:
                print("Unrecognized zmachine file")
            exit(0)
        EventManager.initialize_events()
        memory_map = MemoryMap(game_data)
        transcript_utils = TranscriptUtils(game_file)
        self.output_stream_manager = OutputStreamManager(memory_map, transcript_utils)
        self.interpreter = ZMachineInterpreter(game_file, memory_map)
        self.screen = Screen(self.version, self.output_stream_manager.screen_stream)

    def start(self):
        self.interpreter.do_run()
