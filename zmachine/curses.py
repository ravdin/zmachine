import curses
import atexit
from .enums import TextStyle, Color


class CursesAdapter:
    CURSES_TEXT_STYLES = {
        TextStyle.REVERSE: curses.A_REVERSE,
        TextStyle.BOLD: curses.A_BOLD,
        # Should be "italic" but is not supported by this version of curses.
        TextStyle.ITALIC: curses.A_UNDERLINE
    }

    COLORS = {
        Color.BLACK: curses.COLOR_BLACK,
        Color.RED: curses.COLOR_RED,
        Color.GREEN: curses.COLOR_GREEN,
        Color.YELLOW: curses.COLOR_YELLOW,
        Color.BLUE: curses.COLOR_BLUE,
        Color.MAGENTA: curses.COLOR_MAGENTA,
        Color.CYAN: curses.COLOR_CYAN,
        Color.WHITE: curses.COLOR_WHITE
    }
    CURSES_COLORS = {v: k for k, v in COLORS.items()}

    def __init__(self):
        super().__init__()
        self.main_screen = curses.initscr()
        self.color_pairs = [[0] * 10 for _ in range(10)]
        self.color_pair_index = 1
        self._initialize_curses()
        atexit.register(self.shutdown)

    def _initialize_curses(self):
        curses.noecho()
        curses.cbreak()
        self.main_screen.scrollok(True)
        self.main_screen.leaveok(False)
        self.main_screen.notimeout(False)
        curses.set_escdelay(50)
        self.main_screen.timeout(-1)
        curses.start_color()

    @property
    def height(self) -> int:
        return curses.LINES

    @property
    def width(self) -> int:
        return curses.COLS

    def refresh(self):
        self.main_screen.refresh()

    def write_to_screen(self, text: str):
        self.main_screen.addstr(text)
        self.main_screen.noutrefresh()

    def get_input_char(self, echo: bool = True) -> int:
        c = self.main_screen.getch()
        if echo:
            if 32 <= c <= 126:
                self.main_screen.echochar(c)
            if c in (10, 13):
                self.main_screen.addch(c)
        return c
    
    def get_escape_sequence(self) -> list[int]:
        escape_sequence = []
        try:
            self.main_screen.nodelay(True)
            while True:
                esc_char = self.main_screen.getch()
                if esc_char == -1:
                    break
                escape_sequence += [esc_char]
            return escape_sequence
        finally:
            self.main_screen.nodelay(False)
            curses.noecho()
            curses.cbreak()

    def get_input_string(self, prompt: str, lowercase: bool) -> str:
        if len(prompt) > 0:
            self.main_screen.addstr(prompt)
        curses.echo()
        response = self.main_screen.getstr().decode(encoding='utf-8')
        if lowercase:
            response = response.lower()
        curses.noecho()
        return response

    def get_coordinates(self) -> tuple[int, int]:
        return self.main_screen.getyx()

    def move_cursor(self, y_pos: int, x_pos: int):
        self.main_screen.move(y_pos, x_pos)

    def get_char_at(self, y_pos: int, x_pos: int) -> int:
        return self.main_screen.inch(y_pos, x_pos)
    
    def paint_char_at(self, y_pos: int, x_pos: int, char_and_attr: int):
        ch, attr = char_and_attr & 0xFF, char_and_attr >> 8
        self.main_screen.addch(y_pos, x_pos, ch, attr)

    def erase_screen(self):
        self.main_screen.erase()

    def erase_window(self, top: int, height: int):
        y_cursor, x_cursor = self.main_screen.getyx()
        for y in range(top, top + height):
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

    def set_color(self, background_color: int, foreground_color: int):
        pair_number = self.color_pairs[background_color][foreground_color]
        if pair_number == 0:
            curses.init_pair(
                self.color_pair_index,
                self.COLORS[Color(foreground_color)],
                self.COLORS[Color(background_color)]
            )
            pair_number = self.color_pair_index
            self.color_pairs[background_color][foreground_color] = pair_number
            self.color_pair_index += 1
        color_pair = curses.color_pair(pair_number)
        self.main_screen.attron(color_pair)

    def set_scrollable_height(self, top: int):
        if top == self.height - 1:
            self.main_screen.scrollok(False)
        else:
            self.main_screen.scrollok(True)
            self.main_screen.setscrreg(top, self.height - 1)

    def set_timeout(self, timeout_ms: int):
        timeout_val = -1 if timeout_ms == 0 else timeout_ms
        self.main_screen.timeout(timeout_val)
        curses.noecho()
        curses.cbreak()

    def sound_effect(self, sound_type: int):
        if sound_type == 1:
            curses.beep()

    def shutdown(self):
        try:
            curses.nocbreak()
            curses.echo()
            curses.endwin()
        except curses.error:
            pass # Ignore cleanup errors