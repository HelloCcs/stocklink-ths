"""Bounded local application diagnostics."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from PySide6.QtCore import QStandardPaths


def configure_log(directory=None):
    logger = logging.getLogger('StockLink')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger
    directory = Path(directory) if directory else Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)) / 'StockLink' / 'logs'
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / 'app.log', maxBytes=1_000_000, backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())
    return logger


def log_path(logger):
    return next((handler.baseFilename for handler in logger.handlers if isinstance(handler, RotatingFileHandler)), None)
