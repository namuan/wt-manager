"""Main application class and entry point."""

import sys
import logging
from PyQt6.QtWidgets import QApplication

from .ui.main_window import MainWindow
from .utils.logging_config import setup_logging


class GitWorktreeManagerApp:
    """Main application class for Git Worktree Manager."""

    def __init__(self):
        self.app: QApplication | None = None
        self.main_window: MainWindow | None = None
        self.logger = logging.getLogger(__name__)

    def initialize(self) -> None:
        """Initialize the application."""
        # Set up logging first
        setup_logging()
        self.logger.info("Initializing Git Worktree Manager")

        # Create QApplication
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Git Worktree Manager")
        self.app.setApplicationVersion("0.1.0")
        self.app.setOrganizationName("GitWorktreeManager")

        # Create main window
        self.main_window = MainWindow()

        # Set up application-wide error handling
        self.app.aboutToQuit.connect(self._on_about_to_quit)

        self.logger.info("Application initialized successfully")

    def run(self) -> int:
        """Run the application."""
        if not self.app or not self.main_window:
            raise RuntimeError("Application not initialized. Call initialize() first.")

        self.logger.info("Starting application")

        # Show main window
        self.main_window.show()

        # Start event loop
        return self.app.exec()

    def _on_about_to_quit(self) -> None:
        """Handle application shutdown."""
        self.logger.info("Application shutting down")

        if self.main_window:
            self.main_window.save_state()


def main() -> int:
    """Main entry point for the application."""
    app = GitWorktreeManagerApp()

    try:
        app.initialize()
        return app.run()
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
