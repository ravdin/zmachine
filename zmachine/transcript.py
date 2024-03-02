import os
from event import EventManager, EventArgs


class TranscriptUtils:
    def __init__(self, game_file: str):
        self.game_file = game_file
        self.event_manager = EventManager()
        filename = os.path.basename(game_file)
        base_filename = os.path.splitext(filename)[0]
        self.default_transcript_file = f'{base_filename}.txt'
        self.transcript_full_path = None

    def prompt_transcript_file(self) -> str:
        # This function should not be called more than once in a game session.
        if self.transcript_full_path is None:
            filepath = os.path.dirname(self.game_file)
            self.interpreter_prompt('Enter a file name.')
            script_file = self.interpreter_input(f'Default is "{self.default_transcript_file}": ')
            if script_file == '':
                script_file = self.default_transcript_file
            # If the file already exists and it's a new session, the transcript file will be overwritten.
            self.transcript_full_path = os.path.join(filepath, script_file)
        return self.transcript_full_path

    def interpreter_prompt(self, text):
        self.event_manager.interpreter_prompt.invoke(self, EventArgs(text=text))

    def interpreter_input(self, text):
        event_args = EventArgs(text=text)
        self.event_manager.interpreter_input.invoke(self, event_args)
        return event_args.response
