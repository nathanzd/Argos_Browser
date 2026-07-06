from __future__ import annotations

import io
import logging
import sys
import time
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from typing import Any, Callable

from config import settings


def get_logger(name: str = "web-agent") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(fmt)
        logger.addHandler(stdout_handler)

        file_handler = RotatingFileHandler(
            settings.LOG_DIR / settings.LOG_FILE,
            maxBytes=settings.LOG_MAX_MB * 1024 * 1024,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    return logger


@contextmanager
def capture_output() -> (
    Callable[[], tuple[io.StringIO, io.StringIO]]
):
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = stdout_capture
    sys.stderr = stderr_capture
    try:
        yield lambda: (stdout_capture, stderr_capture)
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


@contextmanager
def time_context() -> Callable[[], float]:
    start = time.perf_counter()
    try:
        yield lambda: time.perf_counter() - start
    finally:
        pass


def truncate(text: str, max_len: int = 500) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."
