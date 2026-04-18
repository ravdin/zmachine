from .error import InvalidScreenOperationException
from .event import EventManager, EventArgs
from .enums import WindowPosition, TextStyle
from .protocol import ITerminalAdapter
from .logging import screen_logger as logger
from .constants import SUPPORTED_VERSIONS, DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR


class Window:
    def __init__(self, height: int, width: int):
        self.height: int = height
        self.width: int = width
        self.y_pos: int = 0
        self.x_pos: int = 0
        self.y_cursor: int = 0
        self.x_cursor: int = 0
        self.style_attributes: int = 0
        self.background_color: int = DEFAULT_BACKGROUND_COLOR
        self.foreground_color: int = DEFAULT_FOREGROUND_COLOR

    def sync_cursor(self, y_pos: int, x_pos: int):
        self.y_cursor, self.x_cursor = y_pos, x_pos


class BaseScreen:
    _TEXT_BUFFER_LENGTH = 1024
    _pause_enabled: bool = True

    def __init__(self, terminal_adapter: ITerminalAdapter, event_manager: EventManager):
        self._version = 0
        self.terminal_adapter = terminal_adapter
        self.height = terminal_adapter.height
        self.width = terminal_adapter.width
        self.lower_window = Window(self.height, self.width)
        self.upper_window = Window(0, 0)
        self.active_window = self.lower_window
        self.output_line_count = 0
        self.text_buffer = ['\0'] * self._TEXT_BUFFER_LENGTH
        self.text_buffer_ptr = 0
        self._pause_enabled = True
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

    @property
    def pause_enabled(self) -> bool:
        return self._pause_enabled
    
    @pause_enabled.setter
    def pause_enabled(self, value: bool) -> None:
        self._pause_enabled = value

    @property
    def buffer_mode(self) -> bool:
        return self._buffer_mode
    
    @buffer_mode.setter
    def buffer_mode(self, value: bool) -> None:
        logger.info(f"Setting buffer mode to {value}")
        self._buffer_mode = value
        if not value:
            self.flush_buffer(self.lower_window)

    @property
    def active_window_id(self) -> 'WindowPosition':
        if self.active_window == self.lower_window:
            return WindowPosition.LOWER
        elif self.active_window == self.upper_window:
            return WindowPosition.UPPER
        else:
            raise InvalidScreenOperationException("Active window is not set to a valid window.")

    def reset_output_line_count(self) -> None:
        self.output_line_count = 0

    def pre_read_input_handler(self, sender, event_args: EventArgs):
        self.reset_output_line_count()
        self.flush_buffer(self.active_window)
        self.terminal_adapter.refresh()

    def refresh_status_line(self, location: str, status: str) -> None:
        raise NotImplementedError(f"Status line is not implemented in v{self.version} screen.")
        
    def set_window(self, window_id: int) -> None:
        logger.info(f"Setting active window to {window_id}")
        if window_id == WindowPosition.LOWER:
            self.set_active_window(self.lower_window)
        elif window_id == WindowPosition.UPPER:
            self.flush_buffer(self.active_window)
            self.set_active_window(self.upper_window)
        else:
            raise InvalidScreenOperationException("Invalid window ID.")
        
    def split_window(self, lines: int) -> None: 
        logger.info(f"Splitting window at line {lines}")
        self.flush_buffer(self.lower_window)
        self.active_window.sync_cursor(*self.terminal_adapter.get_coordinates())
        lower_window_y = lines + self.upper_window.y_pos
        self.upper_window.height = lines
        self.lower_window.height = self.height - lower_window_y
        self.lower_window.y_pos = lower_window_y
        if self.upper_window.y_cursor >= lower_window_y:
            self.reset_cursor(self.upper_window)
            if self.active_window == self.upper_window:
                self.terminal_adapter.move_cursor(self.upper_window.y_cursor, self.upper_window.x_cursor)
        if self.lower_window.y_cursor < lower_window_y:
            self.reset_cursor(self.lower_window)
            if self.active_window == self.lower_window:
                self.terminal_adapter.move_cursor(self.lower_window.y_cursor, self.lower_window.x_cursor)
        self.terminal_adapter.set_scrollable_height(lower_window_y)
        self.terminal_adapter.refresh()

    def erase_window(self, window_id: int) -> None: 
        self.flush_buffer(self.lower_window)
        if window_id == -2:
            self.terminal_adapter.erase_screen()
            self.output_line_count = 0
            self.reset_cursor(self.lower_window)
        elif window_id == -1:
            self.terminal_adapter.erase_screen()
            self.output_line_count = 0
            self.split_window(0)
            self.reset_cursor(self.lower_window)
        elif window_id == WindowPosition.LOWER:
            self.erase(self.lower_window)
        elif window_id == WindowPosition.UPPER:
            self.erase(self.upper_window)
        self.terminal_adapter.move_cursor(self.active_window.y_cursor, self.active_window.x_cursor)
        self.terminal_adapter.refresh()

    def sound_effect(self, type: int) -> None: 
        self.terminal_adapter.sound_effect(type)

    def set_cursor(self, y_pos: int, x_pos: int) -> None:
        raise NotImplementedError(f"Set cursor is not implemented in v{self.version} screen.")

    def set_text_style(self, style: int) -> None:
        raise NotImplementedError(f"Text style is not implemented in v{self.version} screen.")

    def set_color(self, background_color: int, foreground_color: int) -> None:
        raise NotImplementedError(f"Set color is not implemented in v{self.version} screen.")

    def print_table(self, table: list[str]) -> None:
        raise NotImplementedError(f"Print table is not implemented in v{self.version} screen.")

    def on_select_output_stream_handler(self, sender, e: EventArgs):
        self.flush_buffer(self.lower_window)

    def on_quit_handler(self, sender, e: EventArgs):
        self.set_active_window(self.lower_window)
        self.flush_buffer(self.active_window)
        self.terminal_adapter.write_to_screen("\n[Press any key to exit.]")
        self.terminal_adapter.refresh()
        self.terminal_adapter.get_input_char(False)
        self.terminal_adapter.shutdown()

    def print(self, text: str, newline: bool = False):
        if self.buffer_mode and self.active_window == self.lower_window:
            self.write_to_buffer(text, newline)
        else:
            self.write_to_active_window(text, newline)

    def write_to_active_window(self, text: str, newline: bool = False):
        self.flush_buffer(self.active_window)
        self.apply_text_style_attributes(self.active_window)
        self.terminal_adapter.write_to_screen(text)
        if newline:
            self.terminal_adapter.write_to_screen("\n")
        self.terminal_adapter.refresh()

    def apply_text_style_attributes(self, window: Window):
        self.terminal_adapter.apply_style_attributes(window.style_attributes)

    def reset_cursor(self, window: Window):
        if window == self.upper_window:
            window.y_cursor, window.x_cursor = 0, 0
        elif window == self.lower_window:
            window.y_cursor, window.x_cursor = self.height - 1, 0

    def set_active_window(self, window: Window):
        self.active_window.sync_cursor(*self.terminal_adapter.get_coordinates())
        self.active_window = window
        self.terminal_adapter.move_cursor(window.y_cursor, window.x_cursor)
        self.apply_text_style_attributes(window)

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
        self.set_active_window(window)
        output_lines = self.wrap_lines(text)
        self.terminal_adapter.apply_style_attributes(self.active_window.style_attributes)
        for line in output_lines:
            self.terminal_adapter.write_to_screen(line)
            if self.terminal_adapter.get_coordinates()[1] == 0:
                self.output_line_count += 1
            if self.output_line_count >= window.height - 1 and self.pause_enabled:
                self.terminal_adapter.write_to_screen('[MORE]')
                self.terminal_adapter.refresh()
                self.terminal_adapter.get_input_char(False)
                self.terminal_adapter.move_cursor(self.height - 1, 0)
                self.terminal_adapter.clear_to_eol()
                self.output_line_count = 0
        self.set_active_window(active_window)

    def wrap_lines(self, text):
        result = []
        text_pos = 0
        y, x = self.terminal_adapter.get_coordinates()
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
                while line[linepos] == ' ':
                    if x <= self.width:
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
                if len(output_line) > 0 and output_line[-1] == '\n':
                    x = 0
                result += [output_line]
        return result


class ScreenV3(BaseScreen):
    def __init__(self, terminal_adapter: ITerminalAdapter, event_manager: EventManager):
        super().__init__(terminal_adapter, event_manager)
        self._version = 3
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

    def refresh_status_line(self, location: str, status: str) -> None:
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
    def __init__(self, terminal_adapter: ITerminalAdapter, event_manager: EventManager):
        super().__init__(terminal_adapter, event_manager)
        self._version = 4
        self.reset_cursor(self.lower_window)

    def set_cursor(self, y_pos: int, x_pos: int) -> None:
        if self.lower_window == self.active_window:
            return
        # NOTE: According to the z-machine standards, it's not allowed to move the
        # cursor outside the bounds of the upper window.
        # This interpreter will allow it, as long as the cursor stays on the screen.
        if y_pos >= self.height or x_pos >= self.width:
            raise InvalidScreenOperationException("Cursor moved outside the screen bounds.")
        self.terminal_adapter.move_cursor(y_pos, x_pos)
        self.upper_window.sync_cursor(y_pos, x_pos)

    def set_text_style(self, style: int) -> None:
        logger.info(f"Setting text style to {style}")
        self.flush_buffer(self.active_window)
        if style == TextStyle.ROMAN:
            self.active_window.style_attributes = TextStyle.ROMAN
        else:
            self.active_window.style_attributes |= style


class ScreenV5(ScreenV4):
    def __init__(self, terminal_adapter: ITerminalAdapter, event_manager: EventManager):
        super().__init__(terminal_adapter, event_manager)
        self._version = 5

    def set_active_window(self, window: Window):
        super().set_active_window(window)
        self.set_color(window.background_color, window.foreground_color)

    def set_color(self, background_color: int, foreground_color: int) -> None:
        active_window = self.active_window
        if background_color == 0:
            background_color = active_window.background_color
        elif background_color == 1:
            background_color = DEFAULT_BACKGROUND_COLOR
        if foreground_color == 0:
            foreground_color = active_window.foreground_color
        elif foreground_color == 1:
            foreground_color = DEFAULT_FOREGROUND_COLOR
        self.terminal_adapter.set_color(background_color, foreground_color)
        active_window.background_color = background_color
        active_window.foreground_color = foreground_color

    def print_table(self, table: list[str]) -> None:
        self.flush_buffer(self.active_window)
        y, x = self.terminal_adapter.get_coordinates()
        for row in table:
            self.terminal_adapter.move_cursor(y, x)
            self.print(row, False)
            y += 1

    def erase_window(self, window_id: int) -> None:
        self.lower_window.style_attributes = TextStyle.ROMAN
        super().erase_window(window_id)

    def reset_cursor(self, window: Window):
        window.y_cursor, window.x_cursor = window.y_pos, 0