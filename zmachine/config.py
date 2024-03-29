SUPPORTED_VERSIONS = (3, 4, 5)
INTERPRETER_REVISION = 0x101 # Write this as revision 1.1
# TODO: Set from the command line?
# For now, tell the game it's played on an DEC system, with a version number set to 'A'.
INTERPRETER_NUMBER = 0x141
MAX_STACK_LENGTH = 1024
INPUT_BUFFER_LENGTH = 200
LOWER_WINDOW = 0
UPPER_WINDOW = 1
DEFAULT_FOREGROUND_COLOR = 9
DEFAULT_BACKGROUND_COLOR = 2
ESCAPE_SEQUENCE_UP_ARROW = (91, 65)
ESCAPE_SEQUENCE_DOWN_ARROW = (91, 66)
ESCAPE_SEQUENCE_LEFT_ARROW = (91, 67)
ESCAPE_SEQUENCE_RIGHT_ARROW = (91, 68)
ESCAPE_SEQUENCE_F1 = (79, 80)
ESCAPE_SEQUENCE_F2 = (79, 81)
ESCAPE_SEQUENCE_F3 = (79, 82)
ESCAPE_SEQUENCE_F4 = (79, 83)
ESCAPE_SEQUENCE_F5 = (91, 49, 53, 126)
ESCAPE_SEQUENCE_F6 = (91, 49, 55, 126)
ESCAPE_SEQUENCE_F7 = (91, 49, 56, 126)
ESCAPE_SEQUENCE_F8 = (91, 49, 57, 126)
ESCAPE_SEQUENCE_F9 = (91, 50, 48, 126)
ESCAPE_SEQUENCE_F10 = (91, 50, 49, 126)
ESCAPE_SEQUENCE_F11 = (91, 50, 51, 126)
ESCAPE_SEQUENCE_F12 = (91, 50, 52, 126)
STATUS_TYPE_SCORE = 0
STATUS_TYPE_TIME = 1
ROUTINE_TYPE_STORE = 0
ROUTINE_TYPE_DISCARD = 1
ROUTINE_TYPE_DIRECT_CALL = 2
IFF_HEADER = bytearray('FORM'.encode('UTF-8'))
IFZS_ID = bytearray('IFZS'.encode('UTF-8'))
HEADER_CHUNK = 'IFhd'
COMPRESSED_MEMORY_CHUNK = 'CMem'
CALL_STACK_CHUNK = 'Stks'

VERSION_NUMBER_KEY = 'version_number'
RELEASE_NUMBER_KEY = 'release_number'
HIGH_MEMORY_BASE_ADDR_KEY = 'high_memory_base_addr'
INITIAL_PC_KEY = 'initial_pc'
DICTIONARY_TABLE_KEY = 'dictionary_table'
OBJECT_TABLE_KEY = 'object_table'
GLOBAL_VARS_TABLE_KEY = 'global_vars_table'
STATIC_MEMORY_BASE_ADDR_KEY = 'static_memory_base_addr'
SERIAL_NUMBER_KEY = 'serial_number'
ABBREVIATION_TABLE_KEY = 'abbreviation_table'
FILE_LENGTH_KEY = 'file_length'
CHECKSUM_KEY = 'checksum'

GAME_FILE_KEY = 'game_file'
SCREEN_HEIGHT_KEY = 'screen_height'
SCREEN_WIDTH_KEY = 'screen_width'
INTERRUPT_ZCHARS_KEY = 'interrupt_zchars'


CONFIG = {
    VERSION_NUMBER_KEY: 0,
    RELEASE_NUMBER_KEY: bytearray(),
    HIGH_MEMORY_BASE_ADDR_KEY: 0,
    INITIAL_PC_KEY: 0,
    DICTIONARY_TABLE_KEY: 0,
    OBJECT_TABLE_KEY: 0,
    GLOBAL_VARS_TABLE_KEY: 0,
    STATIC_MEMORY_BASE_ADDR_KEY: 0,
    SERIAL_NUMBER_KEY: bytearray(),
    ABBREVIATION_TABLE_KEY: 0,
    FILE_LENGTH_KEY: 0,
    CHECKSUM_KEY: 0,

    GAME_FILE_KEY: '',
    SCREEN_HEIGHT_KEY: 0,
    SCREEN_WIDTH_KEY: 0,
    INTERRUPT_ZCHARS_KEY: []
}
