"""Centralized logging with rotating file handler and Qt bridge signal."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from qtpy.QtCore import QObject, Signal
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QObject = object  # type: ignore[assignment,misc]

from src.utils.paths import logs_dir


class QtLogHandler(logging.Handler, QObject):
    """Bridges Python log records to the GUI LogPanel via a Qt signal.

    Attach this handler to any logger and connect ``log_message`` to a
    ``QTextEdit`` slot to display live log output in the application.

    Example::

        handler = QtLogHandler()
        handler.log_message.connect(my_text_edit.append)
        logging.getLogger("sound_processor").addHandler(handler)
    """

    if _QT_AVAILABLE:
        #: Emitted with the formatted log string for each record.
        log_message = Signal(str)

    def __init__(self) -> None:
        if not _QT_AVAILABLE:
            raise ImportError(
                "qtpy is required to use QtLogHandler. "
                "Install it with: pip install qtpy"
            )
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:
        """Format *record* and emit :attr:`log_message`."""
        try:
            self.log_message.emit(self.format(record))
        except Exception:  # noqa: BLE001 — must not raise inside logging
            self.handleError(record)


def setup_logger(
    name: str = "sound_processor",
    log_dir: Path | None = None,
    level: int = logging.DEBUG,
) -> logging.Logger:
    """Configure and return the named application logger.

    Sets up a rotating file handler (5 MB × 3 backups) and a console handler.
    Safe to call multiple times — returns the existing logger if already
    configured.

    Args:
        name:    Logger name (default ``"sound_processor"``).
        log_dir: Directory for the rotating log file.  Defaults to
                 ``<project_root>/logs``.
        level:   Root logging level (default :data:`logging.DEBUG`).

    Returns:
        Configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        # Already configured — avoid duplicate handlers on re-import.
        return logger

    if log_dir is None:
        log_dir = logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Rotating file handler -------------------------------------------
    file_handler = RotatingFileHandler(
        log_dir / "sound_processor.log",
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # --- Console (stderr) handler ----------------------------------------
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.debug("Logger '%s' initialised (log_dir=%s)", name, log_dir)
    return logger


def get_logger(name: str = "sound_processor") -> logging.Logger:
    """Convenience wrapper — return (possibly unconfigured) named logger.

    Use :func:`setup_logger` for the root app logger.  Child module loggers
    should use this helper with a dotted name::

        log = get_logger("sound_processor.audio.loader")
    """
    return logging.getLogger(name)
