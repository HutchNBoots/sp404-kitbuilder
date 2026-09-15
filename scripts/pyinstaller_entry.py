"""Entry point PyInstaller compiles into the standalone kitbuilder.exe."""

import sys

from kitbuilder.cli import main

if __name__ == "__main__":
    sys.exit(main())
