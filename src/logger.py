import logging
import os
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
_configured = False


def setup_logging(level: str = None) -> logging.Logger:
    global _configured
    if _configured:
        return logging.getLogger("confessit")

    log_level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    os.makedirs(_LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # capture everything; handlers filter

    file_handler = RotatingFileHandler(
        os.path.join(_LOG_DIR, "confessit.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    console_handler = RichHandler(
        level=log_level,
        rich_tracebacks=True,
        show_path=False,
        omit_repeated_times=False,
    )

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Silence noisy third-party loggers
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    _configured = True
    return logging.getLogger("confessit")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"confessit.{name}")
