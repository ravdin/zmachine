from .error import InvalidScreenOperationException
from .event import EventManager, EventArgs
from .enums import TextStyle, FontEnum, SoundEffectEnum
from .protocol import ITerminalAdapter, IGraphicsAdapter, IResourceData
from .logging import screen_logger as logger
from .constants import SUPPORTED_VERSIONS, PAUSE_DISABLED_SENTINEL, DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR
from .window import Window

class BaseScreen:
    _TEXT_BUFFER_LENGTH = 1024
    _pause_enabled: bool = True

    def __init__(self, terminal_adapter: ITerminalAdapter, resource_data: IResourceData, event_manager: EventManager):
        self._version = 0
        self.terminal_adapter = terminal_adapter
        self._resource_data = resource_data
        self.height = terminal_adapter.height
        self.width = terminal_adapter.width
        self.windows: list[Window] = self.init_windows()
        self._active_window_id: int = 0
        self.text_buffer = ['\0'] * self._TEXT_BUFFER_LENGTH
        self.text_buffer_ptr = 0
        self._buffer_mode = True
        self.register_delegates(event_manager)

    def register_delegates(self, event_manager: EventManager):
        event_manager.pre_read_input += self.pre_read_input_handler
        event_manager.on_select_output_stream += self.on_select_output_stream_handler
        event_manager.on_quit += self.on_quit_handler

    @property
    def version(self) -> int:
        if self._version not in SUPPORTED_VERSIONS:
            raise NotImplementedError("Version property must be implemented by subclass.")
        return self._version

    def init_windows(self) -> list[Window]:
        font_size = self.terminal_adapter.font_size
        lower_window = Window(self.height, self.width, font_size)
        lower_window.window_attributes = 0xf
        upper_window = Window(0, 0, font_size)
        return [lower_window, upper_window]

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

    @property
    def buffer_mode(self) -> bool:
        return self._buffer_mode
    
    @buffer_mode.setter
    def buffer_mode(self, value: bool):
        logger.info(f"Setting buffer mode to {value}")
        self._buffer_mode = value
        if not value:
            for window in self.windows:
                self.flush_buffer(window)

    @property
    def transcript_output_enabled(self) -> bool:
        return self.active_window.transcript_enabled
    
    @property
    def resource_data(self) -> IResourceData:
        return self._resource_data

    def reset_output_line_count(self):
        self.active_window.line_count = 0

    def pre_read_input_handler(self, sender, event_args: EventArgs):
        self.reset_output_line_count()
        self.flush_buffer(self.active_window)
        self.terminal_adapter.refresh()

    def refresh_status_line(self, location: str, status: str):
        raise NotImplementedError(f"Status line is not implemented in v{self.version} screen.")
        
    def set_window(self, window_id: int):
        logger.info(f"Setting active window to {window_id}")
        if window_id >= len(self.windows):
            raise InvalidScreenOperationException(f"Invalid window id: {window_id}")
        if self.active_window.buffered_printing:
            self.flush_buffer(self.active_window)
        self.set_active_window(self.windows[window_id])
        
    def split_window(self, lines: int): 
        logger.info(f"Splitting window at line {lines}")
        lower_window = self.windows[0]
        upper_window = self.windows[1]
        self.flush_buffer(lower_window)
        self.active_window.sync_cursor(*self.terminal_adapter.get_coordinates())
        lower_window_y = lines + upper_window.y_pos
        upper_window.height = lines
        lower_window.height = self.height - lower_window_y
        lower_window.y_pos = lower_window_y
        if upper_window.y_cursor >= lower_window_y:
            self.reset_cursor(upper_window)
            if self.active_window == upper_window:
                self.terminal_adapter.move_cursor(upper_window.y_cursor, upper_window.x_cursor)
        if lower_window.y_cursor < lower_window_y:
            self.reset_cursor(lower_window)
            if self.active_window == lower_window:
                self.terminal_adapter.move_cursor(lower_window.y_cursor, lower_window.x_cursor)
        self.terminal_adapter.set_scrollable_height(lower_window_y)
        self.terminal_adapter.refresh()

    def erase_window(self, window_id: int): 
        for window in self.windows:
            self.flush_buffer(window)
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
            self.erase(self.windows[window_id])
        self.terminal_adapter.move_cursor(self.active_window.y_cursor, self.active_window.x_cursor)
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

    def set_cursor(self, y_pos: int, x_pos: int):
        raise NotImplementedError(f"Set cursor is not implemented in v{self.version} screen.")

    def set_text_style(self, style: int):
        raise NotImplementedError(f"Text style is not implemented in v{self.version} screen.")

    def set_color(self, background_color: int, foreground_color: int, window_id: int):
        raise NotImplementedError(f"Set color is not implemented in v{self.version} screen.")

    def set_font(self, font_id: int, window_id: int) -> int:
        raise NotImplementedError(f"Set font is not implemented in v{self.version} screen.")

    def print_table(self, table: list[str]):
        raise NotImplementedError(f"Print table is not implemented in v{self.version} screen.")

    def set_mouse_window(self, window_id: int):
        raise NotImplementedError(f"Mouse window is not implemented in v{self.version} screen.")
    
    def get_picture_size(self, number: int) -> tuple[int, int]:
        raise NotImplementedError(f"Picture dimensions is not implemented in v{self.version} screen.")
    
    def draw_picture(self, number: int, y: int = 0, x: int = 0):
        raise NotImplementedError(f'Draw picture is not implemented in v{self.version} screen.')

    def get_window_property(self, window_id: int, property_number: int) -> int:
        window = self.active_window if window_id == -3 else self.windows[window_id]
        return window.get_property(property_number)

    def put_window_property(self, window_id: int, property_number: int, value: int):
        self.windows[window_id].set_property(property_number, value)

    def on_select_output_stream_handler(self, sender, e: EventArgs):
        for window in self.windows:
            if window.buffered_printing:
                self.flush_buffer(window)

    def on_quit_handler(self, sender, e: EventArgs):
        self.set_active_window(self.windows[0])
        self.flush_buffer(self.active_window)
        self.terminal_adapter.write_to_screen("\n[Press any key to exit.]")
        self.terminal_adapter.refresh()
        self.terminal_adapter.get_input_char(False)
        self.terminal_adapter.shutdown()

    def print(self, text: str, newline: bool = False):
        if self.buffer_mode and self.active_window.buffered_printing:
            self.write_to_buffer(text, newline)
        else:
            self.write_to_active_window(text, newline)

    def write_to_active_window(self, text: str, newline: bool = False):
        self.flush_buffer(self.active_window)
        self.apply_text_settings(self.active_window)
        self.terminal_adapter.write_to_screen(text)
        if newline:
            self.terminal_adapter.write_to_screen("\n")
        self.terminal_adapter.refresh()

    def apply_text_settings(self, window: Window):
        pass

    def reset_cursor(self, window: Window):
        lower_window, upper_window = self.windows
        if window == upper_window:
            window.y_cursor, window.x_cursor = 0, 0
        elif window == lower_window:
            window.y_cursor, window.x_cursor = self.height - 1, 0

    def set_active_window(self, window: Window):
        if window == self.active_window:
            return
        self.active_window.sync_cursor(*self.terminal_adapter.get_coordinates())
        self.active_window = window
        self.terminal_adapter.move_cursor(window.y_cursor, window.x_cursor)
        self.apply_text_settings(window)

    def erase(self, window: Window):
        self.terminal_adapter.erase_window(window.y_pos, window.height)
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

    def flush_buffer(self, window: Window):
        if self.text_buffer_ptr == 0:
            return
        text = ''.join(self.text_buffer[:self.text_buffer_ptr])
        self.text_buffer_ptr = 0
        active_window = self.active_window
        if window != active_window:
            self.set_active_window(window)
        output_lines = self.wrap_lines(text)
        self.apply_text_settings(self.active_window)
        for line in output_lines:
            self.terminal_adapter.write_to_screen(line)
            if self.terminal_adapter.get_coordinates()[1] == 0:
                window.line_count += 1
            if window.line_count >= window.height - 1 and self.pause_enabled:
                self.terminal_adapter.write_to_screen('[MORE]')
                self.terminal_adapter.refresh()
                self.terminal_adapter.get_input_char(False)
                self.terminal_adapter.move_cursor(self.height - 1, 0)
                self.terminal_adapter.clear_to_eol()
                window.line_count = 0
        self.set_active_window(active_window)

    def wrap_lines(self, text: str) -> list[str]:
        result: list[str] = []
        if len(text) == 0:
            return result
        text_pos = 0
        _, x = self.terminal_adapter.get_coordinates()
        if x == 0 and text[0] == ' ' and self.terminal_adapter.at_wrap_boundary:
            text_pos = 1

        while text_pos < len(text):
            line = text[text_pos:]
            line_break = text.find("\n", text_pos)
            if line_break >= 0:
                line = text[text_pos:line_break + 1]
                text_pos = line_break + 1
            else:
                text_pos = len(text)
            if len(line) < self.width - x:
                result += [line]
                x = 0
            else:
                output_line = ''
                linepos = 0
                while linepos < len(line) and line[linepos] == ' ':
                    if x >= self.width:
                        linepos += 1
                        continue
                    output_line += ' '
                    linepos += 1
                    x += 1
                words = line[linepos:].split(' ')
                separator = ''
                for word in words:
                    if len(separator) + len(word) > self.width - x:
                        separator = ''
                        result += [output_line + "\n"]
                        output_line = ''
                        x = 0
                    output_line += f"{separator}{word}"
                    x += len(separator) + len(word)
                    if x == self.width:
                        x = 0
                        separator = ''
                        result += [output_line]
                        output_line = ''
                    else:
                        separator = ' '
                if len(output_line) > 0:
                    result += [output_line]
                    if output_line[-1] == '\n':
                        x = 0
        return result


class ScreenV3(BaseScreen):
    def __init__(self, terminal_adapter: ITerminalAdapter, resource_data: IResourceData, event_manager: EventManager):
        super().__init__(terminal_adapter, resource_data, event_manager)
        self._version = 3
        self.lower_window = self.windows[0]
        self.upper_window = self.windows[1]
        self.upper_window.y_pos = 1
        self.lower_window.y_pos = 1
        self.split_window(0)
        terminal_adapter.set_scrollable_height(1)
        self.reset_cursor(self.lower_window)

    def set_active_window(self, window: Window):
        super().set_active_window(window)
        if window == self.lower_window:
            self.reset_cursor(self.upper_window)

    def split_window(self, lines):
        super().split_window(lines)
        self.erase(self.upper_window)

    def reset_cursor(self, window: Window):
        if window == self.upper_window:
            window.y_cursor, window.x_cursor = 1, 0
        elif window == self.lower_window:
            window.y_cursor, window.x_cursor = self.height - 1, 0

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
        self.lower_window = self.windows[0]
        self.upper_window = self.windows[1]
        self.reset_cursor(self.lower_window)

    def apply_text_settings(self, window: Window):
        self.terminal_adapter.apply_style_attributes(window.text_style_attributes)

    def set_cursor(self, y_pos: int, x_pos: int):
        if self.lower_window == self.active_window:
            return
        if y_pos >= self.height or x_pos >= self.width:
            raise InvalidScreenOperationException("Cursor moved outside the screen bounds.")
        # NOTE: According to the z-machine standards, it's not allowed to move the
        # cursor outside the bounds of the upper window.
        # This interpreter will allow it, as long as the cursor stays on the screen.
        # Per the recommendation in 8.7.2.3, the upper window will resize to accommodate.
        if y_pos >= self.upper_window.height:
            new_height = y_pos + 1
            logger.info(f"Cursor moved outside bounds of upper window, resizing upper window from {self.upper_window.height} to {new_height}")
            self.upper_window.height = new_height
            self.lower_window.height = self.height - new_height
            self.lower_window.y_pos = new_height
        self.terminal_adapter.move_cursor(y_pos, x_pos)
        self.upper_window.sync_cursor(y_pos, x_pos)

    def set_text_style(self, style: int):
        logger.info(f"Setting text style to {style}")
        self.flush_buffer(self.active_window)
        if style == TextStyle.ROMAN:
            self.active_window.text_style_attributes = TextStyle.ROMAN
        else:
            self.active_window.text_style_attributes |= style


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

    def set_color(self, background_color: int, foreground_color: int, window_id: int):
        active_window = self.active_window if window_id < 0 else self.windows[window_id]
        self.flush_buffer(active_window)
        if background_color == 0:
            background_color = active_window.background_color
        elif background_color == 1:
            background_color = DEFAULT_BACKGROUND_COLOR
        if foreground_color == 0:
            foreground_color = active_window.foreground_color
        elif foreground_color == 1:
            foreground_color = DEFAULT_FOREGROUND_COLOR
        self.terminal_adapter.apply_color_settings(background_color, foreground_color)
        active_window.background_color = background_color
        active_window.foreground_color = foreground_color

    def set_font(self, font_id: int, window_id: int) -> int:
        if self.graphics_adapter is None:
            return int(FontEnum.DEFAULT)
        window = self.active_window if window_id == -3 else self.windows[window_id]
        previous_font = window.font
        if font_id != 0:
            if self.graphics_adapter.is_font_supported(font_id):
                new_font = FontEnum(font_id)
                if new_font != previous_font:
                    self.flush_buffer(window)
                    window.font = new_font
            else:
                return 0
        return int(previous_font)

    def print_table(self, table: list[str]):
        self.flush_buffer(self.active_window)
        y, x = self.terminal_adapter.get_coordinates()
        for row in table:
            self.terminal_adapter.move_cursor(y, x)
            self.print(row, False)
            y += 1

    def erase_window(self, window_id: int):
        self.lower_window.text_style_attributes = TextStyle.ROMAN
        super().erase_window(window_id)

    def reset_cursor(self, window: Window):
        window.y_cursor, window.x_cursor = window.y_pos, 0

class ScreenV6(ScreenV5):
    def __init__(self, terminal_adapter, resource_data: IResourceData, event_manager):
        super().__init__(terminal_adapter, resource_data, event_manager)
        self._version = 6

    def init_windows(self) -> list[Window]:
        font_size = self.terminal_adapter.font_size
        result = [
            Window(self.height, self.width, font_size),
            Window(0, self.width, font_size)
        ] + [Window(0, 0, font_size) for _ in range(6)]

        # 8.8.3.3: Window 0 has attribute 1 off and 2, 3, 4 on.
        # Windows 1-7 initially has attribute 4 on and all others off.
        result[0].window_attributes = 0xe
        for i in range(1, 8):
            result[i].window_attributes = 0x8
        return result
    
    def erase_window(self, window_id: int):
        for window in self.windows:
            self.flush_buffer(window)
        if window_id == -2:
            self.terminal_adapter.erase_screen(self.active_window.background_color)
            self.windows[0].line_count = 0
            self.terminal_adapter.refresh()
            return
        elif window_id == -1:
            self.terminal_adapter.erase_screen(self.windows[0].background_color)
            self.windows[0].line_count = 0
            self.split_window(0)
            self.set_active_window(self.windows[0])
        else:
            self.erase(self.windows[window_id])
        self.terminal_adapter.move_cursor(self.active_window.y_cursor, self.active_window.x_cursor)
        self.terminal_adapter.refresh()

    def get_picture_size(self, number) -> tuple[int, int]:
        if self.graphics_adapter is None:
            logger.warning("Picture resources are not available")
            return (0, 0)
        return self.graphics_adapter.get_picture_size(number, self.resource_data)

    def draw_picture(self, number: int, y: int = 0, x: int = 0):
        if self.graphics_adapter is None:
            logger.warning("Picture resources are not available")
            return
        # Coordinates are 1-indexed in the zmachine but 0-indexed in the interpreter.
        y_pos = self.active_window.y_cursor if y == 0 else self.active_window.y_pos + y - 1
        x_pos = self.active_window.x_cursor if x == 0 else self.active_window.x_pos + x - 1
        self.graphics_adapter.draw_picture(number, y_pos, x_pos, self.resource_data)

    def set_mouse_window(self, window_id: int):
        if self.graphics_adapter is None:
            return
        if window_id < 0:
            top, left, bottom, right = 0, 0, self.height, self.width
        else:
            top = self.windows[window_id].y_pos
            left = self.windows[window_id].x_pos
            bottom = top + self.windows[window_id].height
            right = left + self.windows[window_id].width
        self.graphics_adapter.set_mouse_boundary(top=top, left=left, bottom=bottom, right=right)
