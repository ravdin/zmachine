from .memory import MemoryMap

class RuntimeSettings:
    """Runtime settings that can be modified."""
    
    def __init__(self, memory_map: MemoryMap):
        self.memory_map = memory_map

    @property
    def transcript_active_flag(self) -> bool:
        # This flag is the single source of truth of whether the transcript stream is open or not.
        # It can be set with the output_stream opcode or directly by the game.
        # Because the game can set this flag directly, it must be checked every time there
        # is a write to the output streams.
        return self.memory_map.read_word(0x10) & 0x1 == 0x1

    @transcript_active_flag.setter
    def transcript_active_flag(self, value: bool):
        flags2 = self.memory_map.read_word(0x10)
        if value:
            flags2 |= 0x1
        else:
            flags2 &= 0xfffe
        self.memory_map.write_word(0x10, flags2)
        