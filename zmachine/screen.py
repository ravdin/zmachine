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
            4: screen.screen_v4_builder
        }
        builder = builders[self.zmachine.version](zmachine)
        curses.wrapper(builder.build)

    class abstract_screen_builder():
        def __init__(self, zmachine):
            self.zmachine = zmachine
            self.buffer = io.StringIO()

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
            return result

        def flush_buffer(self, window):
            text = self.buffer.getvalue()
            self.buffer = io.StringIO()
            height, width = window.getmaxyx()
            output_lines = self.wrap_lines(text, window)
            line_count = 0
            for line in output_lines:
                window.addstr(line)
                if len(line) > 0 and line[-1] == "\n":
                    line_count += 1
                if line_count == height - 2:
                    window.addstr('[MORE]')
                    window.refresh()
                    window.getch()
                    window.addstr(height - 1, 0, ' ' * 6)
                    window.move(height - 1, 0)
                    line_count = 0
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
            super().input_handler(lowercase)

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
            self.height = height
            self.width = width
            self.zmachine.write_byte(0x20, height)
            self.zmachine.write_byte(0x21, width)
            main_window = curses.newwin(height, width, 0, 0)
            self.main_window = main_window
            self.split_window(0)
            self.buffered_output = True
            self.zmachine.set_erase_window_handler(self.erase_window)
            self.zmachine.set_split_window_handler(self.split_window)
            self.zmachine.set_set_window_handler(self.set_window)
            self.zmachine.set_set_buffer_mode_handler(self.set_buffer_mode)
            self.zmachine.set_set_cursor_handler(self.set_cursor)
            self.zmachine.set_set_text_style_handler(self.set_text_style)
            self.zmachine.set_read_char_handler(self.read_char)
            super().build(stdscr)

        def print_handler(self, text, newline = False):
            if self.active_window == self.lower_window and self.buffered_output:
                super().print_handler(text, newline)
            else:
                self.active_window.addstr(text)
                if newline:
                    self.active_window.addstr("\n")

        def read_char(self):
            self.flush_buffer(self.active_window)
            return self.active_window.getch()

        def erase_window(self, num):
            if num == -2:
                self.upper_window.erase()
                self.lower_window.erase()
            elif num == -1:
                self.split_window(0)
            elif num == 0:
                self.lower_window.erase()
            elif num == 1:
                self.upper_window.erase()

        def split_window(self, lines):
            self.upper_window = self.main_window.derwin(lines, self.width, 0, 0)
            self.lower_window = self.main_window.derwin(self.height - lines, self.width, lines, 0)
            self.lower_window.move(self.height - lines - 1, 0)
            self.lower_window.scrollok(True)
            self.upper_window.scrollok(True)
            self.set_active_window(self.lower_window)

        def set_window(self, window):
            self.set_active_window([self.lower_window, self.upper_window][window])

        def set_cursor(self, y, x):
            self.active_window.move(y - 1, x - 1)

        def set_buffer_mode(self, mode):
            self.buffered_output = mode != 0

        def set_text_style(self, style):
            if style == 0:
                self.active_window.attrset(0)
            if style & 0x1 == 0x1:
                self.active_window.attrset(curses.A_REVERSE)
            if style & 0x2 == 0x2:
                self.active_window.attrset(curses.A_BOLD)
            if style & 0x4 == 0x4:
                self.active_window.attrset(curses.A_ITALIC)
