import logging
import os
from rich.logging import RichHandler

_loggers: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = RichHandler(
            rich_tracebacks=True,
            show_path=False,
            markup=True,
        )
        handler.setLevel(level)
        logger.addHandler(handler)

    _loggers[name] = logger
    return logger
