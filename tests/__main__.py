from screen_test import ScreenTest


def main():
    tester = ScreenTest(4)
    try:
        tester.test_split_window()
        tester.test_overlay()
        tester.test_menu()
        tester.test_erase_window()
    except Exception as e:
        print(f"{e.__str__()}")
    finally:
        tester.shutdown()


if __name__ == '__main__':
    main()
