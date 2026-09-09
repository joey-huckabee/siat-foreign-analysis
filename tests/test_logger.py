"""Logging setup."""

from __future__ import annotations

import io
import logging

from siat_foreign_analysis.logger import PACKAGE_LOGGER_NAME, configure_logging, get_logger


def test_a_module_name_becomes_a_child_of_the_package_logger() -> None:
    assert get_logger("siat_foreign_analysis.scoring").name == "siat_foreign_analysis.scoring"


def test_a_foreign_name_is_adopted_under_the_package_logger() -> None:
    """No call can reconfigure the root logger by accident."""
    assert get_logger("something_else").name == "siat_foreign_analysis.something_else"


def test_the_package_name_itself_is_returned_unchanged() -> None:
    assert get_logger(PACKAGE_LOGGER_NAME).name == PACKAGE_LOGGER_NAME


def test_configure_is_idempotent() -> None:
    """Calling twice replaces the handler rather than duplicating output."""
    configure_logging(logging.INFO)
    configure_logging(logging.INFO)

    assert len(logging.getLogger(PACKAGE_LOGGER_NAME).handlers) == 1


def test_records_reach_the_configured_stream() -> None:
    stream = io.StringIO()
    configure_logging(logging.INFO, stream=stream)

    get_logger("test").info("hello")

    assert "hello" in stream.getvalue()


def test_the_level_is_honoured() -> None:
    stream = io.StringIO()
    configure_logging(logging.WARNING, stream=stream)

    logger = get_logger("test")
    logger.info("suppressed")
    logger.warning("shown")

    written = stream.getvalue()
    assert "suppressed" not in written
    assert "shown" in written


def test_debug_uses_the_verbose_format() -> None:
    stream = io.StringIO()
    configure_logging(logging.DEBUG, stream=stream)

    get_logger("test").debug("detail")

    # The verbose format carries the logger name; the default one does not.
    assert "siat_foreign_analysis.test" in stream.getvalue()


def test_records_do_not_propagate_to_the_root_logger() -> None:
    configure_logging(logging.INFO)

    assert logging.getLogger(PACKAGE_LOGGER_NAME).propagate is False
