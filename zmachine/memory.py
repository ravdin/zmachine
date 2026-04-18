from .error import IllegalWriteException, InvalidMemoryException
from .config import ZMachineConfig
from .logging import LogLevel, memory_logger as logger
from .constants import DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR

class MemoryMap:
    def __init__(self, config: ZMachineConfig):
        self.config = config
        with open(config.game_file, 'rb') as f:
            data = f.read()
        self._memory_map = bytearray(data)
        self._version = self._memory_map[0]
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
        self.set_screen_flags()

    @property
    def static_memory_base_addr(self) -> int:
        return self.config.static_memory_base_addr

    def __getitem__(self, item: int | slice):
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

    def byte_addr(self, ptr: int) -> int:
        return self.read_word(ptr)

    def word_addr(self, ptr) -> int:
        return self.read_word(ptr) << 1

    def unpack_addr(self, packed_addr: int) -> int:
        shift = 1 if self._version <= 3 else 2
        return packed_addr << shift

    def read_byte(self, addr: int) -> int:
        if logger.isEnabledFor(LogLevel.DEBUG):
            logger.debug(f"READ 0x{addr:04X}")
        if addr >= len(self._memory_map):
            raise InvalidMemoryException(f"Address {addr:x} out of bounds")
        return self._memory_map[addr]

    def read_word(self, addr: int) -> int:
        if logger.isEnabledFor(LogLevel.DEBUG):
            logger.debug(f"READ 0x{addr:04X}:0x{addr + 1:04X}")
        if addr + 1 >= len(self._memory_map):
            raise InvalidMemoryException(f"Address {addr:x} out of bounds")
        return self._memory_map[addr] << 8 | self._memory_map[addr + 1]

    def write_byte(self, addr: int, val: int):
        if logger.isEnabledFor(LogLevel.DEBUG):
            logger.debug(f"WRITE 0x{addr:04X} = 0x{val:02X}")
        if addr >= self.config.static_memory_base_addr:
            raise IllegalWriteException(addr)
        self._memory_map[addr] = val & 0xff

    def write_word(self, addr: int, val: int):
        if logger.isEnabledFor(LogLevel.DEBUG):
            logger.debug(f"WRITE 0x{addr:04X}:0x{addr + 1:04X} = 0x{val:02X}")
        if addr + 1 >= self.config.static_memory_base_addr:
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
        self._memory_map[:self.config.static_memory_base_addr] = dynamic_mem
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
