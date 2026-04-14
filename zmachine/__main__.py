import sys
import argparse
import logging
from .logging import setup_logging
from .builder import ZMachineBuilder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('story_file')
    parser.add_argument(
        '--log-level',
        choices=['debug', 'info', 'warning', 'error'],
        default='warning',
        help='Set logging level'
    )
    parser.add_argument(
        '--log-file',
        help='Write logs to file'
    )
    parser.add_argument(
        '--opcode-log-file',
        help='Write opcode logs to file'
    )
    parser.add_argument(
        '--log-memory',
        action='store_true',
        help='Enable memory access logging'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Wait for debugger to attach on port 5678'
    )
    args = parser.parse_args()
    
    if args.debug:
        import debugpy

        debugpy.listen(("127.0.0.1", 5678))
        print("⏳ Waiting for debugger on port 5678...")
        print("   In VSCode: Run > Start Debugging > 'Attach to Z-Machine'")
        debugpy.wait_for_client()
        print("✅ Debugger attached!\n")
    
    # Map string to logging level
    level_map = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR
    }

    # Set up logging
    setup_logging(
        level=level_map[args.log_level],
        log_file=args.log_file,
        opcode_log_file=args.opcode_log_file,
        log_memory=args.log_memory
    )
    
    builder = ZMachineBuilder(args.story_file)
    builder.start()


if __name__ == '__main__':
    main()
