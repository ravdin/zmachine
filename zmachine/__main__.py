import sys
from zmachine import zmachine
from screen import screen

def main():
    game = zmachine(sys.argv[1])
    screen(game)

if __name__ == '__main__':
    main()
