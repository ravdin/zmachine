from memory import MemoryMap
from config import *
from typing import List
from error import *


class TextUtils:
    A0 = 'abcdefghijklmnopqrstuvwxyz'
    A1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    A2 = ' ^0123456789.,!?_#\'"/\\-:()'

    def __init__(self, memory_map: MemoryMap):
        self.memory_map = memory_map
        self.separator_chars = self.get_separator_chars()

    def read_byte(self, ptr):
        return self.memory_map.read_byte(ptr)

    def read_word(self, ptr):
        return self.memory_map.read_word(ptr)

    def read_int16(self, addr):
        num = self.read_word(addr)
        if num >= 0x8000:
            num = -(~num & 0xffff) - 1
        return num

    def get_separator_chars(self):
        ptr = CONFIG[DICTIONARY_TABLE_KEY]
        num_separators = self.read_byte(ptr)
        return [chr(self.read_byte(ptr + i + 1)) for i in range(num_separators)]

    def lookup_dictionary(self, text, dictionary_addr=0):
        def compare_entry(entry_addr, encoded_bytes):
            for i in range(len(encoded_bytes)):
                entry_byte = self.read_byte(entry_addr + i)
                if encoded_bytes[i] < entry_byte:
                    return -1
                elif encoded_bytes[i] > entry_byte:
                    return 1
            return 0

        # Of course, we could load the dictionary into a hashtable for fastest lookup.
        # The dictionary is already loaded into memory, so we'll use it in a binary search.
        def binary_search():
            lo = 0
            hi = num_entries - 1
            while lo < hi:
                mid = (lo + hi) >> 1
                mid_ptr = first_entry_ptr + mid * entry_length
                comparison = compare_entry(mid_ptr, encoded)
                if comparison == 0:
                    return mid_ptr
                elif comparison > 0:
                    lo = mid + 1
                else:
                    hi = mid - 1
            lo_ptr = first_entry_ptr + lo * entry_length
            return lo_ptr if compare_entry(lo_ptr, encoded) == 0 else 0

        def linear_search():
            entry_ptr = first_entry_ptr
            for _ in range(num_entries):
                if compare_entry(entry_ptr, encoded) == 0:
                    return entry_ptr
                entry_ptr += entry_length
            return 0

        encoded_len = 4 if CONFIG[VERSION_NUMBER_KEY] <= 3 else 6
        encoded = self.zscii_encode(text, encoded_len)
        search_method = binary_search
        if dictionary_addr == 0:
            dictionary_addr = CONFIG[DICTIONARY_TABLE_KEY]
        num_separators = self.read_byte(dictionary_addr)
        entry_length = self.read_byte(dictionary_addr + num_separators + 1)
        num_entries = self.read_int16(dictionary_addr + num_separators + 2)
        if num_entries < 0:
            # A negative number of entries means that there are -n unsorted entries.
            search_method = linear_search
            num_entries = -num_entries
        first_entry_ptr = dictionary_addr + num_separators + 4
        return search_method()

    @staticmethod
    def tokenize(command, separator_chars=None):
        if separator_chars is None:
            separator_chars = [',', '.', '"']
        words = list(filter(lambda w: w != '', command.split(' ')))[::-1]
        tokens = []
        positions = []
        current_pos = 0
        while len(words) > 0:
            word = words.pop()
            if word in separator_chars:
                tokens += [word]
                continue
            separator_found = False
            for s in separator_chars:
                pos = word.find(s)
                if pos > -1:
                    separator_found = True
                    words += list(filter(lambda w: w != '', [word[pos + 1:], word[pos], word[:pos]]))
                    break
            if not separator_found:
                tokens += [word]
        for t in tokens:
            pos = command.find(t, current_pos)
            current_pos = pos
            positions += [pos]
        return tokens, positions

    def zscii_decode(self, zchars):
        result = []
        current_alphabet = self.A0
        zptr = 0
        while zptr < len(zchars):
            zchar = zchars[zptr]
            if zchar == 0:
                result += [' ']
            elif zchar in (1, 2, 3):
                zptr += 1
                index = ((zchar - 1) << 5) | zchars[zptr]
                abbreviation = self.abbreviation_lookup(index)
                result += [self.zscii_decode(abbreviation)]
            elif zchar == 4:
                zptr += 1
                current_alphabet = self.A1
                continue
            elif zchar == 5:
                zptr += 1
                current_alphabet = self.A2
                continue
            elif 6 <= zchar <= 31:
                if zchar == 6 and current_alphabet == self.A2:
                    zscii_code = zchars[zptr + 1] << 5 | zchars[zptr + 2]
                    zptr += 2
                    if zscii_code == 9:
                        result += [' ']
                    elif zscii_code < 32 or zscii_code > 126:
                        raise ZSCIIException(f'Invalid zscii code: {zscii_code}')
                    else:
                        result += [chr(zscii_code)]
                elif zchar == 7 and current_alphabet == self.A2:
                    result += ['\n']
                else:
                    result += [current_alphabet[zchar - 6]]
            else:
                raise ZSCIIException(f'Invalid z character: {zchar}')
            current_alphabet = self.A0
            zptr += 1
        return ''.join(result)

    def read_zchars(self, addr: int, buffer: List[int]) -> int:
        word = 0
        while word & 0x8000 != 0x8000:
            word = self.read_word(addr)
            buffer += [(word >> 10) & 0x1f, (word >> 5) & 0x1f, word & 0x1f]
            addr += 2
        return addr

    def abbreviation_lookup(self, index):
        result = []
        addr = self.memory_map.word_addr(CONFIG[ABBREVIATION_TABLE_KEY] + index * 2)
        self.read_zchars(addr, result)
        return result

    def zscii_encode(self, text, byte_len=4) -> list[int]:
        zlen = byte_len // 2 * 3
        zchars = []
        for c in text:
            if 'a' <= c <= 'z':
                zchars += [ord(c) - 91]
            elif c in self.A2[2:]:
                zchars += [5, self.A2.index(c) + 6]
            elif 32 <= ord(c) <= 126:
                ascii_val = ord(c)
                z1 = ascii_val >> 5
                z2 = ascii_val & 0x1f
                zchars += [5, 6, z1, z2]
            else:
                # TODO: The interpreter doesn't recognize wide characters.
                return [0] * byte_len
        if len(zchars) < zlen:
            zchars += [5] * (zlen - len(zchars))
        result = [0] * byte_len
        for i in range(byte_len // 2):
            encoded_ptr = i * 2
            zchars_ptr = i * 3
            result[encoded_ptr] = (zchars[zchars_ptr] << 2) | (zchars[zchars_ptr + 1] >> 3)
            result[encoded_ptr + 1] = ((zchars[zchars_ptr + 1] & 0x7) << 5) | zchars[zchars_ptr + 2]
        result[-2] |= 0x80
        return result
