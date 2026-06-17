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
from typing import Final
from enum import IntEnum, auto
from .protocol import IResourceData
from .event import EventManager, MouseClickEventArgs, RoutineCallEventArgs
from .config import ZMachineConfig
from .settings import RuntimeSettings
from .enums import Color, FontEnum, FunctionKey, StoryEnum, MouseClick
from .constants import FONT3_BITMAP, DEFAULT_FONT_SIZE
from .error import ZMachineException, InvalidPictureResourceException, CursorOutOfBoundsException
from .logging import graphics_logger as logger


class UnitEnum(IntEnum):
    """Indicates if the screen units are measured in characters (up to v5) or pixels (v6)"""
    Character = auto()
    Pixel = auto()

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
        self.screen_width_pixels: Final[int] = window_width
        self.screen_height_pixels: Final[int] = window_height
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
            self.font = pygame.font.SysFont('dejavusansmono', DEFAULT_FONT_SIZE)
            logger.debug("Using DejaVu Sans Mono font")
        except:
            self.font = pygame.font.Font(None, 16)
            logger.debug("Using default font")
        
        # Calculate character dimensions
        test_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz,;_0123456789'
        max_height = self.font.get_height()
        min_descent = 0
        for metric in self.font.metrics(test_chars):
            _, _, miny, maxy, _ = metric
            max_height = max(max_height, miny)
            min_descent = min(min_descent, maxy)
        metrics = self.font.metrics('M')
        self.char_width_pixels: Final[int] = metrics[0][4]
        self.char_height_pixels: Final[int] = max(max_height, max_height - min_descent)

        logger.info(f"Character dimensions: {self.char_width_pixels}x{self.char_height_pixels}")
        
        # Up to version 5, height/width units are characters.
        # For version 6, units are pixels.
        self.unit: Final[UnitEnum] = UnitEnum.Character if config.version <= 5 else UnitEnum.Pixel
        self.char_width_units: Final[int] = self.char_width_pixels if self.unit == UnitEnum.Pixel else 1
        self.char_height_units: Final[int] = self.char_height_pixels if self.unit == UnitEnum.Pixel else 1
        self.screen_width_units: Final[int] = \
            self.screen_width_pixels if self.unit == UnitEnum.Pixel else self.screen_width_pixels // self.char_width_pixels
        self.screen_height_units: Final[int] = \
            self.screen_height_pixels if self.unit == UnitEnum.Pixel else self.screen_height_pixels // self.char_height_pixels

        logger.info(f"Screen size: {self.width} cols x {self.height} rows")
        
        self.cursor_x: int = 0
        # The x-cursor in units.
        self.cursor_y: int = 0
        # The y cursor in units.
        self._cursor_enabled = True
        # Toggle cursor visibility.
        self._scrolling_enabled = True
        # Toggle window scrolling on/off.
        self._line_cache = pygame.Surface((0, 0))
        # Cache the bottom output line.
        
        # Current text attributes (for new characters)
        self.current_fg: tuple[int, ...] = (219, 219, 219)   # Light gray (Z-color 10)
        self.current_bg: tuple[int, ...] = (0, 0, 0)         # Black (Z-color 2)
        self.current_style = 0
        
        # Scrolling region (for split-window support)
        self.scrollable_region = pygame.Rect(0, 0, self.screen_width_pixels, self.screen_height_pixels)
        
        # Input timeout (milliseconds)
        self.input_timeout_ms = 0

        # Mouse boundaries (top, left, bottom, right)
        self.mouse_region = pygame.Rect(0, 0, self.screen_width_pixels, self.screen_height_pixels)

        # Printable region
        self.print_region = pygame.Rect(0, 0, self.screen_width_pixels, self.screen_height_pixels)

        # Configure sound resources.
        self.sound_channel = pygame.mixer.Channel(0)
        self.sound_channel.set_endevent(self.SOUND_END_EVENT)
        self._pending_routine: int = 0
        self._sound_interrupted: bool = False
        self._current_sound_number: int = 0
        self._sound_resources: dict[int, pygame.mixer.Sound] = {}

        # Configure graphics resources.
        self._current_palette: list[pygame.Color] = [pygame.Color(0, 0, 0)] * 16
        
        # Clear screen
        self.screen.fill(self.current_bg)
        pygame.display.flip()
        
        logger.info("Graphics adapter initialized successfully")
    
    # ========================================================================
    # ITerminalAdapter Protocol Implementation (duck typing)
    # ========================================================================
    
    @property
    def height(self) -> int:
        """The height of the terminal in units."""
        return self.screen_height_units
    
    @property
    def width(self) -> int:
        """The width of the terminal in units."""
        return self.screen_width_units
    
    @property
    def font_size(self) -> int:
        return (self.char_height_units << 8) | self.char_width_units
    
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
        if self.unit == UnitEnum.Pixel:
            logger.warning("Avoid set_scrollable_height for pixel display, use GraphicsAdapter.set_scrollable_region instead")
        else:
            top *= self.char_height_pixels
        if top == self.screen_height_pixels:
            self.scrolling_enabled = False
        else:
            self.scrolling_enabled = True
            self.set_scrollable_region(0, top, self.screen_width_pixels, self.screen_height_pixels - top)
    
    def write_to_screen(self, text: str):
        """Write text directly to the terminal."""
        if logger.isEnabledFor(10):  # DEBUG level
            logger.debug(f"Write: {text!r}")
        
        self._at_wrap_boundary = False
        for char in text:
            if char == '\n':
                self._newline()
            else:
                self._put_char(char)
        
        _, cursor_x = self.get_pixel_coordinates()
        if len(text) > 0 and text[-1] != '\n' and cursor_x == self.print_region.left:
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
                        char_code = int(event.key) - pygame.K_F1 + FunctionKey.F1
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
                    x, y = pygame.mouse.get_pos()
                    if not self.mouse_region.collidepoint((x, y)):
                        continue
                    x_coordinate = x if self.unit == UnitEnum.Pixel else x // self.char_width_pixels
                    y_coordinate = y if self.unit == UnitEnum.Pixel else y // self.char_height_pixels
                    event_args = MouseClickEventArgs(x_coordinate, y_coordinate)
                    self.event_manager.on_mouse_click.invoke(self, event_args)
                    return MouseClick.SINGLE_CLICK

            if self.cursor_enabled:
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
                                self.cursor_x -= self.char_width_units
                                cursor_y, cursor_x = self.get_pixel_coordinates()
                                bg_rect = pygame.Rect(cursor_x, cursor_y, self.char_width_pixels, self.char_height_pixels)
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
        
        self.cursor_y = max(0, min(y_pos, self.screen_height_units - 1))
        self.cursor_x = max(0, min(x_pos, self.screen_width_units - 1))

    def move_cursor_to_line_start(self):
        """Move the cursor to the left margin of the current line."""
        left = self.print_region.left
        self.cursor_x = left if self.unit == UnitEnum.Pixel else left // self.char_width_pixels

    def cache_current_line(self):
        y, x = self.get_pixel_coordinates()
        left = self.print_region.left
        region = pygame.Rect(left, y, x - left, self.char_height_pixels)
        self._line_cache = self.screen.subsurface(region).copy()

    def uncache_current_line(self):
        y, _ = self.get_pixel_coordinates()
        left = self.print_region.left
        self.screen.blit(self._line_cache, (left, y))
        cursor_x = left + self._line_cache.get_width()
        if self.unit == UnitEnum.Character:
            cursor_x //= self.char_width_pixels
        self.cursor_x = cursor_x
    
    def erase_screen(self, background_color: int = Color.BLACK):
        """Erase the entire terminal screen."""
        logger.debug("Erase screen")
        
        self.screen.fill(self._zcolor_to_rgb(background_color))
        self.cursor_x = 0
        self.cursor_y = 0
        self.refresh()
    
    def erase_window(self, left: int, top: int, width: int, height: int, background_color: int = Color.BLACK):
        """Erase a portion of the screen."""
        logger.debug(f"Erase window: top={top}, height={height}, left={left}, width={width}")

        color = self._zcolor_to_rgb(background_color)
        
        erase_rect = pygame.Rect(left, top, width, height)
        pygame.draw.rect(self.screen, color, erase_rect)
        self.refresh()
    
    def clear_to_eol(self):
        """Clear from cursor to end of line."""
        if logger.isEnabledFor(10):
            logger.debug(f"Clear to EOL from ({self.cursor_y}, {self.cursor_x})")
        
        cursor_y, cursor_x = self.get_pixel_coordinates()
        erase_rect = pygame.Rect(cursor_x, cursor_y, self.print_region.right - cursor_x, self.char_height_pixels)
        pygame.draw.rect(self.screen, self.current_bg, erase_rect)
        self.refresh()
    
    def apply_style_attributes(self, attributes: int):
        """Apply text style attributes for subsequent output."""
        logger.debug(f"Apply style: {attributes}")
        self.current_style = attributes
    
    def apply_color_settings(self, background_color: int, foreground_color: int):
        """Set foreground and background colors for subsequent output."""
        logger.debug(f"Set color: bg={background_color}, fg={foreground_color}")
        cursor_y, cursor_x = self.get_pixel_coordinates()

        if background_color == -1:
            self.current_bg = tuple(self.screen.get_at((cursor_x, cursor_y)))
        else:    
            self.current_bg = self._zcolor_to_rgb(background_color)
        if foreground_color == -1:
            raise ZMachineException('Current foreground color is not supported')
        else:
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
    @property
    def cursor_enabled(self) -> bool:
        return self._cursor_enabled

    @cursor_enabled.setter
    def cursor_enabled(self, value: bool):
        self._cursor_enabled = value

    @property
    def scrolling_enabled(self) -> bool:
        return self._scrolling_enabled

    @scrolling_enabled.setter
    def scrolling_enabled(self, value: bool):
        self._scrolling_enabled = value

    def is_font_supported(self, font_id: int) -> bool:
        if font_id == FontEnum.PICTURE or font_id not in FontEnum:
            return False
        return True

    def apply_font(self, font: FontEnum):
        self.current_font = font

    def erase_line(self, width: int):
        cursor_y, cursor_x = self.get_coordinates()
        rect = pygame.Rect(cursor_x + self.char_width_pixels, cursor_y, width, self.char_height_pixels)
        self.screen.subsurface(rect).fill(self.current_bg)

    def get_picture_size(self, number: int, resource_data: IResourceData) -> tuple[int, int]:
        """Get the width and height of a picture resource."""
        if not resource_data.is_valid_picture(number):
            return (0, 0)
        picture_data = resource_data.get_picture_data(number)
        scaling_ratio = resource_data.get_scaling_ratio(number, self.screen_width_pixels, self.screen_height_pixels)
        if len(picture_data) == 8:
            width = int.from_bytes(picture_data[0:4], "big")
            height = int.from_bytes(picture_data[4:8], "big")
        else:
            surface = pygame.image.load(io.BytesIO(picture_data))
            width, height = surface.get_size()
        return int(width * scaling_ratio), int(height * scaling_ratio)
    
    def draw_picture(self, number: int, top: int, left: int, resource_data: IResourceData):
        picture_data = resource_data.get_picture_data(number)
        if len(picture_data) == 0:
            raise InvalidPictureResourceException(number)
        
        scaling_ratio = resource_data.get_scaling_ratio(number, self.screen_width_pixels, self.screen_height_pixels)
        
        # TODO: Would probably be good to cache this.
        surface = pygame.image.load(io.BytesIO(picture_data))
        if scaling_ratio != 1:
            scaled_width = scaling_ratio * surface.get_width()
            scaled_height = scaling_ratio * surface.get_height()
            surface = pygame.transform.scale(surface, (scaled_width, scaled_height))

        if surface.get_bitsize() <= 8:
            if resource_data.is_adaptive_picture(number):
                surface.set_palette(self._current_palette)
                surface = surface.convert()
            else:
                palette = surface.get_palette()
                for i in range(2, min(len(palette), 16)):
                    self._current_palette[i] = palette[i]
        self.screen.blit(surface, (left, top))

    def erase_picture(self, number: int, top: int, left: int, resource_data: IResourceData):
        if not resource_data.is_valid_picture(number):
            raise InvalidPictureResourceException(number)
        
        width, height = self.get_picture_size(number, resource_data)
        rect = pygame.Rect(left, top, width, height)
        self.screen.subsurface(rect).fill(self.current_bg)

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

    def scroll_window(self, left: int, top: int, width: int, height: int, pixels: int):
        """Scroll the given area, regardless of the value of scrolling_enabled."""
        scroll_rect = pygame.Rect(left, top, width, height)
        self.screen.subsurface(scroll_rect).scroll(0, -pixels)
        blank_top = top + height - pixels if pixels > 0 else top
        blank_rect = pygame.Rect(left, blank_top, width, abs(pixels))
        self.screen.subsurface(blank_rect).fill(self.current_bg)

    def set_print_region(self, left: int, top: int, width: int, height: int):
        logger.info(f'Setting print region to ({left}, {top}, {width}, {height})')
        self.print_region = pygame.Rect(left, top, width, height)

    def set_scrollable_region(self, left: int, top: int, width: int, height: int):
        logger.info(f'Setting scroll region to ({left}, {top}, {width}, {height})')
        self.scrolling_enabled = True
        self.scrollable_region = pygame.Rect(left, top, width, height)

    def set_mouse_region(self, left: int, top: int, width: int, height: int):
        logger.info(f'Setting mouse region to ({left}, {top}, {width}, {height})')
        self.mouse_region = pygame.Rect(left, top, width, height)
    
    # ========================================================================
    # Internal Helper Methods
    # ========================================================================

    def get_pixel_coordinates(self) -> tuple[int, int]:
        """Pixel coordinates of the cursor (y, x)"""
        if self.unit == UnitEnum.Pixel:
            return self.cursor_y, self.cursor_x
        return self.cursor_y * self.char_height_pixels, self.cursor_x * self.char_width_pixels
    
    def _put_char(self, char: str):
        """Put a single character at cursor position with current style."""
        if self.current_font == FontEnum.GRAPHICS:
            self._render_font3(char)
            return

        cursor_y, cursor_x = self.get_pixel_coordinates()
        reverse_style = bool(self.current_style & 1)
        fg = self.current_bg if reverse_style else self.current_fg
        bg = self.current_fg if reverse_style else self.current_bg
        font = self.font

        # Clear the background
        bg_rect = pygame.Rect(cursor_x, cursor_y, self.char_width_pixels, self.char_height_pixels)
        pygame.draw.rect(self.screen, bg, bg_rect)
        
        # Render the character
        if char != ' ':
            # Handle bold
            bold = bool(self.current_style & 0x02)
            font.set_bold(bold)
            
            # Handle italic
            italic = bool(self.current_style & 0x04)
            font.set_italic(italic)
            
            char_surface = font.render(char, True, fg)
            self.screen.blit(char_surface, (cursor_x, cursor_y))
        
        self.cursor_x += self.char_width_units
        max_x = self.print_region.right // self.char_width_pixels if self.unit == UnitEnum.Character else self.print_region.right
        if self.cursor_x + self.char_width_units - 1 >= max_x:
            self._newline()
    
    def _newline(self):
        """Move cursor to next line."""
        left_margin_pixels = self.print_region.left
        left_margin_units = left_margin_pixels if self.unit == UnitEnum.Pixel else left_margin_pixels // self.char_width_pixels
        self.cursor_x = left_margin_units

        cursor_y, _ = self.get_pixel_coordinates()
        num_lines = self.print_region.height // self.char_height_pixels
        max_y = min(self.print_region.bottom, self.print_region.top + num_lines * self.char_height_pixels)
        if cursor_y + self.char_height_pixels >= max_y:
            if not self.print_region.collidepoint(left_margin_pixels, cursor_y):
                raise CursorOutOfBoundsException(left_margin_pixels, cursor_y)
            if self.scrollable_region.collidepoint(left_margin_pixels, cursor_y):
                self._scroll_up()
        else:
            self.cursor_y += self.char_height_units
    
    def _scroll_up(self):
        """Scroll screen up by one line (in scrollable region)."""
        if not self.scrolling_enabled:
            return
        logger.debug("Scrolling up")
        self.screen.subsurface(self.scrollable_region).scroll(0, -self.char_height_pixels)
        line_count = self.scrollable_region.height // self.char_height_pixels
        bottom_line = pygame.Rect(self.scrollable_region.left,
                                  self.scrollable_region.top + self.char_height_pixels * (line_count - 1),
                                  self.scrollable_region.width,
                                  self.char_height_pixels)
        self.screen.subsurface(bottom_line).fill(self.current_bg)

    def _draw_cursor(self, visible: bool):
        """Draw or erase cursor."""
        cursor_y, cursor_x = self.get_pixel_coordinates()
        cursor_rect = pygame.Rect(cursor_x, cursor_y + self.char_height_pixels - 2, self.char_width_pixels, 2)
        
        if visible:
            pygame.draw.rect(self.screen, self.current_fg, cursor_rect)
        else:
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
    
    def _render_font3(self, char: str):
        top, left = self.get_pixel_coordinates()

        # Clear the background
        bg_rect = pygame.Rect(left, top, self.char_width_pixels, self.char_height_pixels)
        pygame.draw.rect(self.screen, self.current_bg, bg_rect)

        c = ord(char)
        if c >= 32 and c <= 126:
            bitmap = FONT3_BITMAP[c]
            scale_x = self.char_width_pixels / 8.0
            scale_y = self.char_height_pixels / 8.0
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
                        pygame.draw.rect(self.screen, self.current_fg, pixel_rect)
                    pixel_left += pixel_width
                    row_bit >>= 1
                pixel_top += pixel_height
        self.cursor_x += self.char_width_units

        _, cursor_x = self.get_pixel_coordinates()
        if cursor_x + self.char_width_pixels >= self.print_region.right:
            self._newline()

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
