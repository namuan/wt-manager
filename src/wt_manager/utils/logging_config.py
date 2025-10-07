"""Logging configuration for the application."""

import logging
import logging.handlers
import sys

from .path_manager import PathManager


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}"
                f"{self.COLORS['RESET']}"
            )

        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Set up logging configuration for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to files
        log_to_console: Whether to log to console
        max_file_size: Maximum size of log files before rotation
        backup_count: Number of backup log files to keep
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)

        # Use colored formatter for console
        console_formatter = ColoredFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # File handlers
    if log_to_file:
        try:
            log_dir = PathManager.get_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)

            # Main application log
            app_log_file = log_dir / "app.log"
            app_handler = logging.handlers.RotatingFileHandler(
                app_log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            app_handler.setLevel(numeric_level)

            # File formatter (no colors)
            file_formatter = logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            app_handler.setFormatter(file_formatter)
            root_logger.addHandler(app_handler)

            # Error log (only ERROR and CRITICAL)
            error_log_file = log_dir / "errors.log"
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(file_formatter)
            root_logger.addHandler(error_handler)

            # Git operations log
            git_logger = logging.getLogger("wt_manager.services.git")
            git_log_file = log_dir / "git_operations.log"
            git_handler = logging.handlers.RotatingFileHandler(
                git_log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            git_handler.setLevel(logging.DEBUG)
            git_handler.setFormatter(file_formatter)
            git_logger.addHandler(git_handler)
            git_logger.propagate = True  # Also send to root logger

            # Command execution log
            command_logger = logging.getLogger("wt_manager.services.command")
            command_log_file = log_dir / "command_execution.log"
            command_handler = logging.handlers.RotatingFileHandler(
                command_log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            command_handler.setLevel(logging.DEBUG)
            command_handler.setFormatter(file_formatter)
            command_logger.addHandler(command_handler)
            command_logger.propagate = True  # Also send to root logger

        except Exception as e:
            # If file logging fails, at least log to console
            console_logger = logging.getLogger(__name__)
            console_logger.error(f"Failed to set up file logging: {e}")

    # Log the logging setup
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured - Level: {level}, File: {log_to_file}, Console: {log_to_console}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_log_level(level: str) -> None:
    """
    Change the logging level for all handlers.

    Args:
        level: New logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    for handler in root_logger.handlers:
        handler.setLevel(numeric_level)

    logger = logging.getLogger(__name__)
    logger.info(f"Log level changed to {level}")


def log_exception(
    logger: logging.Logger, message: str = "An exception occurred"
) -> None:
    """
    Log an exception with full traceback.

    Args:
        logger: Logger instance to use
        message: Custom message to include with the exception
    """
    logger.exception(message)


class StructuredErrorFormatter(logging.Formatter):
    """Formatter for structured error logging with additional context."""

    def format(self, record):
        # Add structured error information if available
        if hasattr(record, "error_details"):
            # Format the base message
            formatted = super().format(record)

            # Add structured error details
            error_details = record.error_details
            if isinstance(error_details, dict):
                details_lines = []
                for key, value in error_details.items():
                    if value is not None:
                        details_lines.append(f"  {key}: {value}")

                if details_lines:
                    formatted += "\nError Details:\n" + "\n".join(details_lines)

            # Add traceback if available
            if hasattr(record, "traceback") and record.traceback:
                formatted += f"\nTraceback:\n{record.traceback}"

            return formatted

        return super().format(record)


def setup_error_logging() -> None:
    """Set up specialized error logging with structured format."""
    try:
        log_dir = PathManager.get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create error logger with structured formatter
        error_logger = logging.getLogger("wt_manager.errors")

        # Structured error log file
        structured_error_file = log_dir / "structured_errors.log"
        structured_handler = logging.handlers.RotatingFileHandler(
            structured_error_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        structured_handler.setLevel(logging.ERROR)

        # Use structured formatter
        structured_formatter = StructuredErrorFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        structured_handler.setFormatter(structured_formatter)

        error_logger.addHandler(structured_handler)
        error_logger.setLevel(logging.ERROR)
        error_logger.propagate = False  # Don't propagate to avoid duplicate logs

    except Exception as e:
        # Fallback logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to set up structured error logging: {e}")


def log_structured_error(
    error_dict: dict, message: str = "Structured error occurred"
) -> None:
    """
    Log a structured error with detailed information.

    Args:
        error_dict: Dictionary containing error details
        message: Main error message
    """
    error_logger = logging.getLogger("wt_manager.errors")
    error_logger.error(message, extra={"error_details": error_dict})
