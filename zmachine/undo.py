class UndoFrame:
    def __init__(self, dynamic_memory: bytearray, call_stack_bytes: bytearray, pc: int):
        self.dynamic_memory = dynamic_memory
        self.call_stack_bytes = call_stack_bytes
        self.pc = pc

    def serialize(self):
        result = bytearray()
        result.extend(len(self.dynamic_memory).to_bytes(4, "big"))
        result.extend(self.dynamic_memory)
        result.extend(len(self.call_stack_bytes).to_bytes(4, "big"))
        result.extend(self.call_stack_bytes)
        result.extend(self.pc.to_bytes(3, "big"))
        return result

    @classmethod
    def deserialize(cls, data: bytearray):
        dynamic_memory_len = int.from_bytes(data[:4], "big")
        data_ptr = dynamic_memory_len + 4
        dynamic_memory = data[4:data_ptr]
        call_stack_bytes_len = int.from_bytes(data[data_ptr:data_ptr+4], "big")
        data_ptr += 4
        call_stack_bytes = data[data_ptr:data_ptr+call_stack_bytes_len]
        data_ptr += call_stack_bytes_len
        pc = int.from_bytes(data[data_ptr:data_ptr+3], "big")
        return cls(dynamic_memory, call_stack_bytes, pc)


class UndoStack:
    def __init__(self):
        # Assumption there won't be more than this many undos.
        self.STACK_SIZE = 16
        self.stack: list[bytearray] = [bytearray()] * self.STACK_SIZE
        self.sp: int = 0

    def push(self, dynamic_memory: bytearray, call_stack_bytes: bytearray, pc: int):
        frame = UndoFrame(dynamic_memory, call_stack_bytes, pc)
        if self.sp == self.STACK_SIZE:
            self.stack[:self.STACK_SIZE-1] = self.stack[1:]
            self.stack[self.STACK_SIZE-1] = frame.serialize()
        else:
            self.stack[self.sp] = frame.serialize()
            self.sp += 1

    def pop(self) -> UndoFrame | None:
        if self.sp <= 0:
            return None
        self.sp -= 1
        return UndoFrame.deserialize(self.stack[self.sp])
