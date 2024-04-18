import curses
import os
import random
from typing import Callable
from config import *
from screen import ScreenAdapter, Window
from event import EventManager, EventArgs


class CursesAdapter(ScreenAdapter):
    ZSCII_INPUT_HOTKEYS = {
        ESCAPE_SEQUENCE_UP_ARROW: UP_ARROW_CHAR,
        ESCAPE_SEQUENCE_DOWN_ARROW: DOWN_ARROW_CHAR,
        ESCAPE_SEQUENCE_LEFT_ARROW: LEFT_ARROW_CHAR,
        ESCAPE_SEQUENCE_RIGHT_ARROW: RIGHT_ARROW_CHAR,
        ESCAPE_SEQUENCE_F1: F1_CHAR,
        ESCAPE_SEQUENCE_F2: F2_CHAR,
        ESCAPE_SEQUENCE_F3: F3_CHAR,
        ESCAPE_SEQUENCE_F4: F4_CHAR,
        ESCAPE_SEQUENCE_F5: F5_CHAR,
        ESCAPE_SEQUENCE_F6: F6_CHAR,
        ESCAPE_SEQUENCE_F7: F7_CHAR,
        ESCAPE_SEQUENCE_F8: F8_CHAR,
        ESCAPE_SEQUENCE_F9: F9_CHAR,
        ESCAPE_SEQUENCE_F10: F10_CHAR,
        ESCAPE_SEQUENCE_F11: F11_CHAR,
        ESCAPE_SEQUENCE_F12: F12_CHAR
    }

    CURSES_TEXT_STYLES = {
        TEXT_STYLE_REVERSE: curses.A_REVERSE,
        TEXT_STYLE_BOLD: curses.A_BOLD,
        # Should be "italic" but is not supported by this version of curses.
        TEXT_STYLE_ITALIC: curses.A_UNDERLINE
    }

    COLORS = {
        COLOR_BLACK: curses.COLOR_BLACK,
        COLOR_RED: curses.COLOR_RED,
        COLOR_GREEN: curses.COLOR_GREEN,
        COLOR_YELLOW: curses.COLOR_YELLOW,
        COLOR_BLUE: curses.COLOR_BLUE,
        COLOR_MAGENTA: curses.COLOR_MAGENTA,
        COLOR_CYAN: curses.COLOR_CYAN,
        COLOR_WHITE: curses.COLOR_WHITE
    }
    CURSES_COLORS = {v: k for k, v in COLORS.items()}

    def __init__(self):
        super().__init__()
        # noinspection PyTypeChecker
        self.main_screen: curses.window = None
        self.event_manager = EventManager()
        self.record_stream_active = False
        self.color_pairs = [[0] * 10 for _ in range(10)]
        self.color_pair_index = 1
        curses.wrapper(self.build)

    def build(self, main_screen: curses.window):
        curses.cbreak()
        curses.noecho()
        main_screen.scrollok(True)
        main_screen.leaveok(False)
        main_screen.notimeout(False)
        main_screen.nodelay(False)
        curses.set_escdelay(50)
        main_screen.timeout(-1)
        curses.start_color()
        self.main_screen = main_screen

    @property
    def height(self) -> int:
        return curses.LINES

    @property
    def width(self) -> int:
        return curses.COLS

    def refresh(self):
        self.main_screen.refresh()

    def write_to_screen(self, text: str):
        curses.noecho()
        curses.cbreak()
        self.main_screen.addstr(text)
        self.main_screen.noutrefresh()

    def get_input_char(self) -> int:
        return self.main_screen.getch()

    def get_input_string(self, prompt: str, lowercase: bool) -> str:
        if len(prompt) > 0:
            self.main_screen.addstr(prompt)
        curses.echo()
        response = self.main_screen.getstr().decode(encoding='utf-8')
        if lowercase:
            response = response.lower()
        return response

    def get_coordinates(self) -> tuple[int, int]:
        return self.main_screen.getyx()

    def move_cursor(self, y_pos: int, x_pos: int):
        self.main_screen.move(y_pos, x_pos)

    def erase_screen(self):
        self.main_screen.erase()

    def erase_window(self, window: Window):
        y_cursor, x_cursor = self.main_screen.getyx()
        for y in range(window.y_pos, window.y_pos + window.height):
            self.main_screen.move(y, 0)
            self.main_screen.clrtoeol()
        self.main_screen.move(y_cursor, x_cursor)

    def clear_to_eol(self):
        self.main_screen.clrtoeol()

    def apply_style_attributes(self, attributes: int):
        for k, v in self.CURSES_TEXT_STYLES.items():
            if attributes & k == k:
                self.main_screen.attron(v)
            else:
                self.main_screen.attroff(v)

    def set_color(self, window: Window, background_color: int, foreground_color: int):
        if background_color == 0:
            background_color = window.background_color
        elif background_color == 1:
            background_color = DEFAULT_BACKGROUND_COLOR
        if foreground_color == 0:
            foreground_color = window.foreground_color
        elif foreground_color == 1:
            foreground_color = DEFAULT_FOREGROUND_COLOR
        pair_number = self.color_pairs[background_color][foreground_color]
        if pair_number == 0:
            curses.init_pair(
                self.color_pair_index,
                self.COLORS[foreground_color],
                self.COLORS[background_color]
            )
            pair_number = self.color_pair_index
            self.color_pairs[background_color][foreground_color] = pair_number
            self.color_pair_index += 1
        window.background_color = background_color
        window.foreground_color = foreground_color
        color_pair = curses.color_pair(pair_number)
        self.main_screen.attron(color_pair)

    def set_scrollable_height(self, top: int):
        if top == self.height - 1:
            self.main_screen.scrollok(False)
        else:
            self.main_screen.scrollok(True)
            self.main_screen.setscrreg(top, self.height - 1)

    def read_keyboard_input(
            self,
            text_buffer: list[int],
            timeout_ms: int,
            interrupt_routine_caller: Callable[[int], int],
            interrupt_routine_addr: int,
            echo: bool = True
    ):
        curses.noecho()
        curses.cbreak()
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
                if len(escape_sequence) == 1:
                    hotkey = escape_sequence[0]
                    if hotkey == HOTKEY_HELP:
                        self.hotkey_prompt(self.display_help)
                    if hotkey == HOTKEY_SEED:
                        self.hotkey_prompt(self.seed_random_value)
                    if hotkey == HOTKEY_RECORD:
                        active_input_stream_id = CONFIG[ACTIVE_INPUT_STREAM_KEY]
                        if self.record_stream_active:
                            self.hotkey_prompt(self.close_record_stream)
                        else:
                            self.hotkey_prompt(self.open_record_stream)
                    if hotkey == HOTKEY_PLAYBACK:
                        self.hotkey_prompt(self.playback_record_stream)
                        if CONFIG[ACTIVE_INPUT_STREAM_KEY] == INPUT_STREAM_PLAYBACK:
                            text_buffer[0] = 0
                            event_args = EventArgs(
                                text_buffer=text_buffer,
                                timeout_ms=timeout_ms,
                                interrupt_routine_caller=interrupt_routine_caller,
                                interrupt_routine_addr=interrupt_routine_addr,
                                echo=echo
                            )
                            self.event_manager.read_input.invoke(self, event_args)
                            break
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

    def sound_effect(self, sound_type: int):
        if sound_type == 1:
            curses.beep()

    def shutdown(self):
        curses.cbreak()
        curses.endwin()

    def hotkey_prompt(self, hotkey_func: Callable[[], int]):
        curses.echo()
        y, x = self.main_screen.getyx()
        added_lines = hotkey_func()
        new_y, new_x = self.main_screen.getyx()
        for x_pos in range(self.width - 1):
            c = self.main_screen.inch(new_y - added_lines, x_pos)
            self.main_screen.insch(new_y, x_pos, c)
        self.main_screen.move(new_y, x)
        curses.noecho()
        curses.doupdate()

    def display_help(self):
        added_lines = 0
        for line in HELP_TEXT.split("\n"):
            self.main_screen.addstr(line + "\n")
            added_lines += 1
        return added_lines

    def seed_random_value(self):
        self.main_screen.addstr("\n")
        self.main_screen.addstr("Enter a seed value: ")
        seed = self.main_screen.getstr().decode(encoding='utf-8')
        if seed.isdigit():
            random.seed(int(seed))
            self.main_screen.addstr("Random seed set.\n")
        else:
            self.main_screen.addstr("Invalid value, could not set seed.\n")
        return 3

    def get_record_stream_file(self):
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
        return 2, os.path.join(filepath, record_file)

    def open_record_stream(self):
        line_count, record_full_path = self.get_record_stream_file()
        if os.path.exists(record_full_path):
            self.main_screen.addstr("File exists, overwrite? (y is affirmative): ")
            if self.main_screen.getch() != ord('y'):
                self.main_screen.addstr("\nFile not opened, input recording is off.\n\n")
                return line_count + 4
            self.main_screen.addstr("\n")
            line_count += 1
        event_args = EventArgs(stream_id=4, record_full_path=record_full_path)
        self.event_manager.select_output_stream.invoke(self, event_args)
        self.record_stream_active = True
        self.main_screen.addstr("Recording input on.\n\n")
        return line_count + 3

    def close_record_stream(self):
        self.event_manager.select_output_stream.invoke(self, EventArgs(stream_id=-4))
        self.record_stream_active = False
        self.main_screen.addstr("\nRecording input off.\n")
        return 2

    def playback_record_stream(self):
        line_count, record_full_path = self.get_record_stream_file()
        if not os.path.exists(record_full_path):
            self.main_screen.addstr("Could not open file, playback off.\n\n")
            return line_count + 3
        event_args = EventArgs(record_full_path=record_full_path, stream_id=INPUT_STREAM_PLAYBACK)
        self.event_manager.select_input_stream.invoke(self, event_args)
        return line_count
