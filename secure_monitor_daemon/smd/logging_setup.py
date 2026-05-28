import logging
from logging.handlers import RotatingFileHandler

from smd.paths import LOG_FILE


def setup_logging(verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("secure_monitor")
    if logger.handlers:
        return logger
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def log_message(message: str, level: int = logging.INFO) -> None:
    setup_logging().log(level, message)
