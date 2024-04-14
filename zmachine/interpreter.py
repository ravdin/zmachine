import os
import opcodes
from typing import Tuple
from abstract_interpreter import AbstractZMachineInterpreter
from memory import MemoryMap
from object_table import ObjectTable
from event import EventArgs, EventManager
from text import TextUtils
from quetzal import Quetzal
from undo import UndoStack
from stack import *
from error import *
from config import *


class ZMachineInterpreter(AbstractZMachineInterpreter):
    def __init__(self, memory_map: MemoryMap, debug: bool = False):
        self.memory_map = memory_map
        self.text_utils = TextUtils(memory_map)
        self.quetzal = Quetzal(memory_map)
        self._version = CONFIG[VERSION_NUMBER_KEY]
        self.pc = CONFIG[INITIAL_PC_KEY]
        self._object_table = ObjectTable(self.memory_map)
        self.opcodes = opcodes.get_opcodes(self.version)
        self.extended_opcodes = opcodes.get_extended_opcodes(self.version)
        self.call_stack = CallStack()
        self.undo_stack = UndoStack()
        self.quit = False
        self.debug = debug
        self._event_manager = EventManager()
        if self.version <= 3:
            self.status_line_type = (self.read_byte(0x1) & 0x2) >> 1
            self.event_manager.pre_read_input += self.pre_read_input_handler
        if debug:
            debug_file = 'debug.txt'
            filepath = os.path.dirname(CONFIG[GAME_FILE_KEY])
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
        with open(CONFIG[GAME_FILE_KEY], "rb") as s:
            s.seek(0x40)
            for _ in range(0x40, CONFIG[FILE_LENGTH_KEY]):
                checksum += int.from_bytes(s.read(1), "big")
                checksum &= 0xffff
        return checksum == CONFIG[CHECKSUM_KEY]

    def pre_read_input_handler(self, sender, e: EventArgs):
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
        static_mem_ptr = CONFIG[STATIC_MEMORY_BASE_ADDR_KEY]
        with open(CONFIG[GAME_FILE_KEY], "rb") as s:
            dynamic_mem = s.read(static_mem_ptr)
            self.memory_map.reset_dynamic_memory(dynamic_mem)
        self.pc = CONFIG[INITIAL_PC_KEY]
        self.call_stack.clear()
        self.event_manager.erase_window.invoke(self, EventArgs(window_id=LOWER_WINDOW))

    def do_save(self) -> bool:
        return self.quetzal.do_save(self.pc, self.call_stack)

    def do_restore(self) -> bool:
        def reset_pc(pc: int):
            self.pc = pc

        return self.quetzal.do_restore(self.call_stack, reset_pc)

    def do_save_undo(self):
        call_stack_bytes = self.call_stack.serialize()
        if len(call_stack_bytes) == 0:
            self.do_store(0)
            return
        static_memory_base_addr = CONFIG[STATIC_MEMORY_BASE_ADDR_KEY]
        dynamic_memory = self.memory_map[:static_memory_base_addr]
        self.undo_stack.push(dynamic_memory, call_stack_bytes, self.pc)
        self.do_store(1)

    def do_restore_undo(self):
        frame = self.undo_stack.pop()
        if frame is None:
            self.do_store(0)
            return
        dynamic_mem = frame.dynamic_memory
        call_stack_bytes = frame.call_stack_bytes
        pc = frame.pc
        self.memory_map.reset_dynamic_memory(dynamic_mem)
        self.call_stack.deserialize(call_stack_bytes)
        self.pc = pc
        self.do_store(2)

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
        opcode_dict = self.opcodes
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
        elif opcode <= 0xbf and opcode != 0xbe:
            # short form, except 0xbe
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
            if opcode == 0xbe:
                # Extended opcode, opcode number is in next byte.
                opcode_number = self.read_from_pc()
                opcode_dict = self.extended_opcodes
            elif opcode <= 0xdf:
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
        try:
            if self.debug:
                opname = opcode_dict[opcode_number].__name__[3:].upper()
                with open(self.debug_file, 'a') as s:
                    s.write('{0:x}: {1}  {2}\n'.format(instruction_ptr, opname, ','.join([str(o) for o in operands])))
            op = opcode_dict[opcode_number]
            op(self, *operands)
        except KeyError:
            raise UnrecognizedOpcodeException(opcode_number, instruction_ptr)

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
        addr = CONFIG[GLOBAL_VARS_TABLE_KEY] + index * 2
        return self.read_word(addr)

    def set_global_var(self, index, val):
        if index < 0 or index >= 0xf0:
            raise Exception(f"Invalid global variable index: {index}")
        addr = CONFIG[GLOBAL_VARS_TABLE_KEY] + index * 2
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

    def do_routine(self, call_addr: int, args: Tuple[int], routine_type: int = ROUTINE_TYPE_STORE):
        store_varnum = 0
        if routine_type == ROUTINE_TYPE_STORE:
            store_varnum = self.read_from_pc()
        return_pc = self.pc
        self.pc = call_addr
        num_locals = self.read_from_pc()
        if num_locals > 15:
            raise InvalidMemoryException('Invalid call to address {0:x}'.format(call_addr))
        local_vars = [0] * num_locals
        for i in range(num_locals):
            local = 0
            if self.version <= 4:
                local = self.read_from_pc(2)
            if len(args) > i:
                local = args[i]
            local_vars[i] = local
        self.call_stack.push(
            return_pc=return_pc,
            store_varnum=store_varnum,
            local_vars=local_vars,
            arg_count=len(args),
            routine_type=routine_type
        )

    def do_return(self, retval: int):
        stack_frame = self.call_stack.pop()
        store_varnum = stack_frame.store_varnum
        return_pc = stack_frame.return_pc
        routine_type = stack_frame.routine_type
        self.pc = return_pc
        if routine_type == ROUTINE_TYPE_STORE:
            self.write_var(store_varnum, retval)
        elif routine_type == ROUTINE_TYPE_DIRECT_CALL:
            self.stack_push(retval)

    def do_direct_call(self, call_addr: int) -> int:
        """
        Make a direct call to a routine.
        """
        if call_addr == 0:
            return 0
        frame_id = self.call_stack.catch()
        self.do_routine(call_addr, tuple[int](), ROUTINE_TYPE_DIRECT_CALL)
        while self.call_stack.catch() > frame_id:
            self.run_instruction()
        if self.call_stack.catch() != frame_id:
            return 1
        return self.stack_pop()

    def get_arg_count(self) -> int:
        return self.call_stack.current_frame.arg_count

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

    def do_read(self, text_buffer_addr: int, parse_buffer_addr: int, time: int = 0, routine: int = 0):
        timeout_ms = time * 100
        call_addr = self.unpack_addr(routine)
        event_args = EventArgs()
        self.event_manager.pre_read_input.invoke(self, event_args)
        text_buffer_size = self.read_byte(text_buffer_addr)
        if self.version <= 4:
            text_buffer_size += 1
        if text_buffer_size < 3:
            raise Exception("Fatal error: text buffer length less than 3")
        text_buffer = [0] * max(text_buffer_size, INPUT_BUFFER_LENGTH)
        if self.version >= 5:
            initial_size = self.read_byte(text_buffer_addr + 1)
            for i in range(initial_size):
                buffer_char = self.read_byte(text_buffer_addr + i + 2)
                if buffer_char == 0:
                    break
                text_buffer[i] = buffer_char
        event_args.text_buffer = text_buffer
        event_args.timeout_ms = timeout_ms
        event_args.interrupt_routine_caller = self.do_direct_call
        event_args.interrupt_routine_addr = call_addr
        text_addr_offset = 1 if self.version <= 4 else 2
        current_pc = self.pc
        self.event_manager.read_input.invoke(self, event_args)
        # For version 4 or lower, write the characters from the input buffer (without the
        # terminating character) from byte 1 onwards in the text buffer, followed by a 0 byte.
        # For version 5+, write the number of typed characters in byte 1, followed by the character
        # bytes. Store the terminating character.
        input_len = text_buffer.index(0)
        input_chars = text_buffer[:input_len]
        terminating_char = 0 if input_len == 0 else input_chars[-1]
        for i in range(input_len - 1):
            self.write_byte(text_buffer_addr + text_addr_offset + i, input_chars[i])
        if self.version <= 4:
            self.write_byte(text_buffer_addr + input_len, 0)
        else:
            self.write_byte(text_buffer_addr + 1, input_len - 1)
            # A terminating char of 0 means the read timed out.
            # It's possible that a direct call has reset the PC and call stack through a
            # restart or a restore.
            # Only do the store operation if the PC hasn't moved.
            if terminating_char != 0 or self.pc == current_pc:
                self.do_store(terminating_char)
        command = bytearray(text_buffer[:input_len - 1]).decode()
        event_args = EventArgs(command=command, terminating_char=terminating_char)
        self.event_manager.post_read_input.invoke(self, event_args)
        if terminating_char == 13:
            self.parse_command(command, parse_buffer_addr)

    def do_read_char(self, time: int = 0, routine: int = 0):
        self.event_manager.pre_read_input.invoke(self, EventArgs())
        text_buffer = [0]
        event_args = EventArgs(
            timeout_ms=time * 100,
            interrupt_routine_caller=self.do_direct_call,
            interrupt_routine_addr=self.unpack_addr(routine),
            text_buffer=text_buffer,
            echo=False
        )
        self.event_manager.read_input.invoke(self, event_args)
        self.do_store(text_buffer[0])

    def do_tokenize(self, text_addr: int, parse_buffer: int, dictionary_addr: int = 0, flag: int = 0):
        text_length = self.read_byte(text_addr + 1)
        text_buffer = [0] * text_length
        for i in range(text_length):
            text_buffer[i] = self.read_byte(text_addr + i + 2)
        text = str(bytes(text_buffer), encoding='utf-8')
        self.parse_command(text, parse_buffer, dictionary_addr, flag)

    def parse_command(self, command: str, parse_buffer: int, dictionary_addr: int = 0, flag: int = 0):
        if parse_buffer == 0:
            if self.version < 5:
                raise Exception("Invalid parse buffer address")
            return
        separators = self.text_utils.separator_chars
        tokens, positions = self.text_utils.tokenize(command, separators)
        text_buffer_offset = 1 if self.version <= 4 else 2
        max_words = self.read_byte(parse_buffer)
        if max_words < 1:
            raise Exception("Fatal error: parser buffer length less than 6 bytes")
        self.write_byte(parse_buffer + 1, len(tokens))
        parse_ptr = parse_buffer + 2
        for token, position in zip(tokens[:max_words], positions[:max_words]):
            dictionary_ptr = self.text_utils.lookup_dictionary(token, dictionary_addr)
            # If the flag has been set (by the tokenize op), ignore unknown tokens.
            if dictionary_ptr != 0 or flag == 0:
                self.write_word(parse_ptr, dictionary_ptr)
                self.write_byte(parse_ptr + 2, len(token))
                self.write_byte(parse_ptr + 3, position + text_buffer_offset)
            parse_ptr += 4

    def do_encode_text(self, text_addr: int, length: int, start: int, coded_buffer: int):
        text = ['\0'] * length
        for i in range(length):
            text[i] = chr(self.read_byte(text_addr + start + i))
        # This is a version 5+ op, so encoded zscii strings will be 6 bytes.
        byte_len = 6
        encoded = self.text_utils.zscii_encode(text, byte_len)
        for i in range(byte_len):
            self.write_byte(coded_buffer + i, encoded[i])

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

    def do_print_table(self, addr, width, height, skip):
        table = [[0] * width for _ in range(height)]
        for i in range(height):
            for j in range(width):
                table[i][j] = self.read_byte(addr)
                addr += 1
            addr += skip
        self.event_manager.print_table.invoke(self, EventArgs(table=table))
