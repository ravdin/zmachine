from screen_test import ScreenTest


def main():
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
