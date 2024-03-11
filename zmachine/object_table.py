from memory import MemoryMap
from error import *
from config import *


class ObjectTable:
    def __init__(self, memory_map: MemoryMap):
        self.memory_map = memory_map
        self.version = CONFIG[VERSION_NUMBER_KEY]
        self.OBJECT_TABLE = CONFIG[OBJECT_TABLE_KEY]
        self.PROPERTY_DEFAULTS_LENGTH = 31 if self.version <= 3 else 63
        self.OBJECT_BYTES = 9 if self.version <= 3 else 14
        self.MAX_OBJECTS = 0xff if self.version <= 3 else 0xffff
        self.ATTRIBUTE_FLAGS = 32 if self.version <= 3 else 48
        self.PARENT_OFFSET = 4 if self.version <= 3 else 6
        self.SIBLING_OFFSET = 5 if self.version <= 3 else 8
        self.CHILD_OFFSET = 6 if self.version <= 3 else 10

    def read_byte(self, addr):
        return self.memory_map.read_byte(addr)

    def read_word(self, addr):
        return self.memory_map.read_word(addr)

    def byte_addr(self, addr):
        return self.memory_map.byte_addr(addr)

    def write_byte(self, addr, val):
        self.memory_map.write_byte(addr, val)

    def write_word(self, addr, val):
        self.memory_map.write_word(addr, val)

    def get_obj_addr(self, obj_id):
        if obj_id <= 0 or obj_id > self.MAX_OBJECTS:
            raise InvalidMemoryException(f"Object ID '{obj_id}' out of range")
        obj_addr = self.OBJECT_TABLE + \
            self.PROPERTY_DEFAULTS_LENGTH * 2 + \
            self.OBJECT_BYTES * (obj_id - 1)
        # HACK: Beyond Zork was shipped with a bug where the dictionary entry for an object
        # was encoded instead of the object ID. This would put the object address outside of the
        # bounds of the file. The official interpreter would return 0 in this case, which
        # accidentally works.
        if obj_addr > CONFIG[STATIC_MEMORY_BASE_ADDR_KEY]:
            obj_addr = 0
        return obj_addr

    def get_attribute_flag(self, obj_id, attr_num) -> bool:
        if attr_num < 0 or attr_num >= self.ATTRIBUTE_FLAGS:
            raise InvalidArgumentException(f'Invalid attribute: {attr_num}')
        byte_offset = attr_num >> 3
        bit_offset = attr_num & 0x7
        attr_flag = 0x80 >> bit_offset
        obj_addr = self.get_obj_addr(obj_id)
        return self.read_byte(obj_addr + byte_offset) & attr_flag == attr_flag

    def set_attribute_flag(self, obj_id, attr_num, value=bool):
        if attr_num >= self.ATTRIBUTE_FLAGS:
            raise InvalidArgumentException(f'Invalid attribute: {attr_num}')
        byte_offset = attr_num >> 3
        bit_offset = attr_num & 0x7
        attr_flag = 0x80 >> bit_offset
        obj_addr = self.get_obj_addr(obj_id)
        attribute_byte = self.read_byte(obj_addr + byte_offset)
        if value:
            attribute_byte |= attr_flag
        else:
            attribute_byte &= (~attr_flag & 0xff)
        self.write_byte(obj_addr + byte_offset, attribute_byte)

    def get_object_text_zchars(self, obj_id):
        obj_addr = self.get_obj_addr(obj_id)
        prop_header_addr = self.byte_addr(obj_addr + self.OBJECT_BYTES - 2)
        word_count = self.read_byte(prop_header_addr)
        prop_text_addr = prop_header_addr + 1
        result = [0] * word_count * 3
        for i in range(word_count):
            word = self.read_word(prop_text_addr + i * 2)
            result[3*i:3*i+3] = [(word >> 10) & 0x1f, (word >> 5) & 0x1f, word & 0x1f]
        return result

    def get_object_parent_id(self, obj_id):
        obj_addr = self.get_obj_addr(obj_id)
        if self.version <= 3:
            return self.read_byte(obj_addr + self.PARENT_OFFSET)
        return self.read_word(obj_addr + self.PARENT_OFFSET)

    def set_object_parent_id(self, obj_id, val):
        obj_addr = self.get_obj_addr(obj_id)
        if self.version <= 3:
            self.write_byte(obj_addr + self.PARENT_OFFSET, val)
        else:
            self.write_word(obj_addr + self.PARENT_OFFSET, val)

    def get_object_sibling_id(self, obj_id):
        obj_addr = self.get_obj_addr(obj_id)
        if self.version <= 3:
            return self.read_byte(obj_addr + self.SIBLING_OFFSET)
        return self.read_word(obj_addr + self.SIBLING_OFFSET)

    def set_object_sibling_id(self, obj_id, val):
        obj_addr = self.get_obj_addr(obj_id)
        if self.version <= 3:
            self.write_byte(obj_addr + self.SIBLING_OFFSET, val)
        else:
            self.write_word(obj_addr + self.SIBLING_OFFSET, val)

    def get_object_child_id(self, obj_id):
        obj_addr = self.get_obj_addr(obj_id)
        if self.version <= 3:
            return self.read_byte(obj_addr + self.CHILD_OFFSET)
        return self.read_word(obj_addr + self.CHILD_OFFSET)

    def set_object_child_id(self, obj_id, val):
        obj_addr = self.get_obj_addr(obj_id)
        if self.version <= 3:
            self.write_byte(obj_addr + self.CHILD_OFFSET, val)
        else:
            self.write_word(obj_addr + self.CHILD_OFFSET, val)

    def orphan_object(self, obj_id):
        parent_id = self.get_object_parent_id(obj_id)
        if parent_id == 0:
            return
        obj_next_sibling_id = self.get_object_sibling_id(obj_id)
        child_id = self.get_object_child_id(parent_id)
        if child_id == obj_id:
            self.set_object_child_id(parent_id, obj_next_sibling_id)
        else:
            while child_id != 0:
                next_child_id = self.get_object_sibling_id(child_id)
                if next_child_id == obj_id:
                    self.set_object_sibling_id(child_id, obj_next_sibling_id)
                    break
                child_id = next_child_id
        self.set_object_parent_id(obj_id, 0)
        self.set_object_sibling_id(obj_id, 0)

    def insert_object(self, obj_id, parent_id):
        self.orphan_object(obj_id)
        sibling_id = self.get_object_child_id(parent_id)
        self.set_object_parent_id(obj_id, parent_id)
        self.set_object_sibling_id(obj_id, sibling_id)
        self.set_object_child_id(parent_id, obj_id)

    def get_default_property_data(self, prop_id):
        if prop_id <= 0 or prop_id > self.PROPERTY_DEFAULTS_LENGTH:
            raise InvalidArgumentException(f"property id: {prop_id}")
        return self.read_word(self.OBJECT_TABLE + (prop_id - 1) * 2)

    def get_property_num(self, prop_addr):
        size_byte = self.read_byte(prop_addr - 1)
        if self.version <= 3:
            return size_byte & 0x1f
        if size_byte >= 0x80:
            return self.read_byte(prop_addr - 2) & 0x3f
        return size_byte & 0x3f

    def get_property_data_len(self, prop_addr):
        size_byte = self.read_byte(prop_addr - 1)
        if self.version <= 3:
            return (size_byte >> 5) + 1
        if size_byte >= 0x80:
            size = size_byte & 0x3f
            if size == 0:
                size = 64
            return size
        return (size_byte >> 6) + 1

    def get_prop_data_addr(self, prop_header_addr):
        size_byte = self.read_byte(prop_header_addr)
        if size_byte == 0:
            return None
        if self.version <= 3 or size_byte < 0x80:
            return prop_header_addr + 1
        return prop_header_addr + 2

    def get_first_property_addr(self, obj_id):
        obj_addr = self.get_obj_addr(obj_id)
        prop_table_addr = self.byte_addr(obj_addr + self.OBJECT_BYTES - 2)
        text_len = self.read_byte(prop_table_addr)
        prop_header_addr = prop_table_addr + 2 * text_len + 1
        return self.get_prop_data_addr(prop_header_addr)

    def get_next_property_addr(self, prop_addr):
        next_prop_addr = prop_addr + self.get_property_data_len(prop_addr)
        return self.get_prop_data_addr(next_prop_addr)

    def get_next_property_num(self, obj_id, prop_id):
        if prop_id == 0:
            prop_addr = self.get_first_property_addr(obj_id)
        else:
            prop_addr = self.get_property_addr(obj_id, prop_id)
            if prop_addr is None:
                raise InvalidArgumentException(f'Object {obj_id} does not have property {prop_id}')
            prop_addr = self.get_next_property_addr(prop_addr)
            if prop_addr is None:
                return 0
        return self.get_property_num(prop_addr)

    def get_property_addr(self, obj_id, prop_id):
        if prop_id <= 0 or prop_id > self.PROPERTY_DEFAULTS_LENGTH:
            raise InvalidArgumentException(f"Invalid property id: {prop_id}")
        prop_addr = self.get_first_property_addr(obj_id)
        while prop_addr is not None:
            property_num = self.get_property_num(prop_addr)
            if property_num == prop_id:
                return prop_addr
            if property_num < prop_id:
                break
            prop_addr = self.get_next_property_addr(prop_addr)
        return None

    def get_property_data(self, obj_id, prop_id):
        prop_addr = self.get_property_addr(obj_id, prop_id)
        if prop_addr is None:
            return self.get_default_property_data(prop_id)
        size = self.get_property_data_len(prop_addr)
        if size == 1:
            return self.read_byte(prop_addr)
        if size == 2:
            return self.read_word(prop_addr)
        raise InvalidObjectStateException("Invalid size for reading property data")

    def set_property_data(self, obj_id, prop_id, val):
        prop_addr = self.get_property_addr(obj_id, prop_id)
        if prop_addr is None:
            raise InvalidObjectStateException(f"Property {prop_id} does not exist in object {obj_id}")
        size = self.get_property_data_len(prop_addr)
        if size == 1:
            self.write_byte(prop_addr, val)
        elif size == 2:
            self.write_word(prop_addr, val)
        else:
            raise InvalidObjectStateException("Invalid size for writing property data")
