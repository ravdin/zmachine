from memory import MemoryMap
from typing import List
from error import *


class TextUtils:
    A0 = 'abcdefghijklmnopqrstuvwxyz'
    A1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    A2 = ' ^0123456789.,!?_#\'"/\\-:()'

    def __init__(self, memory_map: MemoryMap):
        self.memory_map = memory_map
        self.abbreviation_table = memory_map.abbreviation_table
        self.separator_chars = self.get_separator_chars()
        self.version = memory_map.version

    def read_byte(self, ptr):
        return self.memory_map.read_byte(ptr)

    def read_word(self, ptr):
        return self.memory_map.read_word(ptr)

    def get_separator_chars(self):
        ptr = self.memory_map.dictionary_header
        num_separators = self.read_byte(ptr)
        return [chr(self.read_byte(ptr + i + 1)) for i in range(num_separators)]

    def lookup_dictionary(self, text):
        # Of course, we could load the dictionary into a hashtable for fastest lookup.
        # The dictionary is already loaded into memory, so we'll use it in a binary search.
        def read_entry(entry_addr, entry_bytes):
            result = 0
            for _ in range(entry_bytes >> 1):
                result <<= 16
                result |= self.read_word(entry_addr)
                entry_addr += 2
            return result

        encoded_len = 4 if self.version <= 3 else 6
        encoded = self.zscii_encode(text, encoded_len)
        ptr = self.memory_map.dictionary_header
        num_separators = self.read_byte(ptr)
        entry_length = self.read_byte(ptr + num_separators + 1)
        num_entries = self.read_word(ptr + num_separators + 2)
        ptr += num_separators + 4
        lo = 0
        hi = num_entries - 1
        while lo < hi:
            mid = (lo + hi) >> 1
            mid_ptr = ptr + mid * entry_length
            entry = read_entry(mid_ptr, encoded_len)
            if entry == encoded:
                return mid_ptr
            elif entry < encoded:
                lo = mid + 1
            else:
                hi = mid - 1
        lo_ptr = ptr + lo * entry_length
        return lo_ptr if read_entry(lo_ptr, encoded_len) == encoded else 0

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
        addr = self.memory_map.word_addr(self.abbreviation_table + index * 2)
        self.read_zchars(addr, result)
        return result

    def zscii_encode(self, text, word_len=4):
        zlen = word_len // 2 * 3
        zchars = []
        for c in text:
            if 'a' <= c <= 'z':
                zchars += [ord(c) - 91]
            elif c in self.A2[2:]:
                zchars += [5, self.A2.index(c) + 6]
            elif 32 <= ord(c) <= 126:
                ascii_val = ord(c)
                z1 = ascii_val >> 5 & 0x1f
                z2 = ascii_val & 0x1f
                zchars += [5, 6, z1, z2]
            else:
                return 0
        if len(zchars) < zlen:
            zchars += [5] * (zlen - len(zchars))
        encoded = 0
        for i in range(zlen):
            if i % 3 == 0:
                encoded <<= 1
            encoded <<= 5
            encoded |= zchars[i]
        encoded |= 0x8000
        return encoded
