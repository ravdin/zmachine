import os
import sys
import opcodes
from utils import *
from error import *

SUPPORTED_VERSIONS = (3, 4)
STACK_LENGTH = 1024

class zmachine():
    def __init__(self, file, debug = False):
        with open(file, "rb") as s:
            memory_map = s.read()
        self.file = file
        self.memory_map = bytearray(memory_map)
        self.stack_frame = zmachine.stack_frame()
        self.stack = self.stack_frame.eval_stack
        self.local_vars = self.stack_frame.local_vars
        self.quit = False
        self.debug = debug
        self.save_file = ''
        self.output_streams = 0x1
        self.memory_stream = zmachine.memory_stream(self)
        self.print_handler = self.default_print_handler
        self.input_handler = self.default_input_handler
        self.show_status_handler = self.default_show_status_handler
        self.erase_window_handler = self.default_erase_window_hander
        self.split_window_handler = self.default_split_window_handler
        self.set_window_handler = self.default_set_window_handler
        self.set_buffer_mode_handler = self.default_set_buffer_mode_handler
        self.set_cursor_handler = self.default_set_cursor_handler
        self.set_text_style_handler = self.default_set_text_style_handler
        self.read_char_handler = self.default_read_char_handler
        if debug:
            debug_file = 'debug.txt'
            filepath = os.path.dirname(self.file)
            self.debug_file = os.path.join(filepath, debug_file)
            with open(self.debug_file, 'w') as s:
                s.write('')
        self.do_initialize()

    def do_run(self):
        while not self.quit:
            self.run_instruction()

    def do_initialize(self):
        self.version = self.read_byte(0)
        if self.version not in SUPPORTED_VERSIONS:
            if self.version <= 6:
                self.do_print(f"Unsupported zmachine version: v{self.version}", True)
            else:
                self.do_print("Unrecognized z-machine file", True)
            self.quit = True
            return
        self.PROPERTY_DEFAULTS_LENGTH = 31 if self.version <= 3 else 63
        self.OBJECT_BYTES = 9 if self.version <= 3 else 14
        self.MAX_OBJECTS = 0xff if self.version <= 3 else 0xffff
        self.ATTRIBUTE_FLAGS = 32 if self.version <= 3 else 48
        self.opcodes = opcodes.get_opcodes(self.version)
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
        self.filelen = self.read_word(0x1a) << (1 if self.version <= 3 else 2)
        self.checksum = self.read_word(0x1c)
        self.sp = 0
        self.frame_ptr = 0
        if self.save_file == '':
            filename = os.path.basename(self.file)
            self.save_file = '{0}.sav'.format(os.path.splitext(filename)[0])

    def set_height(self, height):
        self.write_byte(0x20, height)

    def set_width(self, width):
        self.write_byte(0x21, width)

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

    def do_restart(self):
        transcript_bit = self.flags2 & 0x1
        fixed_pitch_bit = self.flags2 & 0x2
        with open(self.file, "rb") as s:
            dynamic_mem = s.read(self.static_mem_ptr)
            self.memory_map[:self.static_mem_ptr] = dynamic_mem
        self.do_initialize()
        flags2 = self.flags2 & 0xfc
        flags2 |= fixed_pitch_bit | transcript_bit
        self.write_byte(0x10, flags2)

    def do_save(self):
        filepath = os.path.dirname(self.file)
        save_file = self.prompt_save_file()
        save_full_path = os.path.join(filepath, save_file)
        if os.path.exists(save_full_path):
            self.do_print('Overwrite existing file? (Y is affirmative) ')
            if self.input_handler() != 'y':
                return False
        header_data = self.release_number[:]
        header_data += self.serial_number
        header_data += self.checksum.to_bytes(2, "big")
        header_data += self.pc.to_bytes(3, "big")
        header_chunk = zmachine.iff_chunk('IFhd', header_data)
        dynamic_memory = self.compress_dynamic_memory()
        mem_chunk = zmachine.iff_chunk('CMem', dynamic_memory)
        stack_data = self.stack_frame.write()
        stack_chunk = zmachine.iff_chunk('Stks', stack_data)
        try:
            with open(save_full_path, 'wb') as s:
                header_chunk.write(s)
                mem_chunk.write(s)
                stack_chunk.write(s)
            self.save_file = save_file
            return True
        except Exception:
            raise
            return False

    def do_restore(self):
        filepath = os.path.dirname(self.file)
        save_file = self.prompt_save_file()
        save_full_path = os.path.join(filepath, save_file)
        if not os.path.exists(save_full_path):
            return False
        transcript_bit = self.flags2 & 0x1
        fixed_pitch_bit = self.flags2 & 0x2

        chunks = {}
        with open(save_full_path, 'rb') as s:
            while True:
                chunk = zmachine.iff_chunk.read(s)
                if len(chunk.header) == 0:
                    break
                chunks[chunk.header] = chunk
        try:
            header_chunk = chunks['IFhd']
            mem_chunk = chunks['CMem']
            stack_chunk = chunks['Stks']
            release_number = header_chunk.data[0:2]
            serial_number = header_chunk.data[2:8]
            checksum = int.from_bytes(header_chunk.data[8:10], "big")
            pc = int.from_bytes(header_chunk.data[10:13], "big")
            encoded_memory = mem_chunk.data
        except Exception as err:
            #print(f'{err}')
            return False
        if release_number != self.release_number or \
           serial_number != self.serial_number or \
           checksum != self.checksum:
            self.do_print("Invalid save file!", True)
            return False
        dynamic_mem = self.uncompress_dynamic_memory(encoded_memory)
        self.memory_map[:self.static_mem_ptr] = dynamic_mem
        self.stack_frame.read(stack_chunk.data)
        self.pc = pc

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

    # There's no need to compress the dynamic memory for the save file
    # as modern computers have plenty of storage space.
    # This method (from Bryan Scattergood) is more interesting and elegant.
    # The main idea is to exclusive-or each byte of the dynamic memory with
    # the byte in the original game file. If the result is zero (not changed),
    # write a zero byte followed by the number of zero bytes (i.e. the number)
    # of bytes we can skip when restoring the dynamic memory).
    # Otherwise, write the result of the exclusive or.
    def compress_dynamic_memory(self):
        result = [0] * self.static_mem_ptr
        result_ptr = 0
        with open(self.file, "rb") as s:
            dynamic_mem = bytearray(s.read(self.static_mem_ptr))
        zero_count = 0
        for ptr in range(self.static_mem_ptr):
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

    def uncompress_dynamic_memory(self, encoded_memory):
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
        return dynamic_mem

    def separator_chars(self):
        ptr = self.dictionary_header
        num_separators = self.read_byte(ptr)
        return [chr(self.read_byte(ptr + i + 1)) for i in range(num_separators)]

    def lookup_dictionary(self, text):
        # Of course, we could load the dictionary into a hashtable for fastest lookup.
        # The dictionary is already loaded into memory though and a binary search is more fun!
        def read_entry(ptr):
            result = self.read_dword(ptr)
            if self.version >= 4:
                result <<= 16
                result |= self.read_word(ptr + 4)
            return result
        encoded_len = 4 if self.version <= 3 else 6
        encoded = zscii_encode(text, encoded_len)
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
            entry = read_entry(mid_ptr)
            if entry == encoded:
                return mid_ptr
            elif entry < encoded:
                lo = mid + 1
            else:
                hi = mid - 1
        lo_ptr = ptr + lo * entry_length
        return lo_ptr if read_entry(lo_ptr) == encoded else 0

    def run_instruction(self):
        instruction_ptr = self.pc
        opcode = self.read_from_pc()
        opcode_number = opcode
        if opcode <= 0x7f:
            # long form, 2OP
            opcode_number = opcode & 0x1f
            operands = [
                self.read_operand(1 if opcode & 0x40 == 0 else 2)[0],
                self.read_operand(1 if opcode & 0x20 == 0 else 2)[0]
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
            if opcode < 0xe0:
                # 2OP form, opcode number is bottom 5 bits.
                opcode_number = opcode & 0x1f
            optypes = [b >> i & 0x3 for i in range(6, -1, -2)]
            if opcode in (0xec, 0xfa):
                # call_vn2 and call_vs2 have extra operands.
                b = self.read_from_pc()
                optypes += [b >> i & 0x3 for i in range(6, -1, -2)]
            operands = []
            for optype in optypes:
                operand, exists = self.read_operand(optype)
                if not exists:
                    break
                operands += [operand]
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

    def read_encoded_zscii_from_pc(self):
        result = []
        word = 0
        while word & 0x8000 != 0x8000:
            word = self.read_word(self.pc)
            result += [word]
            self.pc += 2
        return result

    def write_byte(self, addr, val):
        if addr >= self.static_mem_ptr:
            raise IllegalWriteException(f"{addr:x}")
        self.memory_map[addr] = val & 0xff

    def write_word(self, addr, val):
        if addr + 1 >= self.static_mem_ptr:
            raise IllegalWriteException(f"{addr:x}")
        self.memory_map[addr] = val >> 8 & 0xff
        self.memory_map[addr+1] = val & 0xff

    def write_dword(self, addr, val):
        if addr + 3 >= self.static_mem_ptr:
            raise IllegalWriteException(f"{addr:x}")
        self.memory_map[addr] = val >> 24 & 0xff
        self.memory_map[addr+1] = val >> 16 & 0xff
        self.memory_map[addr+2] = val >> 8 & 0xff
        self.memory_map[addr+3] = val & 0xff

    def byte_addr(self, ptr):
        return self.read_word(ptr)

    def word_addr(self, ptr):
        return self.read_word(ptr) << 1

    def unpack_addr(self, packed_addr):
        shift = 1 if self.version <= 3 else 2
        return packed_addr << shift

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
        if self.stack_frame.sp >= len(self.stack):
            raise Exception('Stack overflow')
        self.stack[self.stack_frame.sp] = val
        self.stack_frame.sp += 1

    def stack_pop(self):
        if self.stack_frame.sp <= 0:
            raise Exception('Stack underflow')
        self.stack_frame.sp -= 1
        return self.stack[self.stack_frame.sp]

    def read_var(self, varnum):
        if varnum == 0:
            return self.stack_pop()
        elif varnum >= 0x1 and varnum <= 0xf:
            # Local vars
            if varnum > self.stack_frame.num_locals:
                raise Exception('Invalid index for local variable')
            return self.local_vars[varnum - 1]
        else:
            # Global vars
            addr = self.global_vars + ((varnum - 0x10) * 2)
            return self.read_word(addr)

    def write_var(self, varnum, val):
        val &= 0xffff
        if varnum == 0:
            self.stack_push(val)
        elif varnum >= 0x1 and varnum <= 0xf:
            if varnum > self.stack_frame.num_locals:
                raise Exception('Invalid index for local variable')
            self.local_vars[varnum - 1] = val
        else:
            addr = self.global_vars + ((varnum - 0x10) * 2)
            self.write_word(addr, val)

    def lookup_object(self, obj_id):
        if obj_id == 0 or obj_id > self.MAX_OBJECTS:
            raise InvalidMemoryException(f"Object ID '{obj_id}' out of range")
        return self.object_header + \
            self.PROPERTY_DEFAULTS_LENGTH * 2 + \
            self.OBJECT_BYTES * (obj_id - 1)

    def get_object_parent_id(self, obj_ptr):
        if self.version <= 3:
            return self.read_byte(obj_ptr + 4)
        else:
            return self.read_word(obj_ptr + 6)

    def set_object_parent_id(self, obj_ptr, val):
        if self.version <= 3:
            self.write_byte(obj_ptr + 4, val)
        else:
            self.write_word(obj_ptr + 6, val)

    def get_object_sibling_id(self, obj_ptr):
        if self.version <= 3:
            return self.read_byte(obj_ptr + 5)
        else:
            return self.read_word(obj_ptr + 8)

    def set_object_sibling_id(self, obj_ptr, val):
        if self.version <= 3:
            self.write_byte(obj_ptr + 5, val)
        else:
            self.write_word(obj_ptr + 8, val)

    def get_object_child_id(self, obj_ptr):
        if self.version <= 3:
            return self.read_byte(obj_ptr + 6)
        else:
            return self.read_word(obj_ptr + 10)

    def set_object_child_id(self, obj_ptr, val):
        if self.version <= 3:
            self.write_byte(obj_ptr + 6, val)
        else:
            self.write_word(obj_ptr + 10, val)

    def orphan_object(self, obj_id):
        obj_ptr = self.lookup_object(obj_id)
        parent_id = self.get_object_parent_id(obj_ptr)
        if parent_id == 0:
            return
        parent_ptr = self.lookup_object(parent_id)
        obj_next_sibling_id = self.get_object_sibling_id(obj_ptr)
        child_id = self.get_object_child_id(parent_ptr)
        if child_id == obj_id:
            self.set_object_child_id(parent_ptr, obj_next_sibling_id)
        else:
            while child_id != obj_id:
                child_ptr = self.lookup_object(child_id)
                child_id = self.get_object_sibling_id(child_ptr)
            self.set_object_sibling_id(child_ptr, obj_next_sibling_id)
        self.set_object_parent_id(obj_ptr, 0)
        self.set_object_sibling_id(obj_ptr, 0)

    def get_property_data(self, prop_ptr):
        size_byte = self.read_byte(prop_ptr)
        if size_byte == 0:
            return 0, None, None
        if self.version <= 3:
            return size_byte & 0x1f, (size_byte >> 5) + 1, prop_ptr + 1
        else:
            num = size_byte & 0x3f
            if size_byte & 0x80 == 0x80:
                data_bytes = self.read_byte(prop_ptr + 1) & 0x3f
                if data_bytes == 0:
                    data_bytes = 0x40
                return num, data_bytes, prop_ptr + 2
            else:
                return num, 1 if size_byte & 0x40 == 0 else 2, prop_ptr + 1

    def get_next_property_id(self, obj_id, prop_id):
        prop_ptr = None
        if prop_id == 0:
            # Get the first property
            obj_ptr = self.lookup_object(obj_id)
            prop_ptr = self.byte_addr(obj_ptr + self.OBJECT_BYTES - 2)
            text_len = self.read_byte(prop_ptr)
            prop_ptr += 2 * text_len + 1
        else:
            prop_ptr = self.lookup_property(obj_id, prop_id)
            if prop_ptr == None:
                raise Exception("Invalid property lookup")
            _, size, data_ptr = self.get_property_data(prop_ptr)
            prop_ptr = data_ptr + size
        return self.get_property_data(prop_ptr)[0]

    def lookup_property(self, obj_id, prop_id):
        obj_ptr = self.lookup_object(obj_id)
        prop_ptr = self.byte_addr(obj_ptr + self.OBJECT_BYTES - 2)
        text_len = self.read_byte(prop_ptr)
        prop_ptr += 2 * text_len + 1
        num = 0xff
        while True:
            num, size, data_ptr = self.get_property_data(prop_ptr)
            if num <= prop_id:
                break
            prop_ptr = data_ptr + size
        return prop_ptr if num == prop_id else None

    def do_routine(self, call_addr, args, discard_result = False):
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
        self.stack_frame.push(
            return_pc = return_pc,
            local_vars = local_vars,
            discard_result = discard_result,
            store_varnum = store_varnum
        )

    def do_return(self, retval):
        store_varnum = self.stack_frame.store_varnum
        return_pc = self.stack_frame.return_pc
        discard_result = self.stack_frame.discard_result
        self.stack_frame.pop()
        self.pc = return_pc
        if not discard_result:
            self.write_var(store_varnum, retval)

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

    def default_erase_window_hander(self, num):
        pass

    def default_split_window_handler(self, lines):
        pass

    def default_set_window_handler(self, window):
        pass

    def default_set_buffer_mode_handler(self, mode):
        pass

    def default_set_cursor_handler(self, y, x):
        pass

    def default_set_text_style_handler(self, style):
        pass

    def default_read_char_handler(self):
        pass

    def set_print_handler(self, handler):
        self.print_handler = handler

    def set_input_handler(self, handler):
        self.input_handler = handler

    def set_show_status_handler(self, handler):
        self.show_status_handler = handler

    def set_erase_window_handler(self, handler):
        self.erase_window_handler = handler

    def set_split_window_handler(self, handler):
        self.split_window_handler = handler

    def set_set_window_handler(self, handler):
        self.set_window_handler = handler

    def set_set_buffer_mode_handler(self, handler):
        self.set_buffer_mode_handler = handler

    def set_set_cursor_handler(self, handler):
        self.set_cursor_handler = handler

    def set_set_text_style_handler(self, handler):
        self.set_text_style_handler = handler

    def set_read_char_handler(self, handler):
        self.read_char_handler = handler

    def get_object_text(self, obj_id):
        obj_ptr = self.lookup_object(obj_id)
        prop_ptr = self.byte_addr(obj_ptr + self.OBJECT_BYTES - 2)
        encoded = self.read_encoded_zscii(prop_ptr + 1)
        return zscii_decode(self, encoded)

    def do_read(self, text_buffer, parse_buffer):
        command = self.input_handler()
        max_text_len = self.read_byte(text_buffer) + 1
        if max_text_len < 3:
            raise Exception("Parse error")
        text_ptr = text_buffer + 1
        for c in command[:max_text_len]:
            self.write_byte(text_ptr, ord(c))
            text_ptr += 1
        self.write_byte(text_ptr, 0)
        separators = self.separator_chars()
        tokens, positions = tokenize(command, separators)
        max_words = self.read_byte(parse_buffer)
        parse_ptr = parse_buffer + 1
        self.write_byte(parse_ptr, len(tokens))
        parse_ptr += 1
        for token, position in zip(tokens[:max_words], positions[:max_words]):
            dictionary_ptr = self.lookup_dictionary(token)
            self.write_word(parse_ptr, dictionary_ptr)
            self.write_byte(parse_ptr + 2, len(token))
            self.write_byte(parse_ptr + 3, position + 1)
            parse_ptr += 4

    def do_print(self, text, newline = False):
        if self.output_streams & 0x4 == 0x4:
            self.memory_stream.write(text)
            if newline:
                self.memory_stream.write("\n")
            return
        if self.output_streams & 0x1 == 0x1:
            self.print_handler(text, newline)

    def do_print_encoded(self, encoded, newline = False):
        text = zscii_decode(self, encoded)
        self.do_print(text, newline)

    class stack_frame():
        def __init__(self, from_frame = None):
            self.return_pc = 0
            self.discard_result = False
            self.store_varnum = 0
            self.args = 0
            self.eval_stack = [0] * STACK_LENGTH
            self.local_vars = [0] * 15
            self.previous_frame = None
            self.sp = 0
            self.num_locals = 0

        def push(self, **kwargs):
            previous_frame = object.__new__(zmachine.stack_frame)
            previous_frame.return_pc = self.return_pc
            previous_frame.discard_result = self.discard_result
            previous_frame.store_varnum = self.store_varnum
            previous_frame.args = self.args
            previous_frame.eval_stack = self.eval_stack[:self.sp]
            previous_frame.local_vars = self.local_vars[:self.num_locals]
            previous_frame.previous_frame = self.previous_frame
            num_locals = 0
            for attr, val in kwargs.items():
                if attr == 'local_vars':
                    num_locals = len(val)
                    self.local_vars[:num_locals] = val
                else:
                    setattr(self, attr, val)
            self.sp = 0
            self.num_locals = num_locals
            self.previous_frame = previous_frame

        def pop(self):
            if self.previous_frame == None:
                raise Exception("Stack underflow")
            previous_frame = self.previous_frame
            self.return_pc = previous_frame.return_pc
            self.discard_result = previous_frame.discard_result
            self.store_varnum = previous_frame.store_varnum
            self.args = previous_frame.args
            self.num_locals = len(previous_frame.local_vars)
            self.local_vars[:self.num_locals] = previous_frame.local_vars
            self.sp = len(previous_frame.eval_stack)
            self.eval_stack[:self.sp] = previous_frame.eval_stack
            self.previous_frame = previous_frame.previous_frame
            del previous_frame

        def read(self, data):
            while self.previous_frame != None:
                self.pop()
            ptr = 0
            dummy_frame = True
            while ptr < len(data):
                if not dummy_frame:
                    self.push()
                dummy_frame = False

                return_pc = int.from_bytes(data[ptr:ptr+3], "big")
                flags = int.from_bytes(data[ptr+3:ptr+4], "big")
                store_varnum = int.from_bytes(data[ptr+4:ptr+5], "big")
                args = int.from_bytes(data[ptr+5:ptr+6], "big")
                stack_len = int.from_bytes(data[ptr+6:ptr+8], "big")
                ptr += 8
                discard_result = flags & 0x10 == 0x10
                num_locals = flags & 0xf
                for i in range(num_locals):
                    self.local_vars[i] = int.from_bytes(data[ptr:ptr+2], "big")
                    ptr += 2
                for i in range(stack_len):
                    self.eval_stack[i] = int.from_bytes(data[ptr:ptr+2], "big")
                    ptr += 2
                self.return_pc = return_pc
                self.discard_result = discard_result
                self.store_varnum = store_varnum
                self.args = args
                self.num_locals = num_locals
                self.sp = stack_len
            return self

        def write(self):
            frames = []
            current_frame = self
            while current_frame != None:
                num_locals = self.num_locals if current_frame == self else len(current_frame.local_vars)
                stack_len = self.sp if current_frame == self else len(current_frame.eval_stack)
                data = [0] * (8 + 2 * num_locals + 2 * stack_len)
                ptr = 0
                flags = num_locals
                if current_frame.discard_result:
                    flags |= 0x10
                data[ptr:ptr+3] = current_frame.return_pc.to_bytes(3, "big")
                data[ptr+3:ptr+4] = flags.to_bytes(1, "big")
                data[ptr+4:ptr+5] = current_frame.store_varnum.to_bytes(1, "big")
                data[ptr+5:ptr+6] = current_frame.args.to_bytes(1, "big")
                data[ptr+6:ptr+8] = stack_len.to_bytes(2, "big")
                ptr += 8
                for i in range(num_locals):
                    data[ptr:ptr+2] = current_frame.local_vars[i].to_bytes(2, "big")
                    ptr += 2
                for i in range(stack_len):
                    data[ptr:ptr+2] = current_frame.eval_stack[i].to_bytes(2, "big")
                    ptr += 2
                frames += [data]
                current_frame = current_frame.previous_frame
            # Frames are written with the oldest frame first.
            result = []
            for frame in frames[::-1]:
                result += frame
            return bytearray(result)

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

    class memory_stream():
        def __init__(self, zmachine):
            self.buffer = [0] * 1024
            self.is_open = False
            self.zmachine = zmachine

        def open(self, addr):
            self.is_open = True
            self.ptr = 0
            self.addr = addr

        def write(self, str):
            if not self.is_open:
                raise Exception("Writing to closed stream")
            def zscii(c):
                return 13 if ord(c) == 10 else ord(c)
            for c in str:
                self.buffer[self.ptr] = zscii(c)
                self.ptr += 1

        def close(self):
            self.zmachine.write_word(self.addr, self.ptr)
            for i in range(self.ptr):
                self.zmachine.write_byte(self.addr + i + 2, self.buffer[i])
            self.is_open = False
