import sys
from builder import ZMachineBuilder


def main():
    builder = ZMachineBuilder(sys.argv[1])
    builder.start()


if __name__ == '__main__':
    main()
