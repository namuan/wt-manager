"""Entry point for Git Worktree Manager.

This module is designed to work both when executed as a package
(`python -m wt_manager`) and when executed as a top-level script in
frozen/packaged environments (e.g., PyInstaller), where relative imports
may fail because there is no package context.
"""

import sys

# Try relative import first (works when run as a module)
try:
    from .app import main  # type: ignore
except Exception:
    # Fallback to absolute import for environments where this file is
    # executed as a top-level script (no package context), such as
    # in PyInstaller onefile/onedir builds.
    from wt_manager.app import main  # type: ignore


if __name__ == "__main__":
    sys.exit(main())
