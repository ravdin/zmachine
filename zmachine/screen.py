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
            self.zmachine.set_set_flags_handler(self.set_flags_handler)
            self.set_flags_handler()

            while not self.zmachine.quit:
                self.zmachine.run_instruction()
            self.flush_buffer(self.active_window)
            self.active_window.addstr("\n[Press any key to exit.]")
            self.active_window.getch()

        def set_active_window(self, window):
            self.active_window = window

        def set_flags_handler(self):
            pass

        def print_handler(self, text, newline = False):
            self.buffer.write(text)
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
            win_height = window.getmaxyx()[0]
            y, x = window.getyx()
            output_lines = self.wrap_lines(text, window)
            for line in output_lines:
                window.addstr(line)
                if x == 0:
                    self.output_line_count += 1
                x = 0
                if self.output_line_count >= win_height - 2:
                    window.addstr('[MORE]')
                    window.refresh()
                    window.getch()
                    window.addstr(win_height - 1, 0, ' ' * 6)
                    window.move(win_height - 1, 0)
                    self.output_line_count = 0
            window.refresh()

        def wrap_lines(self, text, window):
            result = []
            textpos = 0
            y, x = window.getyx()
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
            self.stdscr = stdscr
            self.upper_window = stdscr.derwin(0, width, 0, 0)
            self.lower_window = stdscr.derwin(height, width, 0, 0)
            self.lower_window.scrollok(True)
            self.lower_window.move(height - 1, 0)
            self.active_window = self.lower_window
            self.saved_screen = None
            self.buffered_output = True
            self.has_scrolled_after_resize = False
            self.zmachine.set_erase_window_handler(self.erase_window)
            self.zmachine.set_split_window_handler(self.split_window)
            self.zmachine.set_set_window_handler(self.set_window)
            self.zmachine.set_set_buffer_mode_handler(self.set_buffer_mode)
            self.zmachine.set_set_cursor_handler(self.set_cursor)
            self.zmachine.set_set_text_style_handler(self.set_text_style)
            self.zmachine.set_read_char_handler(self.read_char)
            super().build(stdscr)

        def set_flags_handler(self):
            self.zmachine.write_byte(0x20, self.height)
            self.zmachine.write_byte(0x21, self.width)
            flags1 = self.zmachine.read_byte(0x1)
            # Boldface and emphasis available.
            flags1 |= 0xc
            self.zmachine.write_byte(0x1, flags1)

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
                self.has_scrolled_after_resize = False
                self.upper_window.refresh()
                self.lower_window.refresh()

        def flush_buffer(self, window):
            # After a split_window, the first scroll of the lower window
            # will cause the contents of the upper window to be copied into it.
            # This effect is desirable when the game expands the upper window,
            # writes reversed text near the top of the screen, then shrinks
            # the upper window, leaving the reversed text as an overlay.
            # If the upper window is left expanded (e.g. Library Mode in AMFV),
            # then the duplicated lines in the lower window must be erased.
            if not self.has_scrolled_after_resize and not self.buffered_output:
                upper_window_height = self.height - self.lower_window.getmaxyx()[0]
                y, x = self.lower_window.getyx()
                self.lower_window.addstr("\n")
                self.lower_window.move(0, 0)
                self.lower_window.insertln()
                for i in range(upper_window_height):
                    self.lower_window.move(i, 0)
                    self.lower_window.clrtoeol()
                self.lower_window.move(y, x)
                self.has_scrolled_after_resize = True
            super().flush_buffer(window)

        def read_char(self):
            self.upper_window.refresh()
            self.flush_buffer(self.lower_window)
            return self.active_window.getch()

        def erase_window(self, num):
            self.flush_buffer(self.lower_window)
            if num == -2:
                self.stdscr.erase()
                self.output_line_count = 0
            elif num == -1:
                self.stdscr.erase()
                self.output_line_count = 0
                self.split_window(0)
            elif num == 0:
                self.lower_window.erase()
            elif num == 1:
                self.upper_window.erase()

        def split_window(self, lines):
            self.flush_buffer(self.lower_window)
            prev_lines = self.height - self.lower_window.getmaxyx()[0]
            if lines == 0:
                self.upper_window.erase()
            else:
                ypos = self.upper_window.getyx()[0]
                if ypos >= lines:
                    self.upper_window.move(0, 0)
                self.upper_window.resize(lines, self.width)
            if lines < prev_lines:
                self.lower_window.mvwin(lines, 0)
                self.lower_window.resize(self.height - lines, self.width)
            else:
                self.lower_window.resize(self.height - lines, self.width)
                self.lower_window.mvwin(lines, 0)
            self.has_scrolled_after_resize = False
            self.lower_window.move(self.height - lines - 1, 0)
            self.stdscr.refresh()

        def set_window(self, window):
            if window == 0:
                self.lower_window.leaveok(False)
                self.set_active_window(self.lower_window)
            elif window == 1:
                self.lower_window.leaveok(True)
                self.set_active_window(self.upper_window)

        def set_cursor(self, y, x):
            if self.active_window == self.upper_window:
                self.active_window.move(y - 1, x - 1)

        def set_buffer_mode(self, mode):
            if mode == 0:
                self.flush_buffer(self.lower_window)
            self.buffered_output = mode != 0

        def set_text_style(self, style):
            if self.active_window == self.lower_window:
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
