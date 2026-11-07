#!/usr/bin/env python3
"""Launch the shared CLI in interactive chat mode."""
import sys
from app.cli import main
if __name__ == "__main__":
    sys.argv = [sys.argv[0], "chat", "--interactive", *sys.argv[1:]]
    sys.exit(main())
