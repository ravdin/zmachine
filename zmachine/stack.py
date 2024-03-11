from config import *
from typing import List


class StackFrame:
    def __init__(self, **kwargs):
        self.local_vars = []
        self.eval_stack = EvalStack()
        self.return_pc = 0
        self.store_varnum = 0
        self.arg_count = 0
        self.routine_type = ROUTINE_TYPE_STORE
        for attr, val in kwargs.items():
            setattr(self, attr, val)


class CallStack:
    def __init__(self, dummy_frame: bool = True):
        # The dummy frame should be set for versions 1-5.
        # For these versions the game starts with an evaluation stack that can
        # be used outside a routine.
        # If this interpreter is ever updated for version 6, then the game will start
        # with a main routine instead of an initial instruction.
        self.frames: List[StackFrame] = []
        self.has_dummy_frame = dummy_frame
        self.frame_ptr = 0
        if dummy_frame:
            self.frames += [StackFrame()]
            self.frame_ptr = 1

    @property
    def current_frame(self):
        if self.frame_ptr <= 0:
            raise Exception('No current call frame')
        return self.frames[self.frame_ptr - 1]

    @property
    def eval_stack(self):
        return self.current_frame.eval_stack

    def push(self, **kwargs):
        frame = StackFrame(**kwargs)
        if len(self.frames) == self.frame_ptr:
            self.frames += [frame]
        else:
            self.frames[self.frame_ptr] = frame
        self.frame_ptr += 1

    def pop(self) -> StackFrame:
        if self.frame_ptr <= 0:
            raise Exception("Stack underflow")
        self.frame_ptr -= 1
        return self.frames[self.frame_ptr]

    def clear(self):
        self.frame_ptr = 1 if self.has_dummy_frame else 0
        self.eval_stack.clear()

    def get_local_var(self, index) -> int:
        local_vars = self.current_frame.local_vars
        if index >= len(local_vars):
            raise Exception('Invalid index for local variable')
        return local_vars[index]

    def set_local_var(self, index, value):
        local_vars = self.current_frame.local_vars
        if index >= len(local_vars):
            raise Exception('Invalid index for local variable')
        local_vars[index] = value

    def catch(self) -> int:
        return self.frame_ptr - 1 if self.has_dummy_frame else self.frame_ptr

    def throw(self, frame_index: int):
        frame_ptr = frame_index + 1 if self.has_dummy_frame else frame_index
        if frame_ptr > self.frame_ptr:
            raise Exception('Invalid stack frame')
        self.frame_ptr = frame_ptr

    def serialize(self) -> bytearray:
        result = bytearray()
        for i in range(self.frame_ptr):
            frame = self.frames[i]
            eval_stack_len = len(frame.eval_stack)
            eval_stack_items = frame.eval_stack.get_items()
            num_locals = len(frame.local_vars)
            frame_bytes = [0] * (8 + 2 * num_locals + 2 * eval_stack_len)
            flags = num_locals
            # It's illegal to save the game state inside a direct call routine.
            # If this happens for some reason, stop here and let the save opcode return false.
            if frame.routine_type == ROUTINE_TYPE_DIRECT_CALL:
                return bytearray()
            if frame.routine_type == ROUTINE_TYPE_DISCARD:
                flags |= 0x10
            frame_bytes[:3] = frame.return_pc.to_bytes(3, "big")
            frame_bytes[3:4] = flags.to_bytes(1, "big")
            frame_bytes[4:5] = frame.store_varnum.to_bytes(1, "big")
            frame_bytes[5:6] = (2 ** frame.arg_count - 1).to_bytes(1, "big")
            frame_bytes[6:8] = eval_stack_len.to_bytes(2, "big")
            frame_ptr = 8
            for local_var in frame.local_vars:
                frame_bytes[frame_ptr:frame_ptr + 2] = local_var.to_bytes(2, "big")
                frame_ptr += 2
            for item in eval_stack_items:
                frame_bytes[frame_ptr:frame_ptr + 2] = item.to_bytes(2, "big")
                frame_ptr += 2
            result.extend(frame_bytes)
        return result

    def deserialize(self, data: bytearray):
        frame_index = 0
        data_ptr = 0
        while data_ptr < len(data):
            return_pc = int.from_bytes(data[data_ptr:data_ptr + 3], "big")
            flags = int.from_bytes(data[data_ptr + 3:data_ptr + 4], "big")
            store_varnum = int.from_bytes(data[data_ptr + 4:data_ptr + 5], "big")
            arg_bits = int.from_bytes(data[data_ptr + 5:data_ptr + 6], "big")
            eval_stack_len = int.from_bytes(data[data_ptr + 6:data_ptr + 8], "big")
            if arg_bits & (arg_bits + 1) != 0:
                raise Exception('Save file uses incomplete argument lists')
            arg_count = 0
            while arg_bits > 0:
                arg_count += 1
                arg_bits >>= 1
            discard_result = flags & 0x10 == 0x10
            num_locals = flags & 0xf
            local_vars = [0] * num_locals
            eval_stack_items = [0] * eval_stack_len
            data_ptr += 8
            for i in range(num_locals):
                local_vars[i] = int.from_bytes(data[data_ptr:data_ptr + 2], "big")
                data_ptr += 2
            for i in range(eval_stack_len):
                eval_stack_items[i] = int.from_bytes(data[data_ptr:data_ptr + 2], "big")
                data_ptr += 2
            eval_stack = EvalStack(eval_stack_items)
            frame = StackFrame(
                local_vars=local_vars,
                eval_stack=eval_stack,
                return_pc=return_pc,
                store_varnum=store_varnum,
                arg_count=arg_count,
                routine_type=ROUTINE_TYPE_DISCARD if discard_result else ROUTINE_TYPE_STORE
            )
            if frame_index < len(self.frames):
                self.frames[frame_index] = frame
            else:
                self.frames += [frame]
            frame_index += 1
        self.frame_ptr = frame_index


class EvalStack:
    def __init__(self, items: List[int] = None):
        self.stack: List[int] = []
        self.sp: int = 0
        if items is not None:
            self.set_items(items)

    def push(self, value: int):
        if self.sp >= MAX_STACK_LENGTH:
            raise Exception('Stack overflow')
        if self.sp >= len(self.stack):
            self.stack += [0] * 16
        self.stack[self.sp] = value
        self.sp += 1

    def pop(self) -> int:
        if self.sp <= 0:
            raise Exception('Stack underflow')
        self.sp -= 1
        return self.stack[self.sp]

    def peek(self) -> int:
        if self.sp <= 0:
            raise Exception('Empty stack')
        return self.stack[self.sp - 1]

    def clear(self):
        self.sp = 0

    def get_items(self) -> List[int]:
        return self.stack[:self.sp]

    def set_items(self, stack: List[int]):
        sp = len(stack)
        self.stack[:sp] = stack[:]
        self.sp = sp

    def __len__(self) -> int:
        return self.sp
