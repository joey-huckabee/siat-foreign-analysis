"""Logging for the foreign-analysis pipeline.

The pre-package script wrote its progress with 39 `print()` calls, which put
per-contributor detail and one-line summaries on the same stream at the same
volume with no way to separate them. Everything now logs through a child of
:data:`PACKAGE_LOGGER_NAME`, so a run can be quietened to its conclusions or
opened up to every contributor.

Diagnostics go to **stderr**, leaving stdout free. The reports are files; the
log is commentary about producing them, and the two should not have to be
untangled by whoever redirects the run.
"""

from __future__ import annotations

import logging
import sys
from typing import Final, TextIO

PACKAGE_LOGGER_NAME: Final = "siat_foreign_analysis"
"""Every module in the package logs through a child of this logger."""

_DEFAULT_FORMAT: Final = "%(levelname)-8s %(message)s"
_VERBOSE_FORMAT: Final = "%(levelname)-8s %(asctime)s %(name)s:%(lineno)s %(message)s"
_DATE_FORMAT: Final = "%Y-%m-%dT%H:%M:%S%z"


def get_logger(name: str) -> logging.Logger:
    """Return the package logger, or a named child of it.

    Args:
        name: A module's ``__name__``. A name already inside the package is
            returned as-is; anything else becomes a child of the package
            logger, so no call can accidentally configure the root logger.

    Returns:
        The logger this module should write to.
    """
    if name == PACKAGE_LOGGER_NAME or name.startswith(f"{PACKAGE_LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{PACKAGE_LOGGER_NAME}.{name}")


def configure_logging(level: int = logging.INFO, *, stream: TextIO | None = None) -> None:
    """Attach a single stderr handler to the package logger.

    Idempotent: calling it twice replaces the handler rather than adding a
    second one, so a caller that configures logging and then imports another
    entry point does not get every line twice.

    Propagation to the root logger is switched off. A library embedding this
    package configures its own handlers, and inheriting ours would duplicate
    every record into them.

    Args:
        level: Threshold for the package logger.
        stream: Where records are written. Defaults to :data:`sys.stderr`.
    """
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)

    for existing in list(logger.handlers):
        logger.removeHandler(existing)
        existing.close()

    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    fmt = _VERBOSE_FORMAT if level <= logging.DEBUG else _DEFAULT_FORMAT
    handler.setFormatter(logging.Formatter(fmt, datefmt=_DATE_FORMAT))

    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
