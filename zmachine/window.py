from .enums import FontEnum
from .constants import DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR
from .error import InvalidScreenOperationException

class Window:
    PROPERTIES = {
        0: 'y_pos',
        1: 'x_pos',
        2: 'height',
        3: 'width',
        4: 'y_cursor',
        5: 'x_cursor',
        6: 'left_margin',
        7: 'right_margin',
        8: 'nl_routine',
        9: 'nl_countdown',
        10: 'text_style_attributes',
        11: 'color_data',
        12: 'font_number',
        13: 'font_size',
        14: 'window_attributes',
        15: 'line_count',
        16: 'true_foreground_color',
        17: 'true_background_color'
    }

    def __init__(self, height: int, width: int, font_size: int):
        # The Window class uses 1-index for screen coordinates, to match values read from the game.
        self.y_pos: int = 1
        self.x_pos: int = 1
        self.height: int = height
        self.width: int = width
        # Cursor coordinates are relative to the window, not the screen.
        self.y_cursor: int = 1
        self.x_cursor: int = 1
        self.left_margin: int = 0
        self.right_margin: int = 0
        self.nl_routine: int = 0
        self.nl_countdown: int = 0
        self.text_style_attributes: int = 0
        self.background_color: int = DEFAULT_BACKGROUND_COLOR
        self.foreground_color: int = DEFAULT_FOREGROUND_COLOR
        self.font = FontEnum.DEFAULT
        self.font_size: int = font_size
        self.window_attributes: int = 0
        self.line_count: int = 0
        self.true_foreground_color: int = 0x5ad6    # Light gray
        self.true_background_color: int = 0         # Black

    def get_property(self, property_number: int) -> int:
        property_name = self.PROPERTIES.get(property_number)
        if property_name is None:
            raise InvalidScreenOperationException(f'Unknown property number: {property_number}')
        return int(getattr(self, property_name))
    
    def set_property(self, property_number: int, value: int):
        property_name = self.PROPERTIES.get(property_number)
        if property_name is None:
            raise InvalidScreenOperationException(f'Unknown property number: {property_number}')
        setattr(self, property_name, value)

    def reset_properties(self):
        """Reset all window properties to the defaults."""
        self.y_pos = 1
        self.x_pos = 1
        self.height = 0
        self.width = 0
        self.y_cursor = 1
        self.x_cursor = 1
        self.left_margin = 0
        self.right_margin = 0
        self.nl_routine = 0
        self.nl_countdown = 0
        self.text_style_attributes = 0
        self.background_color = DEFAULT_BACKGROUND_COLOR
        self.foreground_color = DEFAULT_FOREGROUND_COLOR
        self.font = FontEnum.DEFAULT
        # Assumption: The font size will not be changed, so it can stay.
        self.window_attributes = 0
        self.line_count = 0
        self.true_foreground_color = 0x5ad6
        self.true_background_color = 0

    @property
    def font_height(self) -> int:
        return self.font_size >> 8
    
    @property
    def font_width(self) -> int:
        return self.font_size & 0xff
    
    @property
    def lines(self) -> int:
        return self.height // self.font_height
    
    @property
    def columns(self) -> int:
        return self.width // self.font_width
        
    @property
    def color_data(self) -> int:
        return (self.background_color << 8) | self.foreground_color
    
    @color_data.setter
    def color_data(self, value: int):
        self.background_color = value >> 8
        self.foreground_color = value & 0xff

    @property
    def font_number(self) -> int:
        return int(self.font)

    @font_number.setter
    def font_number(self, value: int):
        if value not in FontEnum:
            raise InvalidScreenOperationException(f"Unrecognized font number: {value}")
        self.font = FontEnum(value)

    @property
    def wrapping(self) -> bool:
        """Indicates that printed text that reaches the right margin will continue to the next line."""
        return self.window_attributes & 0x1 == 0x1
    
    @property
    def scrolling(self) -> bool:
        """Indicates the window will scroll when the bottom is reached."""
        return self.window_attributes & 0x2 == 0x2
    
    @property
    def transcript_enabled(self) -> bool:
        """Indicates that text will be copied to output stream 2 (transcript) if open."""
        return self.window_attributes & 0x4 == 0x4
    
    @property
    def buffered_printing(self) -> bool:
        """Indicates that text printed to the window will be temporarily stored in a buffer."""
        return self.window_attributes & 0x8 == 0x8

    @buffered_printing.setter
    def buffered_printing(self, value: bool):
        if value:
            self.window_attributes |= 0x8
        else:
            self.window_attributes &= 0x7