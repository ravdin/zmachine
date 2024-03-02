class ZSCIIException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class IllegalWriteException(Exception):
    def __init__(self, message):
        super().__init__(f"Illegal write to static memory: {message}")


class InvalidMemoryException(Exception):
    def __init__(self, message):
        super().__init__(f"Invalid read operation: {message}")


class InvalidArgumentException(Exception):
    def __init__(self, message):
        super().__init__(f"Invalid argument passed to op: {message}")


class InvalidObjectStateException(Exception):
    def __init__(self, message):
        super().__init__(f"Invalid object state: {message}")
        

class StreamException(Exception):
    def __init__(self, message):
        super().__init__(f"Stream exception: {message}")


class VariableOutOfRangeException(Exception):
    def __init__(self, varnum: int):
        super().__init__(f"Variable reference out of range: {varnum}")
