import os
import opcodes
from typing import Tuple
from abstract_interpreter import AbstractZMachineInterpreter
from memory import MemoryMap
from object_table import ObjectTable
from event import EventArgs, EventManager
from text import TextUtils
from quetzal import Quetzal
from constants import *
from stack import *
from error import *


class ZMachineInterpreter(AbstractZMachineInterpreter):
    def __init__(self, game_file: str, memory_map: MemoryMap, debug: bool = False):
        self.memory_map = memory_map
        self.text_utils = TextUtils(memory_map)
        self.quetzal = Quetzal(memory_map, game_file)
        self.file = game_file
        self._version = memory_map.version
        self.pc = memory_map.initial_pc
        self._object_table = ObjectTable(self.memory_map)
        self.opcodes = opcodes.get_opcodes(self.version)
        self.call_stack = CallStack()
        self.quit = False
        self.debug = debug
        self._event_manager = EventManager()
        # Set interpreter version to 1.1
        self.write_word(0x32, 0x101)
        if self.version <= 3:
            self.status_line_type = (self.read_byte(0x1) & 0x2) >> 1
            self.event_manager.pre_read_input += self.show_status_handler
        self.event_manager.post_read_input += self.post_read_input_handler
        if debug:
            debug_file = 'debug.txt'
            filepath = os.path.dirname(self.file)
            self.debug_file = os.path.join(filepath, debug_file)
            with open(self.debug_file, 'w') as s:
                s.write('')

    @property
    def version(self) -> int:
        return self._version

    @property
    def object_table(self) -> ObjectTable:
        return self._object_table

    @property
    def event_manager(self) -> EventManager:
        return self._event_manager

    def do_run(self):
        try:
            while not self.quit:
                self.run_instruction()
        except Exception as e:
            print(e.__str__())
        finally:
            self.event_manager.quit.invoke(self, EventArgs())

    def do_quit(self):
        self.do_show_status()
        self.quit = True

    def do_verify(self) -> bool:
        checksum = 0
        with open(self.file, "rb") as s:
            s.seek(0x40)
            for _ in range(0x40, self.memory_map.file_len):
                checksum += int.from_bytes(s.read(1), "big")
                checksum &= 0xffff
        return checksum == self.memory_map.checksum

    def show_status_handler(self, sender, e: EventArgs):
        self.do_show_status()

    def do_show_status(self):
        # In later versions, treat as a nop.
        if self.version > 3:
            return
        location, right_status = self.get_status_strings()
        event_args = EventArgs(location=location, right_status=right_status)
        self.event_manager.refresh_status_line.invoke(self, event_args)

    def get_status_strings(self):
        # This should be for version 3 only.
        # In versions 4 and above, the game will handle the status line instructions.
        location_id = self.get_global_var(0)
        global1 = self.get_global_var(1)
        global2 = self.get_global_var(2)
        location = self.get_object_text(location_id)
        # The status line should show score/moves or time, depending on bit 1 of flags1.
        if self.status_line_type == STATUS_TYPE_SCORE:
            score, moves = ZMachineInterpreter.sign_uint16(global1), global2
            right_status = f'Score: {score}'.ljust(16, ' ') + f'Moves: {moves}'.ljust(11, ' ')
        else:
            hours, minutes = global1, global2
            meridian = 'AM' if hours < 12 else 'PM'
            if hours == 0:
                hours = 12
            elif hours > 12:
                hours -= 12
            hh = str(hours).rjust(2, ' ')
            right_status = f'Time: {hh}:{minutes:02} {meridian}'.ljust(17, ' ')
        return location, right_status

    def do_restart(self):
        static_mem_ptr = self.memory_map.static_mem_ptr
        with open(self.file, "rb") as s:
            dynamic_mem = s.read(static_mem_ptr)
            self.memory_map.reset_dynamic_memory(dynamic_mem)
        self.pc = self.memory_map.initial_pc
        self.call_stack.clear()
        self.event_manager.erase_window.invoke(self, EventArgs(window_id=LOWER_WINDOW))

    def do_save(self) -> bool:
        return self.quetzal.do_save(self.pc, self.call_stack)

    def do_restore(self) -> bool:
        def reset_pc(pc: int):
            self.pc = pc
        return self.quetzal.do_restore(self.call_stack, reset_pc)

    def run_instruction(self):
        def large_constant_operand():
            return self.read_from_pc(2)

        def small_constant_operand():
            return self.read_from_pc()

        def variable_operand():
            varnum = self.read_from_pc()
            return self.read_var(varnum)

        instruction_ptr = self.pc
        opcode = self.read_from_pc()
        opcode_number = opcode
        if opcode <= 0x7f:
            # long form, 2OP
            opcode_number = opcode & 0x1f
            if opcode <= 0x1f:
                operands = [small_constant_operand(), small_constant_operand()]
            elif opcode <= 0x3f:
                operands = [small_constant_operand(), variable_operand()]
            elif opcode <= 0x5f:
                operands = [variable_operand(), small_constant_operand()]
            else:
                operands = [variable_operand(), variable_operand()]
        elif opcode <= 0xbf:
            # short form, except 0xbe
            if opcode == 0xbe:
                raise Exception('Extended opcode not supported')
            opcode_number = (opcode & 0xf) | 0x80
            if opcode <= 0x8f:
                operands = [large_constant_operand()]
            elif opcode <= 0x9f:
                operands = [small_constant_operand()]
            elif opcode <= 0xaf:
                operands = [variable_operand()]
            else:
                operands = []
                opcode_number = (opcode & 0xf) | 0xb0
        else:
            # variable form
            operands = []
            if opcode <= 0xdf:
                # 2OP form, opcode number is bottom 5 bits.
                opcode_number = opcode & 0x1f
            if opcode in (0xec, 0xfa):
                # call_vn2 and call_vs2 have extra operands.
                operand_bits = self.read_from_pc(2)
                shift = 14
            else:
                operand_bits = self.read_from_pc()
                shift = 6
            while shift >= 0:
                operand_type = (operand_bits >> shift) & 0x3
                if operand_type == 0:
                    operands += [large_constant_operand()]
                elif operand_type == 1:
                    operands += [small_constant_operand()]
                elif operand_type == 2:
                    operands += [variable_operand()]
                else:
                    break
                shift -= 2
        if self.debug:
            opname = self.opcodes[opcode_number].__name__[3:].upper()
            with open(self.debug_file, 'a') as s:
                s.write('{0:x}: {1}  {2}\n'.format(instruction_ptr, opname, ','.join([str(o) for o in operands])))
        try:
            op = self.opcodes[opcode_number]
            op(self, *operands)
        except KeyError:
            print('{0:x}'.format(instruction_ptr), '{0:x}'.format(opcode), opcode_number)
            raise

    @staticmethod
    def sign_uint14(num):
        # For branch offsets
        if num >= 0x2000:
            num = -(~num & 0x3fff) - 1
        return num

    @staticmethod
    def sign_uint16(num):
        if num >= 0x8000:
            num = -(~num & 0xffff) - 1
        return num

    def read_from_pc(self, num_bytes=1):
        result = 0
        for _ in range(num_bytes):
            result <<= 8
            result |= self.read_byte(self.pc)
            self.pc += 1
        return result

    def write_byte(self, addr, val):
        self.memory_map.write_byte(addr, val)

    def write_word(self, addr, val):
        self.memory_map.write_word(addr, val)

    def unpack_addr(self, packed_addr):
        shift = 1 if self.version <= 3 else 2
        return packed_addr << shift

    def read_byte(self, ptr):
        return self.memory_map.read_byte(ptr)

    def read_word(self, ptr):
        return self.memory_map.read_word(ptr)

    @property
    def eval_stack(self):
        return self.call_stack.eval_stack

    def stack_push(self, val):
        self.eval_stack.push(val)

    def stack_pop(self):
        return self.eval_stack.pop()

    def stack_peek(self):
        return self.eval_stack.peek()

    def get_global_var(self, index):
        if index < 0 or index >= 0xf0:
            raise Exception(f"Invalid global variable index: {index}")
        addr = self.memory_map.global_vars + index * 2
        return self.read_word(addr)

    def set_global_var(self, index, val):
        if index < 0 or index >= 0xf0:
            raise Exception(f"Invalid global variable index: {index}")
        addr = self.memory_map.global_vars + index * 2
        self.write_word(addr, val)

    def read_var(self, varnum):
        if varnum == 0:
            return self.stack_pop()
        elif 0x1 <= varnum <= 0xf:
            # Local vars
            return self.call_stack.get_local_var(varnum - 1)
        elif 0x10 <= varnum <= 0xff:
            # Global vars
            return self.get_global_var(varnum - 0x10)
        else:
            raise VariableOutOfRangeException(varnum)

    def write_var(self, varnum, val):
        val &= 0xffff
        if varnum == 0:
            self.stack_push(val)
        elif 0x1 <= varnum <= 0xf:
            self.call_stack.set_local_var(varnum - 1, val)
        elif 0x10 <= varnum <= 0xff:
            self.set_global_var(varnum - 0x10, val)
        else:
            raise VariableOutOfRangeException(varnum)

    def do_routine(self, call_addr: int, args: Tuple[int], discard_result: bool = False):
        store_varnum = 0
        if not discard_result:
            store_varnum = self.read_from_pc()
        return_pc = self.pc
        self.pc = call_addr
        num_locals = self.read_from_pc()
        if num_locals > 15:
            raise InvalidMemoryException('Invalid call to address {0:x}'.format(call_addr))
        local_vars = [0] * num_locals
        for i in range(num_locals):
            local = self.read_from_pc(2)
            if len(args) > i:
                local = args[i]
            local_vars[i] = local
        self.call_stack.push(
            return_pc=return_pc,
            store_varnum=store_varnum,
            local_vars=local_vars,
            arg_count=len(args),
            discard_result=discard_result
        )

    def do_return(self, retval: int):
        stack_frame = self.call_stack.pop()
        store_varnum = stack_frame.store_varnum
        return_pc = stack_frame.return_pc
        discard_result = stack_frame.discard_result
        self.pc = return_pc
        if not discard_result:
            self.write_var(store_varnum, retval)

    def do_store(self, value: int):
        store = self.read_from_pc()
        self.write_var(store, value)

    def do_branch(self, is_truthy):
        is_true = is_truthy not in (0, False)
        branch = self.read_from_pc()
        jump_cond = branch & 0x80 == 0x80
        offset = branch & 0x3f
        if branch & 0x40 == 0:
            offset = ZMachineInterpreter.sign_uint14(offset << 8 | self.read_from_pc())
        if is_true == jump_cond:
            if offset in (0, 1):
                self.do_return(offset)
            else:
                self.do_jump(offset)

    def do_jump(self, offset: int):
        # If a branch offset is 0 or 1, then the branch should return that value from the current routine.
        # Since the game might make use of an offset of 0 or 1 (ignore the branch or skip over a 1 byte
        # instruction), encoded offsets add 2 to the actual offset value.
        # Branch offsets can never be -1 or -2 with this scheme, but doing this would put the program counter
        # back inside the same instruction and result in bad consequences.
        self.pc += offset - 2

    def get_object_text(self, obj_id: int) -> str:
        zchars = self.object_table.get_object_text_zchars(obj_id)
        return self.text_utils.zscii_decode(zchars)

    def do_read(self, text_buffer, parse_buffer):
        self.event_manager.pre_read_input.invoke(self, EventArgs())
        event_args = EventArgs(text_buffer=text_buffer, parse_buffer=parse_buffer)
        self.event_manager.read_input.invoke(self, event_args)

    def post_read_input_handler(self, sender, event_args: EventArgs):
        command = event_args.command
        text_buffer = event_args.text_buffer
        parse_buffer = event_args.parse_buffer
        max_text_len = self.read_byte(text_buffer) + 1
        if max_text_len < 3:
            raise Exception("Parse error")
        text_ptr = text_buffer + 1
        for c in command[:max_text_len]:
            self.write_byte(text_ptr, ord(c))
            text_ptr += 1
        self.write_byte(text_ptr, 0)
        separators = self.text_utils.separator_chars
        tokens, positions = self.text_utils.tokenize(command, separators)
        max_words = self.read_byte(parse_buffer)
        parse_ptr = parse_buffer + 1
        self.write_byte(parse_ptr, len(tokens))
        parse_ptr += 1
        for token, position in zip(tokens[:max_words], positions[:max_words]):
            dictionary_ptr = self.text_utils.lookup_dictionary(token)
            self.write_word(parse_ptr, dictionary_ptr)
            self.write_byte(parse_ptr + 2, len(token))
            self.write_byte(parse_ptr + 3, position + 1)
            parse_ptr += 4

    def write_to_output_streams(self, text, newline=False):
        event_args = EventArgs(text=text, newline=newline)
        self.event_manager.write_to_streams.invoke(self, event_args)

    def print_from_pc(self, newline=False):
        self.pc = self.print_from_addr(self.pc, newline)

    def print_from_addr(self, addr, newline=False):
        zchars = []
        addr = self.text_utils.read_zchars(addr, zchars)
        text = self.text_utils.zscii_decode(zchars)
        self.write_to_output_streams(text, newline)
        return addr
