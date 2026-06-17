import argparse
from .screen_test import ScreenTest


def main():
    parser = argparse.ArgumentParser()
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
    version = 4
    tester = ScreenTest(version)
    try:
        tester.run()
    except Exception as e:
        print(f"{e.__str__()}")
    finally:
        tester.shutdown()


if __name__ == '__main__':
    main()
