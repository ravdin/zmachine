import struct
from dataclasses import dataclass, field
from .constants import SUPPORTED_VERSIONS, STORY_VERSIONS
from .enums import StoryEnum
from .error import InvalidGameFileException

@dataclass(frozen=True)
class ZMachineConfig:
    """Configuration for a Z-Machine interpreter instance."""

    game_file: str
    """ Path to the game file."""

    # Header values
    version: int = 0
    """ Z-Machine version number (3, 4, or 5)."""
    release_number: bytes = b'\x00\x00'
    """ Release number of the game file."""
    high_memory_base_addr: int = 0
    """ Location of the first byte of high memory. """
    initial_pc: int = 0
    """ Address of the first instruction to execute. """
    dictionary_table_addr: int = 0
    """ Location of the dictionary table."""
    object_table_addr: int = 0
    """ Location of the object table."""
    global_vars_table_addr: int = 0
    """ Location of the global variables table."""
    static_memory_base_addr: int = 0
    """ Location of the first byte of static memory. """
    serial_number: bytes = b'\x00' * 6
    """ Serial number of the game file, used for copy protection. """
    abbreviation_table_addr: int = 0
    """ Location of the abbreviation table."""
    file_length: int = 0
    """ Length of the game file in bytes. """
    checksum: int = 0
    """ Checksum of the game file, used for copy protection. """
    interrupt_zchars: tuple[int, ...] = field(default_factory=tuple)
    """ Terminating characters (version 5 and above)"""
    alphabet_table_addr: int = 0
    """Address of a game provided alphabet table (version 5 and above)"""
    header_extension_addr: int = 0
    """Address of the header extension table (version 5 and above)"""
    routine_offset: int = 0
    """Offset for routine addresses (v6)"""
    strings_offset: int = 0
    """Offset for static strings (v6)"""
    story: StoryEnum = StoryEnum.UNKNOWN

    @classmethod
    def from_game_file(cls, game_file: str) -> 'ZMachineConfig':
        with open(game_file, 'rb') as s:
            game_data = s.read()
        version = game_data[0]
        if version not in SUPPORTED_VERSIONS:
            if 0 < version <= 6:
                raise InvalidGameFileException(f"Unsupported Z-Machine version: v{version}")
            else:
                raise InvalidGameFileException(f"Unrecognized Z-Machine file") 

        (
            release_number,
            high_memory_base_addr,
            initial_pc,
            dictionary_table_addr,
            object_table_addr,
            global_vars_table_addr,
            static_memory_base_addr,
            _,
            serial_number,
            abbreviation_table_addr,
            file_length_raw,
            checksum
        ) = struct.unpack_from(">2s7H6s3H", game_data, 2)
        file_length = file_length_raw << (1 if version <= 3 else 2 if version <= 5 else 3)
        interrupt_zchars: list[int] = []
        alphabet_table_addr = 0
        header_extension_addr = 0
        routine_offset = 0
        strings_offset = 0
        story = STORY_VERSIONS.get(struct.unpack(">H", release_number) + (serial_number,), StoryEnum.UNKNOWN)
        if version >= 5:
            zchars_addr, = struct.unpack_from(">H", game_data, 0x2e)
            zchar = game_data[zchars_addr]
            while zchar != 0:
                interrupt_zchars += [zchar]
                zchars_addr += 1
                zchar = game_data[zchars_addr]
            alphabet_table_addr, header_extension_addr = struct.unpack_from(">HH", game_data, 0x34)
        if version >= 6:
            routine_offset, strings_offset = (val << 3 for val in struct.unpack_from(">HH", game_data, 0x28))

        return cls(
            game_file = game_file,
            version = version,
            release_number = release_number,
            high_memory_base_addr = high_memory_base_addr,
            initial_pc = initial_pc,
            dictionary_table_addr = dictionary_table_addr,
            object_table_addr = object_table_addr,
            global_vars_table_addr = global_vars_table_addr,
            static_memory_base_addr = static_memory_base_addr,
            serial_number = serial_number,
            abbreviation_table_addr = abbreviation_table_addr,
            file_length = file_length,
            checksum = checksum,
            interrupt_zchars = tuple(interrupt_zchars),
            alphabet_table_addr = alphabet_table_addr,
            header_extension_addr = header_extension_addr,
            routine_offset = routine_offset,
            strings_offset = strings_offset,
            story = story
        )
    