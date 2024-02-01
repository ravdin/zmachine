from typing import BinaryIO, Callable, Any
import os
from constants import *
from memory import MemoryMap
from event import EventManager, EventArgs
from stack import CallStack


class Quetzal:
    def __init__(self, memory_map: MemoryMap, game_file: str):
        self.memory_map = memory_map
        self.game_file = game_file
        filename = os.path.basename(game_file)
        base_filename = os.path.splitext(filename)[0]
        self.filepath = os.path.dirname(game_file)
        self.save_file = f'{base_filename}.sav'
        self.event_manager = EventManager()

    def read_byte(self, addr):
        return self.memory_map.read_byte(addr)

    def read_word(self, addr):
        return self.memory_map.read_word(addr)

    def write_word(self, addr, val):
        self.memory_map.write_word(addr, val)

    def do_save(self, pc: int, call_stack: CallStack):
        save_file = self.prompt_save_file()
        save_full_path = os.path.join(self.filepath, save_file)
        if os.path.exists(save_full_path):
            if self.interpreter_input('Overwrite existing file? (Y is affirmative) ') != 'y':
                return False
        data_len = len(IFZS_ID)
        header_data = self.memory_map.release_number[:]
        header_data += self.memory_map.serial_number
        header_data += self.memory_map.checksum.to_bytes(2, "big")
        header_data += pc.to_bytes(3, "big")
        header_chunk = IffChunk(HEADER_CHUNK, header_data)
        dynamic_memory = self.compress_dynamic_memory()
        mem_chunk = IffChunk(COMPRESSED_MEMORY_CHUNK, dynamic_memory)
        stack_data = call_stack.serialize()
        stack_chunk = IffChunk(CALL_STACK_CHUNK, stack_data)
        for chunk in (header_chunk, mem_chunk, stack_chunk):
            data_len += len(chunk)
        try:
            with open(save_full_path, 'wb') as s:
                s.write(IFF_HEADER)
                s.write(data_len.to_bytes(4, "big"))
                s.write(IFZS_ID)
                header_chunk.write(s)
                mem_chunk.write(s)
                stack_chunk.write(s)
            self.save_file = save_file
            return True
        except:
            # TODO: Logging would be nice.
            return False

    def do_restore(self, call_stack: CallStack, reset_pc_callback: Callable[[int], Any]):
        flags2_bits = self.read_word(0x10) & 0x3
        filepath = os.path.dirname(self.game_file)
        save_file = self.prompt_save_file()
        save_full_path = os.path.join(filepath, save_file)
        if not os.path.exists(save_full_path):
            return False
        chunks = {}
        with open(save_full_path, 'rb') as s:
            header = s.read(4)
            data_len = int.from_bytes(s.read(4), "big")
            form_type = s.read(4)
            if header != IFF_HEADER or form_type != IFZS_ID:
                self.interpreter_prompt('Invalid save file!')
                return False
            bytes_read = 0
            while bytes_read < data_len:
                chunk = IffChunk.read(s)
                bytes_read += len(chunk)
                chunks[chunk.header] = chunk
        try:
            header_chunk = chunks[HEADER_CHUNK]
            mem_chunk = chunks[COMPRESSED_MEMORY_CHUNK]
            stack_chunk = chunks[CALL_STACK_CHUNK]
            release_number = header_chunk.data[0:2]
            serial_number = header_chunk.data[2:8]
            checksum = int.from_bytes(header_chunk.data[8:10], "big")
            pc = int.from_bytes(header_chunk.data[10:13], "big")
            encoded_memory = mem_chunk.data
        except Exception as err:
            # print(f'{err}')
            return False
        if release_number != self.memory_map.release_number or \
                serial_number != self.memory_map.serial_number or \
                checksum != self.memory_map.checksum:
            self.interpreter_prompt("Invalid save file!")
            return False
        dynamic_mem = self.uncompress_dynamic_memory(encoded_memory)
        self.memory_map.reset_dynamic_memory(dynamic_mem)
        call_stack.deserialize(stack_chunk.data)
        reset_pc_callback(pc)

        # Set the transcribe and fixed pitch bits to the previous state.
        flags2 = self.read_word(0x10)
        flags2 &= 0xfffc
        flags2 |= flags2_bits
        self.write_word(0x10, flags2)
        return True

    # There's no need to compress the dynamic memory for the save file
    # as modern computers have plenty of storage space.
    # This method (from Bryan Scattergood) is more interesting and elegant.
    # The main idea is to exclusive-or each byte of the dynamic memory with
    # the byte in the original game file. If the result is zero (not changed),
    # write a zero byte followed by the number of zero bytes (i.e. the number
    # of bytes we can skip when restoring the dynamic memory).
    # Otherwise, write the result of the exclusive or.
    def compress_dynamic_memory(self) -> bytearray:
        static_mem_ptr = self.memory_map.static_mem_ptr
        result = [0] * static_mem_ptr
        result_ptr = 0
        with open(self.game_file, "rb") as s:
            dynamic_mem = bytearray(s.read(static_mem_ptr))
        zero_count = 0
        for ptr in range(static_mem_ptr):
            story = self.read_byte(ptr)
            original = dynamic_mem[ptr]
            val = story ^ original
            if val == 0:
                zero_count += 1
            else:
                while zero_count > 0:
                    result[result_ptr + 1] = min(zero_count - 1, 0xff)
                    zero_count = max(zero_count - 0x100, 0)
                    result_ptr += 2
                result[result_ptr] = val
                result_ptr += 1
        return bytearray(result[:result_ptr])

    def uncompress_dynamic_memory(self, encoded_memory) -> bytearray:
        with open(self.game_file, 'rb') as s:
            dynamic_mem = bytearray(s.read(self.memory_map.static_mem_ptr))
        mem_ptr = 0
        byte_ptr = 0
        while byte_ptr < len(encoded_memory):
            val = encoded_memory[byte_ptr]
            if val == 0:
                mem_ptr += encoded_memory[byte_ptr + 1]
                byte_ptr += 2
            else:
                dynamic_mem[mem_ptr] ^= val
                byte_ptr += 1
            mem_ptr += 1
        return dynamic_mem

    def prompt_save_file(self):
        self.interpreter_prompt('Enter a file name.')
        save_file = self.interpreter_input(f'Default is "{self.save_file}": ')
        if save_file == '':
            save_file = self.save_file
        return save_file

    def interpreter_prompt(self, text):
        self.event_manager.interpreter_prompt.invoke(self, EventArgs(text=text))

    def interpreter_input(self, text):
        event_args = EventArgs(text=text)
        self.event_manager.interpreter_input.invoke(self, event_args)
        return event_args.response


class IffChunk:
    def __init__(self, header, data):
        self.header = header[:4]
        self.data = data

    @classmethod
    def read(cls, stream: BinaryIO):
        header = ''.join([chr(b) for b in stream.read(4)])
        count = int.from_bytes(stream.read(4), "big")
        data = stream.read(count)
        # Pad byte.
        if count & 1 == 1:
            stream.read(1)
        return cls(header, data)

    def write(self, stream: BinaryIO):
        header_bytes = bytearray([ord(c) for c in self.header])
        bytes_written = stream.write(header_bytes)
        if bytes_written < 4:
            stream.write(b'\x00' * (4 - bytes_written))
        stream.write(len(self.data).to_bytes(4, "big"))
        stream.write(self.data)
        # Pad byte.
        if len(self.data) & 1 == 1:
            stream.write(b'\x00')

    def __len__(self):
        return len(self.data) + 8 + (len(self.data) & 1)
