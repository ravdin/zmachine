import random
import time
from utils import *
from error import *

def get_opcodes(version):
    predicate = lambda x: version >= x.min_version and version <= x.max_version
    versioned = filter(predicate, opcodes.get_all_opcodes())
    return {item.opcode: item.op for item in versioned}

class opcodes():
    def __init__(self, op, opcode, min_version = 1, max_version = 6):
        self.op = op
        self.opcode = opcode
        self.min_version = min_version
        self.max_version = max_version

    @classmethod
    def get_all_opcodes(cls):
        return [
            cls(op_je, 1),
            cls(op_jl, 2),
            cls(op_jg, 3),
            cls(op_dec_chk, 4),
            cls(op_inc_chk, 5),
            cls(op_jin, 6),
            cls(op_test, 7),
            cls(op_or, 8),
            cls(op_and, 9),
            cls(op_test_attr, 10),
            cls(op_set_attr, 11),
            cls(op_clear_attr, 12),
            cls(op_store, 13),
            cls(op_insert_obj, 14),
            cls(op_loadw, 15),
            cls(op_loadb, 16),
            cls(op_get_prop, 17),
            cls(op_get_prop_addr, 18),
            cls(op_get_next_prop, 19),
            cls(op_add, 20),
            cls(op_sub, 21),
            cls(op_mul, 22),
            cls(op_div, 23),
            cls(op_mod, 24),
            cls(op_call_2s, 25, 4),
            cls(op_jz, 128),
            cls(op_get_sibling, 129),
            cls(op_get_child, 130),
            cls(op_get_parent, 131),
            cls(op_get_prop_len, 132),
            cls(op_inc, 133),
            cls(op_dec, 134),
            cls(op_print_addr, 135),
            cls(op_call_1s, 136, 4),
            cls(op_remove_obj, 137),
            cls(op_print_obj, 138),
            cls(op_ret, 139),
            cls(op_jump, 140),
            cls(op_print_paddr, 141),
            cls(op_load, 142),
            cls(op_rtrue, 176),
            cls(op_rfalse, 177),
            cls(op_print, 178),
            cls(op_print_ret, 179),
            cls(op_nop, 180),
            cls(op_save, 181),
            cls(op_restore, 182),
            cls(op_restart, 183),
            cls(op_ret_popped, 184),
            cls(op_pop, 185),
            cls(op_quit, 186),
            cls(op_new_line, 187),
            cls(op_show_status, 188, 3),
            cls(op_verify, 189, 3),
            cls(op_call, 224),
            cls(op_storew, 225),
            cls(op_storeb, 226),
            cls(op_put_prop, 227),
            cls(op_read, 228),
            cls(op_print_char, 229),
            cls(op_print_num, 230),
            cls(op_random, 231),
            cls(op_push, 232),
            cls(op_pull, 233),
            cls(op_split_window, 234, 4),
            cls(op_set_window, 235, 4),
            cls(op_call, 236, 4),
            cls(op_erase_window, 237, 4),
            cls(op_set_cursor, 239, 4),
            cls(op_set_text_style, 241, 4),
            cls(op_buffer_mode, 242, 4),
            cls(op_output_stream, 243, 3),
            cls(op_sound_effect, 245, 4),
            cls(op_read_char, 246, 4),
            cls(op_scan_table, 247, 4)
        ]

def op_je(zm, *operands):
    a = operands[0]
    zm.do_branch(any(a == b for b in operands[1:]))

@signed_operands
def op_jl(zm, *operands):
    a, b = operands
    zm.do_branch(a < b)

@signed_operands
def op_jg(zm, *operands):
    a, b = operands
    zm.do_branch(a > b)

def op_dec_chk(zm, *operands):
    varnum, value = operands
    ref_val = sign_uint16(zm.read_var(varnum)) - 1
    zm.write_var(varnum, ref_val)
    zm.do_branch(ref_val < value)

def op_inc_chk(zm, *operands):
    varnum, value = operands
    ref_val = sign_uint16(zm.read_var(varnum)) + 1
    zm.write_var(varnum, ref_val)
    zm.do_branch(ref_val > value)

def op_jin(zm, *operands):
    obj_id, parent_id = operands
    obj_ptr = zm.lookup_object(obj_id)
    obj_parent_id = zm.get_object_parent_id(obj_ptr)
    zm.do_branch(obj_parent_id == parent_id)

def op_test(zm, *operands):
    bitmap, flags = operands
    zm.do_branch(bitmap & flags == flags)

def op_or(zm, *operands):
    a, b = operands
    zm.do_store(a | b)

def op_and(zm, *operands):
    a, b = operands
    zm.do_store(a & b)

def op_test_attr(zm, *operands):
    obj_id, attr_num = operands
    if attr_num >= zm.ATTRIBUTE_FLAGS:
        raise InvalidArgumentException(f"{attr_num}")
    byte_offset = attr_num >> 3
    bit_offset = attr_num & 0x7
    obj_ptr = zm.lookup_object(obj_id)
    attributes = zm.read_byte(obj_ptr + byte_offset)
    attr_flags = attributes & (0x80 >> bit_offset)
    zm.do_branch(attr_flags)

def op_set_attr(zm, *operands):
    obj_id, attr_num = operands
    if attr_num >= zm.ATTRIBUTE_FLAGS:
        raise InvalidArgumentException(f"{attr_num}")
    byte_offset = attr_num >> 3
    bit_offset = attr_num & 0x7
    obj_ptr = zm.lookup_object(obj_id)
    attr_flags = zm.read_byte(obj_ptr + byte_offset)
    attr_flags |= (0x80 >> bit_offset)
    zm.write_byte(obj_ptr + byte_offset, attr_flags)

def op_clear_attr(zm, *operands):
    obj_id, attr_num = operands
    if attr_num >= zm.ATTRIBUTE_FLAGS:
        raise InvalidArgumentException(f"{attr_num}")
    byte_offset = attr_num >> 3
    bit_offset = attr_num & 0x7
    obj_ptr = zm.lookup_object(obj_id)
    attr_flags = zm.read_byte(obj_ptr + byte_offset)
    attr_flags &= (~(0x80 >> bit_offset) & 0xff)
    zm.write_byte(obj_ptr + byte_offset, attr_flags)

def op_store(zm, *operands):
    varnum, value = operands
    zm.write_var(varnum, value)

def op_insert_obj(zm, *operands):
    obj_id, parent_id = operands
    zm.orphan_object(obj_id)
    obj_ptr = zm.lookup_object(obj_id)
    parent_ptr = zm.lookup_object(parent_id)
    first_child_id = zm.get_object_child_id(parent_ptr)
    zm.set_object_parent_id(obj_ptr, parent_id)
    zm.set_object_sibling_id(obj_ptr, first_child_id)
    zm.set_object_child_id(parent_ptr, obj_id)

def op_loadw(zm, *operands):
    ptr, word_index = operands
    result = zm.read_word(ptr + 2 * word_index)
    zm.do_store(result)

def op_loadb(zm, *operands):
    ptr, byte_index = operands
    result = zm.read_byte(ptr + byte_index)
    zm.do_store(result)

def op_get_prop(zm, *operands):
    obj_id, prop_id = operands
    prop_ptr = zm.lookup_property(obj_id, prop_id)
    result = 0
    if prop_ptr == None:
        if prop_id < 0 or prop_id > zm.PROPERTY_DEFAULTS_LENGTH:
            raise InvalidArgumentException(f"property id: {prop_id}")
        result = zm.read_word(zm.object_header + ((prop_id - 1) * 2))
    else:
        _, size, data_ptr = zm.get_property_data(prop_ptr)
        if size == 1:
            result = zm.read_byte(data_ptr)
        elif size == 2:
            result = zm.read_word(data_ptr)
        else:
            raise Exception("Invalid size for property")
    zm.do_store(result)

def op_get_prop_addr(zm, *operands):
    obj_id, prop_id = operands
    result = 0
    prop_ptr = zm.lookup_property(obj_id, prop_id)
    if prop_ptr != None:
        result = zm.get_property_data(prop_ptr)[2]
    zm.do_store(result)

def op_get_next_prop(zm, *operands):
    obj_id, prop_id = operands
    result = zm.get_next_property_id(obj_id, prop_id)
    zm.do_store(result)

@signed_operands
def op_add(zm, *operands):
    a, b = operands
    zm.do_store(a + b)

@signed_operands
def op_sub(zm, *operands):
    a, b = operands
    zm.do_store(a - b)

@signed_operands
def op_mul(zm, *operands):
    a, b = operands
    zm.do_store(a * b)

@signed_operands
def op_div(zm, *operands):
    a, b = operands
    zm.do_store(a // b)

@signed_operands
def op_mod(zm, *operands):
    a, b = operands
    zm.do_store(a % b)

def op_call_2s(zm, *operands):
    op_call(zm, *operands)

def op_jz(zm, *operands):
    zm.do_branch(operands[0] == 0)

def op_get_sibling(zm, *operands):
    obj_ptr = zm.lookup_object(operands[0])
    sibling_id = zm.get_object_sibling_id(obj_ptr)
    zm.do_store(sibling_id)
    zm.do_branch(sibling_id)

def op_get_child(zm, *operands):
    obj_ptr = zm.lookup_object(operands[0])
    child_id = zm.get_object_child_id(obj_ptr)
    zm.do_store(child_id)
    zm.do_branch(child_id)

def op_get_parent(zm, *operands):
    obj_id = operands[0]
    obj_ptr = zm.lookup_object(obj_id)
    parent_id = zm.get_object_parent_id(obj_ptr)
    zm.do_store(parent_id)

def op_get_prop_len(zm, *operands):
    data_ptr = operands[0]
    result = 0
    if data_ptr != 0:
        size_byte = zm.read_byte(data_ptr - 1)
        if zm.version <= 3:
            result = (size_byte >> 5) + 1
        elif size_byte & 0x80 == 0x80:
            result = size_byte & 0x3f
            if result == 0:
                result = 64
        else:
            result = (size_byte >> 6) + 1
    zm.do_store(result)

def op_inc(zm, *operands):
    varnum = operands[0]
    ref_val = sign_uint16(zm.read_var(varnum)) + 1
    zm.write_var(varnum, ref_val)

def op_dec(zm, *operands):
    varnum = operands[0]
    ref_val = sign_uint16(zm.read_var(varnum)) - 1
    zm.write_var(varnum, ref_val)

def op_print_addr(zm, *operands):
    ptr = operands[0]
    encoded = zm.read_encoded_zscii(ptr)
    zm.do_print_encoded(encoded)

def op_call_1s(zm, *operands):
    op_call(zm, *operands)

def op_print_obj(zm, *operands):
    obj_id = operands[0]
    obj_text = zm.get_object_text(obj_id)
    zm.do_print(obj_text)

def op_ret(zm, *operands):
    zm.do_return(operands[0])

def op_remove_obj(zm, *operands):
    zm.orphan_object(operands[0])

@signed_operands
def op_jump(zm, *operands):
    zm.pc += operands[0] - 2

def op_print_paddr(zm, *operands):
    addr = zm.unpack_addr(operands[0])
    encoded = zm.read_encoded_zscii(addr)
    zm.do_print_encoded(encoded)

def op_load(zm, *operands):
    varnum = operands[0]
    ref_val = zm.read_var(varnum)
    zm.do_store(ref_val)

def op_rtrue(zm, *operands):
    zm.do_return(True)

def op_rfalse(zm, *operands):
    zm.do_return(False)

def op_print(zm, *operands):
    encoded = zm.read_encoded_zscii_from_pc()
    zm.do_print_encoded(encoded)

def op_print_ret(zm, *operands):
    encoded = zm.read_encoded_zscii_from_pc()
    zm.do_print_encoded(encoded, True)
    zm.do_return(True)

def op_nop(zm, *operands):
    return

def op_save(zm, *operands):
    success = zm.do_save()
    if zm.version <= 3:
        zm.do_branch(success)
    else:
        zm.do_store(1 if success else 0)

def op_restore(zm, *operands):
    success = zm.do_restore()
    if zm.version <= 3:
        # Technically, op_restore doesn't branch.
        # On success, the branch occurs from the save op that produced the file.
        # On failure, proceed with the next instruction.
        zm.do_branch(success)
    else:
        zm.do_store(2 if success else 0)

def op_restart(zm, *operands):
    zm.do_restart()

def op_ret_popped(zm, *operands):
    retval = zm.stack_pop()
    zm.do_return(retval)

def op_pop(zm, *operands):
    zm.stack_pop()

def op_quit(zm, *operands):
    zm.quit = True

def op_new_line(zm, *operands):
    zm.do_print('', True)

def op_show_status(zm, *operands):
    zm.do_show_status()

def op_verify(zm, *operands):
    zm.do_branch(zm.do_verify())

def op_call(zm, *operands):
    if len(operands) == 0 or operands[0] == 0:
        # Legal state, return 0
        zm.do_store(0)
        return
    call_addr, args = zm.unpack_addr(operands[0]), operands[1:]
    zm.do_routine(call_addr, args)

def op_storew(zm, *operands):
    ptr, word_index, value = operands
    zm.write_word(ptr + 2 * word_index, value)

def op_storeb(zm, *operands):
    ptr, byte_index, value = operands
    zm.write_byte(ptr + byte_index, value)

def op_put_prop(zm, *operands):
    obj_id, prop_id, value = operands
    prop_ptr = zm.lookup_property(obj_id, prop_id)
    if prop_ptr == None:
        raise Exception("Property does not exist")
    _, prop_size, data_ptr = zm.get_property_data(prop_ptr)
    if prop_size > 2:
        raise Exception("Invalid call to put_prop")
    if prop_size == 1:
        zm.write_byte(data_ptr, value)
    if prop_size == 2:
        zm.write_word(data_ptr, value)

def op_read(zm, *operands):
    zm.do_read(*operands)

def op_print_char(zm, *operands):
    zscii_code = operands[0]
    if zscii_code == 0:
        return
    elif zscii_code < 32 or zscii_code > 126:
        if zscii_code == 10:
            zscii_code = 13
        if zscii_code != 13:
            raise ZSCIIException("Invalid ZSCII code '{0}'".format(zscii_code))
    else:
        zm.do_print(chr(zscii_code))

@signed_operands
def op_print_num(zm, *operands):
    zm.do_print(str(operands[0]))

@signed_operands
def op_random(zm, *operands):
    r = operands[0]
    result = 0
    if r > 0:
        result = random.randint(1, r)
    elif r < 0:
        random.seed(r)
    else:
        random.seed(round(time.time() * 1000) % 1000)
    zm.do_store(result)

def op_push(zm, *operands):
    zm.stack_push(operands[0])

def op_pull(zm, *operands):
    value = zm.stack_pop()
    zm.write_var(operands[0], value)

def op_split_window(zm, *operands):
    zm.split_window_handler(operands[0])

def op_set_window(zm, *operands):
    zm.set_window_handler(operands[0])

@signed_operands
def op_erase_window(zm, *operands):
    zm.erase_window_handler(operands[0])

def op_set_cursor(zm, *operands):
    y, x = operands
    zm.set_cursor_handler(y, x)

def op_set_text_style(zm, *operands):
    zm.set_text_style_handler(operands[0])

def op_buffer_mode(zm, *operands):
    zm.set_buffer_mode_handler(operands[0])

def op_output_stream(zm, *operands):
    stream = sign_uint16(operands[0])
    if stream == 0:
        pass
    elif stream == 1:
        zm.output_streams |= 0x1
    elif stream == -1:
        zm.output_streams &= 0xe
    elif stream == 3:
        if zm.output_streams & 0x4 == 0x4:
            raise #TODO: This should open another stream.
        zm.output_streams |= 0x4
        zm.memory_stream.open(operands[1])
    elif stream == -3:
        zm.output_streams &= 0xb
        zm.memory_stream.close()
    else:
        raise Exception(f"Op not supported: {operands[0]}")

# TODO: Treating this as a nop.
def op_sound_effect(zm, *operands):
    pass

def op_read_char(zm, *operands):
    char = zm.read_char_handler()
    if char == 10:
        char = 13
    zm.do_store(char)

def op_scan_table(zm, *operands):
    word, addr, length = operands
    result = 0
    for i in range(length):
        if zm.read_word(addr) == word:
            result = addr
            break
        addr += 2
    zm.do_store(result)
    zm.do_branch(result)
