from collections.abc import Iterator
from .error import InvalidScreenOperationException
from .event import EventManager, EventArgs, RoutineCallEventArgs
from .enums import TextStyle, FontEnum, SoundEffectEnum
from .protocol import ITerminalAdapter, IGraphicsAdapter, IResourceData
from .logging import screen_logger as logger
from .constants import SUPPORTED_VERSIONS, PAUSE_DISABLED_SENTINEL, DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR
from .window import Window

class BaseScreen:
    _TEXT_BUFFER_LENGTH = 1024
    def __init__(self, terminal_adapter: ITerminalAdapter, resource_data: IResourceData, event_manager: EventManager):
        self._version = 0
        self.terminal_adapter = terminal_adapter
        self.event_manager = event_manager
        self._resource_data = resource_data
        self.height = terminal_adapter.height
        self.width = terminal_adapter.width
        self.windows: list[Window] = self.init_windows()
        self._active_window_id: int = 0
        self.text_buffer = ['\0'] * self._TEXT_BUFFER_LENGTH
        self.text_buffer_ptr = 0
        self.register_delegates()

    def register_delegates(self):
        self.event_manager.pre_read_input += self.pre_read_input_handler
        self.event_manager.post_read_input += self.post_read_input_handler
        self.event_manager.on_select_output_stream += self.on_select_output_stream_handler
        self.event_manager.on_quit += self.on_quit_handler

    @property
    def version(self) -> int:
        if self._version not in SUPPORTED_VERSIONS:
            raise NotImplementedError("Version property must be implemented by subclass.")
        return self._version

    def init_windows(self) -> list[Window]:
        font_size = self.terminal_adapter.font_size
        lower_window = Window(self.height, self.width, font_size)
        lower_window.window_attributes = 0xf
        upper_window = Window(0, self.width, font_size)
        return [lower_window, upper_window]

    def get_window(self, window_id: int) -> Window:
        if window_id == -3:
            return self.active_window
        elif 0 <= window_id < len(self.windows):
            return self.windows[window_id]
        raise InvalidScreenOperationException(f"Invalid window id {window_id}")

    @property
    def active_window(self) -> Window:
        if self._active_window_id >= len(self.windows):
            raise InvalidScreenOperationException(f"Active window id {self._active_window_id} is invalid")
        return self.windows[self._active_window_id]
    
    @active_window.setter
    def active_window(self, window: Window):
        for i in range(len(self.windows)):
            if self.windows[i] == window:
                self._active_window_id = i
                return
        raise InvalidScreenOperationException(f"Active window is invalid")

    @property
    def pause_enabled(self) -> bool:
        return self.active_window.line_count != PAUSE_DISABLED_SENTINEL
    
    @pause_enabled.setter
    def pause_enabled(self, value: bool):
        if value and self.active_window.line_count == PAUSE_DISABLED_SENTINEL:
            self.active_window.line_count = 0
        elif not value:
            self.active_window.line_count = PAUSE_DISABLED_SENTINEL

    def set_buffer_mode(self, value: bool):
        window_id = 0
        logger.info(f"Setting buffer mode to {value} in window {window_id}")
        window = self.windows[window_id]
        window.buffered_printing = value
        if not value and window == self.active_window:
            self.flush_buffer()

    @property
    def transcript_output_enabled(self) -> bool:
        return self.active_window.transcript_enabled
    
    @property
    def resource_data(self) -> IResourceData:
        return self._resource_data
    
    def restart_screen(self):
        self.erase_window(0)

    def reset_output_line_count(self):
        self.active_window.line_count = 0

    def pre_read_input_handler(self, sender, event_args: EventArgs):
        self.flush_buffer()
        self.terminal_adapter.refresh()

    def post_read_input_handler(self, sender, event_args: EventArgs):
        self.reset_output_line_count()

    def refresh_status_line(self, location: str, status: str):
        raise NotImplementedError(f"Status line is not implemented in v{self.version} screen.")
        
    def set_window(self, window_id: int):
        logger.info(f"Setting active window to {window_id}")
        if window_id >= len(self.windows):
            raise InvalidScreenOperationException(f"Invalid window id: {window_id}")
        self.flush_buffer()
        self.set_active_window(self.windows[window_id])
        
    def split_window(self, lines: int):
        logger.info(f"Splitting window at line {lines}")
        lower_window, upper_window = self.windows[:2]
        self.flush_buffer()
        self.store_cursor_coordinates()
        lower_window.height = self.height - lines
        lower_window.y_pos = lines + 1
        lower_window.y_cursor += upper_window.height - lines
        upper_window.height = lines
        if upper_window.y_cursor > upper_window.height:
            self.reset_cursor(upper_window)
            if self.active_window == upper_window:
                self.set_cursor_to_active_window()
        if lower_window.y_cursor <= 0:
            lower_window.y_cursor = 1
            if self.active_window == lower_window:
                self.set_cursor_to_active_window()
        self.terminal_adapter.set_scrollable_height(lower_window.y_pos - 1)
        self.terminal_adapter.refresh()

    def erase_window(self, window_id: int): 
        self.flush_buffer()
        if window_id == -2:
            self.terminal_adapter.erase_screen()
            self.windows[0].line_count = 0
            self.reset_cursor(self.windows[0])
        elif window_id == -1:
            self.terminal_adapter.erase_screen()
            self.windows[0].line_count = 0
            self.split_window(0)
            self.reset_cursor(self.windows[0])
        else:
            window = self.get_window(window_id)
            self.erase(window)
        self.set_cursor_to_active_window()
        self.terminal_adapter.refresh()

    def sound_effect(self, number: int, effect: int, volume: int, repeats: int, routine: int): 
        if number in (1, 2):
            self.terminal_adapter.beep()
        if not isinstance(self.terminal_adapter, IGraphicsAdapter):
            return
        graphics_adapter: IGraphicsAdapter = self.terminal_adapter
        if effect == SoundEffectEnum.PREPARE:
            sound_data = self.resource_data.get_sound_data(number)
            if len(sound_data) > 0:
                graphics_adapter.load_sound_effect(number, sound_data)
        elif effect == SoundEffectEnum.PLAY:
            sound_data = self.resource_data.get_sound_data(number)
            if len(sound_data) > 0:
                graphics_adapter.play_sound_effect(number, sound_data, volume, repeats, routine)
        elif effect == SoundEffectEnum.INTERRUPT:
            graphics_adapter.interrupt_sound_effect(number)
        elif effect == SoundEffectEnum.UNLOAD:
            graphics_adapter.unload_sound_effect(number)

    def get_cursor(self) -> tuple[int, int]:
        raise NotImplementedError(f"Get cursor is not implemented in v{self.version} screen.")

    def set_cursor(self, y_cursor: int, x_cursor: int, window_id: int = -3):
        raise NotImplementedError(f"Set cursor is not implemented in v{self.version} screen.")

    def set_text_style(self, style: int):
        raise NotImplementedError(f"Text style is not implemented in v{self.version} screen.")

    def set_color(self, foreground_color: int, background_color: int, window_id: int = -3):
        raise NotImplementedError(f"Set color is not implemented in v{self.version} screen.")

    def erase_line(self, value: int):
        raise NotImplementedError(f"Erase line is not implemented in v{self.version} screen.")

    def set_font(self, font_id: int, window_id: int = -3) -> int:
        raise NotImplementedError(f"Set font is not implemented in v{self.version} screen.")

    def print_table(self, table: list[str]):
        raise NotImplementedError(f"Print table is not implemented in v{self.version} screen.")

    def set_mouse_window(self, window_id: int):
        raise NotImplementedError(f"Mouse window is not implemented in v{self.version} screen.")
    
    def get_picture_size(self, number: int) -> tuple[int, int]:
        raise NotImplementedError(f"Picture dimensions is not implemented in v{self.version} screen.")
    
    def draw_picture(self, number: int, y: int = 0, x: int = 0):
        raise NotImplementedError(f'Draw picture is not implemented in v{self.version} screen.')
    
    def erase_picture(self, number: int, y: int = 0, x: int = 0):
        raise NotImplementedError(f'Erase picture is not implemented in v{self.version} screen.')

    def set_cursor_enabled(self, value: bool):
        raise NotImplementedError(f'Cursor enable is not implemented in v{self.version} screen.')
    
    def move_window(self, window_id: int, y: int, x: int):
        raise NotImplementedError(f'Move window is not implemented in v{self.version} screen.')
    
    def set_margins(self, left: int, right: int, window_id: int = -3):
        raise NotImplementedError(f'Set margins is not implemented in v{self.version} screen.')

    def resize_window(self, window_id: int, y: int, x: int):
        raise NotImplementedError(f'Resize window is not implemented in v{self.version} screen.')
    
    def set_window_attributes(self, window_id: int, flags: int, operation: int = 0):
        raise NotImplementedError(f'Set window attributes is not implemented in v{self.version} screen.')
    
    def scroll_window(self, window_id: int, pixels: int):
        raise NotImplementedError(f'Scroll window not implemented in v{self.version} screen')

    def get_window_property(self, window_id: int, property_number: int) -> int:
        window = self.get_window(window_id)
        if property_number in (4, 5) and window == self.active_window:
            # If reading the cursor coordinates for the active window,
            # flush the buffer first for an accurate read.
            self.store_cursor_coordinates()
        return window.get_property(property_number)

    def put_window_property(self, window_id: int, property_number: int, value: int):
        window = self.get_window(window_id)
        window.set_property(property_number, value)

    def on_select_output_stream_handler(self, sender, e: EventArgs):
        self.flush_buffer()

    def on_quit_handler(self, sender, e: EventArgs):
        self.set_active_window(self.windows[0])
        self.flush_buffer()
        self.terminal_adapter.write_to_screen("\n[Press any key to exit.]")
        self.terminal_adapter.refresh()
        self.terminal_adapter.get_input_char(False)
        self.terminal_adapter.shutdown()

    def print(self, text: str, newline: bool = False):
        window = self.active_window
        if window.buffered_printing:
            self.write_to_buffer(text, newline)
        else:
            self.flush_buffer()
            self.apply_text_settings(self.active_window)
            if not window.wrapping:
                _, cursor_x = self.terminal_adapter.get_coordinates()
                char_width = self.terminal_adapter.font_size & 0xff
                right_margin_position = window.x_pos + window.width - window.right_margin - 1
                available_width_chars = (right_margin_position - cursor_x) // char_width
                if len(text) >= available_width_chars:
                    text = text[:available_width_chars]
            self.terminal_adapter.write_to_screen(text)
            if newline:
                self.terminal_adapter.write_to_screen("\n")
            self.terminal_adapter.refresh()

    def apply_text_settings(self, window: Window):
        pass
    
    def set_cursor_to_active_window(self):
        """Move the cursor to the coordinates stored in the active window."""
        self.flush_buffer()
        active_window = self.active_window
        top, left = active_window.y_pos - 1, active_window.x_pos - 1
        relative_y, relative_x = active_window.y_cursor - 1, active_window.x_cursor - 1
        abs_y, abs_x = relative_y + top, relative_x + left
        logger.debug(f"Setting cursor to y: {abs_y}, x: {abs_x}")
        self.terminal_adapter.move_cursor(abs_y, abs_x)

    def store_cursor_coordinates(self):
        """Store the current cursor coordinates in the active window."""
        active_window = self.active_window
        self.flush_buffer()
        abs_y, abs_x = self.terminal_adapter.get_coordinates()
        top, left = active_window.y_pos - 1, active_window.x_pos - 1
        relative_y, relative_x = abs_y - top, abs_x - left
        if 0 <= relative_y < active_window.height and 0 <= relative_x < active_window.width:
            # Only store if the cursor is in the boundaries of the window.
            # Otherwise do nothing.
            active_window.y_cursor = relative_y + 1
            active_window.x_cursor = relative_x + 1

    def reset_cursor(self, window: Window):
        lower_window, upper_window = self.windows
        if window == upper_window:
            window.y_cursor, window.x_cursor = 1, 1
        elif window == lower_window:
            window.y_cursor, window.x_cursor = window.height, 1

    def set_active_window(self, window: Window):
        if window == self.active_window:
            return
        self.store_cursor_coordinates()
        self.active_window = window
        self.set_cursor_to_active_window()
        self.apply_text_settings(window)

    def erase(self, window: Window):
        left = window.x_pos - 1
        top = window.y_pos - 1
        width = window.width
        height = window.height
        self.terminal_adapter.erase_window(left, top, width, height)
        window.line_count = 0
        self.reset_cursor(window)

    def write_to_buffer(self, text: str, newline: bool):
        text_len = len(text)
        while self.text_buffer_ptr + text_len + 1 >= len(self.text_buffer):
            self.text_buffer += ['\0'] * self._TEXT_BUFFER_LENGTH
        prev_ptr = self.text_buffer_ptr
        next_ptr = self.text_buffer_ptr + text_len
        self.text_buffer[prev_ptr:next_ptr] = text
        if newline:
            self.text_buffer[next_ptr] = "\n"
            next_ptr += 1
        self.text_buffer_ptr = next_ptr

    def flush_buffer(self):
        if self.text_buffer_ptr == 0:
            return
        logger.debug(f"Flush buffer for window {self._active_window_id}")
        text = ''.join(self.text_buffer[:self.text_buffer_ptr])
        self.text_buffer_ptr = 0
        window = self.active_window
        available_lines = window.height // window.font_height
        self.apply_text_settings(window)
        for line in self.wrap_lines(text):
            self.terminal_adapter.write_to_screen(line)
            _, x_cursor = self.terminal_adapter.get_coordinates()
            left_margin = window.x_pos + window.left_margin - 1
            if window.scrolling and self.pause_enabled and x_cursor == left_margin:
                window.line_count += 1
                if window.line_count >= available_lines - 1:
                    self.terminal_adapter.write_to_screen('[MORE]')
                    self.terminal_adapter.refresh()
                    self.terminal_adapter.get_input_char(False)
                    self.terminal_adapter.move_cursor_to_line_start()
                    self.terminal_adapter.clear_to_eol()
                    window.line_count = 0
                if window.nl_countdown > 0:
                    window.nl_countdown -= 1
                    logger.debug(f'Newline counter: {window.nl_countdown}')
                    if window.nl_countdown == 0:
                        event_args = RoutineCallEventArgs(window.nl_routine)
                        self.event_manager.on_routine_call.invoke(self, event_args)

    def wrap_lines(self, text: str) -> Iterator[str]:
        if len(text) == 0:
            return
        active_window = self.active_window
        text_pos = 0
        char_width = active_window.font_width
        _, x_cursor_absolute = self.terminal_adapter.get_coordinates()
        x_cursor = x_cursor_absolute - active_window.x_pos + 1
        if x_cursor == 0 and text[0] == ' ' and self.terminal_adapter.at_wrap_boundary:
            text_pos = 1

        if not self.active_window.wrapping:
            available_width_units = active_window.width - \
                active_window.right_margin - \
                max(active_window.left_margin, x_cursor)
            available_width_chars = available_width_units // char_width
            yield text[:available_width_chars]
            return

        while text_pos < len(text):
            available_width_units = active_window.width - \
                active_window.right_margin - \
                max(active_window.left_margin, x_cursor)
            x_cursor = 0
            available_width_chars = available_width_units // char_width
            remaining_text = text[text_pos:]
            nl_index = remaining_text.find('\n', 0, available_width_chars + 1)
            if nl_index >= 0:
                yield remaining_text[:min(nl_index + 1, available_width_chars)]
                text_pos += nl_index + 1
                continue
            if len(remaining_text) <= available_width_chars:
                yield remaining_text
                break
            space_index = remaining_text.rfind(' ', 0, available_width_chars + 1)
            if space_index >= 0:
                newline = '\n' if space_index < available_width_chars else ''
                yield remaining_text[:space_index] + newline
                text_pos += space_index + 1
            else:
                yield remaining_text[:available_width_chars]
                text_pos += available_width_chars


class ScreenV3(BaseScreen):
    def __init__(self, terminal_adapter: ITerminalAdapter, resource_data: IResourceData, event_manager: EventManager):
        super().__init__(terminal_adapter, resource_data, event_manager)
        self._version = 3
        lower_window, upper_window = self.windows
        upper_window.y_pos = 1
        lower_window.y_pos = 1
        self.split_window(0)
        terminal_adapter.set_scrollable_height(1)
        self.reset_cursor(lower_window)
        self.set_cursor_to_active_window()

    def set_active_window(self, window: Window):
        super().set_active_window(window)
        lower_window, upper_window = self.windows
        if window == lower_window:
            self.reset_cursor(upper_window)

    def split_window(self, lines):
        super().split_window(lines)
        self.erase(self.windows[1])

    def reset_cursor(self, window: Window):
        lower_window, upper_window = self.windows
        if window == upper_window:
            window.y_cursor, window.x_cursor = 1, 1
        elif window == lower_window:
            window.y_cursor, window.x_cursor = window.height, 1

    def refresh_status_line(self, location: str, status: str):
        y, x = self.terminal_adapter.get_coordinates()
        self.terminal_adapter.move_cursor(0, 0)
        self.terminal_adapter.apply_style_attributes(TextStyle.REVERSE)
        self.terminal_adapter.write_to_screen(' ' * self.width)
        self.terminal_adapter.move_cursor(0, 1)
        self.terminal_adapter.write_to_screen(location)
        self.terminal_adapter.move_cursor(0, self.width - len(status) - 3)
        self.terminal_adapter.write_to_screen(status)
        self.terminal_adapter.apply_style_attributes(TextStyle.ROMAN)
        self.terminal_adapter.move_cursor(y, x)


class ScreenV4(BaseScreen):
    def __init__(self, terminal_adapter: ITerminalAdapter, resource_data: IResourceData, event_manager: EventManager):
        super().__init__(terminal_adapter, resource_data, event_manager)
        self._version = 4
        self.reset_cursor(self.windows[0])

    def apply_text_settings(self, window: Window):
        self.terminal_adapter.apply_style_attributes(window.text_style_attributes)

    def get_cursor(self) -> tuple[int, int]:
        self.store_cursor_coordinates()
        return self.active_window.y_cursor, self.active_window.x_cursor

    def set_cursor(self, y_cursor: int, x_cursor: int, window_id: int = -3):
        lower_window, upper_window = self.windows
        if self.active_window != upper_window:
            # 8.7.2.3: The opcode has no effect when the lower window is selected.
            return
        # As an opcode instruction, coordinates are 1-indexed.
        if y_cursor > self.height or x_cursor > self.width:
            raise InvalidScreenOperationException("Cursor moved outside the screen bounds.")
        # NOTE: According to the z-machine standards, it's not allowed to move the
        # cursor outside the bounds of the upper window.
        # This interpreter will allow it, as long as the cursor stays on the screen.
        # Per the recommendation in 8.7.2.3, the upper window will resize to accommodate.
        if y_cursor > upper_window.height:
            logger.info(f"Cursor moved outside bounds of upper window, resizing upper window from {upper_window.height} to {y_cursor}")
            upper_window.height = y_cursor
            lower_window.height = self.height - y_cursor
            lower_window.y_pos = y_cursor + 1
        upper_window.y_cursor = y_cursor
        upper_window.x_cursor = x_cursor
        self.set_cursor_to_active_window()

    def set_text_style(self, style: int):
        logger.info(f"Setting text style to {style}")
        self.flush_buffer()
        if style == TextStyle.ROMAN:
            self.active_window.text_style_attributes = TextStyle.ROMAN
        else:
            self.active_window.text_style_attributes |= style

    def erase_line(self, value: int):
        if value == 1:
            self.terminal_adapter.clear_to_eol()


class ScreenV5(ScreenV4):
    def __init__(self, terminal_adapter: ITerminalAdapter, resource_data: IResourceData, event_manager: EventManager):
        super().__init__(terminal_adapter, resource_data, event_manager)
        self.graphics_adapter: IGraphicsAdapter | None = (
            terminal_adapter if isinstance(terminal_adapter, IGraphicsAdapter)
            else None
        )
        self._version = 5

    def apply_text_settings(self, window: Window):
        super().apply_text_settings(window)
        self.terminal_adapter.apply_color_settings(window.background_color, window.foreground_color)
        if self.graphics_adapter:
            self.graphics_adapter.apply_font(window.font)

    def set_color(self, foreground_color: int, background_color: int, window_id: int = -3):
        window = self.get_window(window_id)
        if window == self.active_window:
            self.flush_buffer()
        if background_color == 0:
            background_color = window.background_color
        elif background_color == 1:
            background_color = DEFAULT_BACKGROUND_COLOR
        if foreground_color == 0:
            foreground_color = window.foreground_color
        elif foreground_color == 1:
            foreground_color = DEFAULT_FOREGROUND_COLOR
        self.terminal_adapter.apply_color_settings(background_color, foreground_color)
        window.background_color = background_color
        window.foreground_color = foreground_color

    def set_font(self, font_id: int, window_id: int = -3) -> int:
        if self.graphics_adapter is None:
            return int(FontEnum.DEFAULT)
        window = self.get_window(window_id)
        previous_font = window.font
        if font_id != 0:
            if self.graphics_adapter.is_font_supported(font_id):
                new_font = FontEnum(font_id)
                if new_font != previous_font:
                    if window == self.active_window:
                        self.flush_buffer()
                    window.font = new_font
            else:
                return 0
        return int(previous_font)

    def print_table(self, table: list[str]):
        self.flush_buffer()
        y, x = self.terminal_adapter.get_coordinates()
        for row in table:
            self.terminal_adapter.move_cursor(y, x)
            self.apply_text_settings(self.active_window)
            self.terminal_adapter.write_to_screen(row)
            y += self.active_window.font_height

    def erase_window(self, window_id: int):
        self.windows[0].text_style_attributes = TextStyle.ROMAN
        super().erase_window(window_id)

    def reset_cursor(self, window: Window):
        window.y_cursor, window.x_cursor = 1, 1

class ScreenV6(ScreenV5):
    def __init__(self, terminal_adapter, resource_data, event_manager):
        super().__init__(terminal_adapter, resource_data, event_manager)
        self.graphics_adapter: IGraphicsAdapter = terminal_adapter
        self._version = 6
        self.height = self.graphics_adapter.screen_height_pixels
        self.width = self.graphics_adapter.screen_width_pixels

    def init_windows(self) -> list[Window]:
        if not isinstance(self.terminal_adapter, IGraphicsAdapter):
            raise InvalidScreenOperationException("Invalid terminal for v6")
        font_size = self.terminal_adapter.font_size
        result = [
            Window(self.height, self.width, font_size),
            Window(0, self.width, font_size)
        ] + [Window(0, 0, font_size) for _ in range(6)]
        self.reset_window_attributes(result)
        return result
    
    def set_print_region(self, window: Window):
        self.graphics_adapter.set_print_region(window.x_pos + window.left_margin - 1,
                                               window.y_pos - 1,
                                               max(window.width - window.left_margin - window.right_margin, 0),
                                               window.height)
        
    def set_scrollable_region(self, window: Window):
        # The scrollable region should be the window boundary, without the margins.
        if window.scrolling:
            self.graphics_adapter.set_scrollable_region(window.x_pos - 1, window.y_pos - 1, window.width, window.height)
        else:
            self.graphics_adapter.scrolling_enabled = False
    
    def restart_screen(self):
        for window in self.windows:
            window.reset_properties()
        lower_window, upper_window = self.windows[:2]
        lower_window.width = self.width
        upper_window.width = self.width
        self.erase_window(-1)
        self.reset_window_attributes(self.windows)
        self.reset_cursor(lower_window)
        self.set_print_region(lower_window)
        self.set_scrollable_region(lower_window)

    def reset_window_attributes(self, windows: list[Window]):
        windows[0].window_attributes = 0xf
        for window in windows[1:]:
            window.window_attributes = 0x8

    def split_window(self, lines: int):
        # Roughly emulates up to v5.
        # Stack windows 0 and 1, and move the cursor if necessary.
        height = lines
        logger.info(f"Splitting window at height {height}")
        lower_window, upper_window = self.windows[:2]
        self.flush_buffer()
        self.store_cursor_coordinates()
        lower_window.height = self.height - height
        lower_window.y_pos = height + 1
        lower_window.y_cursor += upper_window.height - height
        upper_window.height = height
        upper_window.y_pos = 1
        if upper_window.y_cursor > upper_window.height:
            self.reset_cursor(upper_window)
        if lower_window.y_cursor <= 0:
            lower_window.y_cursor = 1
        self.set_cursor_to_active_window()
        self.set_print_region(lower_window)
        self.set_scrollable_region(lower_window)
        self.terminal_adapter.refresh()
    
    def set_cursor(self, y_cursor: int, x_cursor: int, window_id: int = -3):
        window = self.get_window(window_id)
        if y_cursor <= 0 or x_cursor <= 0:
            raise InvalidScreenOperationException(f'Invalid cursor coordinates: ({y_cursor}, {x_cursor})')
        if x_cursor <= window.left_margin:
            x_cursor = window.left_margin + 1
        window.y_cursor = y_cursor
        window.x_cursor = x_cursor
        if window == self.active_window:
            self.set_cursor_to_active_window()

    def set_active_window(self, window):
        super().set_active_window(window)
        self.set_scrollable_region(window)
        self.set_print_region(window)

    def print_table(self, table: list[str]):
        # Since the game has calculated the rows to print,
        # print the table regardless of whether it fits in the active window width.
        self.flush_buffer()
        window = self.active_window
        width = window.width
        left_margin = window.left_margin
        right_margin = window.right_margin
        window.width = self.width
        window.left_margin = 0
        window.right_margin = 0
        self.set_print_region(window)
        try:
            super().print_table(table)
        finally:
            window.width = width
            window.left_margin = left_margin
            window.right_margin = right_margin
            self.set_print_region(window)

    def set_margins(self, left: int, right: int, window_id: int = -3):
        window = self.get_window(window_id)
        self.flush_buffer()
        self.store_cursor_coordinates()
        delta_left = window.left_margin - left
        window.left_margin = left
        window.right_margin = right

        if window.x_cursor <= left or window.x_cursor > window.width - window.right_margin:
            window.x_cursor = left + 1
        elif delta_left > 0:
            window.x_cursor -= delta_left

        if window == self.active_window:
            self.set_print_region(window)
            self.set_cursor_to_active_window()

    def set_cursor_enabled(self, value: bool):
        self.graphics_adapter.cursor_enabled = value

    def erase_line(self, value: int):
        if value == 1:
            self.terminal_adapter.clear_to_eol()
        else:
            _, cursor_x = self.terminal_adapter.get_coordinates()
            width = min(value - 1, self.active_window.width - self.active_window.right_margin - cursor_x)
            self.graphics_adapter.erase_line(width)

    def move_window(self, window_id: int, y: int, x: int):
        window = self.get_window(window_id)
        logger.info(f'Move window {window_id} to {x}x{y}')
        window.y_pos = y
        window.x_pos = x
        if window == self.active_window:
            self.set_print_region(window)
            self.set_scrollable_region(window)

    def resize_window(self, window_id: int, y: int, x: int):
        window = self.get_window(window_id)
        logger.info(f'Resize window {window_id} to {x}x{y}')
        window.height = y
        window.width = x
        if window.x_cursor > x or window.y_cursor > y:
            self.reset_cursor(window)
        if window == self.active_window:
            self.set_print_region(window)
            self.set_scrollable_region(window)

    def scroll_window(self, window_id: int, pixels: int):
        window = self.get_window(window_id)
        self.graphics_adapter.scroll_window(
            window.x_pos - 1, window.y_pos - 1, window.width, window.height, pixels
        )

    def get_picture_size(self, number) -> tuple[int, int]:
        return self.graphics_adapter.get_picture_size(number, self.resource_data)

    def draw_picture(self, number: int, y: int = 0, x: int = 0):
        self.flush_buffer()
        top, left = self._get_absolute_coordinates(y, x)
        logger.info(f"Draw picture {number} at ({left}, {top})")
        self.graphics_adapter.draw_picture(number, top, left, self.resource_data)

    def erase_picture(self, number: int, y: int = 0, x: int = 0):
        top, left = self._get_absolute_coordinates(y, x)
        self.graphics_adapter.erase_picture(number, top, left, self.resource_data)

    def set_mouse_window(self, window_id: int):
        if window_id < 0:
            left, top, width, height = 0, 0, self.width, self.height
        else:
            left = self.windows[window_id].x_pos - 1
            top = self.windows[window_id].y_pos - 1
            width = self.windows[window_id].width
            height = self.windows[window_id].height
        self.graphics_adapter.set_mouse_region(left, top, width, height)

    def set_window_attributes(self, window_id: int, flags: int, operation: int = 0):
        """Set attributes for a given window."""
        window = self.get_window(window_id)
        flags &= 0xf
        # 0: Set to the flags.
        # 1: Set the bits supplied.
        # 2: Clear the ones supplied.
        # 3: Reverse the bits supplied.
        if operation == 0:
            window.window_attributes = flags
        elif operation == 1:
            window.window_attributes |= flags
        elif operation == 2:
            window.window_attributes &= (~flags & 0xf)
        elif operation == 3:
            window.window_attributes ^= flags
        else:
            raise InvalidScreenOperationException(f"Invalid window style operation: {operation}")

    def _get_absolute_coordinates(self, y: int, x: int) -> tuple[int, int]:
        window = self.active_window
        window_top = window.y_pos - 1
        window_left = window.x_pos - 1
        relative_top = window.y_cursor - 1 if y == 0 else y - 1
        relative_left = window.x_cursor - 1 if x == 0 else x - 1
        return (window_top + relative_top, window_left + relative_left)