import curses
from event import EventManager, EventArgs
from stream import ScreenStream
from constants import *


class Screen:
    def __init__(self, version, output_stream: ScreenStream):
        builders = {
            3: Screen.ScreenV3Builder,
            4: Screen.ScreenV4Builder,
        }
        builder = builders[version](output_stream)
        curses.wrapper(builder.build)

    class AbstractScreenBuilder:
        def __init__(self, output_stream: ScreenStream):
            self.stdscr = None
            self.lower_window = None
            self.upper_window = None
            self.active_window = None
            self.height = None
            self.width = None
            self.output_line_count = 0
            self.output_stream = output_stream
            self.event_manager = EventManager()
            self.register_delegates()

        def build(self, stdscr):
            self.stdscr = stdscr
            height, width = stdscr.getmaxyx()
            self.height = height
            self.width = width

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

        def quit_handler(self, sender, e: EventArgs):
            self.flush_buffer(self.active_window)
            curses.cbreak()
            self.active_window.addstr("\n[Press any key to exit.]")
            self.active_window.getch()
            curses.endwin()

        def sound_effect_handler(self, sender, e: EventArgs):
            if e.type == 1:
                curses.beep()

        def split_window_handler(self, sender, e: EventArgs):
            self.split_window(e.lines)

        def split_window(self, lines):
            self.flush_buffer(self.lower_window)
            prev_lines = self.height - self.lower_window.getmaxyx()[0]
            if lines == 0:
                self.upper_window.erase()
            else:
                ypos = self.upper_window.getyx()[0]
                if ypos >= lines:
                    self.reset_cursor(self.upper_window)
                self.upper_window.resize(lines, self.width)
            if lines < prev_lines:
                self.lower_window.mvwin(lines, 0)
                self.lower_window.resize(self.height - lines, self.width)
            else:
                if self.height == lines:
                    self.lower_window.erase()
                else:
                    self.lower_window.resize(self.height - lines, self.width)
                    self.lower_window.mvwin(lines, 0)
            self.reset_cursor(self.lower_window)
            self.stdscr.noutrefresh()

        def set_window_handler(self, sender, e: EventArgs):
            window_id = e.window_id
            if window_id == LOWER_WINDOW:
                self.lower_window.leaveok(False)
                self.set_active_window(self.lower_window)
                self.reset_cursor(self.lower_window)
            elif window_id == UPPER_WINDOW:
                self.lower_window.leaveok(True)
                self.set_active_window(self.upper_window)

        def erase_window_handler(self, sender, e: EventArgs):
            window_id = e.window_id
            self.flush_buffer(self.lower_window)
            if window_id == -2:
                self.stdscr.erase()
                self.output_line_count = 0
            elif window_id == -1:
                self.stdscr.erase()
                self.output_line_count = 0
                self.split_window(0)
                self.set_active_window(self.lower_window)
                self.reset_cursor(self.lower_window)
            elif window_id == LOWER_WINDOW:
                self.lower_window.erase()
                self.reset_cursor(self.lower_window)
            elif window_id == UPPER_WINDOW:
                self.upper_window.erase()
                self.reset_cursor(self.upper_window)

        def select_output_stream_handler(self, sender, e: EventArgs):
            self.flush_buffer(self.lower_window)

        def reset_cursor(self, window):
            if window == self.upper_window:
                window.move(0, 0)
            elif window == self.lower_window:
                window_height = window.getmaxyx()[0]
                window.move(window_height - 1, 0)

        def set_active_window(self, window):
            self.active_window = window

        def print_to_active_window(self, text, newline: bool):
            self.active_window.addstr(text)
            if newline:
                self.active_window.addstr("\n")

        def print_to_active_window_handler(self, sender, e: EventArgs):
            self.flush_buffer(self.active_window)
            text, newline = e.text, e.get('newline', False)
            self.print_to_active_window(text, newline)

        def interpreter_prompt_handler(self, sender, e: EventArgs):
            self.lower_window.addstr(e.text + "\n")

        def interpreter_input_handler(self, sender, e: EventArgs):
            lowercase = True
            if hasattr(e, 'lowercase'):
                lowercase = e.lowercase
            if hasattr(e, 'text'):
                self.lower_window.addstr(e.text)
            e.response = self.read_keyboard_input(lowercase).strip()

        def read_keyboard_input(self, lowercase=True):
            curses.doupdate()
            curses.echo()
            result = self.active_window.getstr().decode(encoding="utf-8")
            if lowercase:
                result = result.lower()
            curses.noecho()
            self.output_line_count = 0
            return result

        def pre_read_input_handler(self, sender, event_args: EventArgs):
            self.output_line_count = 0
            self.flush_buffer(self.active_window)
            curses.doupdate()

        def read_input_handler(self, sender, event_args: EventArgs):
            command = self.read_keyboard_input()
            event_args.command = command
            self.event_manager.post_read_input.invoke(self, event_args)

        def flush_buffer(self, window):
            text = self.output_stream.flush_buffer()
            win_height = window.getmaxyx()[0]
            output_lines = self.wrap_lines(text, window)
            for line in output_lines:
                window.addstr(line)
                x = window.getyx()[1]
                if x == 0:
                    self.output_line_count += 1
                if self.output_line_count >= win_height - 2:
                    window.addstr('[MORE]')
                    window.refresh()
                    curses.cbreak()
                    window.getch()
                    window.addstr(win_height - 1, 0, ' ' * 6)
                    window.move(win_height - 1, 0)
                    self.output_line_count = 0
            window.noutrefresh()

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

    class ScreenV3Builder(AbstractScreenBuilder):
        def __init__(self, output_stream: ScreenStream):
            super().__init__(output_stream)
            self.event_manager.refresh_status_line += self.refresh_status_line

        def build(self, stdscr):
            height, width = stdscr.getmaxyx()
            self.upper_window = curses.newwin(1, width, 0, 0)
            self.upper_window.attrset(curses.A_REVERSE)
            self.lower_window = curses.newwin(height - 1, width, 1, 0)
            self.lower_window.move(height - 2, 0)
            self.lower_window.scrollok(True)
            self.set_active_window(self.lower_window)
            super().build(stdscr)

        def split_window(self, lines):
            super().split_window(lines)
            self.upper_window.erase()

        def refresh_status_line(self, sender, event_args: EventArgs):
            # HACK: curses raises an exception when a character is written
            # to the last character position in the window.
            try:
                self.upper_window.addstr(0, 0, ' ' * self.width)
            except curses.error:
                pass
            location = event_args.location
            right_status = event_args.right_status
            self.upper_window.addstr(0, 1, location)
            self.upper_window.addstr(0, self.width - len(right_status) - 3, right_status)
            self.upper_window.refresh()

    class ScreenV4Builder(AbstractScreenBuilder):
        def __init__(self, output_stream: ScreenStream):
            super().__init__(output_stream)
            self.has_scrolled_after_resize = False

        def build(self, stdscr):
            height, width = stdscr.getmaxyx()
            self.event_manager.set_screen_dimensions.invoke(self, EventArgs(height=height, width=width))
            self.stdscr = stdscr
            self.upper_window = stdscr.derwin(0, width, 0, 0)
            self.lower_window = stdscr.derwin(height, width, 0, 0)
            self.lower_window.scrollok(True)
            self.lower_window.move(height - 1, 0)
            self.active_window = self.lower_window
            super().build(stdscr)

        def register_delegates(self):
            super().register_delegates()
            self.event_manager.set_buffer_mode += self.set_buffer_mode_handler
            self.event_manager.set_cursor += self.set_cursor_handler
            self.event_manager.set_text_style += self.set_text_style_handler
            self.event_manager.read_char += self.read_char_handler

        def print_to_active_window(self, text, newline):
            if self.active_window == self.lower_window:
                super().print_to_active_window(text, newline)
            else:
                try:
                    self.active_window.addstr(text)
                    if newline:
                        self.active_window.addstr("\n")
                    self.active_window.noutrefresh()
                    curses.doupdate()
                except curses.error:
                    pass
                self.has_scrolled_after_resize = False

        def flush_buffer(self, window):
            # After a split_window, the first scroll of the lower window
            # will cause the contents of the upper window to be copied into it.
            # This effect is desirable when the game expands the upper window,
            # writes reversed text near the top of the screen, then shrinks
            # the upper window, leaving the reversed text as an overlay.
            # If the upper window is left expanded (e.g. Library Mode in AMFV),
            # then the duplicated lines in the lower window must be erased.
            if not self.has_scrolled_after_resize and self.output_stream.has_buffer():
                lower_window_height = self.lower_window.getmaxyx()[0]
                upper_window_height = self.height - lower_window_height
                y, x = self.lower_window.getyx()
                self.lower_window.addstr("\n")
                self.lower_window.move(0, 0)
                self.lower_window.insertln()
                for i in range(min(upper_window_height, lower_window_height)):
                    self.lower_window.move(i, 0)
                    self.lower_window.clrtoeol()
                self.lower_window.move(y, x)
                self.has_scrolled_after_resize = True
            super().flush_buffer(window)

        def read_char_handler(self, sender, e: EventArgs):
            self.flush_buffer(self.lower_window)
            curses.doupdate()
            curses.cbreak()
            e.char = self.active_window.getch()

        def split_window(self, lines):
            super().split_window(lines)
            self.has_scrolled_after_resize = False

        def set_cursor_handler(self, sender, e: EventArgs):
            y, x = e.y, e.x
            if self.active_window == self.upper_window:
                self.active_window.move(y - 1, x - 1)

        def set_buffer_mode_handler(self, sender, e: EventArgs):
            if e.mode == 0:
                self.flush_buffer(self.lower_window)

        def set_text_style_handler(self, sender, e: EventArgs):
            if self.active_window == self.lower_window:
                self.flush_buffer(self.lower_window)
            self.upper_window.noutrefresh()
            styles = {
                0x1: curses.A_REVERSE,
                0x2: curses.A_BOLD,
                # Should be "italic" but is not supported by this version of curses.
                0x4: curses.A_UNDERLINE
            }
            for k, v in styles.items():
                if e.style & k == k:
                    self.active_window.attron(v)
                else:
                    self.active_window.attroff(v)
