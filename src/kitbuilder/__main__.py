"""Zero-install fallback: `python -m kitbuilder scan/report/export ...`."""

import sys

from kitbuilder.cli import main

if __name__ == "__main__":
    sys.exit(main())
