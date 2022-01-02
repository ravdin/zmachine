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
            3: screen.screen_v3_builder(zmachine)
        }
        curses.wrapper(builders[self.zmachine.version].build)

    class screen_builder():
        def __init__(self, zmachine):
            self.zmachine = zmachine

        def build(self, stdscr):
            self.buffer = io.StringIO()
            self.zmachine.set_print_handler(self.print_handler)
            self.zmachine.set_input_handler(self.input_handler)

        def set_active_window(self, window):
            self.active_window = window

        def print_handler(self, text, newline = False):
            self.buffer.write(str(text))
            if newline:
                self.buffer.write("\n")

        def input_handler(self, lowercase = True):
            self.refresh_status_line()
            self.flush_buffer()
            curses.echo()
            result = self.active_window.getstr().decode(encoding="utf-8")
            if lowercase:
                result = result.lower()
            curses.noecho()
            return result

    class screen_v3_builder(screen_builder):
        def build(self, stdscr):
            super().build(stdscr)
            self.zmachine.set_show_status_handler(self.refresh_status_line)
            height, width = stdscr.getmaxyx()
            self.height = height
            self.width = width
            self.status_line = curses.newwin(1, width, 0, 0)
            self.status_line.attrset(curses.A_REVERSE)
            self.game_window = curses.newwin(height - 1, width, 1, 0)
            self.game_window.move(height - 2, 0)
            self.game_window.scrollok(True)
            self.set_active_window(self.game_window)

            while not self.zmachine.quit:
                self.zmachine.run_instruction()
            self.flush_buffer()
            self.game_window.addstr("\n[Press any key to exit.]")
            self.game_window.getch()

        def flush_buffer(self):
            text = self.buffer.getvalue()
            self.buffer = io.StringIO()
            height, width = self.game_window.getmaxyx()
            output_lines = self.wrap_lines(text)
            line_count = 0
            for line in output_lines:
                self.game_window.addstr(line)
                if len(line) > 0 and line[-1] == "\n":
                    line_count += 1
                if line_count == height - 2:
                    self.game_window.addstr('[MORE]')
                    self.game_window.refresh()
                    self.game_window.getch()
                    self.game_window.addstr(height - 1, 0, ' ' * 6)
                    self.game_window.move(height - 1, 0)
                    line_count = 0
            self.game_window.refresh()

        def wrap_lines(self, text):
            result = []
            textpos = 0
            while textpos < len(text):
                y, x = self.game_window.getyx()
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
