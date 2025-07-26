import logging.config
import os
import re
import tomllib
from pathlib import Path
from pythonjsonlogger import jsonlogger


def get_package_version() -> str:
    """Read the package version from pyproject.toml."""
    try:
        # Get the path to pyproject.toml (assuming it's in the project root)
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)

        version = pyproject_data.get("project", {}).get("version", "unknown")
        return version
    except Exception:
        # Fallback if we can't read the version
        return "unknown"


class VersionFilter(logging.Filter):
    """Filter to add package version to all log records."""

    def __init__(self) -> None:
        super().__init__()
        self.version = get_package_version()

    def filter(self, record: logging.LogRecord) -> bool:
        """Add version information to the log record."""
        record.version = self.version
        return True


class SecurityFilter(logging.Filter):
    """Filter to remove sensitive information from logs."""

    SENSITIVE_KEYS = {
        "authorization",
        "x-cashu",
        "bearer",
        "token",
        "key",
        "secret",
        "password",
        "cashu_token",
        "bearer_key",
        "api_key",
        "nsec",
        "upstream_api_key",
        "refund_address",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out sensitive information from log records."""
        try:
            # Get the formatted message
            message = record.getMessage()

            # Simple redaction - replace anything that looks like sensitive data
            for key in self.SENSITIVE_KEYS:
                if key in message.lower():
                    # Use regex to find and redact sensitive patterns
                    # This looks for the key followed by optional characters and captures sensitive data
                    patterns = [
                        rf"{key}[:\s=]+([a-zA-Z0-9_\-\.]+)",  # key: value or key=value
                        rf'{key}[:\s=]+["\']([^"\']+)["\']',  # key: "value" or key='value'
                        rf"Bearer\s+([a-zA-Z0-9_\-\.]+)",  # Bearer token
                        rf"cashu[A-Z]+([a-zA-Z0-9_\-\.=/+]+)",  # Cashu tokens
                    ]

                    for pattern in patterns:
                        message = re.sub(
                            pattern, f"{key}: [REDACTED]", message, flags=re.IGNORECASE
                        )

            # Update the record message
            record.msg = message
            record.args = ()  # Clear args since we've formatted the message

        except Exception:
            # If anything goes wrong with filtering, just pass through the original record
            # We don't want logging to break the application
            pass

        return True


def get_log_level() -> str:
    """Get log level from environment variable."""
    return os.environ.get("LOG_LEVEL", "INFO").upper()


def setup_logging() -> None:
    """Configure centralized logging for the application."""

    log_level = get_log_level()

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": jsonlogger.JsonFormatter,
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d %(version)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s v%(version)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "filters": {
            "version_filter": {"()": VersionFilter},
            "security_filter": {"()": SecurityFilter},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "json"
                if os.environ.get("LOG_FORMAT", "json").lower() == "json"
                else "standard",
                "stream": "ext://sys.stdout",
                "filters": ["version_filter", "security_filter"],
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "json",
                "filename": "logs/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "filters": ["version_filter", "security_filter"],
            },
        },
        "loggers": {
            "router": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "router.payment": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "router.cashu": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "router.proxy": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "router.auth": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            # Suppress verbose third-party logging
            "httpx": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "httpcore": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {"level": log_level, "handlers": ["console"]},
    }

    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    logging.config.dictConfig(LOGGING_CONFIG)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given module name."""
    return logging.getLogger(name)
