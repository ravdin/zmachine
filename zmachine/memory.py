from error import *
from config import *
from event import EventManager, EventArgs
from config import *


class MemoryMap:
    def __init__(self, data: bytes):
        self._memory_map = bytearray(data)
        self.event_manager = EventManager()
        self._version = self._memory_map[0]
        self.set_config()
        if self._version <= 3:
            # Split screen available.
            self.flags1_mask = 0x20
        if self._version >= 4:
            # Bold, italic, and fixed width font available.
            # Timed input available.
            self.flags1_mask = 0x9c
        if self._version == 5:
            # Colors available.
            self.flags1_mask |= 1
        self.register_delegates()

    def set_config(self):
        CONFIG[VERSION_NUMBER_KEY] = self._version
        CONFIG[RELEASE_NUMBER_KEY] = self._memory_map[0x2:0x4]
        CONFIG[HIGH_MEMORY_BASE_ADDR_KEY] = self.byte_addr(0x4)
        CONFIG[INITIAL_PC_KEY] = self.byte_addr(0x6)
        CONFIG[DICTIONARY_TABLE_KEY] = self.byte_addr(0x8)
        CONFIG[OBJECT_TABLE_KEY] = self.byte_addr(0xa)
        CONFIG[GLOBAL_VARS_TABLE_KEY] = self.byte_addr(0xc)
        CONFIG[STATIC_MEMORY_BASE_ADDR_KEY] = self.byte_addr(0xe)
        CONFIG[SERIAL_NUMBER_KEY] = self._memory_map[0x12:0x18]
        CONFIG[ABBREVIATION_TABLE_KEY] = self.byte_addr(0x18)
        CONFIG[FILE_LENGTH_KEY] = self.read_word(0x1a) << (1 if self._version <= 3 else 2)
        CONFIG[CHECKSUM_KEY] = self.read_word(0x1c)
        if self._version >= 5:
            self.get_interrupt_zchars(CONFIG[INTERRUPT_ZCHARS_KEY])

    def register_delegates(self):
        event_manager = EventManager()
        event_manager.post_init += self.post_init_handler

    def post_init_handler(self, sender, e: EventArgs):
        self.set_screen_flags()
        self.write_word(0x1e, INTERPRETER_NUMBER)
        self.write_word(0x32, INTERPRETER_REVISION)
        self.write_byte(0x20, CONFIG[SCREEN_HEIGHT_KEY])
        self.write_byte(0x21, CONFIG[SCREEN_WIDTH_KEY])
        if self._version == 5:
            self.write_word(0x22, CONFIG[SCREEN_WIDTH_KEY])
            self.write_word(0x24, CONFIG[SCREEN_HEIGHT_KEY])
            self.write_byte(0x26, 1)
            self.write_byte(0x27, 1)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return self._memory_map[item.start:item.stop:item.step]
        elif isinstance(item, int):
            return self._memory_map[item]
        raise Exception('Invalid type for array index')

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            self._memory_map[key.start:key.stop:key.step] = value
        elif isinstance(key, int):
            self._memory_map[key] = value
        raise Exception('Invalid type for array index')

    def byte_addr(self, ptr):
        return self.read_word(ptr)

    def word_addr(self, ptr):
        return self.read_word(ptr) << 1

    def unpack_addr(self, packed_addr):
        shift = 1 if self._version <= 3 else 2
        return packed_addr << shift

    def read_byte(self, addr):
        return self._memory_map[addr]

    def read_word(self, addr):
        return self._memory_map[addr] << 8 | self._memory_map[addr + 1]

    def write_byte(self, addr, val):
        if addr >= CONFIG[STATIC_MEMORY_BASE_ADDR_KEY]:
            raise IllegalWriteException(addr)
        self._memory_map[addr] = val & 0xff

    def write_word(self, addr, val):
        if addr + 1 >= CONFIG[STATIC_MEMORY_BASE_ADDR_KEY]:
            raise IllegalWriteException(addr)
        self._memory_map[addr] = val >> 8 & 0xff
        self._memory_map[addr + 1] = val & 0xff

    def reset_dynamic_memory(self, dynamic_mem: bytes):
        # To be called after restart or restore.
        # Preserve the height/width settings, which the game may or may not honor.
        flags2_mask = (self.read_word(0x10) | 0x3) & 0xfffc
        word_addresses = [0x1e, 0x32]
        if self._version >= 4:
            word_addresses += [0x1e, 0x20]
        if self._version >= 5:
            word_addresses += [0x22, 0x24, 0x26, 0x2c]
        restore_values = {addr: self.read_word(addr) for addr in word_addresses}
        self._memory_map[:CONFIG[STATIC_MEMORY_BASE_ADDR_KEY]] = dynamic_mem
        self.set_screen_flags()
        flags2 = self.read_word(0x10)
        self.write_word(0x10, flags2 & flags2_mask)
        for addr, val in restore_values.items():
            self.write_word(addr, val)

    def set_screen_flags(self):
        flags1 = self.read_byte(0x1)
        flags1 |= self.flags1_mask
        self.write_byte(0x1, flags1)
        if self._version == 5:
            flags2 = self.read_word(0x10)
            # Clear bits 3, 4, and 5.
            flags2 &= 0xc7
            self.write_word(0x10, flags2)
            self.write_byte(0x2c, DEFAULT_BACKGROUND_COLOR)
            self.write_byte(0x2d, DEFAULT_FOREGROUND_COLOR)

    def get_interrupt_zchars(self, buffer: list[int]):
        addr = self.read_word(0x2e)
        while True:
            zchar = self.read_byte(addr)
            if zchar == 0:
                break
            buffer += [zchar]
            addr += 1

    @property
    def transcript_active_flag(self) -> bool:
        # This flag is the single source of truth of whether the transcript stream is open or not.
        # It can be set with the output_stream opcode or directly by the game.
        # Because the game can set this flag directly, it must be checked every time there
        # is a write to the output streams.
        return self.read_word(0x10) & 0x1 == 0x1

    @transcript_active_flag.setter
    def transcript_active_flag(self, value: bool):
        flags2 = self.read_word(0x10)
        if value:
            flags2 |= 0x1
        else:
            flags2 &= 0xfffe
        self.write_word(0x10, flags2)
