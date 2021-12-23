import io
import curses
import textwrap

class screen():
    def __init__(self, zmachine):
        self.zmachine = zmachine
        self.buffer = io.StringIO()
        zmachine.set_print_handler(self.print_handler)
        zmachine.set_input_handler(self.input_handler)
        zmachine.set_show_status_handler(self.refresh_status_line)
        curses.wrapper(self.init_screen)

    def init_screen(self, stdscr):
        stdscr.clear()
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        self.height = height
        self.width = width
        self.status_line = curses.newwin(1, width, 0, 0)
        self.status_line.attrset(curses.A_REVERSE)
        self.status_line.addstr(0, 0, ' ' * (width - 1))
        self.game_window = curses.newwin(height - 1, width, 1, 0)
        self.game_window.scrollok(True)

        while not self.zmachine.quit:
            self.zmachine.run_instruction()
        self.flush_buffer()
        self.game_window.addstr("[Type any key to exit.]")
        self.game_window.getch()

    def flush_buffer(self):
        text = self.buffer.getvalue()
        self.buffer = io.StringIO()
        height, width = self.game_window.getmaxyx()
        output_lines = self.wrap_lines(text)
        line_count = 0
        for line in output_lines:
            self.game_window.addstr(line)
            if line[-1] == "\n":
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

    def print_handler(self, text, newline = False):
        self.buffer.write(str(text))
        if newline:
            self.buffer.write("\n")
            #self.flush_buffer()

    def input_handler(self, lowercase = True):
        self.refresh_status_line()
        self.flush_buffer()
        curses.echo()
        result = self.game_window.getstr().decode(encoding="utf-8")
        if lowercase:
            result = result.lower()
        curses.noecho()
        return result

    def refresh_status_line(self):
        location = self.zmachine.get_location()
        self.status_line.addstr(0, 0, ' ' * (self.width - 1))
        self.status_line.addstr(0, 1, location)
        self.status_line.addstr(0, self.width - 30, self.zmachine.get_right_status())
        self.status_line.refresh()
