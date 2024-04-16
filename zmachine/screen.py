from abc import ABC, abstractmethod
from typing import Callable
from event import EventManager, EventArgs
from config import *


class Window:
    def __init__(self, height: int, width: int):
        self.height = height
        self.width = width
        self.y_pos = 0
        self.x_pos = 0
        self.y_cursor = 0
        self.x_cursor = 0
        self.style_attributes = 0
        self.background_color = DEFAULT_BACKGROUND_COLOR
        self.foreground_color = DEFAULT_FOREGROUND_COLOR

    def sync_cursor(self, y_pos: int, x_pos: int):
        self.y_cursor, self.x_cursor = y_pos, x_pos


class ScreenAdapter(ABC):
    def __init__(self):
        pass

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
    def get_input_char(self) -> int:
        pass

    @abstractmethod
    def get_input_string(self, prompt: str, lowercase: bool) -> str:
        pass

    @abstractmethod
    def read_keyboard_input(
            self,
            text_buffer: list[int],
            timeout_ms: int,
            interrupt_routine_caller: Callable[[int], int],
            interrupt_routine_addr: int,
            echo: bool = True
    ):
        pass

    @abstractmethod
    def get_coordinates(self) -> tuple[int, int]:
        pass

    @abstractmethod
    def move_cursor(self, y_pos: int, x_pos: int):
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

    def __init__(self, screen_adapter: ScreenAdapter):
        self.screen_adapter = screen_adapter
        self.height = screen_adapter.height
        self.width = screen_adapter.width
        self.lower_window = Window(self.height, self.width)
        self.upper_window = Window(0, 0)
        self.active_window = self.lower_window
        self.output_line_count = 0
        self.text_buffer = ['\0'] * self._TEXT_BUFFER_LENGTH
        self.text_buffer_ptr = 0
        self.event_manager = EventManager()
        self.register_delegates()

    def register_delegates(self):
        self.event_manager.pre_read_input += self.pre_read_input_handler
        self.event_manager.read_input += self.read_input_handler
        self.event_manager.set_window += self.set_window_handler
        self.event_manager.split_window += self.split_window_handler
        self.event_manager.erase_window += self.erase_window_handler
        self.event_manager.print_to_active_window += self.print_to_active_window_handler
        self.event_manager.interpreter_prompt += self.interpreter_prompt_handler
        self.event_manager.interpreter_input += self.interpreter_input_handler
        self.event_manager.select_output_stream += self.select_output_stream_handler
        self.event_manager.sound_effect += self.sound_effect_handler
        self.event_manager.quit += self.quit_handler

    def pre_read_input_handler(self, sender, event_args: EventArgs):
        self.output_line_count = 0
        self.flush_buffer(self.active_window)
        self.screen_adapter.refresh()

    def read_input_handler(self, sender, event_args: EventArgs):
        timeout_ms: int = event_args.timeout_ms
        text_buffer: list[int] = event_args.text_buffer
        interrupt_routine_caller: Callable[[int], int] = event_args.interrupt_routine_caller
        interrupt_routine_addr: int = event_args.interrupt_routine_addr
        echo = event_args.get('echo', True)
        self.screen_adapter.read_keyboard_input(
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
        if window_id == LOWER_WINDOW:
            self.set_active_window(self.lower_window)
        elif window_id == UPPER_WINDOW:
            self.flush_buffer(self.active_window)
            self.set_active_window(self.upper_window)

    def split_window_handler(self, sender, e: EventArgs):
        self.split_window(e.lines)

    def erase_window_handler(self, sender, e: EventArgs):
        window_id = e.window_id
        self.flush_buffer(self.lower_window)
        if window_id == -2:
            self.screen_adapter.erase_screen()
            self.output_line_count = 0
            self.reset_cursor(self.lower_window)
        elif window_id == -1:
            self.screen_adapter.erase_screen()
            self.output_line_count = 0
            self.split_window(0)
            self.reset_cursor(self.lower_window)
        elif window_id == LOWER_WINDOW:
            self.erase(self.lower_window)
        elif window_id == UPPER_WINDOW:
            self.erase(self.upper_window)
        self.screen_adapter.move_cursor(self.active_window.y_cursor, self.active_window.x_cursor)
        self.screen_adapter.refresh()

    def print_to_active_window_handler(self, sender, e: EventArgs):
        self.flush_buffer(self.active_window)
        text, newline = e.text, e.get('newline', False)
        self.print_to_active_window(text, newline)
        self.screen_adapter.refresh()

    def interpreter_prompt_handler(self, sender, e: EventArgs):
        self.write_to_screen(e.text + "\n")

    def interpreter_input_handler(self, sender, e: EventArgs):
        lowercase = e.get('lowercase', True)
        prompt = e.get('text', '')
        e.response = self.screen_adapter.get_input_string(prompt, lowercase)

    def select_output_stream_handler(self, sender, e: EventArgs):
        self.flush_buffer(self.lower_window)

    def sound_effect_handler(self, sender, e: EventArgs):
        self.screen_adapter.sound_effect(e.type)

    def quit_handler(self, sender, e: EventArgs):
        self.set_active_window(self.lower_window)
        self.flush_buffer(self.active_window)
        self.write_to_screen("\n[Press any key to exit.]")
        self.screen_adapter.refresh()
        self.screen_adapter.get_input_char()
        self.screen_adapter.shutdown()

    def write_to_screen(self, text):
        self.screen_adapter.write_to_screen(text)

    def print_to_active_window(self, text: str, newline: bool):
        self.apply_text_style_attributes(self.active_window)
        self.write_to_screen(text)
        if newline:
            self.write_to_screen("\n")
        self.screen_adapter.refresh()

    def move_cursor(self, y_pos, x_pos):
        self.screen_adapter.move_cursor(y_pos, x_pos)

    def apply_text_style_attributes(self, window: Window):
        self.screen_adapter.apply_style_attributes(window.style_attributes)

    def reset_cursor(self, window: Window):
        if window == self.upper_window:
            window.y_cursor, window.x_cursor = 0, 0
        elif window == self.lower_window:
            window.y_cursor, window.x_cursor = self.height - 1, 0

    def set_active_window(self, window: Window):
        self.active_window.sync_cursor(*self.screen_adapter.get_coordinates())
        self.active_window = window
        self.move_cursor(window.y_cursor, window.x_cursor)
        self.apply_text_style_attributes(window)

    def split_window(self, lines):
        self.flush_buffer(self.lower_window)
        self.active_window.sync_cursor(*self.screen_adapter.get_coordinates())
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
        self.screen_adapter.set_scrollable_height(lower_window_y)
        self.screen_adapter.refresh()

    def erase(self, window: Window):
        self.screen_adapter.erase_window(window)
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
        self.screen_adapter.apply_style_attributes(self.active_window.style_attributes)
        for line in output_lines:
            self.write_to_screen(line)
            if self.screen_adapter.get_coordinates()[1] == 0:
                self.output_line_count += 1
            if self.output_line_count >= window.height - 1:
                self.write_to_screen('[MORE]')
                self.screen_adapter.refresh()
                self.screen_adapter.get_input_char()
                self.move_cursor(self.height - 1, 0)
                self.screen_adapter.clear_to_eol()
                self.output_line_count = 0
        self.set_active_window(active_window)

    def wrap_lines(self, text):
        result = []
        text_pos = 0
        y, x = self.screen_adapter.get_coordinates()
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
    def __init__(self, screen_adapter: ScreenAdapter):
        super().__init__(screen_adapter)
        self.upper_window.y_pos = 1
        self.lower_window.y_pos = 1
        self.split_window(0)
        screen_adapter.set_scrollable_height(1)
        self.reset_cursor(self.lower_window)

    def register_delegates(self):
        super().register_delegates()
        self.event_manager.refresh_status_line += self.refresh_status_line_handler

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
        y, x = self.screen_adapter.get_coordinates()
        self.move_cursor(0, 0)
        self.screen_adapter.apply_style_attributes(TEXT_STYLE_REVERSE)
        self.write_to_screen(' ' * self.width)
        location = event_args.location
        right_status = event_args.right_status
        self.move_cursor(0, 1)
        self.write_to_screen(location)
        self.move_cursor(0, self.width - len(right_status) - 3)
        self.write_to_screen(right_status)
        self.screen_adapter.apply_style_attributes(TEXT_STYLE_ROMAN)
        self.move_cursor(y, x)


class ScreenV4(BaseScreen):
    def __init__(self, screen_adapter: ScreenAdapter):
        super().__init__(screen_adapter)
        self.reset_cursor(self.lower_window)
        CONFIG[SCREEN_HEIGHT_KEY] = screen_adapter.height
        CONFIG[SCREEN_WIDTH_KEY] = screen_adapter.width

    def register_delegates(self):
        super().register_delegates()
        self.event_manager.set_buffer_mode += self.set_buffer_mode_handler
        self.event_manager.set_cursor += self.set_cursor_handler
        self.event_manager.set_text_style += self.set_text_style_handler

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
        if e.mode == 0:
            self.flush_buffer(self.lower_window)

    def set_text_style_handler(self, sender, e: EventArgs):
        self.flush_buffer(self.active_window)
        style_attribute = e.style
        if style_attribute == TEXT_STYLE_ROMAN:
            self.active_window.style_attributes = TEXT_STYLE_ROMAN
        else:
            self.active_window.style_attributes |= e.style


class ScreenV5(ScreenV4):
    def __init__(self, screen_adapter: ScreenAdapter):
        super().__init__(screen_adapter)

    def register_delegates(self):
        super().register_delegates()
        self.event_manager.print_table += self.print_table_handler
        self.event_manager.set_color += self.set_color_handler

    def print_table_handler(self, sender, e: EventArgs):
        self.print_table(e.table)

    def set_color_handler(self, sender, e: EventArgs):
        self.set_color(self.active_window, e.background_color, e.foreground_color)

    def set_active_window(self, window: Window):
        super().set_active_window(window)
        self.set_color(window, window.background_color, window.foreground_color)

    def set_color(self, window: Window, background_color: int, foreground_color: int):
        self.screen_adapter.set_color(window, background_color, foreground_color)

    def print_table(self, table):
        self.flush_buffer(self.active_window)
        y, x = self.screen_adapter.get_coordinates()
        for row in table:
            if 0 in row:
                row = row[:row.index(0)]
            self.move_cursor(y, x)
            text = str(bytes(row), encoding='utf-8')
            self.print_to_active_window(text, False)
            y += 1

    def erase_window_handler(self, sender, e: EventArgs):
        self.lower_window.style_attributes = TEXT_STYLE_ROMAN
        super().erase_window_handler(sender, e)

    def reset_cursor(self, window: Window):
        window.y_cursor, window.x_cursor = window.y_pos, 0