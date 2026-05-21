from enum import IntEnum, StrEnum, Enum, auto
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
    HELP = 729
    PLAYBACK = 960
    RECORD = 174
    SEED = 223

class MouseClick(IntEnum):
    MENU = 252
    DOUBLE_CLICK = 253
    SINGLE_CLICK = 254

class FunctionKey(IntEnum):
    F1 = 133
    F2 = 134
    F3 = 135
    F4 = 136
    F5 = 137
    F6 = 138
    F7 = 139
    F8 = 140
    F9 = 141
    F10 = 142
    F11 = 143
    F12 = 144

class UIType(IntEnum):
    TEXT = auto()
    GRAPHICS = auto()

class FontEnum(IntEnum):
    DEFAULT = 1
    PICTURE = 2
    GRAPHICS = 3
    COURIER = 4

class SoundEffectEnum(IntEnum):
    PREPARE = 1
    PLAY = 2
    INTERRUPT = 3
    UNLOAD = 4

class TerminalMapping(NamedTuple):
    escape_sequence: tuple[int, ...]
    zscii_char: int

class TerminalEscape(Enum):
    CURSOR_UP = TerminalMapping((91, 65), Cursor.UP)
    CURSOR_DOWN = TerminalMapping((91, 66), Cursor.DOWN)
    CURSOR_LEFT = TerminalMapping((91, 67), Cursor.LEFT)
    CURSOR_RIGHT = TerminalMapping((91, 68), Cursor.RIGHT)
    F1 = TerminalMapping((79, 80), FunctionKey.F1)
    F2 = TerminalMapping((79, 81), FunctionKey.F2)
    F3 = TerminalMapping((79, 82), FunctionKey.F3)
    F4 = TerminalMapping((79, 83), FunctionKey.F4)
    F5 = TerminalMapping((91, 49, 53, 126), FunctionKey.F5)
    F6 = TerminalMapping((91, 49, 55, 126), FunctionKey.F6)
    F7 = TerminalMapping((91, 49, 56, 126), FunctionKey.F7)
    F8 = TerminalMapping((91, 49, 57, 126), FunctionKey.F8)
    F9 = TerminalMapping((91, 50, 48, 126), FunctionKey.F9)
    F10 = TerminalMapping((91, 50, 49, 126), FunctionKey.F10)
    F11 = TerminalMapping((91, 50, 51, 126), FunctionKey.F11)
    F12 = TerminalMapping((91, 50, 52, 126), FunctionKey.F12)
    HELP = TerminalMapping((ord('h'),), Hotkey.HELP)
    PLAYBACK = TerminalMapping((ord('p'),), Hotkey.PLAYBACK)
    RECORD = TerminalMapping((ord('r'),), Hotkey.RECORD)
    SEED = TerminalMapping((ord('s'),), Hotkey.SEED)
    MENU_CLICK = TerminalMapping((MouseClick.MENU,), MouseClick.MENU)
    DOUBLE_CLICK = TerminalMapping((MouseClick.DOUBLE_CLICK,), MouseClick.DOUBLE_CLICK)
    SINGLE_CLICK = TerminalMapping((MouseClick.SINGLE_CLICK,), MouseClick.SINGLE_CLICK)

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
    
class StoryEnum(StrEnum):
    AMFV = "A Mind Forever Voyaging"
    ARTHUR = "Arthur"
    BALLYHOO = "Ballyhoo"
    BEYOND_ZORK = "Beyond Zork"
    BORDER_ZONE = "Border Zone"
    BUREAUCRACY = "Bureaucracy"
    CUTTHROATS = "Cutthroats"
    DEADLINE = "Deadline"
    ENCHANTER = "Enchanter"
    HHGG = "The Hitchhiker's Guide To The Galaxy"
    HOLLYWOOD_HIJINX = "Hollywood Hijinx"
    INFIDEL = "Infidel"
    LGOP = "Leather Goddesses of Phobos"
    LURKING_HORROR = "Lurking Horror"
    MOONMIST = "Moonmist"
    NORD_AND_BERT = "Nord and Bert Couldn't Make Head or Tail of It"
    PLANETFALL = "Planetfall"
    PLUNDERED_HEARTS = "Plundered Hearts"
    SEASTALKER = "Seastalker"
    SHERLOCK = "Sherlock"
    SORCERER = "Sorcerer"
    SPELLBREAKER = "Spellbreaker"
    STARCROSS = "Starcross"
    STATIONFALL = "Stationfall"
    SUSPECT = "Suspect"
    SUSPENDED = "Suspended"
    TRINITY = "Trinity"
    WISHBRINGER = "Wishbringer"
    WITNESS = "Witness"
    ZORK_ZERO = "Zork Zero"
    ZORK1 = "Zork I"
    ZORK2 = "Zork II"
    ZORK3 = "Zork III"
    UNKNOWN = ""
    