"""Discovering and reading GitHub-Metrics documents.

Two shapes are accepted from the input directory: bare ``*.json`` files, and
``*.json`` members inside ``*.tar.gz`` archives, so a scan directory can be
handed over as the archive it was shipped in.

Reads are bounded. A document is refused before extraction if it declares a
size over the ceiling, and refused during extraction if it turns out to be
larger than it declared - a tar header states a member's size and nothing
enforces it, so the declared size alone is not a limit.
"""

from __future__ import annotations

import json
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from siat_foreign_analysis.errors import (
    InputDecodeError,
    InputNotAFileError,
    InputNotFoundError,
    InputTooLargeError,
    InputUnreadableError,
)
from siat_foreign_analysis.logger import get_logger
from siat_foreign_analysis.paths import resolve_path, resolve_within

logger = get_logger(__name__)

DEFAULT_INPUT_DIR = Path("input")
"""Where documents are looked for when no path is given."""

MAX_JSON_BYTES = 25 * 1024 * 1024
"""Ceiling for a single document, in bytes."""

PathLike = str | Path | PurePosixPath
"""Anything accepted as a document location, on disk or inside an archive."""


@dataclass(frozen=True)
class InputSource:
    """One document to score, wherever it came from.

    Attributes:
        archive: The ``.tar.gz`` holding the document, or ``None`` when the
            document is a file on disk.
        member: The member name inside the archive, or the path on disk.
    """

    archive: Path | None
    member: PurePosixPath

    def describe(self) -> str:
        r"""Return a single readable identity for logs and error messages.

        The pre-package script rendered these by joining a native path to a
        POSIX one with a literal separator, producing
        ``input\\docs.tar.gz/bcrypt.json`` on Windows. This renders the
        archive in its native form and marks the boundary, so the two halves
        are distinguishable (roadmap item 15).

        Returns:
            ``archive::member`` for an archived document, or the plain path.
        """
        if self.archive is None:
            return str(self.member)
        return f"{self.archive}::{self.member}"


def read_json(
    json_path: PathLike,
    *,
    tar_gz_path: Path | str | None = None,
    encoding: str = "UTF-8",
    strict_utf8: bool = False,
    max_json_bytes: int = MAX_JSON_BYTES,
) -> Any:
    """Load a JSON document from disk or from inside a ``.tar.gz`` archive.

    Args:
        json_path: Path on disk when ``tar_gz_path`` is ``None``, otherwise
            the member name inside that archive.
        tar_gz_path: Archive to read from, or ``None`` to read from disk.
        encoding: Text encoding of the document.
        strict_utf8: Raise on undecodable bytes rather than replacing them.
        max_json_bytes: Refuse a document larger than this.

    Returns:
        The decoded document.

    Raises:
        InputNotFoundError: The file, or the named member, does not exist.
        InputTooLargeError: The document exceeds ``max_json_bytes``.
        InputNotAFileError: The member is not a regular file.
        InputUnreadableError: The archive would not yield the member.
        InputDecodeError: The bytes read are not valid JSON.
    """
    errors_mode = "strict" if strict_utf8 else "replace"

    if tar_gz_path is None:
        raw = _read_from_disk(Path(json_path), max_json_bytes)
        source = str(json_path)
    else:
        raw = _read_from_archive(Path(tar_gz_path), str(json_path), max_json_bytes)
        source = f"{tar_gz_path}::{json_path}"

    text = raw.decode(encoding, errors=errors_mode)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputDecodeError(f"{source}: not valid JSON: {exc}") from exc


def _read_from_disk(path: Path, max_json_bytes: int) -> bytes:
    """Read a bounded number of bytes from a file on disk.

    Args:
        path: File to read.
        max_json_bytes: Refuse a file larger than this.

    Returns:
        The file's bytes.

    Raises:
        InputNotFoundError: The path is not an existing regular file.
        InputTooLargeError: The file exceeds ``max_json_bytes``.
    """
    if not path.is_file():
        raise InputNotFoundError(f"JSON file not found: {path}")

    size = path.stat().st_size
    if size > max_json_bytes:
        raise InputTooLargeError(f"JSON file too large ({size} bytes): {path}")

    return path.read_bytes()


def _read_from_archive(archive: Path, member_name: str, max_json_bytes: int) -> bytes:
    """Read a bounded number of bytes from one member of an archive.

    The member is checked twice. Its declared size is refused before any
    bytes are extracted, and the read itself takes one byte more than the
    ceiling, so a member whose header understates its stream is caught rather
    than trusted.

    Args:
        archive: The ``.tar.gz`` to read from.
        member_name: Name of the member inside the archive.
        max_json_bytes: Refuse a member larger than this.

    Returns:
        The member's bytes.

    Raises:
        InputNotFoundError: The archive holds no such member.
        InputNotAFileError: The member is not a regular file.
        InputTooLargeError: The member exceeds ``max_json_bytes``.
        InputUnreadableError: The archive would not yield the member.
    """
    with tarfile.open(archive, mode="r:gz") as handle:
        try:
            member = handle.getmember(member_name)
        except KeyError as exc:
            raise InputNotFoundError(
                f"JSON member not found in archive: {archive}::{member_name}"
            ) from exc

        # Only regular files. A directory, symlink or hardlink named like a
        # document is not one, and following a link out of the archive is
        # exactly the traversal this refuses to do.
        if not member.isfile():
            raise InputNotAFileError(f"Member is not a regular file: {archive}::{member_name}")

        if member.size > max_json_bytes:
            raise InputTooLargeError(
                f"JSON member too large ({member.size} bytes): {archive}::{member_name}"
            )

        extracted = handle.extractfile(member)
        if extracted is None:
            raise InputUnreadableError(f"Unable to extract member: {archive}::{member_name}")

        raw = extracted.read(max_json_bytes + 1)

    if len(raw) > max_json_bytes:
        raise InputTooLargeError(
            f"JSON member exceeded max_json_bytes while reading: {archive}::{member_name}"
        )

    return raw


def get_json_member_paths_in_tar_gz(
    tar_gz_path: Path | str,
    *,
    case_insensitive: bool = True,
    only_regular_files: bool = True,
) -> list[tuple[Path, PurePosixPath]]:
    """Enumerate JSON members inside a ``.tar.gz`` archive.

    Args:
        tar_gz_path: Archive to walk.
        case_insensitive: Match ``.JSON`` as well as ``.json``.
        only_regular_files: Skip directories, symlinks and hardlinks.

    Returns:
        ``(archive_path, member_path)`` for every JSON member, at any depth.
        :class:`~pathlib.PurePosixPath` is used for the member because tar
        member names always use ``/`` regardless of host operating system.
    """
    archive = Path(tar_gz_path)
    results: list[tuple[Path, PurePosixPath]] = []

    with tarfile.open(archive, mode="r:gz") as handle:
        for member in handle.getmembers():
            if only_regular_files and not member.isfile():
                continue

            name = member.name
            check = name.lower() if case_insensitive else name
            if check.endswith(".json"):
                results.append((archive, PurePosixPath(name)))

    return results


def discover_inputs(input_dir: Path | str = DEFAULT_INPUT_DIR) -> list[InputSource]:
    """Find every document to score, archives first then bare files.

    Both searches are recursive. GitHub-Metrics writes its documents as
    ``<output>/<owner>/<repoid>.json``, so a scan directory copied across
    verbatim has every document one level down. Matching only the top level
    found none of them and wrote an empty report without saying so, which is
    the worst of both: no result and no error (roadmap item 9).

    Results are sorted, so a run over the same directory scores its documents
    in the same order every time and the report keys come out in a stable
    order.

    Every discovered path is confirmed to resolve inside the input directory.
    A scan directory arrives from somewhere else, and a symlink in it pointing
    outside would otherwise be followed by an ordinary read.

    Args:
        input_dir: Directory to search, at any depth.

    Returns:
        Sources in the order they will be scored.

    Raises:
        PathEscapeError: A discovered document or archive resolves outside
            the input directory.
    """
    directory = resolve_path(input_dir)
    sources: list[InputSource] = []

    if not directory.is_dir():
        logger.warning("Input directory does not exist: %s", directory)
        return sources

    for archive_path in sorted(directory.rglob("*.tar.gz")):
        archive = resolve_within(directory, archive_path, what=f"Archive {archive_path.name}")
        members = get_json_member_paths_in_tar_gz(tar_gz_path=archive)
        logger.debug("Archive %s holds %d JSON member(s)", archive, len(members))
        sources.extend(InputSource(archive=found_in, member=member) for found_in, member in members)

    for direct_path in sorted(directory.rglob("*.json")):
        document = resolve_within(directory, direct_path, what=f"Document {direct_path.name}")
        sources.append(InputSource(archive=None, member=PurePosixPath(document.as_posix())))

    if not sources:
        logger.warning("No JSON documents or .tar.gz archives found in %s", directory)

    return sources
