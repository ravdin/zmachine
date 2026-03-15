from typing import Final
from enums import Color

SUPPORTED_VERSIONS: Final[tuple[int, ...]] = (3, 4, 5)

# Interpreter identification
INTERPRETER_REVISION: Final[int] = 0x101 # Write this as revision 1.1
# TODO: Set from the command line?
# For now, tell the game it's played on an DEC system, with a version number set to 'A'.
INTERPRETER_NUMBER: Final[int] = 0x141

# Limits
MAX_STACK_LENGTH: Final[int] = 1024
INPUT_BUFFER_LENGTH: Final[int] = 200

# Screen defaults
DEFAULT_FOREGROUND_COLOR: Final[Color] = Color.WHITE
DEFAULT_BACKGROUND_COLOR: Final[Color] = Color.BLACK

IFF_HEADER: Final[bytearray] = bytearray('FORM'.encode('UTF-8'))
IFZS_ID: Final[bytearray] = bytearray('IFZS'.encode('UTF-8'))