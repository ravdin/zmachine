class ZSCIIException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)

class IllegalWriteException(Exception):
    def __init__(self):
        super().__init__("Illegal write to static memory")

class InvalidMemoryException(Exception):
    def __init__(self, message):
        super().__init__(f"Invalid read operation: {message}")
