from typing import Callable, List, Dict, Any

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


class EventManager():
    def __init__(self):
        # Write output to active output streams.
        self.write_to_streams = Event()
        # Activate a hotkey event handler.
        self.activate_hotkey = Event()
        # Activate an input stream for reading.
        self.select_input_stream = Event()
        # Activate or deactivate an output stream.
        self.select_output_stream = Event()
        # Handle events that should occur before the user is presented with a prompt.
        self.pre_read_input = Event()
        # Inform the screen to present the user with an input prompt.
        self.read_input = Event()
        # The user has entered input to be read by the parser.
        self.post_read_input = Event()
        # Toggle debug mode.
        self.toggle_debug = Event()
        # Raised when quitting the game.
        self.quit = Event()
