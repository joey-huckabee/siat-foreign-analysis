"""The exception hierarchy.

Every leaf inherits both :class:`ForeignAnalysisError` and the built-in the
pre-package script raised at the same point. Both bases are contract: the
first lets an embedder catch the family, the second keeps code written
against the old behaviour working. These tests exist so neither is dropped by
accident.
"""

from __future__ import annotations

import pytest

from siat_foreign_analysis.errors import (
    ConfigError,
    ConfigInvalidError,
    ConfigNotFoundError,
    DocumentError,
    ForeignAnalysisError,
    InputDecodeError,
    InputError,
    InputNotAFileError,
    InputNotFoundError,
    InputTooLargeError,
    InputUnreadableError,
    MissingFieldError,
    OutputError,
)

LEAVES = [
    ConfigNotFoundError,
    ConfigInvalidError,
    InputNotFoundError,
    InputTooLargeError,
    InputNotAFileError,
    InputUnreadableError,
    InputDecodeError,
    MissingFieldError,
    OutputError,
]


@pytest.mark.parametrize("error", LEAVES)
def test_every_error_is_a_foreign_analysis_error(error: type[Exception]) -> None:
    assert issubclass(error, ForeignAnalysisError)


@pytest.mark.parametrize(
    ("error", "builtin"),
    [
        (ConfigNotFoundError, FileNotFoundError),
        (ConfigInvalidError, ValueError),
        (InputNotFoundError, FileNotFoundError),
        (InputTooLargeError, ValueError),
        (InputNotAFileError, IsADirectoryError),
        (InputUnreadableError, OSError),
        (InputDecodeError, ValueError),
        (MissingFieldError, KeyError),
        (OutputError, OSError),
    ],
)
def test_the_builtin_base_is_preserved(error: type[Exception], builtin: type[Exception]) -> None:
    """1.1.0 raised these built-ins; catching them still works."""
    assert issubclass(error, builtin)


@pytest.mark.parametrize(
    ("error", "family"),
    [
        (ConfigNotFoundError, ConfigError),
        (ConfigInvalidError, ConfigError),
        (InputNotFoundError, InputError),
        (InputTooLargeError, InputError),
        (InputNotAFileError, InputError),
        (InputUnreadableError, InputError),
        (InputDecodeError, InputError),
        (MissingFieldError, DocumentError),
    ],
)
def test_each_leaf_sits_under_its_family(error: type[Exception], family: type[Exception]) -> None:
    assert issubclass(error, family)


def test_a_missing_field_names_the_field_and_the_document() -> None:
    error = MissingFieldError("stars_score", "input/bcrypt.json")

    assert error.field == "stars_score"
    assert error.source == "input/bcrypt.json"
    assert "stars_score" in str(error)
    assert "input/bcrypt.json" in str(error)


def test_a_missing_field_reads_cleanly_despite_being_a_key_error() -> None:
    """KeyError.__str__ is repr(), which would quote the whole message.

    Only the field name is quoted, and that is deliberate - it is the one
    part of the message that could otherwise be mistaken for prose.
    """
    assert str(MissingFieldError("name", "doc.json")) == ("doc.json: document has no field 'name'")
