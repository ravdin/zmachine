from typing import Callable, List, Dict, Any


class SingletonMeta(type):
    """
    A Singleton metaclass that creates a single instance of a class.
    """
    _instances: Dict[type, "SingletonMeta"] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class EventArgs:
    def __init__(self, **kwargs):
        self._attributes: Dict[str, Any] = kwargs.copy()

    def kwargs(self):
        return self._attributes

    def get(self, name, default):
        if name in self._attributes:
            return self._attributes[name]
        return default

    def __getattr__(self, name):
        if name in self._attributes:
            return self._attributes[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any):
        if name == '_attributes':
            super().__setattr__(name, value)
        else:
            self._attributes[name] = value


class Event:
    def __init__(self):
        self.delegates: List[Callable] = []

    def __iadd__(self, other: Callable):
        if other not in self.delegates:
            self.delegates += [other]
        return self

    def __isub__(self, other):
        if other in self.delegates:
            self.delegates.remove(other)
        return self

    def invoke(self, sender, e: EventArgs):
        for delegate in self.delegates:
            delegate(sender, e)


class EventManager(metaclass=SingletonMeta):
    def __init__(self):
        self._attributes: Dict[str, Event] = {}
        # This event is raised after all components have been initialized.
        self.post_init = Event()
        # Write output to active output streams.
        self.write_to_streams = Event()
        # Write unbuffered output to the active screen window.
        self.print_to_active_window = Event()
        # Activate or deactivate an output stream.
        self.select_output_stream = Event()
        # Refresh the status line (version 3).
        self.refresh_status_line = Event()
        # Handle events that should occur before the user is presented with a prompt.
        self.pre_read_input = Event()
        # Inform the screen to present the user with an input prompt.
        self.read_input = Event()
        # The user has entered input to be read by the parser.
        self.post_read_input = Event()
        # Write to the lower window. To be used for interpreter prompts such as transcript or save files.
        self.interpreter_prompt = Event()
        # Raised when the user has entered input from an interpreter prompt.
        self.interpreter_input = Event()
        # Get a list of zchars in the input stream that should terminate a read op (version 5+).
        self.get_interrupt_zchars = Event()
        # Set the active screen window.
        self.set_window = Event()
        # Turn the buffer mode on or off.
        self.set_buffer_mode = Event()
        # Set the text style (reverse background, underline, bold).
        self.set_text_style = Event()
        # Set the cursor position.
        self.set_cursor = Event()
        # Set the height of the upper/lower window.
        self.split_window = Event()
        # Erase a window.
        self.erase_window = Event()
        # Print a table from the print_table op.
        self.print_table = Event()
        # Emit a sound.
        self.sound_effect = Event()
        # Change the screen colors.
        self.set_color = Event()
        # Raised when quitting the game.
        self.quit = Event()

    @classmethod
    def initialize_events(cls):
        return cls()

    def __getattr__(self, name):
        if name in self._attributes:
            return self._attributes[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Event):
        if name == '_attributes':
            super().__setattr__(name, value)
        else:
            self._attributes[name] = value
