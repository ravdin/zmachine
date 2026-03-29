import os
import random
import time
from functools import wraps
from .protocol import ITerminalAdapter, IInputSource, IOutputStreamManager
from .config import ZMachineConfig
from .settings import RuntimeSettings

def hotkey_wrapper(hotkey_func):
    @wraps(hotkey_func)
    def wrapper(self, *args, **kwargs):
        line_chars = self.get_current_line_chars()
        self.erase_current_line()
        try:
            result = hotkey_func(self, *args, **kwargs)
        finally:
            self.restore_current_line_chars(line_chars)
            self.terminal_adapter.refresh()
        return result
    return wrapper

class HotkeyHandler:
    def __init__(self, 
                 config: ZMachineConfig, 
                 runtime_settings: RuntimeSettings,
                 terminal_adapter: ITerminalAdapter, 
                 output_stream_manager: IOutputStreamManager):
        self.config = config
        self.runtime_settings = runtime_settings
        self.terminal_adapter = terminal_adapter
        self.output_stream_manager = output_stream_manager

    def get_current_line_chars(self) -> list[int]:
        y_pos, x_pos = self.terminal_adapter.get_coordinates()
        line_chars = [0] * x_pos
        for x in range(x_pos):
            line_chars[x] = self.terminal_adapter.get_char_at(y_pos, x)
        return line_chars
    
    def restore_current_line_chars(self, line_chars: list[int]):
        y_pos, _ = self.terminal_adapter.get_coordinates()
        x_pos = 0
        for char in line_chars:
            self.terminal_adapter.paint_char_at(y_pos, x_pos, char)
            x_pos += 1
        self.terminal_adapter.move_cursor(y_pos, x_pos)

    def erase_current_line(self):
        y_pos, _ = self.terminal_adapter.get_coordinates()
        self.terminal_adapter.move_cursor(y_pos, 0)
        self.terminal_adapter.clear_to_eol()
        
    @hotkey_wrapper
    def display_help(self):
        help_text = (
            'Hotkey options:',
            'Alt-h: Display this menu',
            'Alt-s: Set a random seed',
            'Alt-r: Record input',
            'Alt-p: Playback recorded input',
            'Alt-d: Write instructions to debug file',
            ''
        )
        for item in help_text:
            self.terminal_adapter.write_to_screen(item + '\n')

    @hotkey_wrapper
    def toggle_debug_mode(self):
        debug_mode = self.runtime_settings.toggle_debug_mode()
        if debug_mode:
            self.terminal_adapter.write_to_screen("Debug mode enabled.\n")
        else:
            self.terminal_adapter.write_to_screen("Debug mode disabled.\n")

    @hotkey_wrapper
    def set_random_seed(self):
        seed = self.terminal_adapter.get_input_string("Enter random seed: ", lowercase=False)
        if seed.isdigit():
            random.seed(int(seed))
            self.terminal_adapter.write_to_screen(f"Random seed set to {seed}\n")
        else:
            self.terminal_adapter.write_to_screen("Invalid seed. Enter a numeric value.\n")

    @hotkey_wrapper
    def open_record_stream(self):
        game_file = self.config.game_file
        filepath = os.path.dirname(game_file)
        filename = os.path.basename(game_file)
        base_filename = os.path.splitext(filename)[0]
        default_record_file = f'{base_filename}.rec'
        self.terminal_adapter.write_to_screen("Enter a file name for recording input.\n")
        record_file = self.terminal_adapter.get_input_string(f"Default is {default_record_file}: ", lowercase=False)
        if record_file == '':
            record_file = default_record_file
        record_file_path = os.path.join(filepath, record_file)
        if os.path.exists(record_file_path):
            if self.terminal_adapter.get_input_string('Overwrite existing file? (Y is affirmative): ', lowercase=True) != 'y':
                self.terminal_adapter.write_to_screen("Recording cancelled.\n")
                return
        new_seed = int(time.time())
        with open(record_file_path, 'w') as f:
            f.write(f'# GAME: {filename}\n')
            f.write(f'# SEED: {new_seed}\n')
            f.write('---\n')
        random.seed(new_seed)
        self.terminal_adapter.write_to_screen(f"Recording input to {record_file_path} with seed {new_seed}\n")
        self.output_stream_manager.open_record_stream(record_file_path)

    def close_record_stream(self):
        self.output_stream_manager.close_record_stream()
        self.terminal_adapter.write_to_screen("Stopped recording input.\n")

    def playback_recorded_input(self, input_source: IInputSource) -> bool:
        """Prompt the user for a playback file and switch to the playback input stream if successful."""
        game_file = self.config.game_file
        commands = []
        seed: int | None = None
        in_metadata_section = True
        filepath = os.path.dirname(game_file)
        filename = os.path.basename(game_file)
        base_filename = os.path.splitext(filename)[0]
        default_playback_filename = f'{base_filename}.rec'
        self.terminal_adapter.write_to_screen("Enter a file name for playback.\n")
        playback_filename = self.terminal_adapter.get_input_string(f"Default is {default_playback_filename}: ", lowercase=False)
        if playback_filename == '':
            playback_filename = default_playback_filename
        playback_file_path = os.path.join(filepath, playback_filename)
        if not os.path.exists(playback_file_path):
            self.terminal_adapter.write_to_screen("Unable to open playback file.\n")
            return False
        with open(playback_file_path, 'r') as playback_file:
            for line in playback_file:
                if in_metadata_section:
                    if line.startswith('# SEED:'):
                        seed_str = line.split(':', 1)[1].strip()
                        if seed_str.isdigit():
                            seed = int(seed_str) 
                    elif line.startswith('# GAME:'):
                        game_str = line.split(':', 1)[1].strip()
                        if game_str != filename:
                            self.terminal_adapter.write_to_screen("Playback file does not match the current game.\n")
                            return False
                    elif line.startswith('---'):
                        in_metadata_section = False
                else:
                    if line == '\n':
                        commands += [line]
                    else:
                        commands += [line.strip()]
            if len(commands) == 0:
                self.terminal_adapter.write_to_screen("Playback file is empty.\n")
                return False
            if seed is None:
                self.terminal_adapter.write_to_screen("Warning: No random seed found in recording.\n")
            else:
                random.seed(seed)
                self.terminal_adapter.write_to_screen(f"Random seed set to {seed}\n")
            input_source.select_playback_stream(commands)
        return True