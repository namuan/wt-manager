"""Entry point for Git Worktree Manager when run as a module."""

import sys
from .app import main

if __name__ == "__main__":
    sys.exit(main())
