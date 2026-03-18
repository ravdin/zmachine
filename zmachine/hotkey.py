import os
import random
import time
from enums import InputStreamType, OutputStreamType, Hotkey
from event import EventManager, EventArgs
from screen import BaseScreen
from config import ZMachineConfig

class HotkeyManager:
    def __init__(self, config: ZMachineConfig, screen: BaseScreen, event_manager: EventManager):
        self.config = config
        self.screen = screen
        self.terminal_adapter = screen.terminal_adapter
        self.event_manager = event_manager
        self.recording_input = False
        event_manager.activate_hotkey += self.activate_hotkey_handler

    def activate_hotkey_handler(self, sender, e: EventArgs):
        hotkey = e.hotkey
        line_chars = self.get_current_line_chars()
        self.erase_current_line()
        if hotkey == Hotkey.HELP:
            self.display_help()
        elif hotkey == Hotkey.SEED:
            self.set_random_seed()
        elif hotkey == Hotkey.PLAYBACK:
            success = self.playback_recorded_input()
            e.playback_open = success
        elif hotkey == Hotkey.RECORD:
            if self.recording_input:
                self.close_record_stream()
                self.recording_input = False
            else:
                self.open_record_stream()
                self.recording_input = True
        elif hotkey == Hotkey.DEBUG:
            debug_mode = self.toggle_debug_mode()
            if debug_mode:
                self.screen.write_to_screen("Debug mode enabled.\n")
            else:
                self.screen.write_to_screen("Debug mode disabled.\n")
        self.restore_current_line_chars(line_chars)
        self.terminal_adapter.refresh()

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
            self.screen.write_to_screen(item + '\n')

    def toggle_debug_mode(self) -> bool:
        event_args = EventArgs()
        self.event_manager.toggle_debug.invoke(self, event_args)
        return event_args.debug_mode

    def set_random_seed(self):
        seed = self.screen.get_input_string("Enter random seed: ", lowercase=False)
        if seed.isdigit():
            random.seed(int(seed))
            self.screen.write_to_screen(f"Random seed set to {seed}\n")
        else:
            self.screen.write_to_screen("Invalid seed. Enter a numeric value.\n")

    def open_record_stream(self):
        game_file = self.config.game_file
        filepath = os.path.dirname(game_file)
        filename = os.path.basename(game_file)
        base_filename = os.path.splitext(filename)[0]
        default_record_file = f'{base_filename}.rec'
        self.screen.write_to_screen("Enter a file name for recording input.\n")
        record_file = self.screen.get_input_string(f"Default is {default_record_file}: ", lowercase=False)
        if record_file == '':
            record_file = default_record_file
        record_file_path = os.path.join(filepath, record_file)
        if os.path.exists(record_file_path):
            if self.screen.get_input_string('Overwrite existing file? (Y is affirmative): ', lowercase=True) != 'y':
                self.screen.write_to_screen("Recording cancelled.\n")
                return False
        new_seed = int(time.time())
        with open(record_file_path, 'w') as f:
            f.write(f'# GAME: {filename}\n')
            f.write(f'# SEED: {new_seed}\n')
            f.write('---\n')
        random.seed(new_seed)
        self.screen.write_to_screen(f"Recording input to {record_file_path} with seed {new_seed}\n")
        event_args = EventArgs(stream_id=OutputStreamType.RECORD, record_full_path=record_file_path)
        self.event_manager.select_output_stream.invoke(self, event_args)

    def close_record_stream(self):
        event_args = EventArgs(stream_id=-(OutputStreamType.RECORD.value))
        self.event_manager.select_output_stream.invoke(self, event_args)
        self.screen.write_to_screen("Stopped recording input.\n")

    def playback_recorded_input(self) -> bool:
        """Prompt the user for a playback file and switch to the playback input stream if successful."""
        game_file = self.config.game_file
        commands = []
        seed: int = None
        in_metadata_section = True
        filepath = os.path.dirname(game_file)
        filename = os.path.basename(game_file)
        base_filename = os.path.splitext(filename)[0]
        default_playback_file = f'{base_filename}.rec'
        self.screen.write_to_screen("Enter a file name for playback.\n")
        playback_file = self.screen.get_input_string(f"Default is {default_playback_file}: ", lowercase=False)
        if playback_file == '':
            playback_file = default_playback_file
        playback_file_path = os.path.join(filepath, playback_file)
        if not os.path.exists(playback_file_path):
            self.screen.write_to_screen("Unable to open playback file.\n")
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
                            self.screen.write_to_screen("Playback file does not match the current game.\n")
                            return False
                    elif line.startswith('---'):
                        in_metadata_section = False
                else:
                    if line == '\n':
                        commands += [line]
                    else:
                        commands += [line.strip()]
            if len(commands) == 0:
                self.screen.write_to_screen("Playback file is empty.\n")
                return False
            if seed is None:
                self.screen.write_to_screen("Warning: No random seed found in recording.\n")
            else:
                random.seed(seed)
                self.screen.write_to_screen(f"Random seed set to {seed}\n")
            event_args = EventArgs(input_stream_type=InputStreamType.PLAYBACK, commands=commands)
            self.event_manager.select_input_stream.invoke(self, event_args)
        return True