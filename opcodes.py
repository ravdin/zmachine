import random
import time
from utils import *

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
    obj_a_ptr = zm.lookup_object(obj_id)
    obj_a_parent = zm.read_byte(obj_a_ptr + 4)
    zm.do_branch(obj_a_parent == parent_id)

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
    obj_ptr = zm.lookup_object(obj_id)
    attributes = zm.read_dword(obj_ptr)
    attr_val = attributes & (0x80000000 >> attr_num)
    zm.do_branch(attr_val)

def op_set_attr(zm, *operands):
    obj_id, attr = operands
    obj_ptr = zm.lookup_object(obj_id)
    attr_flags = zm.read_dword(obj_ptr)
    attr_flags |= (0x80000000 >> attr)
    zm.write_dword(obj_ptr, attr_flags)

def op_clear_attr(zm, *operands):
    obj_id, attr = operands
    obj_ptr = zm.lookup_object(obj_id)
    attr_flags = zm.read_dword(obj_ptr)
    attr_flags &= (~(0x80000000 >> attr) & 0xffffffff)
    zm.write_dword(obj_ptr, attr_flags)

def op_store(zm, *operands):
    varnum, value = operands
    zm.write_var(varnum, value)

def op_insert_obj(zm, *operands):
    obj_id, parent_id = operands
    zm.orphan_object(obj_id)
    obj_ptr = zm.lookup_object(obj_id)
    parent_ptr = zm.lookup_object(parent_id)
    first_child_id = zm.read_byte(parent_ptr + 6)
    zm.write_byte(obj_ptr + 4, parent_id)
    zm.write_byte(obj_ptr + 5, first_child_id)
    zm.write_byte(parent_ptr + 6, obj_id)

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
        result = zm.read_word(zm.object_header + ((prop_id - 1) * 2))
    else:
        size_byte = zm.read_byte(prop_ptr)
        size = (size_byte >> 5) + 1
        if size == 1:
            result = zm.read_byte(prop_ptr + 1)
        elif size == 2:
            result = zm.read_word(prop_ptr + 1)
        else:
            raise Exception("Invalid size for property")
    zm.do_store(result)

def op_get_prop_addr(zm, *operands):
    obj_id, prop_id = operands
    prop_ptr = zm.lookup_property(obj_id, prop_id)
    zm.do_store(0 if prop_ptr == None else prop_ptr + 1)

def op_get_next_prop(zm, *operands):
    obj_id, prop_id = operands
    result = 0
    if prop_id == 0:
        # Get the first property
        obj_ptr = zm.lookup_object(obj_id)
        prop_ptr = zm.byte_addr(obj_ptr + 7)
        text_len = zm.read_byte(prop_ptr)
        prop_ptr += 2 * text_len + 1
        result = zm.read_byte(prop_ptr) & 0x1f
    else:
        prop_ptr = zm.lookup_property(obj_id, prop_id)
        if prop_ptr == None:
            raise Exception("Invalid property lookup")
        size = (zm.read_byte(prop_ptr) >> 5) + 1
        next_prop_info = zm.read_byte(prop_ptr + size + 1)
        if next_prop_info != 0:
            result = next_prop_info & 0x1f
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

def op_jz(zm, *operands):
    zm.do_branch(operands[0] == 0)

def op_get_sibling(zm, *operands):
    obj_ptr = zm.lookup_object(operands[0])
    sibling_id = zm.read_byte(obj_ptr + 5)
    zm.do_store(sibling_id)
    zm.do_branch(sibling_id)

def op_get_child(zm, *operands):
    obj_ptr = zm.lookup_object(operands[0])
    child_id = zm.read_byte(obj_ptr + 6)
    zm.do_store(child_id)
    zm.do_branch(child_id)

def op_get_parent(zm, *operands):
    obj_id = operands[0]
    obj_ptr = zm.lookup_object(obj_id)
    zm.do_store(zm.read_byte(obj_ptr + 4))

def op_get_prop_len(zm, *operands):
    prop_ptr = operands[0]
    result = 0
    if prop_ptr != 0:
        size_byte = zm.read_byte(prop_ptr - 1)
        result = (size_byte >> 5) + 1
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

def op_ret(zm, *operands):
    zm.do_return(operands[0])

def op_remove_obj(zm, *operands):
    zm.orphan_object(operands[0])

def op_print_obj(zm, *operands):
    obj_id = operands[0]
    if obj_id == 0 or obj_id > 0xff:
        raise Exception('Invalid object: {0}'.format(obj_id))
    obj_ptr = zm.lookup_object(obj_id)
    prop_ptr = zm.byte_addr(obj_ptr + 7)
    encoded = zm.read_encoded_zscii(prop_ptr + 1)
    zm.do_print_encoded(encoded)

@signed_operands
def op_jump(zm, *operands):
    zm.pc += operands[0] - 2

def op_print_paddr(zm, *operands):
    addr = operands[0] << 1
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
    encoded = zm.read_encoded_zscii(zm.pc)
    zm.pc += len(encoded) * 2
    zm.do_print_encoded(encoded)

def op_print_ret(zm, *operands):
    encoded = zm.read_encoded_zscii(zm.pc)
    zm.pc += len(encoded) * 2
    zm.do_print_encoded(encoded, True)
    zm.do_return(True)

def op_nop(zm, *operands):
    return

def op_save(zm, *operands):
    success = zm.do_save()
    zm.do_branch(success)

def op_restore(zm, *operands):
    success = zm.do_restore()
    # Technically, op_restore doesn't branch.
    # On success, the branch occurs from the save op that produced the file.
    # On failure, proceed with the next instruction.
    zm.do_branch(success)

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
    call_addr, args = operands[0] << 1, operands[1:]
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
    prop_size = (zm.read_byte(prop_ptr) >> 5) + 1
    if prop_size > 2:
        raise Exception("Invalid call to put_prop")
    if prop_size == 1:
        zm.write_byte(prop_ptr + 1, value & 0xff)
    if prop_size == 2:
        zm.write_word(prop_ptr + 1, value)

def op_read(zm, *operands):
    zm.do_read(*operands)

def op_print_char(zm, *operands):
    zscii_code = operands[0]
    if zscii_code == 0:
        return
    elif zscii_code < 32 or zscii_code > 126:
        raise Exception("Invalid ZSCII code '{0}'".format(zscii_code))
    else:
        zm.do_print(chr(zscii_code))

@signed_operands
def op_print_num(zm, *operands):
    zm.do_print(operands[0])

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
