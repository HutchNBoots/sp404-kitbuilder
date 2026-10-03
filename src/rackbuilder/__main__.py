"""Zero-install fallback: `python -m rackbuilder build ...`."""

import sys

from rackbuilder.cli import main

if __name__ == "__main__":
    sys.exit(main())
