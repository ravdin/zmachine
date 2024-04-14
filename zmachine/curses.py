import curses


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