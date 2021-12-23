from error import ZSCIIException

def signed_operands(op):
    def sign_and_call(*args):
        zm, operands = args[0], [sign_uint16(o) for o in args[1:]]
        return op(zm, *operands)
    return sign_and_call

def sign_uint16(num):
    if num >= 0x8000:
        num = -(~num & 0xffff) - 1
    return num

def tokenize(command, separator_chars = [',', '.', '"']):
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
                words += list(filter(lambda w: w != '', [word[pos+1:], word[pos], word[:pos]]))
                break
        if separator_found:
            continue
        tokens += [word]
    for t in tokens:
        pos = command[current_pos:].find(t)
        if len(positions) > 0:
            pos += positions[-1]
        current_pos = pos
        positions += [pos]
    return tokens, positions

# TODO: Extend this for other versions besides V3.
def zscii_decode(encoded, abbreviations = None):
    result = []
    zchars = []
    for word in encoded:
        zchars += [word >> 10 & 0x1f, word >> 5 & 0x1f, word & 0x1f]
    A0 = 'abcdefghijklmnopqrstuvwxyz'
    A1 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    A2 = ' ^0123456789.,!?_#\'"/\-:()'
    current_alphabet = A0
    zptr = 0
    while zptr < len(zchars):
        zchar = zchars[zptr]
        if zchar == 0:
            result += [' ']
        elif zchar in (1, 2, 3):
            zptr += 1
            result += [abbreviations[32 * (zchar - 1) + zchars[zptr]]]
        elif zchar == 4:
            zptr += 1
            current_alphabet = A1
            continue
        elif zchar == 5:
            zptr += 1
            current_alphabet = A2
            continue
        elif zchar >= 6 and zchar <= 31:
            if zchar == 6 and current_alphabet == A2:
                zscii_code = zchars[zptr+1] << 5 | zchars[zptr+2]
                zptr += 2
                if zscii_code == 9:
                    result += [' ']
                elif zscii_code < 32 or zscii_code > 126:
                    raise ZSCIIException(f'Invalid zscii code: {zscii_code}')
                else:
                    result += [chr(zscii_code)]
            elif zchar == 7 and current_alphabet == A2:
                result += ['\n']
            else:
                result += [current_alphabet[zchar-6]]
        else:
            raise ZSCIIException(f'Invalid z character: {zchar}')
        current_alphabet = A0
        zptr += 1
    return ''.join(result)

def zscii_encode(text, word_len = 4):
    # TODO: standardize this for other zmachine versions
    A2 = ' ^0123456789.,!?_#\'"/\-:()'
    zlen = word_len // 2 * 3
    zchars = []
    for c in text:
        if c >= 'a' and c <= 'z':
            zchars += [ord(c) - 91]
        elif c in A2[2:]:
            zchars += [5, A2.index(c) + 6]
        elif ord(c) >= 32 and ord(c) <= 126:
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
