"""PyInstaller entrypoint for the bundled engine and full CLI."""

import multiprocessing
from app.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
