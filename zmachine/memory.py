from error import *
from event import EventManager, EventArgs


class MemoryMap:
    def __init__(self, data: bytes):
        self.memory_map = bytearray(data)
        self.event_manager = EventManager()
        self.version = self.read_byte(0)
        self.release_number = self.memory_map[0x2:0x4]
        self.high_mem_address = self.byte_addr(0x4)
        self.initial_pc = self.byte_addr(0x6)
        self.dictionary_header = self.byte_addr(0x8)
        self.object_header = self.byte_addr(0xa)
        self.global_vars = self.byte_addr(0xc)
        self.static_mem_ptr = self.byte_addr(0xe)
        self.serial_number = self.memory_map[0x12:0x18]
        self.abbreviation_table = self.byte_addr(0x18)
        self.file_len = self.read_word(0x1a) << (1 if self.version <= 3 else 2)
        self.checksum = self.read_word(0x1c)
        if self.version <= 3:
            # Split screen available.
            self.flags1_mask = 0x20
        else:
            # Bold, italic, and fixed width font available.
            self.flags1_mask = 0x1c
        self.flags1_mask = 0x20 if self.version <= 3 else 0x1c
        self.set_screen_flags()
        # Set the interpreter number to 1.1
        self.write_word(0x32, 0x101)
        self.set_event_handlers()

    def set_event_handlers(self):
        event_manager = EventManager()
        event_manager.set_screen_dimensions += self.set_screen_dimensions

    def __getitem__(self, item):
        if isinstance(item, slice):
            return self.memory_map[item.start:item.stop:item.step]
        elif isinstance(item, int):
            return self.memory_map[item]
        else:
            raise Exception('Invalid type for array index')

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            self.memory_map[key.start:key.stop:key.step] = value
        elif isinstance(key, int):
            self.memory_map[key] = value
        else:
            raise Exception('Invalid type for array index')

    def byte_addr(self, ptr):
        return self.read_word(ptr)

    def word_addr(self, ptr):
        return self.read_word(ptr) << 1

    def unpack_addr(self, packed_addr):
        shift = 1 if self.version <= 3 else 2
        return packed_addr << shift

    def read_byte(self, addr):
        return self[addr]

    def read_word(self, addr):
        return self[addr] << 8 | self[addr + 1]

    def read_dword(self, addr):
        result = 0
        for i in range(4):
            result <<= 8
            result |= self[addr + i]
        return result

    def write_byte(self, addr, val):
        if addr >= self.static_mem_ptr:
            raise IllegalWriteException(f"{addr:x}")
        self[addr] = val & 0xff

    def write_word(self, addr, val):
        if addr + 1 >= self.static_mem_ptr:
            raise IllegalWriteException(f"{addr:x}")
        self[addr] = val >> 8 & 0xff
        self[addr + 1] = val & 0xff

    def write_dword(self, addr, val):
        if addr + 3 >= self.static_mem_ptr:
            raise IllegalWriteException(f"{addr:x}")
        self[addr] = val >> 24 & 0xff
        self[addr + 1] = val >> 16 & 0xff
        self[addr + 2] = val >> 8 & 0xff
        self[addr + 3] = val & 0xff

    def reset_dynamic_memory(self, dynamic_mem):
        # To be called after restart or restore.
        flags2_mask = (self.read_word(0x10) | 0x3) & 0xfffc
        word_addresses = [0x32]
        if self.version == 4:
            word_addresses += [0x1e, 0x20]
        restore_values = {addr: self.read_word(addr) for addr in word_addresses}
        self.memory_map[:self.static_mem_ptr] = dynamic_mem
        self.set_screen_flags()
        flags2 = self.read_word(0x10)
        self.write_word(0x10, flags2 & flags2_mask)
        for addr, val in restore_values.items():
            self.write_word(addr, val)

    def set_screen_flags(self):
        flags1 = self.read_byte(0x1)
        self.write_byte(0x1, flags1 | self.flags1_mask)

    def set_screen_dimensions(self, sender, e: EventArgs):
        self.write_byte(0x20, e.height)
        self.write_byte(0x21, e.width)

    @property
    def transcript_active_flag(self) -> bool:
        return self.read_word(0x10) & 0x1 == 0x1

    @transcript_active_flag.setter
    def transcript_active_flag(self, value: bool):
        flags2 = self.read_word(0x10)
        if value:
            flags2 |= 0x1
        else:
            flags2 &= 0xfffe
        self.write_word(0x10, flags2)
