#!/usr/bin/env python3
"""Compatibility entry point; install with pip install -e . for `omnidev`."""
from app.cli import *
if __name__ == "__main__":
    import sys
    sys.exit(main())
