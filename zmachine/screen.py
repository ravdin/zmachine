from __future__ import absolute_import
import curses
import random
import os
from typing import Callable
from event import EventManager, EventArgs
from input import KeyboardReader
from stream import ScreenStream
from config import *


class Window:
    def __init__(self):
        self.height = 0
        self.width = 0
        self.y_pos = 0
        self.x_pos = 0
        self.y_cursor = 0
        self.x_cursor = 0
        self.style_attributes = 0
        self.color_pair = 0

    def sync_cursor(self, main_screen: curses.window):
        self.y_cursor, self.x_cursor = main_screen.getyx()

    def apply_style_attributes(self, main_screen: curses.window):
        styles = {
            0x1: curses.A_REVERSE,
            0x2: curses.A_BOLD,
            # Should be "italic" but is not supported by this version of curses.
            0x4: curses.A_UNDERLINE
        }
        for k, v in styles.items():
            if self.style_attributes & k == k:
                main_screen.attron(v)
            else:
                main_screen.attroff(v)

    def apply_color_attributes(self, main_screen: curses.window):
        main_screen.attron(self.color_pair)


class Screen:
    def __init__(self, version, output_stream: ScreenStream):
        builders = {
            3: Screen.ScreenV3Builder,
            4: Screen.ScreenV4Builder,
            5: Screen.ScreenV5Builder,
        }
        builder = builders[version](output_stream)
        curses.wrapper(builder.build)

    class AbstractScreenBuilder:
        ZSCII_INPUT_HOTKEYS = {
            ESCAPE_SEQUENCE_UP_ARROW: 129,
            ESCAPE_SEQUENCE_DOWN_ARROW: 130,
            ESCAPE_SEQUENCE_LEFT_ARROW: 131,
            ESCAPE_SEQUENCE_RIGHT_ARROW: 132,
            ESCAPE_SEQUENCE_F1: 133,
            ESCAPE_SEQUENCE_F2: 134,
            ESCAPE_SEQUENCE_F3: 135,
            ESCAPE_SEQUENCE_F4: 136,
            ESCAPE_SEQUENCE_F5: 137,
            ESCAPE_SEQUENCE_F6: 138,
            ESCAPE_SEQUENCE_F7: 139,
            ESCAPE_SEQUENCE_F8: 140,
            ESCAPE_SEQUENCE_F9: 141,
            ESCAPE_SEQUENCE_F10: 142,
            ESCAPE_SEQUENCE_F11: 143,
            ESCAPE_SEQUENCE_F12: 144
        }

        def __init__(self, output_stream: ScreenStream):
            # noinspection PyTypeChecker
            self.main_screen: curses.window = None
            self.height = 0
            self.width = 0
            self.lower_window = Window()
            self.upper_window = Window()
            self.active_window = self.lower_window
            self.output_line_count = 0
            self.record_stream_active = False
            self.keyboard_input_active = True
            self.output_stream = output_stream
            self.event_manager = EventManager()
            self.register_delegates()

        def build(self, main_screen: curses.window):
            curses.raw()
            curses.noecho()
            curses.intrflush(True)
            main_screen.scrollok(True)
            main_screen.leaveok(False)
            main_screen.notimeout(False)
            curses.set_escdelay(50)
            main_screen.timeout(-1)
            self.height = curses.LINES
            self.width = curses.COLS
            self.lower_window.height = self.height
            self.lower_window.width = self.width
            self.upper_window.width = self.width
            CONFIG[SCREEN_HEIGHT_KEY] = self.height
            CONFIG[SCREEN_WIDTH_KEY] = self.width
            self.main_screen = main_screen

        def register_delegates(self):
            self.event_manager.pre_read_input += self.pre_read_input_handler
            self.event_manager.read_input += self.read_input_handler
            self.event_manager.set_window += self.set_window_handler
            self.event_manager.split_window += self.split_window_handler
            self.event_manager.erase_window += self.erase_window_handler
            self.event_manager.print_to_active_window += self.print_to_active_window_handler
            self.event_manager.interpreter_prompt += self.interpreter_prompt_handler
            self.event_manager.interpreter_input += self.interpreter_input_handler
            self.event_manager.select_input_stream += self.select_input_stream_handler
            self.event_manager.select_output_stream += self.select_output_stream_handler
            self.event_manager.sound_effect += self.sound_effect_handler
            self.event_manager.quit += self.quit_handler

        def quit_handler(self, sender, e: EventArgs):
            self.set_active_window(self.lower_window)
            self.flush_buffer(self.active_window)
            self.main_screen.addstr("\n[Press any key to exit.]")
            self.main_screen.getch()
            curses.cbreak()
            curses.endwin()

        def sound_effect_handler(self, sender, e: EventArgs):
            if e.type == 1:
                curses.beep()

        def split_window_handler(self, sender, e: EventArgs):
            self.split_window(e.lines)

        def split_window(self, lines):
            self.flush_buffer(self.lower_window)
            self.active_window.sync_cursor(self.main_screen)
            lower_window_y = lines + self.upper_window.y_pos
            self.upper_window.height = lines
            self.lower_window.height = self.height - lower_window_y
            self.lower_window.y_pos = lower_window_y
            if self.upper_window.y_cursor >= lower_window_y:
                self.reset_cursor(self.upper_window)
                if self.active_window == self.upper_window:
                    self.main_screen.move(self.upper_window.y_cursor, self.upper_window.x_cursor)
            if self.lower_window.y_cursor < lower_window_y:
                self.reset_cursor(self.lower_window)
                if self.active_window == self.lower_window:
                    self.main_screen.move(self.lower_window.y_cursor, self.lower_window.x_cursor)
            if self.lower_window.height <= 1:
                self.main_screen.scrollok(False)
            else:
                self.main_screen.scrollok(True)
                self.main_screen.setscrreg(lower_window_y, self.height - 1)
            self.main_screen.noutrefresh()

        def set_window(self, window_id):
            if window_id == LOWER_WINDOW:
                self.set_active_window(self.lower_window)
            elif window_id == UPPER_WINDOW:
                self.flush_buffer(self.active_window)
                self.set_active_window(self.upper_window)

        def set_window_handler(self, sender, e: EventArgs):
            self.set_window(e.window_id)

        def erase(self, window: Window):
            y_cursor, x_cursor = self.main_screen.getyx()
            for y in range(window.y_pos, window.y_pos + window.height):
                self.main_screen.move(y, 0)
                self.main_screen.clrtoeol()
            self.reset_cursor(window)
            self.main_screen.move(y_cursor, x_cursor)

        def erase_window_handler(self, sender, e: EventArgs):
            window_id = e.window_id
            self.flush_buffer(self.lower_window)
            if window_id == -2:
                self.main_screen.erase()
                self.output_line_count = 0
                self.reset_cursor(self.lower_window)
            elif window_id == -1:
                self.main_screen.erase()
                self.output_line_count = 0
                self.split_window(0)
                self.reset_cursor(self.lower_window)
            elif window_id == LOWER_WINDOW:
                self.erase(self.lower_window)
            elif window_id == UPPER_WINDOW:
                self.erase(self.upper_window)
            self.main_screen.move(self.active_window.y_cursor, self.active_window.x_cursor)
            self.main_screen.noutrefresh()
            curses.doupdate()

        def select_input_stream_handler(self, sender, e: EventArgs):
            if e.stream_id == INPUT_STREAM_PLAYBACK:
                self.keyboard_input_active = False
            elif e.stream_id == INPUT_STREAM_KEYBOARD:
                self.keyboard_input_active = True

        def select_output_stream_handler(self, sender, e: EventArgs):
            self.flush_buffer(self.lower_window)

        def reset_cursor(self, window: Window):
            if window == self.upper_window:
                window.y_cursor, window.x_cursor = 0, 0
            elif window == self.lower_window:
                window.y_cursor, window.x_cursor = self.height - 1, 0

        def set_active_window(self, window: Window):
            self.active_window.sync_cursor(self.main_screen)
            self.active_window = window
            self.main_screen.move(window.y_cursor, window.x_cursor)
            window.apply_style_attributes(self.main_screen)

        def print_to_active_window(self, text: str, newline: bool):
            self.active_window.apply_style_attributes(self.main_screen)
            self.main_screen.addstr(text)
            if newline:
                self.main_screen.addstr("\n")

        def print_to_active_window_handler(self, sender, e: EventArgs):
            self.flush_buffer(self.active_window)
            text, newline = e.text, e.get('newline', False)
            self.print_to_active_window(text, newline)
            self.main_screen.noutrefresh()

        def interpreter_prompt_handler(self, sender, e: EventArgs):
            self.main_screen.addstr(e.text + "\n")

        def interpreter_input_handler(self, sender, e: EventArgs):
            lowercase = True
            if hasattr(e, 'lowercase'):
                lowercase = e.lowercase
            if hasattr(e, 'text'):
                self.main_screen.addstr(e.text)
            curses.echo()
            response = self.main_screen.getstr().decode(encoding='utf-8')
            if lowercase:
                response = response.lower()
            e.response = response

        def read_keyboard_input(
                self,
                text_buffer: list[int],
                timeout_ms: int,
                interrupt_routine_caller: Callable[[int], int],
                interrupt_routine_addr: int,
                echo: bool = True
        ):
            curses.raw()
            curses.noecho()
            curses.intrflush(True)
            timeout_val = -1 if timeout_ms == 0 else timeout_ms
            self.main_screen.timeout(timeout_val)
            buffer_pos = 0
            while buffer_pos < len(text_buffer) and text_buffer[buffer_pos] != 0:
                buffer_pos += 1
            while buffer_pos < len(text_buffer):
                c = self.main_screen.getch()
                if c == 27:
                    # Escape sequence.
                    # For special characters (arrows, function keys), the remaining characters
                    # will be in the curses input stream.
                    escape_sequence = []
                    self.main_screen.timeout(0)
                    while True:
                        esc_char = self.main_screen.getch()
                        if esc_char == -1:
                            self.main_screen.timeout(timeout_val)
                            break
                        escape_sequence += [esc_char]
                    self.main_screen.timeout(timeout_val)
                    if tuple(escape_sequence) in self.ZSCII_INPUT_HOTKEYS.keys():
                        c = self.ZSCII_INPUT_HOTKEYS[tuple(escape_sequence)]
                    elif len(escape_sequence) == 1:
                        hotkey = escape_sequence[0]
                        if hotkey == HOTKEY_HELP:
                            self.__hotkey_prompt(self.__display_help)
                        elif hotkey == HOTKEY_SEED:
                            self.__hotkey_prompt(self.__seed_random_value)
                        elif hotkey == HOTKEY_RECORD:
                            if self.record_stream_active:
                                self.__hotkey_prompt(self.__close_record_stream)
                            else:
                                self.__hotkey_prompt(self.__open_record_stream)
                        continue
                    elif len(escape_sequence) > 0:
                        # Unrecognized escape sequence, ignore.
                        continue
                    # If the hotkey is recognized as an interrupt character, write it to the buffer
                    # and stop here.
                    # If the input buffer length is 1 (read_char), write the character to the buffer.
                    # Otherwise, ignore the character.
                    if c in CONFIG[INTERRUPT_ZCHARS_KEY]:
                        text_buffer[buffer_pos] = c
                        break
                    if len(text_buffer) == 1:
                        text_buffer[0] = c
                        break
                    continue
                if c == -1:
                    # Timed out.
                    if interrupt_routine_caller(interrupt_routine_addr) != 0:
                        text_buffer[0] = 0
                        return
                    continue
                elif c in (8, 127):
                    # Delete and backspace; will treat as backspace.
                    if len(text_buffer) == 1:
                        text_buffer[0] = 8
                        break
                    if buffer_pos > 0:
                        buffer_pos -= 1
                        text_buffer[buffer_pos] = 0
                        y, x = self.main_screen.getyx()
                        self.main_screen.move(y, x - 1)
                        self.main_screen.clrtoeol()
                    continue
                elif c in (10, 13):
                    if echo:
                        self.main_screen.addch(c)
                        self.output_line_count = 0
                    text_buffer[buffer_pos] = 13
                    break
                elif c < 32 or c > 126:
                    # TODO: Ignore non-ascii characters for now.
                    continue
                if echo:
                    self.main_screen.echochar(c)
                if ord('A') <= c <= ord('Z'):
                    c += 32
                text_buffer[buffer_pos] = c
                buffer_pos += 1
            self.main_screen.timeout(-1)

        def pre_read_input_handler(self, sender, event_args: EventArgs):
            self.output_line_count = 0
            self.flush_buffer(self.active_window)
            curses.doupdate()

        def read_input_handler(self, sender, event_args: EventArgs):
            if not self.keyboard_input_active:
                return
            timeout_ms: int = event_args.timeout_ms
            text_buffer: list[int] = event_args.text_buffer
            interrupt_routine_caller: Callable[[int], int] = event_args.interrupt_routine_caller
            interrupt_routine_addr: int = event_args.interrupt_routine_addr
            echo = event_args.get('echo', True)
            self.read_keyboard_input(text_buffer, timeout_ms, interrupt_routine_caller, interrupt_routine_addr, echo)

        def flush_buffer(self, window: Window):
            text = self.output_stream.flush_buffer()
            if len(text) == 0:
                return
            active_window = self.active_window
            self.set_active_window(window)
            output_lines = self.wrap_lines(text)
            self.active_window.apply_style_attributes(self.main_screen)
            for line in output_lines:
                self.main_screen.addstr(line)
                if self.main_screen.getyx()[1] == 0:
                    self.output_line_count += 1
                if self.height < MAX_SCREEN_HEIGHT and self.output_line_count >= window.height - 1:
                    self.main_screen.addstr('[MORE]')
                    self.main_screen.refresh()
                    self.main_screen.getch()
                    self.main_screen.move(self.height - 1, 0)
                    self.main_screen.clrtoeol()
                    self.output_line_count = 0
            self.main_screen.noutrefresh()
            self.set_active_window(active_window)

        def wrap_lines(self, text):
            result = []
            textpos = 0
            y, x = self.main_screen.getyx()
            while textpos < len(text):
                line = text[textpos:]
                line_break = text.find("\n", textpos)
                if line_break >= 0:
                    line = text[textpos:line_break+1]
                    textpos = line_break + 1
                else:
                    textpos = len(text)
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

        def __hotkey_prompt(self, hotkey_func: Callable[[], int]):
            curses.echo()
            text_style = self.lower_window.style_attributes
            y, x = self.main_screen.getyx()
            self.lower_window.style_attributes = 0
            added_lines = hotkey_func()
            new_y, new_x = self.main_screen.getyx()
            for x_pos in range(self.width - 1):
                c = self.main_screen.inch(new_y - added_lines, x_pos)
                self.main_screen.insch(new_y, x_pos, c)
            self.main_screen.move(new_y, x)
            self.lower_window.style_attributes = text_style
            curses.noecho()
            curses.doupdate()

        def __display_help(self):
            added_lines = 0
            for line in HELP_TEXT.split("\n"):
                self.main_screen.addstr(line + "\n")
                added_lines += 1
            return added_lines

        def __seed_random_value(self):
            self.main_screen.addstr("\n")
            self.main_screen.addstr("Enter a seed value: ")
            seed = self.main_screen.getstr().decode(encoding='utf-8')
            if seed.isdigit():
                random.seed(int(seed))
                self.main_screen.addstr("Random seed set.\n")
            else:
                self.main_screen.addstr("Invalid value, could not set seed.\n")
            return 3

        def __open_record_stream(self):
            game_file = CONFIG[GAME_FILE_KEY]
            filepath = os.path.dirname(game_file)
            filename = os.path.basename(game_file)
            base_filename = os.path.splitext(filename)[0]
            default_record_file = f'{base_filename}.rec'
            self.main_screen.addstr("\n")
            self.main_screen.addstr("Enter a file name.\n")
            self.main_screen.addstr(f'Default is "{default_record_file}": ')
            record_file = self.main_screen.getstr().decode(encoding='utf-8')
            if record_file == '':
                record_file = default_record_file
            record_full_path = os.path.join(filepath, record_file)
            additional_line_count = 0
            if os.path.exists(record_full_path):
                self.main_screen.addstr("File exists, overwrite? (y is affirmative): ")
                if self.main_screen.getch() != ord('y'):
                    self.main_screen.addstr("\nFile not opened, input recording is off.\n\n")
                    return 6
                self.main_screen.addstr("\n")
                additional_line_count = 1
            event_args = EventArgs(stream_id=4, record_full_path=os.path.join(filepath, record_file))
            self.event_manager.select_output_stream.invoke(self, event_args)
            self.main_screen.addstr("Recording input on.\n\n")
            self.record_stream_active = True
            return 5 + additional_line_count

        def __close_record_stream(self):
            self.event_manager.select_output_stream.invoke(self, EventArgs(stream_id=-4))
            self.main_screen.addstr("\nRecording input off.\n")
            self.record_stream_active = False
            return 1

    class ScreenV3Builder(AbstractScreenBuilder):
        def __init__(self, output_stream: ScreenStream):
            super().__init__(output_stream)
            self.upper_window.y_pos = 1
            self.lower_window.y_pos = 1
            self.event_manager.refresh_status_line += self.refresh_status_line

        def build(self, main_screen: curses.window):
            super().build(main_screen)
            self.split_window(0)
            self.main_screen.setscrreg(1, self.height - 1)
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

        def refresh_status_line(self, sender, event_args: EventArgs):
            y, x = self.main_screen.getyx()
            self.main_screen.attron(curses.A_REVERSE)
            # HACK: curses raises an exception when a character is written
            # to the last character position in the window.
            try:
                self.main_screen.addstr(0, 0, ' ' * self.width)
            except curses.error:
                pass
            location = event_args.location
            right_status = event_args.right_status
            self.main_screen.addstr(0, 1, location)
            self.main_screen.addstr(0, self.width - len(right_status) - 3, right_status)
            self.main_screen.attroff(curses.A_REVERSE)
            self.main_screen.move(y, x)

    class ScreenV4Builder(AbstractScreenBuilder):
        def build(self, main_screen: curses.window):
            super().build(main_screen)
            self.reset_cursor(self.lower_window)

        def register_delegates(self):
            super().register_delegates()
            self.event_manager.set_buffer_mode += self.set_buffer_mode_handler
            self.event_manager.set_cursor += self.set_cursor_handler
            self.event_manager.set_text_style += self.set_text_style_handler

        def set_cursor_handler(self, sender, e: EventArgs):
            y, x = e.y, e.x
            if self.lower_window == self.active_window:
                return
            # NOTE: According to the z-machine standards, it's not allowed to move the
            # cursor outside the bounds of the upper window.
            # This interpreter will allow it, as long as the cursor stays on the screen.
            if y > self.height or x > self.width:
                raise Exception("Cursor moved outside window")
            self.main_screen.move(y - 1, x - 1)
            self.upper_window.sync_cursor(self.main_screen)

        def set_buffer_mode_handler(self, sender, e: EventArgs):
            if e.mode == 0:
                self.flush_buffer(self.lower_window)

        def set_text_style_handler(self, sender, e: EventArgs):
            self.flush_buffer(self.active_window)
            style_attribute = e.style
            if style_attribute == 0:
                self.active_window.style_attributes = 0
            else:
                self.active_window.style_attributes |= e.style

    class ScreenV5Builder(ScreenV4Builder):
        COLORS = {
            2: curses.COLOR_BLACK,
            3: curses.COLOR_RED,
            4: curses.COLOR_GREEN,
            5: curses.COLOR_YELLOW,
            6: curses.COLOR_BLUE,
            7: curses.COLOR_MAGENTA,
            8: curses.COLOR_CYAN,
            9: curses.COLOR_WHITE
        }
        CURSES_COLORS = {v: k for k, v in COLORS.items()}

        def __init__(self, output_stream: ScreenStream):
            super().__init__(output_stream)
            self.color_pairs = [[0] * 10 for _ in range(10)]
            self.color_pair_index = 1

        def build(self, main_screen: curses.window):
            super().build(main_screen)
            curses.start_color()
        
        def register_delegates(self):
            super().register_delegates()
            self.event_manager.print_table += self.print_table_handler
            self.event_manager.set_color += self.set_color_handler

        def print_table_handler(self, sender, e: EventArgs):
            self.print_table(e.table)

        def print_table(self, table):
            self.flush_buffer(self.active_window)
            y, x = self.main_screen.getyx()
            for row in table:
                if 0 in row:
                    row = row[:row.index(0)]
                self.main_screen.move(y, x)
                text = str(bytes(row), encoding='utf-8')
                self.print_to_active_window(text, False)
                y += 1

        def set_color_handler(self, sender, e: EventArgs):
            self.set_color(e.foreground_color, e.background_color)

        def set_color(self, foreground_color, background_color):
            self.flush_buffer(self.active_window)
            current_colors = self.get_current_colors()
            if foreground_color == 0:
                foreground_color = current_colors[0]
            elif foreground_color == 1:
                foreground_color = DEFAULT_FOREGROUND_COLOR
            if background_color == 0:
                background_color = current_colors[1]
            elif background_color == 1:
                background_color = DEFAULT_BACKGROUND_COLOR
            pair_number = self.color_pairs[foreground_color][background_color]
            if pair_number == 0:
                curses.init_pair(
                    self.color_pair_index,
                    self.COLORS[foreground_color],
                    self.COLORS[background_color]
                )
                pair_number = self.color_pair_index
                self.color_pairs[foreground_color][background_color] = pair_number
                self.color_pair_index += 1
            self.active_window.color_pair = curses.color_pair(pair_number)
            self.active_window.apply_color_attributes(self.main_screen)

        def get_current_colors(self):
            pair_number = curses.pair_number(self.active_window.color_pair)
            curses_fg, curses_bg = curses.pair_content(pair_number)
            return self.CURSES_COLORS[curses_fg], self.CURSES_COLORS[curses_bg]

        def set_active_window(self, window: Window):
            super().set_active_window(window)
            window.apply_color_attributes(self.main_screen)

        def erase_window_handler(self, sender, e: EventArgs):
            self.lower_window.style_attributes = 0
            super().erase_window_handler(sender, e)

        def reset_cursor(self, window: Window):
            window.y_cursor, window.x_cursor = window.y_pos, 0
