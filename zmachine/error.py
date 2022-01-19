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
