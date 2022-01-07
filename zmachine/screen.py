import io
import curses
import textwrap
from utils import sign_uint16

class screen():
    def __init__(self, zmachine):
        self.zmachine = zmachine
        if self.zmachine.quit:
            return
        builders = {
            3: screen.screen_v3_builder,
            4: screen.screen_v4_builder,
        }
        builder = builders[self.zmachine.version](zmachine)
        curses.wrapper(builder.build)

    class abstract_screen_builder():
        def __init__(self, zmachine):
            self.zmachine = zmachine
            self.buffer = io.StringIO()
            self.output_line_count = 0

        def build(self, stdscr):
            height, width = stdscr.getmaxyx()
            self.height = height
            self.width = width
            self.zmachine.set_print_handler(self.print_handler)
            self.zmachine.set_input_handler(self.input_handler)

            while not self.zmachine.quit:
                self.zmachine.run_instruction()
            self.flush_buffer(self.active_window)
            self.active_window.addstr("\n[Press any key to exit.]")
            self.active_window.getch()

        def set_active_window(self, window):
            self.active_window = window

        def print_handler(self, text, newline = False):
            self.buffer.write(str(text))
            if newline:
                self.buffer.write("\n")

        def input_handler(self, lowercase = True):
            self.flush_buffer(self.active_window)
            curses.echo()
            result = self.active_window.getstr().decode(encoding="utf-8")
            if lowercase:
                result = result.lower()
            curses.noecho()
            self.output_line_count = 0
            return result

        def flush_buffer(self, window):
            text = self.buffer.getvalue()
            self.buffer = io.StringIO()
            height, width = window.getmaxyx()
            y, x = window.getyx()
            output_lines = self.wrap_lines(text, window)
            for line in output_lines:
                window.addstr(line)
                if x == 0:
                    self.output_line_count += 1
                x = 0
                if self.output_line_count >= height - 2:
                    window.addstr('[MORE]')
                    window.refresh()
                    window.getch()
                    window.addstr(height - 1, 0, ' ' * 6)
                    window.move(height - 1, 0)
                    self.output_line_count = 0
            window.refresh()

        def wrap_lines(self, text, window):
            result = []
            textpos = 0
            while textpos < len(text):
                y, x = window.getyx()
                line = text[textpos:]
                line_break = text.find("\n", textpos)
                if line_break >= 0:
                    line = text[textpos:line_break+1]
                    textpos = line_break + 1
                else:
                    textpos = len(text)
                if len(line) < self.width - x:
                    result += [line]
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
                    result += [output_line]
            return result

    class screen_v3_builder(abstract_screen_builder):
        def build(self, stdscr):
            height, width = stdscr.getmaxyx()
            self.zmachine.set_show_status_handler(self.refresh_status_line)
            self.status_line = curses.newwin(1, width, 0, 0)
            self.status_line.attrset(curses.A_REVERSE)
            self.game_window = curses.newwin(height - 1, width, 1, 0)
            self.game_window.move(height - 2, 0)
            self.game_window.scrollok(True)
            self.set_active_window(self.game_window)
            super().build(stdscr)

        def input_handler(self, lowercase = True):
            self.refresh_status_line()
            return super().input_handler(lowercase)

        def refresh_status_line(self):
            location_id = self.zmachine.read_var(0x10)
            location = self.zmachine.get_object_text(location_id)
            right_status = self.get_right_status()
            # HACK: curses raises an exception when a character is written
            # to the last character position in the window.
            try:
                self.status_line.addstr(0, 0, ' ' * self.width)
            except:
                pass
            self.status_line.addstr(0, 1, location)
            self.status_line.addstr(0, self.width - len(right_status) - 3, right_status)
            self.status_line.refresh()

        def get_right_status(self):
            global1 = self.zmachine.read_var(0x11)
            global2 = self.zmachine.read_var(0x12)
            if self.zmachine.flags1 & 0x2 == 0:
                score = sign_uint16(global1)
                return f'Score: {score}'.ljust(16, ' ') + f'Moves: {global2}'.ljust(11, ' ')
            else:
                meridian = 'AM' if global1 < 12 else 'PM'
                if global1 == 0:
                    global1 = 12
                elif global1 > 12:
                    global1 -= 12
                hh = str(global1).rjust(2, ' ')
                mm = global2
                return f'Time: {hh}:{mm:02} {meridian}'.ljust(17, ' ')

    class screen_v4_builder(abstract_screen_builder):
        def build(self, stdscr):
            height, width = stdscr.getmaxyx()
            self.zmachine.write_byte(0x20, height)
            self.zmachine.write_byte(0x21, width)
            self.upper_window = curses.newwin(0, width, 0, 0)
            self.lower_window = curses.newwin(height, width, 0, 0)
            self.lower_window.scrollok(True)
            self.lower_window.move(height - 1, 0)
            self.active_window = self.lower_window
            self.buffered_output = True
            self.zmachine.set_erase_window_handler(self.erase_window)
            self.zmachine.set_split_window_handler(self.split_window)
            self.zmachine.set_set_window_handler(self.set_window)
            self.zmachine.set_set_buffer_mode_handler(self.set_buffer_mode)
            self.zmachine.set_set_cursor_handler(self.set_cursor)
            self.zmachine.set_set_text_style_handler(self.set_text_style)
            self.zmachine.set_read_char_handler(self.read_char)
            super().build(stdscr)

        def input_handler(self, lowercase = True):
            self.upper_window.refresh()
            return super().input_handler(lowercase)

        def print_handler(self, text, newline = False):
            if self.active_window == self.lower_window and self.buffered_output:
                super().print_handler(text, newline)
            else:
                try:
                    self.active_window.addstr(text)
                    if newline:
                        self.active_window.addstr("\n")
                except curses.error:
                    pass
                self.active_window.refresh()

        def read_char(self):
            self.upper_window.refresh()
            self.flush_buffer(self.lower_window)
            return self.active_window.getch()

        def erase_window(self, num):
            self.flush_buffer(self.lower_window)
            if num == -2:
                self.upper_window.erase()
                self.lower_window.erase()
            elif num == -1:
                self.upper_window.erase()
                self.lower_window.erase()
                self.split_window(0)
            elif num == 0:
                self.lower_window.erase()
            elif num == 1:
                self.upper_window.erase()

        def split_window(self, lines):
            try:
                self.upper_window.resize(lines, self.width)
            except curses.error:
                pass
            self.lower_window.resize(self.height - lines, self.width)
            self.lower_window.mvwin(lines, 0)
            self.lower_window.move(self.height - lines - 1, 0)

        def set_window(self, window):
            self.active_window.refresh()
            if window == 0:
                self.set_active_window(self.lower_window)
            elif window == 1:
                self.set_active_window(self.upper_window)

        def set_cursor(self, y, x):
            self.active_window.move(y - 1, x - 1)

        def set_buffer_mode(self, mode):
            self.buffered_output = mode != 0

        def set_text_style(self, style):
            self.flush_buffer(self.lower_window)
            self.active_window.refresh()
            styles = {
                0x1: curses.A_REVERSE,
                0x2: curses.A_BOLD,
                # Should be "italic" but is not supported by this version of curses.
                0x4: curses.A_UNDERLINE
            }
            for k, v in styles.items():
                if style & k == k:
                    self.active_window.attron(v)
                else:
                    self.active_window.attroff(v)
