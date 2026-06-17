from .logging import error_logger as logger

class ZMachineException(Exception):
    """Base class for all Z-machine exceptions."""
    def __init__(self, message):
        logger.error(message)
        super().__init__(message)


class InvalidScreenOperationException(ZMachineException):
    """Raised when screen operation is not allowed."""
    pass


class CursorOutOfBoundsException(ZMachineException):
    def __init__(self, cursor_x: int, cursor_y: int):
        super().__init__(f"Cursor out of bounds: ({cursor_x}, {cursor_y})")


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


class InvalidBlorbFileException(ZMachineException):
    def __init__(self, filename: str):
        super().__init__(f'"{filename}" is not a valid blorb file')


class InvalidPictureResourceException(ZMachineException):
    def __init__(self, number: int):
        super().__init__(f'Attempting to draw unrecognized picture resource: {number}')


class UnsupportedExecutableResourceException(ZMachineException):
    def __init__(self, chunk_type: bytes):
        super().__init__(f'"{chunk_type!r}" is not a supported executable resource')
