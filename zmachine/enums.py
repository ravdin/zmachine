from enum import IntEnum, Enum, auto
from typing import NamedTuple, Optional

class RoutineType(IntEnum):
    STORE = 0
    DISCARD = 1
    DIRECT_CALL = 2

class WindowPosition(IntEnum):
    LOWER = 0
    UPPER = 1

class StatusType(IntEnum):
    SCORE = 0
    TIME = 1

class InputStreamType(IntEnum):
    KEYBOARD = 0
    PLAYBACK = 1

class OutputStreamType(IntEnum):
    SCREEN = 1
    TRANSCRIPT = 2
    MEMORY = 3
    RECORD = 4

class TextStyle(IntEnum):
    ROMAN = 0
    REVERSE = 1
    BOLD = 2
    ITALIC = 4
    FIXED_WIDTH = 8

class Color(IntEnum):
    BLACK = 2
    RED = 3
    GREEN = 4
    YELLOW = 5
    BLUE = 6
    MAGENTA = 7
    CYAN = 8
    WHITE = 9
    
class Cursor(IntEnum):
    UP = 129
    DOWN = 130
    LEFT = 131
    RIGHT = 132

class Hotkey(IntEnum):
    DEBUG = 2000
    HELP = 2001
    PLAYBACK = 2002
    RECORD = 2003
    SEED = 2004

class UIType(IntEnum):
    TEXT = auto()
    GRAPHICS = auto()

class TerminalMapping(NamedTuple):
    escape_sequence: tuple[int, ...]
    zscii_char: int

class TerminalEscape(Enum):
    CURSOR_UP = TerminalMapping((91, 65), Cursor.UP)
    CURSOR_DOWN = TerminalMapping((91, 66), Cursor.DOWN)
    CURSOR_LEFT = TerminalMapping((91, 67), Cursor.LEFT)
    CURSOR_RIGHT = TerminalMapping((91, 68), Cursor.RIGHT)
    F1 = TerminalMapping((79, 80), 133)
    F2 = TerminalMapping((79, 81), 134)
    F3 = TerminalMapping((79, 82), 135)
    F4 = TerminalMapping((79, 83), 136)
    F5 = TerminalMapping((91, 49, 53, 126), 137)
    F6 = TerminalMapping((91, 49, 55, 126), 138)
    F7 = TerminalMapping((91, 49, 56, 126), 139)
    F8 = TerminalMapping((91, 49, 57, 126), 140)
    F9 = TerminalMapping((91, 50, 48, 126), 141)
    F10 = TerminalMapping((91, 50, 49, 126), 142)
    F11 = TerminalMapping((91, 50, 51, 126), 143)
    F12 = TerminalMapping((91, 50, 52, 126), 144)
    DEBUG = TerminalMapping((ord('d'),), Hotkey.DEBUG)
    HELP = TerminalMapping((ord('h'),), Hotkey.HELP)
    PLAYBACK = TerminalMapping((ord('p'),), Hotkey.PLAYBACK)
    RECORD = TerminalMapping((ord('r'),), Hotkey.RECORD)
    SEED = TerminalMapping((ord('s'),), Hotkey.SEED)

    @property
    def sequence(self) -> tuple[int, ...]:
        return self.value.escape_sequence
    
    @property
    def zscii_char(self) -> int:
        return self.value.zscii_char
    
    @classmethod
    def values(cls) -> list[int]:
        return [e.zscii_char for e in cls]
    
    @classmethod
    def lookup_sequence(cls, escape_sequence: tuple[int, ...]) -> Optional['TerminalEscape']:
        for escape in cls:
            if escape.sequence == escape_sequence:
                return escape
        return None
    