"""Entry point PyInstaller compiles into the standalone rackbuilder.exe."""

import sys

from rackbuilder.cli import main

if __name__ == "__main__":
    sys.exit(main())
