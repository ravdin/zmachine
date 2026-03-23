from abc import ABC, abstractmethod
from typing import Callable
from event import EventManager, EventArgs
from enums import WindowPosition, TextStyle
from constants import DEFAULT_BACKGROUND_COLOR, DEFAULT_FOREGROUND_COLOR


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


class TerminalAdapter(ABC):
    @property
    @abstractmethod
    def height(self) -> int:
        pass

    @property
    @abstractmethod
    def width(self) -> int:
        pass

    @abstractmethod
    def refresh(self):
        pass

    @abstractmethod
    def set_scrollable_height(self, top: int):
        pass

    @abstractmethod
    def write_to_screen(self, text: str):
        pass

    @abstractmethod
    def get_input_char(self, echo: bool = True) -> int:
        pass

    @abstractmethod
    def get_escape_sequence(self) -> list[int]:
        pass

    @abstractmethod
    def get_input_string(self, prompt: str, lowercase: bool) -> str:
        pass

    @abstractmethod
    def set_timeout(self, timeout_ms: int):
        pass

    @abstractmethod
    def get_coordinates(self) -> tuple[int, int]:
        pass

    @abstractmethod
    def move_cursor(self, y_pos: int, x_pos: int):
        pass

    @abstractmethod
    def get_char_at(self, y_pos: int, x_pos: int) -> int:
        pass

    @abstractmethod
    def paint_char_at(self, y_pos: int, x_pos: int, char: int):
        pass

    @abstractmethod
    def erase_screen(self):
        pass

    @abstractmethod
    def erase_window(self, window: Window):
        pass

    @abstractmethod
    def clear_to_eol(self):
        pass

    @abstractmethod
    def apply_style_attributes(self, attributes: int):
        pass

    @abstractmethod
    def set_color(self, window: Window, background_color: int, foreground_color: int):
        pass

    @abstractmethod
    def sound_effect(self, sound_type: int):
        pass

    @abstractmethod
    def shutdown(self):
        pass


class BaseScreen:
    _TEXT_BUFFER_LENGTH = 1024
    _pause_enabled: bool = True

    def __init__(self, terminal_adapter: TerminalAdapter, event_manager: EventManager):
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
        self.register_delegates(event_manager)

    def register_delegates(self, event_manager: EventManager):
        event_manager.pre_read_input += self.pre_read_input_handler
        event_manager.set_window += self.set_window_handler
        event_manager.split_window += self.split_window_handler
        event_manager.erase_window += self.erase_window_handler
        event_manager.print_to_active_window += self.print_to_active_window_handler
        event_manager.interpreter_prompt += self.interpreter_prompt_handler
        event_manager.interpreter_input += self.interpreter_input_handler
        event_manager.select_output_stream += self.select_output_stream_handler
        event_manager.sound_effect += self.sound_effect_handler
        event_manager.quit += self.quit_handler

    @property
    def pause_enabled(self) -> bool:
        return self._pause_enabled
    
    @pause_enabled.setter
    def pause_enabled(self, value: bool):
        self._pause_enabled = value

    def reset_output_line_count(self):
        self.output_line_count = 0

    def get_input_string(self, prompt: str, lowercase: bool) -> str:
        return self.terminal_adapter.get_input_string(prompt, lowercase)

    def pre_read_input_handler(self, sender, event_args: EventArgs):
        self.reset_output_line_count()
        self.flush_buffer(self.active_window)
        self.terminal_adapter.refresh()

    def read_input_handler(self, sender, event_args: EventArgs):
        timeout_ms: int = event_args.timeout_ms
        text_buffer: list[int] = event_args.text_buffer
        interrupt_routine_caller: Callable[[int], int] = event_args.interrupt_routine_caller
        interrupt_routine_addr: int = event_args.interrupt_routine_addr
        echo = event_args.get('echo', True)
        self.terminal_adapter.read_keyboard_input(
            text_buffer,
            timeout_ms,
            interrupt_routine_caller,
            interrupt_routine_addr,
            echo
        )
        if echo:
            buffer_len = text_buffer.index(0)
            if buffer_len > 0 and text_buffer[buffer_len - 1] == 13:
                self.output_line_count = 0

    def set_window_handler(self, sender, e: EventArgs):
        window_id = e.window_id
        if window_id == WindowPosition.LOWER:
            self.set_active_window(self.lower_window)
        elif window_id == WindowPosition.UPPER:
            self.flush_buffer(self.active_window)
            self.set_active_window(self.upper_window)

    def split_window_handler(self, sender, e: EventArgs):
        self.split_window(e.lines)

    def erase_window_handler(self, sender, e: EventArgs):
        window_id = e.window_id
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

    def print_to_active_window_handler(self, sender, e: EventArgs):
        self.flush_buffer(self.active_window)
        text, newline = e.text, e.get('newline', False)
        self.print_to_active_window(text, newline)
        self.terminal_adapter.refresh()

    def interpreter_prompt_handler(self, sender, e: EventArgs):
        self.write_to_screen(e.text + "\n")

    def interpreter_input_handler(self, sender, e: EventArgs):
        lowercase = e.get('lowercase', True)
        prompt = e.get('text', '')
        e.response = self.get_input_string(prompt, lowercase)

    def select_output_stream_handler(self, sender, e: EventArgs):
        self.flush_buffer(self.lower_window)

    def sound_effect_handler(self, sender, e: EventArgs):
        self.terminal_adapter.sound_effect(e.type)

    def quit_handler(self, sender, e: EventArgs):
        self.set_active_window(self.lower_window)
        self.flush_buffer(self.active_window)
        self.write_to_screen("\n[Press any key to exit.]")
        self.terminal_adapter.refresh()
        self.terminal_adapter.get_input_char(False)
        self.terminal_adapter.shutdown()

    def write_to_screen(self, text):
        self.terminal_adapter.write_to_screen(text)

    def print_to_active_window(self, text: str, newline: bool):
        self.apply_text_style_attributes(self.active_window)
        self.write_to_screen(text)
        if newline:
            self.write_to_screen("\n")
        self.terminal_adapter.refresh()

    def move_cursor(self, y_pos, x_pos):
        self.terminal_adapter.move_cursor(y_pos, x_pos)

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
        self.move_cursor(window.y_cursor, window.x_cursor)
        self.apply_text_style_attributes(window)

    def split_window(self, lines):
        self.flush_buffer(self.lower_window)
        self.active_window.sync_cursor(*self.terminal_adapter.get_coordinates())
        lower_window_y = lines + self.upper_window.y_pos
        self.upper_window.height = lines
        self.lower_window.height = self.height - lower_window_y
        self.lower_window.y_pos = lower_window_y
        if self.upper_window.y_cursor >= lower_window_y:
            self.reset_cursor(self.upper_window)
            if self.active_window == self.upper_window:
                self.move_cursor(self.upper_window.y_cursor, self.upper_window.x_cursor)
        if self.lower_window.y_cursor < lower_window_y:
            self.reset_cursor(self.lower_window)
            if self.active_window == self.lower_window:
                self.move_cursor(self.lower_window.y_cursor, self.lower_window.x_cursor)
        self.terminal_adapter.set_scrollable_height(lower_window_y)
        self.terminal_adapter.refresh()

    def erase(self, window: Window):
        self.terminal_adapter.erase_window(window)
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
            self.write_to_screen(line)
            if self.terminal_adapter.get_coordinates()[1] == 0:
                self.output_line_count += 1
            if self.output_line_count >= window.height - 1 and self.pause_enabled:
                self.write_to_screen('[MORE]')
                self.terminal_adapter.refresh()
                self.terminal_adapter.get_input_char(False)
                self.move_cursor(self.height - 1, 0)
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
    def __init__(self, terminal_adapter: TerminalAdapter, event_manager: EventManager):
        super().__init__(terminal_adapter, event_manager)
        self.upper_window.y_pos = 1
        self.lower_window.y_pos = 1
        self.split_window(0)
        terminal_adapter.set_scrollable_height(1)
        self.reset_cursor(self.lower_window)

    def register_delegates(self, event_manager: EventManager):
        super().register_delegates(event_manager)
        event_manager.refresh_status_line += self.refresh_status_line_handler

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

    def refresh_status_line_handler(self, sender, event_args: EventArgs):
        y, x = self.terminal_adapter.get_coordinates()
        self.move_cursor(0, 0)
        self.terminal_adapter.apply_style_attributes(TextStyle.REVERSE)
        self.write_to_screen(' ' * self.width)
        location = event_args.location
        right_status = event_args.right_status
        self.move_cursor(0, 1)
        self.write_to_screen(location)
        self.move_cursor(0, self.width - len(right_status) - 3)
        self.write_to_screen(right_status)
        self.terminal_adapter.apply_style_attributes(TextStyle.ROMAN)
        self.move_cursor(y, x)


class ScreenV4(BaseScreen):
    def __init__(self, terminal_adapter: TerminalAdapter, event_manager: EventManager):
        super().__init__(terminal_adapter, event_manager)
        self.reset_cursor(self.lower_window)

    def register_delegates(self, event_manager: EventManager):
        super().register_delegates(event_manager)
        event_manager.set_buffer_mode += self.set_buffer_mode_handler
        event_manager.set_cursor += self.set_cursor_handler
        event_manager.set_text_style += self.set_text_style_handler

    def set_cursor_handler(self, sender, e: EventArgs):
        y, x = e.y - 1, e.x - 1
        if self.lower_window == self.active_window:
            return
        # NOTE: According to the z-machine standards, it's not allowed to move the
        # cursor outside the bounds of the upper window.
        # This interpreter will allow it, as long as the cursor stays on the screen.
        if y >= self.height or x >= self.width:
            raise Exception("Cursor moved outside window")
        self.move_cursor(y, x)
        self.upper_window.sync_cursor(y, x)

    def set_buffer_mode_handler(self, sender, e: EventArgs):
        if e.mode in (0, False):
            self.flush_buffer(self.lower_window)

    def set_text_style_handler(self, sender, e: EventArgs):
        self.flush_buffer(self.active_window)
        style_attribute = e.style
        if style_attribute == TextStyle.ROMAN:
            self.active_window.style_attributes = TextStyle.ROMAN
        else:
            self.active_window.style_attributes |= e.style


class ScreenV5(ScreenV4):
    def __init__(self, terminal_adapter: TerminalAdapter, event_manager: EventManager):
        super().__init__(terminal_adapter, event_manager)

    def register_delegates(self, event_manager: EventManager):
        super().register_delegates(event_manager)
        event_manager.print_table += self.print_table_handler
        event_manager.set_color += self.set_color_handler

    def print_table_handler(self, sender, e: EventArgs):
        self.print_table(e.table)

    def set_color_handler(self, sender, e: EventArgs):
        self.set_color(self.active_window, e.background_color, e.foreground_color)

    def set_active_window(self, window: Window):
        super().set_active_window(window)
        self.set_color(window, window.background_color, window.foreground_color)

    def set_color(self, window: Window, background_color: int, foreground_color: int):
        self.terminal_adapter.set_color(window, background_color, foreground_color)

    def print_table(self, table):
        self.flush_buffer(self.active_window)
        y, x = self.terminal_adapter.get_coordinates()
        for row in table:
            if 0 in row:
                row = row[:row.index(0)]
            self.move_cursor(y, x)
            text = str(bytes(row), encoding='utf-8')
            self.print_to_active_window(text, False)
            y += 1

    def erase_window_handler(self, sender, e: EventArgs):
        self.lower_window.style_attributes = TextStyle.ROMAN
        super().erase_window_handler(sender, e)

    def reset_cursor(self, window: Window):
        window.y_cursor, window.x_cursor = window.y_pos, 0