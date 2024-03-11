import random
import time
from typing import Callable, Dict, Any
from functools import wraps
from abstract_interpreter import AbstractZMachineInterpreter
from config import ROUTINE_TYPE_DISCARD
from event import EventArgs
from error import *


def get_opcodes(version) -> Dict[int, Callable[[AbstractZMachineInterpreter, int, ...], Any]]:
    def predicate(opcode: Opcode):
        return opcode.min_version <= version <= opcode.max_version
    versioned = filter(predicate, Opcode.get_all_opcodes())
    return {item.opcode: item.op for item in versioned}


def get_extended_opcodes(version) -> Dict[int, Callable[[AbstractZMachineInterpreter, int, ...], Any]]:
    def predicate(opcode: Opcode):
        return opcode.min_version <= version <= opcode.max_version
    versioned = filter(predicate, Opcode.get_extended_opcodes())
    return {item.opcode: item.op for item in versioned}


def signed_operands(op):
    @wraps(op)
    def sign_and_execute(*args):
        zm, operands = args[0], [sign_uint16(o) for o in args[1:]]
        return op(zm, *operands)
    return sign_and_execute


def sign_uint16(num):
    if num >= 0x8000:
        num = -(~num & 0xffff) - 1
    return num


class Opcode:
    def __init__(self,
                 op: Callable[[AbstractZMachineInterpreter, int, ...], Any],
                 opcode: int,
                 min_version: int = 1,
                 max_version: int = 6):
        self.op = op
        self.opcode: int = opcode
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
            cls(op_call_vn, 26, 5),
            cls(op_set_color, 27, 5),
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
            cls(op_not, 143, max_version=4),
            cls(op_call_1n, 143, 5),
            cls(op_rtrue, 176),
            cls(op_rfalse, 177),
            cls(op_print, 178),
            cls(op_print_ret, 179),
            cls(op_nop, 180),
            cls(op_save, 181, max_version=4),
            cls(op_restore, 182, max_version=4),
            cls(op_restart, 183),
            cls(op_ret_popped, 184),
            cls(op_pop, 185),
            cls(op_quit, 186),
            cls(op_new_line, 187),
            cls(op_show_status, 188, 3),
            cls(op_verify, 189, 3),
            cls(op_piracy, 191, 5),
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
            cls(op_split_window, 234, 3),
            cls(op_set_window, 235, 3),
            cls(op_call, 236, 4, 5),
            cls(op_call_vs, 236, 5),
            cls(op_erase_window, 237, 4),
            cls(op_set_cursor, 239, 4),
            cls(op_set_text_style, 241, 4),
            cls(op_buffer_mode, 242, 4),
            cls(op_output_stream, 243, 3),
            cls(op_sound_effect, 245),
            cls(op_read_char, 246, 4),
            cls(op_scan_table, 247, 4),
            cls(op_not, 248, 5),
            cls(op_call_vn, 249, 5),
            cls(op_call_vn2, 250, 5),
            cls(op_tokenize, 251, 5),
            cls(op_encode_text, 252, 5),
            cls(op_copy_table, 253, 5),
            cls(op_print_table, 254, 5),
            cls(op_check_arg_count, 255, 5)
        ]

    @classmethod
    def get_extended_opcodes(cls):
        return [
            cls(op_save, 0, 5),
            cls(op_restore, 1, 5),
            cls(op_log_shift, 2, 5),
            cls(op_art_shift, 3, 5),
            cls(op_set_font, 4, 5),
            cls(op_save_undo, 9, 5),
            cls(op_restore_undo, 10, 5)
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


@signed_operands
def op_dec_chk(zm, *operands):
    varnum, value = operands
    ref_val = sign_uint16(zm.read_var(varnum)) - 1
    zm.write_var(varnum, ref_val)
    zm.do_branch(ref_val < value)


@signed_operands
def op_inc_chk(zm, *operands):
    varnum, value = operands
    ref_val = sign_uint16(zm.read_var(varnum)) + 1
    zm.write_var(varnum, ref_val)
    zm.do_branch(ref_val > value)


def op_jin(zm, *operands):
    obj_id, parent_id = operands
    obj_parent_id = zm.object_table.get_object_parent_id(obj_id)
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
    result = False
    if obj_id != 0:
        # There is no object ID of 0, but some Infocom games will test
        # an attribute of the parent of object after it has been
        # removed from the object tree.
        # Presumably historical interpreters handled it by assuming that attributes
        # of a null object are false.
        result = zm.object_table.get_attribute_flag(obj_id, attr_num)
    zm.do_branch(result)


def op_set_attr(zm, *operands):
    obj_id, attr_num = operands
    zm.object_table.set_attribute_flag(obj_id, attr_num, True)


def op_clear_attr(zm, *operands):
    obj_id, attr_num = operands
    zm.object_table.set_attribute_flag(obj_id, attr_num, False)


def op_store(zm, *operands):
    varnum, value = operands
    if varnum == 0:
        zm.stack_pop()
        zm.stack_push(value)
    else:
        zm.write_var(varnum, value)


def op_insert_obj(zm, *operands):
    obj_id, parent_id = operands
    zm.object_table.insert_object(obj_id, parent_id)


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
    result = zm.object_table.get_property_data(obj_id, prop_id)
    zm.do_store(result)


def op_get_prop_addr(zm, *operands):
    obj_id, prop_id = operands
    prop_addr = zm.object_table.get_property_addr(obj_id, prop_id)
    if prop_addr is None:
        prop_addr = 0
    zm.do_store(prop_addr)


def op_get_next_prop(zm, *operands):
    obj_id, prop_id = operands
    result = zm.object_table.get_next_property_num(obj_id, prop_id)
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
    result = a // b
    if result < 0:
        result += 1
    zm.do_store(result)


@signed_operands
def op_mod(zm, *operands):
    a, b = operands
    result = a % b
    # Python's modulo works differently from the C compiler for negative numbers.
    # This interpreter will be consistent with what historical interpreters likely would have done.
    if a < 0 < b or a > 0 > b:
        result -= b
    zm.do_store(result)


def op_call_2s(zm, *operands):
    op_call(zm, *operands)


def op_jz(zm, *operands):
    zm.do_branch(operands[0] == 0)


def op_get_sibling(zm, *operands):
    obj_id = operands[0]
    sibling_id = zm.object_table.get_object_sibling_id(obj_id)
    zm.do_store(sibling_id)
    zm.do_branch(sibling_id)


def op_get_child(zm, *operands):
    obj_id = operands[0]
    child_id = 0
    if obj_id != 0:
        child_id = zm.object_table.get_object_child_id(obj_id)
    zm.do_store(child_id)
    zm.do_branch(child_id)


def op_get_parent(zm, *operands):
    obj_id = operands[0]
    parent_id = zm.object_table.get_object_parent_id(obj_id)
    zm.do_store(parent_id)


def op_get_prop_len(zm, *operands):
    prop_addr = operands[0]
    result = 0
    if prop_addr != 0:
        result = zm.object_table.get_property_data_len(prop_addr)
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
    zm.print_from_addr(ptr)


def op_call_1s(zm, *operands):
    op_call(zm, *operands)


def op_print_obj(zm, *operands):
    obj_id = operands[0]
    obj_text = zm.get_object_text(obj_id)
    zm.write_to_output_streams(obj_text)


def op_ret(zm, *operands):
    zm.do_return(operands[0])


def op_remove_obj(zm, *operands):
    zm.object_table.orphan_object(operands[0])


@signed_operands
def op_jump(zm, *operands):
    zm.do_jump(operands[0])


def op_print_paddr(zm, *operands):
    addr = zm.unpack_addr(operands[0])
    zm.print_from_addr(addr)


def op_load(zm, *operands):
    varnum = operands[0]
    if varnum == 0:
        ref_val = zm.stack_peek()
    else:
        ref_val = zm.read_var(varnum)
    zm.do_store(ref_val)


def op_not(zm, *operands):
    val = (~operands[0]) & 0xffff
    zm.do_store(val)


def op_call_1n(zm, *operands):
    op_call_vn(zm, *operands)


def op_rtrue(zm, *operands):
    zm.do_return(1)


def op_rfalse(zm, *operands):
    zm.do_return(0)


def op_print(zm, *operands):
    zm.print_from_pc()


def op_print_ret(zm, *operands):
    zm.print_from_pc(True)
    zm.do_return(1)


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
    zm.do_quit()


def op_new_line(zm, *operands):
    zm.write_to_output_streams('', True)


def op_show_status(zm, *operands):
    zm.do_show_status()


def op_verify(zm, *operands):
    zm.do_branch(zm.do_verify())


def op_piracy(zm, *operands):
    # Branch if the interpreter believes the game bytes to be genuine.
    # This interpreter is unconditionally gullible.
    zm.do_branch(True)


def op_call(zm, *operands):
    if len(operands) == 0 or operands[0] == 0:
        # Legal state, return 0
        zm.do_store(0)
        return
    call_addr, args = zm.unpack_addr(operands[0]), operands[1:]
    zm.do_routine(call_addr, args)


def op_call_vs(zm, *operands):
    op_call(zm, *operands)


def op_storew(zm, *operands):
    ptr, word_index, value = operands
    zm.write_word(ptr + 2 * word_index, value)


def op_storeb(zm, *operands):
    ptr, byte_index, value = operands
    zm.write_byte(ptr + byte_index, value)


def op_put_prop(zm, *operands):
    obj_id, prop_id, value = operands
    zm.object_table.set_property_data(obj_id, prop_id, value)


def op_read(zm, *operands):
    zm.do_read(*operands)


def op_print_char(zm, *operands):
    zscii_code = operands[0]
    if zscii_code == 0:
        return
    # HACK: Treat the tab character like a space.
    if zscii_code == 9:
        zscii_code = 32
    if zscii_code < 32 or zscii_code > 126:
        if zscii_code == 10:
            zscii_code = 13
        if zscii_code != 13 and not (155 <= zscii_code <= 251):
            raise ZSCIIException("Invalid ZSCII code '{0}'".format(zscii_code))
    zm.write_to_output_streams(chr(zscii_code))


@signed_operands
def op_print_num(zm, *operands):
    zm.write_to_output_streams(str(operands[0]))


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
    varnum = operands[0]
    value = zm.stack_pop()
    if varnum == 0:
        zm.stack_pop()
        zm.stack_push(value)
    else:
        zm.write_var(varnum, value)


def op_split_window(zm, *operands):
    zm.event_manager.split_window.invoke(zm, EventArgs(lines=operands[0]))


def op_set_window(zm, *operands):
    zm.event_manager.set_window.invoke(zm, EventArgs(window_id=operands[0]))


@signed_operands
def op_erase_window(zm, *operands):
    zm.event_manager.erase_window.invoke(zm, EventArgs(window_id=operands[0]))


def op_set_cursor(zm, *operands):
    y, x = operands
    zm.event_manager.set_cursor.invoke(zm, EventArgs(y=y, x=x))


def op_set_text_style(zm, *operands):
    zm.event_manager.set_text_style.invoke(zm, EventArgs(style=operands[0]))


def op_buffer_mode(zm, *operands):
    zm.event_manager.set_buffer_mode.invoke(zm, EventArgs(mode=operands[0]))


def op_output_stream(zm, *operands):
    stream_id = sign_uint16(operands[0])
    event_args = EventArgs(stream_id=stream_id)
    if stream_id == 3:
        event_args.table_addr = operands[1]
    zm.event_manager.select_output_stream.invoke(zm, event_args)


def op_sound_effect(zm, *operands):
    zm.event_manager.sound_effect.invoke(zm, EventArgs(type=operands[0]))


def op_read_char(zm, *operands):
    zm.do_read_char(*operands[1:])


def op_scan_table(zm, *operands):
    word, addr, length = operands[:3]
    form = 0x82 if len(operands) < 4 else operands[3]
    reader = zm.read_word if form >= 0x80 else zm.read_byte
    field_len = form & 0x7f
    result = 0
    for _ in range(length):
        val = reader(addr)
        if val == word:
            result = addr
            break
        addr += field_len
    zm.do_store(result)
    zm.do_branch(result)


def op_call_vn(zm, *operands):
    if len(operands) == 0 or operands[0] == 0:
        return
    call_addr, args = zm.unpack_addr(operands[0]), operands[1:]
    zm.do_routine(call_addr, args, ROUTINE_TYPE_DISCARD)


def op_set_color(zm, *operands):
    event_args = EventArgs(foreground_color=operands[0], background_color=operands[1])
    zm.event_manager.set_color.invoke(zm, event_args)


def op_call_vn2(zm, *operands):
    op_call_vn(zm, *operands)


def op_tokenize(zm, *operands):
    zm.do_tokenize(*operands)


def op_encode_text(zm, *operands):
    zm.do_encode_text(*operands)


def op_check_arg_count(zm, *operands):
    argument_number = operands[0]
    zm.do_branch(argument_number <= zm.get_arg_count())


def op_copy_table(zm, *operands):
    first, second, size = operands
    size = sign_uint16(size)
    if second == 0:
        for i in range(size):
            zm.write_byte(first + i, 0)
    else:
        if size > 0 and first < second < first + size:
            iterator = range(size - 1, -1, -1)
        else:
            iterator = range(abs(size))
        for i in iterator:
            val = zm.read_byte(first + i)
            zm.write_byte(second + i, val)


def op_print_table(zm, *operands):
    addr, width = operands[0:2]
    height = 1 if len(operands) < 3 else operands[2]
    skip = 0 if len(operands) < 4 else operands[3]
    zm.do_print_table(addr, width, height, skip)


# Extended opcodes

def op_log_shift(zm, *operands):
    number, places = operands
    places = sign_uint16(places)
    if places > 0:
        number = sign_uint16(number) << places
    else:
        number >>= -places
    zm.do_store(number)


@signed_operands
def op_art_shift(zm, *operands):
    number, places = operands
    if places > 0:
        number <<= places
    else:
        number >>= -places
    zm.do_store(number)


def op_set_font(zm, *operands):
    # Curses doesn't have different fonts.
    zm.do_store(0)


def op_save_undo(zm, *operands):
    zm.do_save_undo()


def op_restore_undo(zm, *operands):
    zm.do_restore_undo()
