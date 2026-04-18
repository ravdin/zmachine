from typing import Callable, List, Any
from dataclasses import dataclass

@dataclass
class EventArgs:
    """Base class for event arguments."""
    pass


@dataclass
class PostReadInputEventArgs(EventArgs):
    command: str | None
    terminating_char: int


class Event[T: EventArgs]:
    def __init__(self):
        self.delegates: List[Callable[[Any, T], None]] = []

    def __iadd__(self, other: Callable[[Any, T], None]) -> 'Event[T]':
        if other not in self.delegates:
            self.delegates += [other]
        return self

    def __isub__(self, other: Callable[[Any, T], None]) -> 'Event[T]':
        if other in self.delegates:
            self.delegates.remove(other)
        return self

    def invoke(self, sender, e: T):
        for delegate in self.delegates:
            delegate(sender, e)


class EventManager():
    def __init__(self):
        # Handle events that should occur when an output stream is selected.
        self.on_select_output_stream = Event[EventArgs]()
        # Handle events that should occur before the user is presented with a prompt.
        self.pre_read_input = Event[EventArgs]()
        # The user has entered input to be read by the parser.
        self.post_read_input = Event[PostReadInputEventArgs]()
        # Raised when quitting the game.
        self.on_quit = Event[EventArgs]()
