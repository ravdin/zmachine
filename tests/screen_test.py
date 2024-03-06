import curses
from zmachine.screen import Screen
from zmachine.stream import ScreenStream
from zmachine.event import EventManager, EventArgs


class ScreenTest:
    def __init__(self, version: int):
        self.stream = ScreenStream()
        self.stream.buffer_mode = True
        self.height = 0
        self.width = 0
        self.event_manager = self.stream.event_manager
        self.event_manager.set_screen_dimensions += self.set_dimensions_handler
        self.screen = Screen(version, self.stream)
        curses.noecho()
        self.init_status_line()

    def init_status_line(self):
        self.event_manager.erase_window.invoke(self, EventArgs(window_id=-2))
        self.split_window(1)
        self.set_window(1)
        self.stream.buffer_mode = False
        self.set_text_style(1)
        for _ in range(self.width + 1):
            self.stream.write(' ', False)
        self.set_window(0)
        self.stream.buffer_mode = True

    def write_to_status_line(self, text, line, lpad=0):
        self.set_window(1)
        self.stream.buffer_mode = False
        self.set_cursor(line, 1)
        self.stream.write(" " * lpad, False)
        self.stream.write(text, False)
        for _ in range(lpad + len(text), self.width + 1):
            self.stream.write(' ', False)
        self.set_window(0)
        self.stream.buffer_mode = True

    def set_dimensions_handler(self, sender, e: EventArgs):
        self.width = e.width
        self.height = e.height
        self.stream.write(f"Screen width: {self.width}", True)
        self.stream.write(f"Screen height: {self.height}", True)

    def write_message(self, message):
        self.set_window(0)
        self.stream.buffer_mode = True
        self.event_manager.pre_read_input.invoke(self, EventArgs())
        self.stream.write(f"{message} (press any key)...", True)
        self.read_char()

    def read_char(self):
        event_args = EventArgs()
        self.event_manager.read_char.invoke(self, event_args)
        return event_args.char

    def set_text_style(self, style):
        self.event_manager.set_text_style.invoke(self, EventArgs(style=style))

    def enter_menu(self):
        menu_width = 40
        if self.width < menu_width:
            self.write_message('Unable to test menu, screen too narrow')
            return
        self.erase_window(0)
        self.split_window(5)
        self.write_to_status_line("Testing menu", 1, 3)
        self.set_window(1)
        self.stream.buffer_mode = False
        menu_items = ['Menu item 1', 'Menu item 2', 'Menu item 3', 'Menu item 4']
        cursor_coordinates = [(3, 1), (4, 1), (5, 1), (3, 21)]
        self.set_cursor(2, 1)
        self.set_text_style(0)
        self.stream.write(" ", False)
        for y in range(3, 6):
            self.set_text_style(1)
            self.set_cursor(y, 1)
            self.stream.write("  " * menu_width, False)
        for i in range(4):
            self.set_cursor(*cursor_coordinates[i])
            self.stream.write("  " + menu_items[i], False)
        self.set_cursor(*cursor_coordinates[0])
        self.stream.write(">", False)
        self.write_message(menu_items[0])
        for menu_ptr in range(1, 4):
            self.set_window(1)
            self.stream.buffer_mode = False
            self.set_cursor(*cursor_coordinates[menu_ptr-1])
            self.stream.write(" ", False)
            self.set_cursor(*cursor_coordinates[menu_ptr])
            self.stream.write(">", False)
            self.write_message(menu_items[menu_ptr])
        self.write_message("Menu test complete, should see selected menu items in lower window")

    def exit_menu(self):
        self.erase_window(1)
        self.split_window(1)
        self.write_to_status_line("Upper window line 1", 1, 3)

    def set_window(self, window_id):
        self.event_manager.set_window.invoke(self, EventArgs(window_id=window_id))

    def set_cursor(self, y, x):
        self.event_manager.set_cursor.invoke(self, EventArgs(y=y, x=x))

    def split_window(self, lines):
        self.event_manager.split_window.invoke(self, EventArgs(lines=lines))

    def erase_window(self, window_id):
        self.event_manager.erase_window.invoke(self, EventArgs(window_id=window_id))

    def test_split_window(self):
        self.write_message("1. Setting upper window to 1 line")
        self.write_to_status_line("Upper window line 1", 1, 3)
        self.write_message("2. Setting upper window to 2 lines")
        self.split_window(2)
        self.write_to_status_line("Upper window line 1", 1, 3)
        self.write_to_status_line("Upper window line 2", 2, 3)
        self.write_message("3. Setting upper window to 1 line")
        self.split_window(1)
        self.write_message("Split test complete, 3 lines expected in the lower window")

    def test_menu(self):
        self.enter_menu()
        self.exit_menu()
        self.write_message("Closed menu")

    def test_overlay(self):
        text = """All things (e.g. a camel's journey through
a needle's eye) are possible, it's true.
But picture how the camel feels, drawn out
In one long bloody thread, from tail to snout.
                    -- C.S. Lewis"""
        self.write_message("Testing overlay...")
        overlay_width = 50
        if self.width <= overlay_width:
            self.write_message("Can't test overlay, window is too narrow")
            return
        self.split_window(8)
        self.set_window(1)
        self.set_text_style(1)
        x_pos = (self.width - overlay_width) // 2
        y_pos = 3
        for line in text.split("\n"):
            self.set_cursor(y_pos, x_pos)
            self.stream.write(" " * 2, False)
            self.stream.write(line, False)
            for _ in range(2 + len(line), overlay_width + 1):
                self.stream.write(" ", False)
            y_pos += 1
        self.split_window(1)
        self.write_to_status_line("Upper window line 1", 1)
        self.set_window(0)
        self.write_message("Should see overlay with lower window text preserved")

    def test_erase_window(self):
        self.write_message("Erasing lower window...")
        self.event_manager.erase_window.invoke(self, EventArgs(window_id=0))

    def shutdown(self):
        self.stream.write("Shutting down...", False)
        self.event_manager.read_char.invoke(self, EventArgs())
        self.event_manager.quit.invoke(self, EventArgs())
