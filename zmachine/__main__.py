import sys
from .builder import ZMachineBuilder


def main():
    # Check for --debug flag
    debug_mode = '--debug' in sys.argv
    if debug_mode:
        import debugpy
        sys.argv.remove('--debug')

        debugpy.listen(("127.0.0.1", 5678))
        print("⏳ Waiting for debugger on port 5678...")
        print("   In VSCode: Run > Start Debugging > 'Attach to Z-Machine'")
        debugpy.wait_for_client()
        print("✅ Debugger attached!\n")
    
    if len(sys.argv) < 2:
        print("Usage: python -m zmachine [--debug] [GAME_FILE]")
        return
    
    builder = ZMachineBuilder(sys.argv[1])
    builder.start()


if __name__ == '__main__':
    main()
