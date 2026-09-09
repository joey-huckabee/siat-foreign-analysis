"""Exception hierarchy for the foreign-analysis pipeline.

Every error raised deliberately by this package descends from
:class:`ForeignAnalysisError`, so a caller embedding the package can catch
the whole family with one clause. The leaf classes additionally inherit the
built-in exception the pre-package script raised at the same point -
:class:`FileNotFoundError`, :class:`ValueError` and so on - so code written
against that behaviour keeps working. The built-in base is part of each
class's contract, not an implementation detail.
"""

from __future__ import annotations


class ForeignAnalysisError(Exception):
    """Base class for every error this package raises deliberately."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ConfigError(ForeignAnalysisError):
    """The country configuration could not be used."""


class ConfigNotFoundError(ConfigError, FileNotFoundError):
    """The configuration file does not exist at the given path."""


class ConfigInvalidError(ConfigError, ValueError):
    """The configuration file exists but is not valid.

    Raised for malformed JSON, a missing `adversarial_nations` list, and a
    nation entry that does not carry both a name and a country code.
    """


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


class InputError(ForeignAnalysisError):
    """An input document could not be read."""


class InputNotFoundError(InputError, FileNotFoundError):
    """A JSON file, or a named member inside an archive, does not exist."""


class InputTooLargeError(InputError, ValueError):
    """A document exceeded the bounded-read ceiling.

    Raised both from the declared size, before any bytes are read, and from
    the read itself, which takes one byte more than the ceiling so that a
    member understating its own length is still caught.
    """


class InputNotAFileError(InputError, IsADirectoryError):
    """An archive member is a directory, symlink, or other non-regular entry."""


class InputUnreadableError(InputError, OSError):
    """An archive member is a regular file the archive will not yield."""


class InputDecodeError(InputError, ValueError):
    """A document was read but is not valid JSON."""


class PathEscapeError(InputError, ValueError):
    """A path resolved outside the directory it was found in.

    Raised for a document under the input directory, or a report under the
    output directory, whose resolved location leaves that directory. A
    symlink is the usual cause.

    Sits under :class:`InputError` because a run meeting one has been handed
    a directory it cannot safely walk, which is an input problem however the
    link got there.
    """


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentError(ForeignAnalysisError):
    """A repository document was read but cannot be scored."""


class MissingFieldError(DocumentError, KeyError):
    """A document lacks a field the score is computed from.

    The pre-package script raised a bare :class:`KeyError` naming the field
    and nothing else, which said nothing about which of the input documents
    was at fault. This names the document as well.
    """

    def __init__(self, field: str, source: str) -> None:
        """Record the absent field and the document that lacked it.

        Args:
            field: Name of the document key that was not present.
            source: Human-readable identity of the offending document.
        """
        self.field = field
        self.source = source
        super().__init__(f"{source}: document has no field {field!r}")

    def __str__(self) -> str:
        """Return the message without ``KeyError``'s repr-quoting."""
        return f"{self.source}: document has no field {self.field!r}"


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


class OutputError(ForeignAnalysisError, OSError):
    """The output directory or one of the reports could not be written."""
