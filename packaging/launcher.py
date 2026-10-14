"""PyInstaller entry point (an absolute import, unlike screencapture/__main__.py)."""
import sys

from screencapture.app import main

if __name__ == "__main__":
    sys.exit(main())
