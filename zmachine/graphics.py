"""
Graphics-based terminal adapter using pygame.

Provides rendering for both text and graphics in Z-Machine games.
Supports V1-V5 text mode, V5 graphics (Beyond Zork), and V6 full graphics.

File: zmachine/graphics.py
"""
import pygame
import sys
import io
import numpy as np
from dataclasses import dataclass
from .protocol import IResourceData
from .event import EventManager, MouseClickEventArgs, RoutineCallEventArgs
from .config import ZMachineConfig
from .settings import RuntimeSettings
from .enums import Color, FontEnum, FunctionKey, StoryEnum, MouseClick
from .constants import FONT3_BITMAP, DEFAULT_FONT_SIZE
from .error import InvalidPictureResourceException
from .logging import graphics_logger as logger


@dataclass
class Cell:
    """Represents a single character cell with its display attributes."""
    char: str = ' '
    fg: tuple = (219, 219, 219)         # Light gray
    bg: tuple = (0, 0, 0)               # Black
    style: int = 0                      # Style flags (bold, italic, reverse)
    font: FontEnum = FontEnum.DEFAULT   # Font for output


class GraphicsAdapter:
    """
    Graphics-based terminal adapter for Z-Machine.
    
    Uses pygame to render both text and graphics, supporting:
    - All text-based games (V1-V8)
    - V5 graphics (Beyond Zork font 3)
    - V6 full graphics with Blorb images
    
    Implements ITerminalAdapter protocol via duck typing.
    """
    SOUND_END_EVENT = pygame.USEREVENT + 1
    
    def __init__(self, 
                 event_manager: EventManager,
                 config: ZMachineConfig,
                 runtime_settings: RuntimeSettings, 
                 window_width: int = 1280, 
                 window_height: int = 800):
        """
        Initialize pygame window.
        
        Args:
            window_width: Window width in pixels (default 1280)
            window_height: Window height in pixels (default 800)
        """
        logger.info(f"Initializing graphics adapter: {window_width}x{window_height}")
        
        pygame.init()
        self.window_width = window_width
        self.window_height = window_height
        self.event_manager = event_manager
        self.screen = pygame.display.set_mode((window_width, window_height))
        self._mouse_enabled = runtime_settings.mouse_enabled
        self._at_wrap_boundary = False
        self.current_font = FontEnum.DEFAULT
        self.beep_sound = self._make_beep()
        pygame.key.set_repeat(500, 100)  # 500ms delay, then repeat every 100ms
        title = "Z-Machine Interpreter" if config.story == StoryEnum.UNKNOWN else config.story
        pygame.display.set_caption(f"{title}")
        
        # Font setup - try monospace first
        try:
            self.font = pygame.font.SysFont('courier', DEFAULT_FONT_SIZE)
            logger.debug("Using Courier font")
        except:
            self.font = pygame.font.Font(None, 16)
            logger.debug("Using default font")
        
        # Calculate character dimensions
        test_surface = self.font.render('M', True, (255, 255, 255))
        self.char_width = test_surface.get_width()
        self.char_height = self.font.get_height()

        logger.info(f"Character dimensions: {self.char_width}x{self.char_height}")
        
        # Calculate screen size in characters
        self._width = window_width // self.char_width
        self._height = window_height // self.char_height
        
        logger.info(f"Screen size: {self._width} cols x {self._height} rows")
        
        # Screen buffer (rows x cols of Cell objects)
        self.screen_buffer = [[Cell() for _ in range(self._width)] 
                             for _ in range(self._height)]
        self.cursor_x = 0
        self.cursor_y = 0
        
        # Current text attributes (for new characters)
        self.current_fg = (219, 219, 219)   # Light gray (Z-color 10)
        self.current_bg = (0, 0, 0)         # Black (Z-color 2)
        self.current_style = 0
        
        # Scrolling region (for split-window support)
        self.scroll_top = 0
        
        # Input timeout (milliseconds)
        self.input_timeout_ms = 0

        # Mouse boundaries (top, left, bottom, right)
        self.mouse_boundary = (0, 0, self.height, self.width)

        # Configure sound resources.
        self.sound_channel = pygame.mixer.Channel(0)
        self.sound_channel.set_endevent(self.SOUND_END_EVENT)
        self._pending_routine: int = 0
        self._sound_interrupted: bool = False
        self._current_sound_number: int = 0
        self._sound_resources: dict[int, pygame.mixer.Sound] = {}
        
        # Clear screen
        self.screen.fill(self.current_bg)
        pygame.display.flip()
        
        logger.info("Graphics adapter initialized successfully")
    
    # ========================================================================
    # ITerminalAdapter Protocol Implementation (duck typing)
    # ========================================================================
    
    @property
    def height(self) -> int:
        """The height of the terminal in characters."""
        return self._height
    
    @property
    def width(self) -> int:
        """The width of the terminal in characters."""
        return self._width
    
    @property
    def font_size(self) -> int:
        return (self.char_height << 8) | self.char_width
    
    @property
    def at_wrap_boundary(self) -> bool:
        """Indicates that the output text of the last line has reached the edge of the screen."""
        return self._at_wrap_boundary
    
    def refresh(self):
        """Refresh the terminal display."""
        pygame.display.flip()
    
    def set_scrollable_height(self, top: int):
        """Set the scrollable height of the terminal."""
        logger.debug(f"Set scrollable height: top={top}")
        self.scroll_top = top
    
    def write_to_screen(self, text: str):
        """Write text directly to the terminal."""
        if logger.isEnabledFor(10):  # DEBUG level
            logger.debug(f"Write: {text!r}")
        
        for char in text:
            if char == '\n':
                self._newline()
            else:
                self._put_char(char)
        
        if self.cursor_x >= self.width:
            self._newline()
            self._at_wrap_boundary = True
        self.refresh()
    
    def get_input_char(self, echo: bool = True) -> int:
        """
        Get a single input character.
        
        Args:
            echo: Whether to echo the character to screen
            
        Returns:
            Character code (ASCII or special key code)
        """
        logger.debug(f"Getting input char (echo={echo})")
        
        pygame.event.clear(pygame.KEYDOWN, False)
        clock = pygame.time.Clock()
        start_time = pygame.time.get_ticks()
        cursor_visible = False
        cursor_blink_time = 0
        
        while True:
            # Check timeout
            if self.input_timeout_ms > 0:
                elapsed = pygame.time.get_ticks() - start_time
                if elapsed >= self.input_timeout_ms:
                    logger.debug("Input timeout")
                    return -1
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    logger.info("User closed window")
                    pygame.quit()
                    sys.exit(0)

                if event.type == self.SOUND_END_EVENT:
                    if self._sound_interrupted:
                        self._sound_interrupted = False
                    elif self._pending_routine != 0:
                        routine_call_event_args = RoutineCallEventArgs(self._pending_routine)
                        self.event_manager.on_routine_call.invoke(self, routine_call_event_args)
                        self._pending_routine = 0
                    self._current_sound_number = 0
                    continue
                
                if event.type == pygame.KEYDOWN:
                    # Handle special keys
                    if event.key == pygame.K_UP:
                        char_code = 129
                    elif event.key == pygame.K_DOWN:
                        char_code = 130
                    elif event.key == pygame.K_LEFT:
                        char_code = 131
                    elif event.key == pygame.K_RIGHT:
                        char_code = 132
                    elif pygame.K_F1 <= event.key <= pygame.K_F12:
                        char_code = event.key - pygame.K_F1 + FunctionKey.F1
                    elif event.key == pygame.K_RETURN:
                        self._draw_cursor(False)
                        char_code = 13  # Enter
                    elif event.key == pygame.K_BACKSPACE:
                        char_code = 8  # Backspace
                    elif event.key == pygame.K_ESCAPE:
                        char_code = 27  # Escape
                    elif event.unicode:
                        char_code = ord(event.unicode)
                    else:
                        continue
                    
                    # Echo if requested (like CursesAdapter)
                    if echo:
                        if 32 <= char_code <= 126:  # Printable characters
                            self._put_char(chr(char_code))
                            self.refresh()
                        if char_code in (10, 13):  # Newline
                            self._newline()
                            self.refresh()
                    
                    logger.debug(f"Input char: {char_code}")
                    self._draw_cursor(False)
                    return char_code
                
                if event.type == pygame.MOUSEBUTTONDOWN and self._mouse_enabled:
                    pixel_x, pixel_y = pygame.mouse.get_pos()
                    x, y = pixel_x // self.char_width, pixel_y // self.char_height
                    boundary_top, boundary_left, boundary_bottom, boundary_right = self.mouse_boundary
                    if x < boundary_left or x >= boundary_right or y < boundary_top or y >= boundary_bottom:
                        continue
                    event_args = MouseClickEventArgs(x_coordinate=x, y_coordinate=y)
                    self.event_manager.on_mouse_click.invoke(self, event_args)
                    return MouseClick.SINGLE_CLICK
                
            cursor_blink_time, cursor_visible = self._update_cursor_blink(
                cursor_blink_time, cursor_visible, clock.get_time()
            )
            
            clock.tick(60)
    
    def get_input_string(self, prompt: str, lowercase: bool) -> str:
        """
        Get a string of input from the terminal.
        
        Args:
            prompt: Prompt to display
            lowercase: Whether to convert input to lowercase
            
        Returns:
            Input string
        """
        logger.debug(f"Getting input string with prompt: {prompt!r}")
        
        if prompt:
            self.write_to_screen(prompt)
        
        input_buffer = ""
        cursor_visible = False
        cursor_blink_time = 0
        
        clock = pygame.time.Clock()
        
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    logger.info("User closed window")
                    pygame.quit()
                    sys.exit(0)
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        self._draw_cursor(False)
                        self._newline()
                        self.refresh()
                        result = input_buffer.lower() if lowercase else input_buffer
                        logger.debug(f"Input string: {result!r}")
                        return result
                    
                    elif event.key == pygame.K_BACKSPACE:
                        if input_buffer:
                            input_buffer = input_buffer[:-1]
                            self._draw_cursor(False)
                            # Move cursor back and erase character
                            if self.cursor_x > 0:
                                self.cursor_x -= 1
                                self.screen_buffer[self.cursor_y][self.cursor_x] = Cell()
                                x = self.cursor_x * self.char_width
                                y = self.cursor_y * self.char_height
                                bg_rect = pygame.Rect(x, y, self.char_width, self.char_height)
                                pygame.draw.rect(self.screen, self.current_bg, bg_rect)
                            self.refresh()
                    
                    elif event.unicode and event.unicode.isprintable():
                        char = event.unicode
                        input_buffer += char
                        self._draw_cursor(False)
                        self._put_char(char)
                        self.refresh()
            
            # Blink cursor
            cursor_blink_time, cursor_visible = self._update_cursor_blink(
                cursor_blink_time, cursor_visible, clock.get_time()
            )
            
            clock.tick(60)
    
    def set_timeout(self, timeout_ms: int):
        """Set the input timeout in milliseconds."""
        logger.debug(f"Set timeout: {timeout_ms}ms")
        self.input_timeout_ms = timeout_ms
    
    def get_coordinates(self) -> tuple[int, int]:
        """Get the current cursor coordinates as (y, x) tuple."""
        return (self.cursor_y, self.cursor_x)
    
    def move_cursor(self, y_pos: int, x_pos: int):
        """Move the cursor to specified coordinates."""
        if logger.isEnabledFor(10):
            logger.debug(f"Move cursor: ({y_pos}, {x_pos})")
        
        self.cursor_y = max(0, min(y_pos, self._height - 1))
        self.cursor_x = max(0, min(x_pos, self._width - 1))
    
    def get_char_at(self, y_pos: int, x_pos: int) -> int:
        """Get the character code at specified coordinates."""
        if 0 <= y_pos < self._height and 0 <= x_pos < self._width:
            char = self.screen_buffer[y_pos][x_pos].char
            return ord(char) if char else 32
        return 32
    
    def paint_char_at(self, y_pos: int, x_pos: int, char: int):
        """Paint a character at specified coordinates with current attributes."""
        if 0 <= y_pos < self._height and 0 <= x_pos < self._width:
            char_str = chr(char) if 32 <= char <= 126 else ' '
            
            # Update buffer with current attributes
            self.screen_buffer[y_pos][x_pos] = Cell(
                char=char_str,
                fg=self.current_fg,
                bg=self.current_bg,
                style=self.current_style,
                font=self.current_font
            )
            
            # Render the cell
            x = x_pos * self.char_width
            y = y_pos * self.char_height
            self._render_cell(y_pos, x_pos, x, y)
    
    def erase_screen(self, background_color: int = Color.BLACK):
        """Erase the entire terminal screen."""
        logger.debug("Erase screen")
        
        self.screen_buffer = [[Cell() for _ in range(self._width)] 
                             for _ in range(self._height)]
        self.screen.fill(self._zcolor_to_rgb(background_color))
        self.cursor_x = 0
        self.cursor_y = 0
        self.refresh()
    
    def erase_window(self, top: int, height: int, background_color: int = Color.BLACK):
        """Erase a portion of the screen."""
        logger.debug(f"Erase window: top={top}, height={height}")

        color = self._zcolor_to_rgb(background_color)
        
        for row in range(top, min(top + height, self._height)):
            self.screen_buffer[row] = [Cell() for _ in range(self._width)]
        
        pixel_y = top * self.char_height
        pixel_height = height * self.char_height
        erase_rect = pygame.Rect(0, pixel_y, self.window_width, pixel_height)
        pygame.draw.rect(self.screen, color, erase_rect)
        self.refresh()
    
    def clear_to_eol(self):
        """Clear from cursor to end of line."""
        if logger.isEnabledFor(10):
            logger.debug(f"Clear to EOL from ({self.cursor_y}, {self.cursor_x})")
        
        for x in range(self.cursor_x, self._width):
            self.screen_buffer[self.cursor_y][x] = Cell()
        
        pixel_x = self.cursor_x * self.char_width
        pixel_y = self.cursor_y * self.char_height
        pixel_width = (self._width - self.cursor_x) * self.char_width
        erase_rect = pygame.Rect(pixel_x, pixel_y, pixel_width, self.char_height)
        pygame.draw.rect(self.screen, (0, 0, 0), erase_rect)
        self.refresh()
    
    def apply_style_attributes(self, attributes: int):
        """Apply text style attributes for subsequent output."""
        logger.debug(f"Apply style: {attributes}")
        self.current_style = attributes
    
    def apply_color_settings(self, background_color: int, foreground_color: int):
        """Set foreground and background colors for subsequent output."""
        logger.debug(f"Set color: bg={background_color}, fg={foreground_color}")
        
        self.current_bg = self._zcolor_to_rgb(background_color)
        self.current_fg = self._zcolor_to_rgb(foreground_color)

    def beep(self):
        self.beep_sound.play()

    def shutdown(self):
        """Cleanup pygame resources."""
        logger.info("Shutting down graphics adapter")
        pygame.quit()

    # ========================================================================
    # IGraphicsAdapter Protocol Implementation (duck typing)
    # ========================================================================

    def is_font_supported(self, font_id: int) -> bool:
        if font_id == FontEnum.PICTURE or font_id not in FontEnum:
            return False
        return True

    def apply_font(self, font: FontEnum):
        self.current_font = font

    def get_picture_size(self, number: int, resource_data: IResourceData) -> tuple[int, int]:
        """Get the width and height of a picture resource."""
        if not resource_data.is_valid_picture(number):
            return (0, 0)
        picture_data = resource_data.get_picture_data(number)
        surface = pygame.image.load(io.BytesIO(picture_data))
        return surface.get_size()
    
    def draw_picture(self, number: int, y: int, x: int, resource_data: IResourceData):
        picture_data = resource_data.get_picture_data(number)
        if len(picture_data) == 0:
            raise InvalidPictureResourceException(number)
        
        pixel_x = x * self.char_width
        pixel_y = y * self.char_height
        # TODO: Would probably be good to cache this.
        surface = pygame.image.load(io.BytesIO(picture_data))
        self.screen.blit(surface, (pixel_x, pixel_y))

    def load_sound_effect(self, number: int, sound_data: bytes):
        if number not in self._sound_resources and len(sound_data) > 0:
            self._sound_resources[number] = pygame.mixer.Sound(io.BytesIO(sound_data))
    
    def play_sound_effect(self, number: int, sound_data: bytes, volume: int, repeats: int, routine: int):
        """Play a sound effect."""
        logger.debug(f"Play sound effect: number {number}, volume {volume}, repeats {repeats}, routine {routine}")

        if pygame.mixer.get_busy():
            self.interrupt_sound_effect(0)
        self.load_sound_effect(number, sound_data)
        if number not in self._sound_resources:
            return
        sound = self._sound_resources[number]
        if volume < 0:
            sound.set_volume(1.0)
        else:
            sound.set_volume(volume / 8.0)
        loops = repeats if repeats <= 0 else repeats - 1
        self.sound_channel.play(sound, loops = loops)
        self._pending_routine = routine
        self._current_sound_number = number

    def interrupt_sound_effect(self, number: int):
        if number in (0, self._current_sound_number):
            self._sound_interrupted = True
            self.sound_channel.stop()

    def unload_sound_effect(self, number: int):
        self.interrupt_sound_effect(number)
        if number == 0:
            self._sound_resources.clear()
        elif number in self._sound_resources:
            del self._sound_resources[number]

    def set_mouse_boundary(self, top: int, left: int, bottom: int, right: int):
        self.mouse_boundary = (top, left, bottom, right)
    
    # ========================================================================
    # Internal Helper Methods
    # ========================================================================
    
    def _render_cell(self, row: int, col: int, pixel_x: int, pixel_y: int):
        """Render a single cell with its stored attributes."""
        cell = self.screen_buffer[row][col]
        fg = cell.fg
        bg = cell.bg
        
        # Handle reverse video (swap fg/bg)
        if cell.style & 0x01:
            fg, bg = bg, fg
        
        # Clear background
        bg_rect = pygame.Rect(pixel_x, pixel_y, self.char_width, self.char_height)
        pygame.draw.rect(self.screen, bg, bg_rect)

        if cell.font == FontEnum.GRAPHICS:
            self._render_font3(row, col, pixel_x, pixel_y)
            return
        
        # Render character
        if cell.char != ' ':
            # Handle bold
            bold = bool(cell.style & 0x02)
            self.font.set_bold(bold)
            
            # Handle italic
            italic = bool(cell.style & 0x04)
            self.font.set_italic(italic)
            
            char_surface = self.font.render(cell.char, True, fg)
            self.screen.blit(char_surface, (pixel_x, pixel_y))
            
            # Reset font styles
            self.font.set_bold(False)
            self.font.set_italic(False)
    
    def _put_char(self, char: str):
        """Put a single character at cursor position with current style."""
        if self.cursor_x >= self._width:
            self._newline()
        
        if self.cursor_y >= self._height:
            self._scroll_up()
        
        # Update buffer with character AND current style
        self.screen_buffer[self.cursor_y][self.cursor_x] = Cell(
            char=char,
            fg=self.current_fg,
            bg=self.current_bg,
            style=self.current_style,
            font = self.current_font
        )
        
        # Render the cell
        x = self.cursor_x * self.char_width
        y = self.cursor_y * self.char_height
        self._render_cell(self.cursor_y, self.cursor_x, x, y)
        
        self.cursor_x += 1
    
    def _newline(self):
        """Move cursor to next line."""
        self.cursor_x = 0
        self.cursor_y += 1
        self._at_wrap_boundary = False

        if self.cursor_y >= self._height:
            self._scroll_up()
    
    def _scroll_up(self):
        """Scroll screen up by one line (in scrollable region)."""
        logger.debug("Scrolling up")
        
        if self.scroll_top > 0:
            # Keep top lines, scroll the rest
            top_lines = self.screen_buffer[:self.scroll_top]
            scrollable_lines = self.screen_buffer[self.scroll_top:]
            self.screen_buffer = (top_lines + 
                                 scrollable_lines[1:] + 
                                 [[Cell() for _ in range(self._width)]])
        else:
            # Scroll entire screen
            self.screen_buffer = (self.screen_buffer[1:] + 
                                 [[Cell() for _ in range(self._width)]])
        
        self.cursor_y = self._height - 1
        self._redraw_all()
    
    def _redraw_all(self):
        """Redraw entire screen from buffer."""
        self.screen.fill((0, 0, 0))
        
        for row in range(self._height):
            for col in range(self._width):
                x = col * self.char_width
                y = row * self.char_height
                self._render_cell(row, col, x, y)
    
    def _draw_cursor(self, visible: bool):
        """Draw or erase cursor."""
        x = self.cursor_x * self.char_width
        y = self.cursor_y * self.char_height
        
        if visible:
            cursor_rect = pygame.Rect(x, y + self.char_height - 2, 
                                     self.char_width, 2)
            pygame.draw.rect(self.screen, self.current_fg, cursor_rect)
        else:
            cursor_rect = pygame.Rect(x, y + self.char_height - 2, 
                                     self.char_width, 2)
            pygame.draw.rect(self.screen, self.current_bg, cursor_rect)

    def _update_cursor_blink(self, cursor_blink_time: int, cursor_visible: bool, dt: int) -> tuple[int, bool]:
        """Update cursor blink state. Returns (new_blink_time, new_visible)."""
        cursor_blink_time += dt
        if cursor_blink_time > 500:
            cursor_blink_time = 0
            cursor_visible = not cursor_visible
            self._draw_cursor(cursor_visible)
            pygame.display.flip()
        return cursor_blink_time, cursor_visible
    
    def _zcolor_to_rgb(self, zcolor: int) -> tuple:
        """Convert Z-Machine color code to RGB tuple."""
        colors = {
            Color.BLACK:       (0, 0, 0),
            Color.RED:         (248, 0, 0),
            Color.GREEN:       (0, 236, 0),
            Color.YELLOW:      (248, 248, 0),
            Color.BLUE:        (0, 173, 219),
            Color.MAGENTA:     (255, 0, 255),
            Color.CYAN:        (0, 248, 248),
            Color.WHITE:       (255, 255, 255),
            Color.LIGHT_GRAY:  (219, 219, 219),
            Color.MEDIUM_GRAY: (195, 195, 195),
            Color.DARK_GRAY:   (161, 161, 161)
        }
        return colors.get(Color(zcolor), (219, 219, 219))
    
    def _render_font3(self, row: int, col: int, left: int, top: int):
        cell = self.screen_buffer[row][col]

        c = ord(cell.char)
        if c >= 32 and c <= 126:
            bitmap = FONT3_BITMAP[c]
            scale_x = self.char_width / 8.0
            scale_y = self.char_height / 8.0
            pixel_top = top
            for y in range(8):
                row_bit = 0x80
                pixel_left = left
                pixel_height = int((y + 1) * scale_y) - int(y * scale_y)
                for x in range(8):
                    if (bitmap[y] << x) & 0xff == 0:
                        break
                    pixel_width = int((x + 1) * scale_x) - int(x * scale_x)
                    if bitmap[y] & row_bit == row_bit:
                        pixel_rect = pygame.Rect(pixel_left, pixel_top, pixel_width, pixel_height)
                        pygame.draw.rect(self.screen, cell.fg, pixel_rect)
                    pixel_left += pixel_width
                    row_bit >>= 1
                pixel_top += pixel_height

    def _make_beep(self, frequency: int = 440, duration_ms: int = 200, volume: float = 0.3) -> pygame.mixer.Sound:
        """Generate a simple sine wave beep."""
        sample_rate = 44100
        num_samples = int(sample_rate * duration_ms / 1000)
        
        t = np.linspace(0, duration_ms / 1000, num_samples, False)
        wave = np.sin(2 * np.pi * frequency * t) * volume
        
        # Convert to 16-bit signed integers
        wave = (wave * 32767).astype(np.int16)
        
        # pygame expects stereo
        stereo = np.column_stack([wave, wave])
        
        return pygame.sndarray.make_sound(stereo)
