# Z-Machine interpreter

Python 3 implementation of a z-machine interpreter, for playing Infocom games. To play a z-machine file:

`python -m zmachine [GAME_FILE] [--graphics]`

The games will be rendered in a terminal with [curses](https://docs.python.org/3/howto/curses.html) by default. The optional `--graphics` flag will open the game in a separate window with enhanced graphics rendering. This option has a dependency on the [pygame](https://www.pygame.org) package.

The interpreter supports z-machine versions 3-6. Version 3 is the build for most of the older Infocom games such as the Zork trilogy. Version 4 games include Trinity, AMFV, and Bureaucracy. Version 5 games include Border Zone and Beyond Zork. Version 6 games include Zork Zero, Arthur, and Shogun. Save files are in [Quetzal](http://inform-fiction.org/zmachine/standards/quetzal/index.html) format and should be compatible with the Frotz interpreter.

Version 6 games require graphics rendering and the `--graphics` flag is enabled by default. The interpreter will recognize a [blorb](https://ifarchive.org/indexes/if-archive/infocom/media/blorb/) resource that is in the same directory as the game file.

The original Zork trilogy (written by Tim Anderson, Marc Blank, Bruce Daniels, and Dave Lebling) is in the `games` directory.

## Further notes

The [Z-Machine Standards Document](https://www.inform-fiction.org/zmachine/standards/z1point1/index.html), by Graham Nelson, is an indispensable guide for decoding the z-machine instructions.

This space intentionally left blank.
