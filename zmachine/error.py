class ZMachineException(Exception):
    """Base class for all Z-machine exceptions."""
    pass

class InvalidScreenOperationException(ZMachineException):
    """Raised when screen operation is not allowed."""
    pass

class InvalidGameFileException(ZMachineException):
    def __init__(self, message):
        super().__init__(f"Invalid game file: {message}")

class ZSCIIException(ZMachineException):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class IllegalWriteException(ZMachineException):
    def __init__(self, addr: int):
        super().__init__(f"Illegal write to static memory: 0x{addr:x}")


class InvalidMemoryException(ZMachineException):
    def __init__(self, message):
        super().__init__(f"Invalid read operation: {message}")


class UnrecognizedOpcodeException(ZMachineException):
    def __init__(self, opcode_number: int, instruction_ptr: int):
        super().__init__(f'Unknown opcode {opcode_number} at instruction address {instruction_ptr:x}')


class InvalidArgumentException(ZMachineException):
    def __init__(self, message):
        super().__init__(f"Invalid argument passed to op: {message}")


class InvalidObjectStateException(ZMachineException):
    def __init__(self, message):
        super().__init__(f"Invalid object state: {message}")
        

class StreamException(ZMachineException):
    def __init__(self, message):
        super().__init__(f"Stream exception: {message}")


class VariableOutOfRangeException(ZMachineException):
    def __init__(self, varnum: int):
        super().__init__(f"Variable reference out of range: {varnum}")
