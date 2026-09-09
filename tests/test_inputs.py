"""Reading documents from disk and from archives, and finding them."""

from __future__ import annotations

import io
import json
import tarfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

import pytest

from siat_foreign_analysis.errors import (
    InputDecodeError,
    InputError,
    InputNotAFileError,
    InputNotFoundError,
    InputTooLargeError,
    InputUnreadableError,
)
from siat_foreign_analysis.inputs import (
    InputSource,
    discover_inputs,
    get_json_member_paths_in_tar_gz,
    read_json,
)
from tests.conftest import write_tar_gz

PAYLOAD = json.dumps({"name": "example"}).encode()


# ---------------------------------------------------------------------------
# Reading from disk
# ---------------------------------------------------------------------------


def test_reads_a_document_from_disk(tmp_path: Path) -> None:
    path = tmp_path / "doc.json"
    path.write_bytes(PAYLOAD)

    assert read_json(path) == {"name": "example"}


def test_a_missing_file_is_reported_as_missing(tmp_path: Path) -> None:
    with pytest.raises(InputNotFoundError, match="JSON file not found"):
        read_json(tmp_path / "absent.json")


def test_a_directory_is_not_a_document(tmp_path: Path) -> None:
    with pytest.raises(InputNotFoundError):
        read_json(tmp_path)


def test_an_oversized_file_is_refused_before_it_is_read(tmp_path: Path) -> None:
    path = tmp_path / "big.json"
    path.write_bytes(b"[" + b"0," * 100 + b"0]")

    with pytest.raises(InputTooLargeError, match="too large"):
        read_json(path, max_json_bytes=10)


def test_malformed_json_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_bytes(b"{not json")

    with pytest.raises(InputDecodeError, match=r"broken\.json"):
        read_json(path)


def test_undecodable_bytes_are_replaced_by_default(tmp_path: Path) -> None:
    path = tmp_path / "latin.json"
    path.write_bytes('{"name": "caf\xe9"}'.encode("latin-1"))

    assert read_json(path)["name"].startswith("caf")


def test_undecodable_bytes_raise_under_strict_utf8(tmp_path: Path) -> None:
    path = tmp_path / "latin.json"
    path.write_bytes('{"name": "caf\xe9"}'.encode("latin-1"))

    with pytest.raises(UnicodeDecodeError):
        read_json(path, strict_utf8=True)


# ---------------------------------------------------------------------------
# Reading from archives
# ---------------------------------------------------------------------------


def test_reads_a_member_from_an_archive(
    tar_gz_factory: Callable[[str, dict[str, bytes]], Path],
) -> None:
    archive = tar_gz_factory("docs.tar.gz", {"a/doc.json": PAYLOAD})

    assert read_json("a/doc.json", tar_gz_path=archive) == {"name": "example"}


def test_a_missing_member_names_the_archive(
    tar_gz_factory: Callable[[str, dict[str, bytes]], Path],
) -> None:
    archive = tar_gz_factory("docs.tar.gz", {"a/doc.json": PAYLOAD})

    with pytest.raises(InputNotFoundError, match="not found in archive"):
        read_json("a/absent.json", tar_gz_path=archive)


def test_a_directory_member_is_refused(tmp_path: Path) -> None:
    archive = tmp_path / "docs.tar.gz"
    with tarfile.open(archive, mode="w:gz") as handle:
        info = tarfile.TarInfo(name="a")
        info.type = tarfile.DIRTYPE
        handle.addfile(info)

    with pytest.raises(InputNotAFileError, match="not a regular file"):
        read_json("a", tar_gz_path=archive)


def test_a_symlink_member_is_refused(tmp_path: Path) -> None:
    """Following a link out of the archive is the traversal this refuses."""
    archive = tmp_path / "docs.tar.gz"
    with tarfile.open(archive, mode="w:gz") as handle:
        info = tarfile.TarInfo(name="escape.json")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../../etc/passwd"
        handle.addfile(info)

    with pytest.raises(InputNotAFileError):
        read_json("escape.json", tar_gz_path=archive)


def test_a_member_declaring_an_oversize_is_refused(
    tar_gz_factory: Callable[[str, dict[str, bytes]], Path],
) -> None:
    archive = tar_gz_factory("docs.tar.gz", {"doc.json": b"x" * 100})

    with pytest.raises(InputTooLargeError, match="member too large"):
        read_json("doc.json", tar_gz_path=archive, max_json_bytes=10)


def test_a_member_understating_its_size_is_caught_while_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The read takes one byte past the ceiling, and that byte is the check.

    A tar header states a member's size and nothing enforces it, so the
    declared-size check is a claim rather than a limit. Reaching the guard
    needs a stream longer than the header admits, which `tarfile` will not
    produce on its own - it bounds every `extractfile` stream by the declared
    size - so the oversized stream is substituted here. The guard is
    unreachable through `tarfile`'s own API and is kept as the cheap half of
    a belt-and-braces pair.
    """
    archive = tmp_path / "liar.tar.gz"
    with tarfile.open(archive, mode="w:gz") as handle:
        info = tarfile.TarInfo(name="doc.json")
        info.size = 5
        handle.addfile(info, io.BytesIO(b"x" * 5))

    # Signature must match TarFile.extractfile; neither argument is needed.
    def oversized(  # pylint: disable=unused-argument
        self: tarfile.TarFile, member: object
    ) -> io.BytesIO:
        return io.BytesIO(b"x" * 5000)

    monkeypatch.setattr(tarfile.TarFile, "extractfile", oversized)

    with pytest.raises(InputTooLargeError, match="while reading"):
        read_json("doc.json", tar_gz_path=archive, max_json_bytes=10)


def test_a_member_the_archive_will_not_yield_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "docs.tar.gz"
    with tarfile.open(archive, mode="w:gz") as handle:
        info = tarfile.TarInfo(name="doc.json")
        info.size = len(PAYLOAD)
        handle.addfile(info, io.BytesIO(PAYLOAD))

    monkeypatch.setattr(tarfile.TarFile, "extractfile", lambda self, member: None)

    with pytest.raises(InputUnreadableError, match="Unable to extract"):
        read_json("doc.json", tar_gz_path=archive)


def test_a_non_regular_member_named_like_a_document_is_skipped(tmp_path: Path) -> None:
    """A directory called `dir.json` matches the suffix and is not a file."""
    archive = tmp_path / "docs.tar.gz"
    with tarfile.open(archive, mode="w:gz") as handle:
        info = tarfile.TarInfo(name="dir.json")
        info.type = tarfile.DIRTYPE
        handle.addfile(info)

    assert get_json_member_paths_in_tar_gz(archive) == []
    assert len(get_json_member_paths_in_tar_gz(archive, only_regular_files=False)) == 1


def test_every_size_error_is_an_input_error(
    tar_gz_factory: Callable[[str, dict[str, bytes]], Path],
) -> None:
    """One except clause catches the whole family."""
    archive = tar_gz_factory("docs.tar.gz", {"doc.json": b"x" * 100})

    with pytest.raises(InputError):
        read_json("doc.json", tar_gz_path=archive, max_json_bytes=10)


# ---------------------------------------------------------------------------
# Enumerating archives
# ---------------------------------------------------------------------------


def test_json_members_are_found_at_any_depth(
    tar_gz_factory: Callable[[str, dict[str, bytes]], Path],
) -> None:
    archive = tar_gz_factory(
        "docs.tar.gz",
        {"scan/owner/a.json": PAYLOAD, "scan/b.json": PAYLOAD, "notes.txt": b"hello"},
    )

    members = [member for _, member in get_json_member_paths_in_tar_gz(archive)]

    assert PurePosixPath("scan/owner/a.json") in members
    assert PurePosixPath("scan/b.json") in members
    assert len(members) == 2


def test_uppercase_suffixes_are_matched_by_default(
    tar_gz_factory: Callable[[str, dict[str, bytes]], Path],
) -> None:
    archive = tar_gz_factory("docs.tar.gz", {"A.JSON": PAYLOAD})

    assert len(get_json_member_paths_in_tar_gz(archive)) == 1
    assert get_json_member_paths_in_tar_gz(archive, case_insensitive=False) == []


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_discovers_bare_documents(tmp_path: Path) -> None:
    (tmp_path / "b.json").write_bytes(PAYLOAD)
    (tmp_path / "a.json").write_bytes(PAYLOAD)
    (tmp_path / "notes.txt").write_bytes(b"ignored")

    sources = discover_inputs(tmp_path)

    assert [Path(str(source.member)).name for source in sources] == ["a.json", "b.json"]
    assert all(source.archive is None for source in sources)


def test_archives_are_discovered_before_bare_files(
    tmp_path: Path, tar_gz_factory: Callable[[str, dict[str, bytes]], Path]
) -> None:
    (tmp_path / "bare.json").write_bytes(PAYLOAD)
    archive = tar_gz_factory("docs.tar.gz", {"inner.json": PAYLOAD})
    archive.rename(tmp_path / "docs.tar.gz")

    sources = discover_inputs(tmp_path)

    assert sources[0].archive is not None
    assert sources[-1].archive is None


def test_a_missing_input_directory_yields_nothing(tmp_path: Path) -> None:
    assert discover_inputs(tmp_path / "absent") == []


def test_an_empty_input_directory_yields_nothing(tmp_path: Path) -> None:
    assert discover_inputs(tmp_path) == []


def test_nested_documents_are_read(tmp_path: Path) -> None:
    """Roadmap item 9: a scan directory copied verbatim used to score nothing.

    GitHub-Metrics writes `<owner>/<repoid>.json`, so this is the shape a
    real scan arrives in.
    """
    nested = tmp_path / "pyca"
    nested.mkdir()
    (nested / "bcrypt.json").write_bytes(PAYLOAD)

    sources = discover_inputs(tmp_path)

    assert [Path(str(s.member)).name for s in sources] == ["bcrypt.json"]


def test_documents_are_found_at_any_depth(tmp_path: Path) -> None:
    for depth in ("a.json", "one/b.json", "one/two/c.json"):
        target = tmp_path / depth
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PAYLOAD)

    names = [Path(str(s.member)).name for s in discover_inputs(tmp_path)]

    assert sorted(names) == ["a.json", "b.json", "c.json"]


def test_nested_archives_are_found_too(tmp_path: Path) -> None:
    nested = tmp_path / "scans" / "2026-09"
    nested.mkdir(parents=True)
    write_tar_gz(nested / "docs.tar.gz", {"inner.json": PAYLOAD})

    sources = discover_inputs(tmp_path)

    assert len(sources) == 1
    assert sources[0].archive is not None


def test_discovery_order_is_stable(tmp_path: Path) -> None:
    """Report keys come out in discovery order, so it must not wobble."""
    for name in ("z.json", "a.json", "m/n.json"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PAYLOAD)

    first = [s.member for s in discover_inputs(tmp_path)]
    second = [s.member for s in discover_inputs(tmp_path)]

    assert first == second == sorted(first)


# ---------------------------------------------------------------------------
# InputSource
# ---------------------------------------------------------------------------


def test_a_bare_source_describes_itself_as_a_path() -> None:
    source = InputSource(archive=None, member=PurePosixPath("input/bcrypt.json"))
    assert source.describe() == "input/bcrypt.json"


def test_an_archived_source_marks_the_archive_boundary() -> None:
    """Roadmap item 15: the two halves used to run together."""
    source = InputSource(archive=Path("input/docs.tar.gz"), member=PurePosixPath("bcrypt.json"))

    described = source.describe()

    assert described.endswith("::bcrypt.json")
    assert "docs.tar.gz" in described
