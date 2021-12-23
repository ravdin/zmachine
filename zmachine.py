import os
import sys
import opcodes
from utils import *
from error import *

class zmachine():
    def __init__(self, file, debug = False):
        with open(file, "rb") as s:
            memory_map = s.read()
        self.file = file
        self.memory_map = bytearray(memory_map)
        self.stack = [0] * 1024
        self.num_locals = 0
        self.local_vars = [0] * 15
        self.quit = False
        self.debug = debug
        self.save_file = ''
        self.print_handler = self.default_print_handler
        self.input_handler = self.default_input_handler
        self.show_status_handler = self.default_show_status_handler
        self.do_initialize()
        self.setup_abbreviations()

    def do_run(self):
        while not self.quit:
            self.run_instruction()

    def do_initialize(self):
        self.version = self.read_byte(0)
        if self.version != 3:
            if self.version <= 6:
                do_print(f"Unsupported version V{self.version}")
            else:
                do_print("Unrecognized z-machine file")
            self.quit = True
            return
        self.flags1 = self.read_byte(0x1)
        self.release_number = self.memory_map[0x2:0x4]
        self.pc = self.byte_addr(0x6)
        self.dictionary_header = self.byte_addr(0x8)
        self.flags2 = self.read_byte(0x10)
        self.object_header = self.byte_addr(0xa)
        self.global_vars = self.byte_addr(0xc)
        self.static_mem_ptr = self.byte_addr(0xe)
        self.serial_number = self.memory_map[0x12:0x18]
        self.abbreviation_table = self.byte_addr(0x18)
        self.filelen = self.read_word(0x1a) * 2 #TODO: depends on the version
        self.checksum = self.read_word(0x1c)
        self.sp = 0
        self.frame_ptr = 0
        if self.save_file == '':
            filename = os.path.basename(self.file)
            self.save_file = '{0}.sav'.format(os.path.splitext(filename)[0])

    def do_verify(self):
        checksum = 0
        with open(self.file, "rb") as s:
            s.seek(0x40)
            for _ in range(0x40, self.filelen):
                checksum += int.from_bytes(s.read(1), "big")
                checksum &= 0xffff
        return checksum == self.checksum

    def do_show_status(self):
        self.show_status_handler()

    def do_save(self):
        filepath = os.path.dirname(self.file)
        save_file = self.prompt_save_file()
        save_full_path = os.path.join(filepath, save_file)
        if os.path.exists(save_full_path):
            self.do_print('Overwrite existing file? (Y is affirmative) ')
            if self.input_handler() != 'y':
                return False
        header_data = self.release_number
        header_data += self.serial_number
        header_data += self.checksum
        header_data += self.pc.to_bytes(3, "big")
        header_chunk = zmachine.iff_chunk('IFhd', header_data)
        dynamic_memory = self.compress_dynamic_memory()
        mem_chunk = zmachine.iff_chunk('CMem', dynamic_memory)
        # Non standard way to save the stack state.
        stack_data = self.frame_ptr.to_bytes(2, "big")
        stack_data += self.num_locals.to_bytes(1, "big")
        for i in range(self.num_locals):
            stack_data += self.local_vars[i].to_bytes(2, "big")
        for stack_item in self.stack[:self.sp]:
            stack_data += stack_item.to_bytes(2, "big")
        stack_chunk = zmachine.iff_chunk('Stck', stack_data)
        try:
            with open(save_full_path, 'wb') as s:
                header_chunk.write(s)
                mem_chunk.write(s)
                stack_chunk.write(s)
            self.save_file = save_file
            return True
        except Exception:
            return False

    def do_restore(self):
        filepath = os.path.dirname(self.file)
        save_file = self.prompt_save_file()
        save_full_path = os.path.join(filepath, save_file)
        if not os.path.exists(save_full_path):
            return False
        transcript_bit = self.flags2 & 0x1
        fixed_pitch_bit = self.flags2 & 0x2

        release_number = 0
        serial_number = 0
        checksum = 0
        pc = 0
        encoded_memory = 0
        frame_ptr = 0
        num_locals = 0
        stack_data = 0
        local_vars = []
        try:
            with open(save_full_path, 'rb') as s:
                header_chunk = zmachine.iff_chunk.read(s)
                mem_chunk = zmachine.iff_chunk.read(s)
                stack_chunk = zmachine.iff_chunk.read(s)
                release_number = header_chunk.data[0:2]
                serial_number = header_chunk.data[2:8]
                checksum = int.from_bytes(header_chunk.data[8:10], "big")
                pc = int.from_bytes(header_chunk.data[10:13], "big")
                encoded_memory = mem_chunk.data
                frame_ptr = int.from_bytes(stack_chunk.data[0:2], "big")
                num_locals = int.from_bytes(stack_chunk.data[2:3], "big")
                local_vars = stack_chunk.data[3:3+2*num_locals]
                stack_data = stack_chunk.data[3+2*num_locals:]
        except Exception as err:
            #print(f'{err}')
            return False
        if release_number != self.release_number or \
           serial_number != self.serial_number or \
           checksum != self.checksum:
            do_print("Invalid save file!", True)
            return False
        dynamic_mem = []
        with open(self.file, 'rb') as s:
            dynamic_mem = bytearray(s.read(self.static_mem_ptr))
        mem_ptr = 0
        byte_ptr = 0
        while byte_ptr < len(encoded_memory):
            val = encoded_memory[byte_ptr]
            if val == 0:
                mem_ptr += int.from_bytes(encoded_memory[byte_ptr + 1:byte_ptr + 3], "big")
                byte_ptr += 3
            else:
                dynamic_mem[mem_ptr] ^= val
                mem_ptr += 1
                byte_ptr += 1
        self.memory_map[:self.static_mem_ptr] = dynamic_mem
        self.pc = pc
        self.frame_ptr = frame_ptr
        self.num_locals = num_locals
        for i in range(0, num_locals, 2):
            self.local_vars[i // 2] = int.from_bytes(local_vars[i:i+2], "big")
        sp = 0
        for w in range(0, len(stack_data), 2):
            self.stack[sp] = int.from_bytes(stack_data[w:w+2], "big")
            sp += 1
        self.sp = sp

        flags2_ptr = 0x10
        flags2 = self.read_byte(flags2_ptr) & 0xfc
        flags2 |= fixed_pitch_bit | transcript_bit
        self.write_byte(flags2_ptr, flags2)
        return True

    def prompt_save_file(self):
        self.do_print('Enter a file name.', True)
        self.do_print(f'Default is "{self.save_file}": ')
        save_file = self.input_handler(lowercase = False).strip()
        if save_file == '':
            save_file = self.save_file
        return save_file

    def compress_dynamic_memory(self):
        result = [0] * self.static_mem_ptr
        result_ptr = 0
        with open(self.file, "rb") as s:
            dynamic_mem = bytearray(s.read(self.static_mem_ptr))
        zero_count = 0
        for ptr in range(static_mem_ptr):
            story = self.read_byte(ptr)
            original = dynamic_mem[ptr]
            val = story ^ original
            if val == 0:
                zero_count += 1
            else:
                if zero_count != 0:
                    result[result_ptr] = 0
                    result[result_ptr + 1:result_ptr + 3] = zero_count.to_bytes(2, "big")
                    result_ptr += 3
                    zero_count = 0
                result[result_ptr] = val
                result_ptr += 1
        return bytearray(result[:result_ptr])

    def separator_chars(self):
        ptr = self.dictionary_header
        num_separators = self.read_byte(ptr)
        return [chr(self.read_byte(ptr + i + 1)) for i in range(num_separators)]

    def setup_abbreviations(self):
        self.abbreviations = [0] * 96
        ptr = self.abbreviation_table
        for i in range(len(self.abbreviations)):
            abbrev_ptr = self.word_addr(ptr)
            encoded = self.read_encoded_zscii(abbrev_ptr)
            self.abbreviations[i] = zscii_decode(encoded)
            ptr += 2

    def lookup_dictionary(self, text):
        encoded = zscii_encode(text)
        ptr = self.dictionary_header
        num_separators = self.read_byte(ptr)
        entry_length = self.read_byte(ptr + num_separators + 1)
        num_entries = self.read_word(ptr + num_separators + 2)
        ptr += num_separators + 4
        lo = 0
        hi = num_entries - 1
        while lo < hi:
            mid = (lo + hi) // 2
            mid_ptr = ptr + mid * entry_length
            entry = self.read_dword(mid_ptr)
            if entry == encoded:
                return mid_ptr
            elif entry < encoded:
                lo = mid + 1
            else:
                hi = mid - 1
        lo_ptr = ptr + lo * entry_length
        return lo_ptr if self.read_dword(lo_ptr) == encoded else 0

    def run_instruction(self):
        instruction_ptr = self.pc
        opcode = self.read_from_pc()
        opcode_number = opcode
        if opcode <= 0x7f:
            # long form, 2OP
            opcode_number = opcode & 0x1f
            operands = [
                self.read_operand(1 if opcode >> 6 & 0x1 == 0 else 2)[0],
                self.read_operand(1 if opcode >> 5 & 0x1 == 0 else 2)[0]
            ]
        elif opcode <= 0xbf:
            # short form, except 0xbe
            if opcode == 0xbe:
                raise Exception('Extended opcode not supported')
            operand, exists = self.read_operand(opcode >> 4 & 0x3)
            opcode_number = opcode & 0xf | (0x80 if exists else 0xb0)
            operands = [operand] if exists else []
        else:
            # variable form
            b = self.read_from_pc()
            # TODO: double variable (4.4.3.1)
            if opcode < 0xe0:
                # 2OP form, opcode number is bottom 5 bits.
                opcode_number = opcode & 0x1f
            optypes = [b >> i & 0x3 for i in range(6, -1, -2)]
            operands = []
            for optype in optypes:
                operand, exists = self.read_operand(optype)
                if not exists:
                    break
                operands += [operand]
        try:
            op = self.opcodes[opcode_number]
            op(self, *operands)
        except KeyError:
            print('{0:x}'.format(instruction_ptr), '{0:x}'.format(opcode), opcode_number)
            raise

    def read_operand(self, optype):
        if optype == 0:
            return self.read_from_pc(2), True
        elif optype == 1:
            return self.read_from_pc(), True
        elif optype == 2:
            varnum = self.read_from_pc()
            return self.read_var(varnum), True
        else:
            return None, False

    @staticmethod
    def sign_uint14(num):
        # For branch offsets
        if num >= 0x2000:
            num = -(~num & 0x3fff) - 1
        return num

    def read_from_pc(self, num_bytes = 1):
        result = 0
        for _ in range(num_bytes):
            result <<= 8
            result |= self.read_byte(self.pc)
            self.pc += 1
        return result

    def write_byte(self, addr, val):
        if addr >= self.static_mem_ptr:
            raise IllegalWriteException()
        self.memory_map[addr] = val & 0xff

    def write_word(self, addr, val):
        if addr >= self.static_mem_ptr:
            raise IllegalWriteException()
        self.memory_map[addr] = val >> 8 & 0xff
        self.memory_map[addr+1] = val & 0xff

    def write_dword(self, addr, val):
        if addr >= self.static_mem_ptr:
            raise IllegalWriteException()
        self.memory_map[addr] = val >> 24 & 0xff
        self.memory_map[addr+1] = val >> 16 & 0xff
        self.memory_map[addr+2] = val >> 8 & 0xff
        self.memory_map[addr+3] = val & 0xff

    def byte_addr(self, ptr):
        return self.read_word(ptr)

    def word_addr(self, ptr):
        return self.read_word(ptr) << 1

    def packed_addr(self, ptr):
        return self.read_word(ptr) << 1

    def read_byte(self, ptr):
        return self.memory_map[ptr]

    def read_word(self, ptr):
        return self.memory_map[ptr] << 8 | self.memory_map[ptr + 1]

    def read_dword(self, ptr):
        result = 0
        for i in range(4):
            result <<= 8
            result |= self.memory_map[ptr + i]
        return result

    def read_encoded_zscii(self, ptr):
        result = []
        word = 0
        while word & 0x8000 != 0x8000:
            word = self.read_word(ptr)
            result += [word]
            ptr += 2
        return result

    def stack_push(self, val):
        if self.sp >= len(self.stack):
            raise Exception('Stack overflow')
        self.stack[self.sp] = val
        self.sp += 1

    def stack_pop(self):
        if self.sp <= 0:
            raise Exception('Stack underflow')
        self.sp -= 1
        return self.stack[self.sp]

    def read_var(self, varnum):
        if varnum == 0:
            return self.stack_pop()
        elif varnum >= 0x1 and varnum <= 0xf:
            # Local vars
            if varnum > self.num_locals:
                raise Exception('Invalid index for local variable')
            return self.local_vars[varnum - 1]
        else:
            # Global vars
            addr = self.global_vars + ((varnum - 0x10) * 2)
            return self.read_word(addr)

    def write_var(self, varnum, val):
        if varnum == 0:
            self.stack_push(val)
        elif varnum >= 0x1 and varnum <= 0xf:
            if varnum > self.num_locals:
                raise Exception('Invalid index for local variable')
            self.local_vars[varnum - 1] = val
        else:
            addr = self.global_vars + ((varnum - 0x10) * 2)
            self.write_word(addr, val)

    def lookup_object(self, obj_id):
        if obj_id == 0:
            return None
        return self.object_header + 31 * 2 + 9 * (obj_id - 1)

    def orphan_object(self, obj_id):
        parent_offset, sibling_offset, child_offset = 4, 5, 6
        obj_ptr = self.lookup_object(obj_id)
        parent_id = self.read_byte(obj_ptr + parent_offset)
        if parent_id == 0:
            return
        parent_ptr = self.lookup_object(parent_id)
        obj_next_sibling_id = self.read_byte(obj_ptr + sibling_offset)
        child_id = self.read_byte(parent_ptr + child_offset)
        if child_id == obj_id:
            self.write_byte(parent_ptr + child_offset, obj_next_sibling_id)
        else:
            while child_id != obj_id:
                child_ptr = self.lookup_object(child_id)
                child_id = self.read_byte(child_ptr + sibling_offset)
            self.write_byte(child_ptr + sibling_offset, obj_next_sibling_id)
        self.write_byte(obj_ptr + parent_offset, 0)
        self.write_byte(obj_ptr + sibling_offset, 0)

    def lookup_property(self, obj_id, prop_id):
        obj_ptr = self.lookup_object(obj_id)
        prop_ptr = self.byte_addr(obj_ptr + 7)
        text_len = self.read_byte(prop_ptr)
        prop_ptr += 2 * text_len + 1
        num = 0xff
        while True:
            size_byte = self.read_byte(prop_ptr)
            if size_byte == 0:
                break
            num = size_byte & 0x1f
            if num <= prop_id:
                break
            size = (size_byte >> 5) + 1
            prop_ptr += size + 1
        return prop_ptr if num == prop_id else None

    def do_routine(self, call_addr, args):
        store = self.read_from_pc()
        self.stack_push(self.pc)
        self.stack_push(store)
        for i in range(self.num_locals):
            self.stack_push(self.local_vars[self.num_locals - i - 1])
        self.stack_push(self.num_locals)
        self.stack_push(self.frame_ptr)
        self.frame_ptr = self.sp
        self.pc = call_addr
        self.num_locals = self.read_from_pc()
        for i in range(self.num_locals):
            local = self.read_from_pc(2)
            if len(args) > i:
                local = args[i]
            self.local_vars[i] = local

    def do_return(self, retval):
        self.sp = self.frame_ptr
        self.frame_ptr = self.stack_pop()
        self.num_locals = self.stack_pop()
        for i in range(self.num_locals):
            self.local_vars[i] = self.stack_pop()
        store = self.stack_pop()
        self.pc = self.stack_pop()
        self.write_var(store, retval)

    def do_store(self, retval):
        store = self.read_from_pc()
        self.write_var(store, retval)

    def do_branch(self, is_truthy):
        is_true = is_truthy not in (0, False)
        branch = self.read_from_pc()
        jump_cond = branch & 0x80 == 0x80
        offset = branch & 0x3f
        if branch & 0x40 == 0:
            offset = zmachine.sign_uint14(offset << 8 | self.read_from_pc())
        if is_true == jump_cond:
            if offset in (0, 1):
                self.do_return(offset)
            else:
                self.pc += offset - 2

    def default_print_handler(self, text, newline = False):
        print(text, end = '\n' if newline else '')

    def default_input_handler(self):
        return input().lower()

    def default_show_status_handler(self):
        pass

    def set_print_handler(self, handler):
        self.print_handler = handler

    def set_input_handler(self, handler):
        self.input_handler = handler

    def set_show_status_handler(self, handler):
        self.show_status_handler = handler

    def get_location(self):
        obj_id = self.read_var(0x10)
        obj_ptr = self.lookup_object(obj_id)
        prop_ptr = self.byte_addr(obj_ptr + 7)
        encoded = self.read_encoded_zscii(prop_ptr + 1)
        return zscii_decode(encoded, self.abbreviations)

    def get_right_status(self):
        global1 = self.read_var(0x11)
        global2 = self.read_var(0x12)
        if self.flags1 & 0x2 == 0:
            return f'Score: {global1}'.ljust(15, ' ') + f'Moves: {global2}'
        else:
            hh = str(global1 % 12).rjust(2, ' ')
            mm = global2
            meridian = 'AM' if global1 < 12 else 'PM'
            return f'Time: {hh}:{mm:02} {meridian}'

    def do_read(self):
        return self.input_handler()

    def do_print(self, text, newline = False):
        self.print_handler(text, newline)

    def do_print_encoded(self, ptr, newline = False):
        encoded = self.read_encoded_zscii(ptr)
        text = zscii_decode(encoded, self.abbreviations)
        self.do_print(text, newline)

    opcodes = \
    {
        1:   opcodes.op_je,
        2:   opcodes.op_jl,
        3:   opcodes.op_jg,
        4:   opcodes.op_dec_chk,
        5:   opcodes.op_inc_chk,
        6:   opcodes.op_jin,
        7:   opcodes.op_test,
        8:   opcodes.op_or,
        9:   opcodes.op_and,
        10:  opcodes.op_test_attr,
        11:  opcodes.op_set_attr,
        12:  opcodes.op_clear_attr,
        13:  opcodes.op_store,
        14:  opcodes.op_insert_obj,
        15:  opcodes.op_loadw,
        16:  opcodes.op_loadb,
        17:  opcodes.op_get_prop,
        18:  opcodes.op_get_prop_addr,
        19:  opcodes.op_get_next_prop,
        20:  opcodes.op_add,
        21:  opcodes.op_sub,
        22:  opcodes.op_mul,
        23:  opcodes.op_div,
        24:  opcodes.op_mod,
        128: opcodes.op_jz,
        129: opcodes.op_get_sibling,
        130: opcodes.op_get_child,
        131: opcodes.op_get_parent,
        132: opcodes.op_get_prop_len,
        133: opcodes.op_inc,
        134: opcodes.op_dec,
        135: opcodes.op_print_addr,
        137: opcodes.op_remove_obj,
        138: opcodes.op_print_obj,
        139: opcodes.op_ret,
        140: opcodes.op_jump,
        141: opcodes.op_print_paddr,
        142: opcodes.op_load,
        176: opcodes.op_rtrue,
        177: opcodes.op_rfalse,
        178: opcodes.op_print,
        179: opcodes.op_print_ret,
        180: opcodes.op_nop,
        181: opcodes.op_save,
        182: opcodes.op_restore,
        183: opcodes.op_restart,
        184: opcodes.op_ret_popped,
        185: opcodes.op_pop,
        186: opcodes.op_quit,
        187: opcodes.op_new_line,
        188: opcodes.op_show_status,
        189: opcodes.op_verify,
        224: opcodes.op_call,
        225: opcodes.op_storew,
        226: opcodes.op_storeb,
        227: opcodes.op_put_prop,
        228: opcodes.op_read,
        229: opcodes.op_print_char,
        230: opcodes.op_print_num,
        231: opcodes.op_random,
        232: opcodes.op_push,
        233: opcodes.op_pull
    }

    class iff_chunk():
        def __init__(self, header, data):
            self.header = header[:4]
            self.data = data

        @classmethod
        def read(cls, stream):
            header = ''.join([chr(b) for b in stream.read(4)])
            count = int.from_bytes(stream.read(4), "big")
            data = stream.read(count)
            # Pad byte
            if count & 1 == 1:
                stream.read(1)
            return cls(header, data)

        def write(self, stream):
            header_bytes = bytearray([ord(c) for c in self.header])
            bytes_written = stream.write(header_bytes)
            if bytes_written < 4:
                stream.write(b'\x00' * (4 - bytes_written))
            stream.write(len(self.data).to_bytes(4, "big"))
            stream.write(self.data)
            if len(self.data) & 1 == 1:
                stream.write(b'\x00')
