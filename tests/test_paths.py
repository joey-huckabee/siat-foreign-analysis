"""Path containment.

The input directory is walked, and what is found there is read. A scan
directory or an unpacked archive arrives from somewhere else, so a symlink
inside it pointing out is followed by an ordinary read unless something
checks. These are the tests for that check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from siat_foreign_analysis.errors import ForeignAnalysisError, InputError, PathEscapeError
from siat_foreign_analysis.inputs import discover_inputs
from siat_foreign_analysis.paths import resolve_path, resolve_within

PAYLOAD = json.dumps({"name": "example"}).encode()


def symlinks_work(tmp_path: Path) -> bool:
    """Return whether this platform and account can create symlinks.

    Windows needs Developer Mode or elevation, so the symlink tests skip
    rather than fail on a machine that cannot make one.
    """
    target = tmp_path / "_probe_target"
    target.write_text("x", encoding="UTF-8")
    try:
        (tmp_path / "_probe_link").symlink_to(target)
    except (OSError, NotImplementedError):
        return False
    return True


# ---------------------------------------------------------------------------
# resolve_path
# ---------------------------------------------------------------------------


def test_a_relative_path_becomes_absolute(tmp_path: Path) -> None:
    assert resolve_path(tmp_path).is_absolute()


def test_dot_segments_are_removed(tmp_path: Path) -> None:
    assert resolve_path(tmp_path / "a" / ".." / "b") == resolve_path(tmp_path / "b")


def test_a_path_need_not_exist(tmp_path: Path) -> None:
    assert resolve_path(tmp_path / "not-here").name == "not-here"


# ---------------------------------------------------------------------------
# resolve_within
# ---------------------------------------------------------------------------


def test_a_child_is_allowed(tmp_path: Path) -> None:
    base = resolve_path(tmp_path)
    assert resolve_within(base, base / "report.json", what="report") == base / "report.json"


def test_a_deeper_descendant_is_allowed(tmp_path: Path) -> None:
    base = resolve_path(tmp_path)
    deep = base / "a" / "b" / "c.json"
    assert resolve_within(base, deep, what="doc") == deep


def test_the_base_itself_is_allowed(tmp_path: Path) -> None:
    base = resolve_path(tmp_path)
    assert resolve_within(base, base, what="base") == base


def test_a_sibling_is_refused(tmp_path: Path) -> None:
    base = resolve_path(tmp_path / "inside")
    base.mkdir()

    with pytest.raises(PathEscapeError, match="outside"):
        resolve_within(base, tmp_path / "elsewhere.json", what="doc")


def test_a_parent_traversal_is_refused(tmp_path: Path) -> None:
    base = resolve_path(tmp_path / "inside")
    base.mkdir()

    with pytest.raises(PathEscapeError, match="outside"):
        resolve_within(base, base / ".." / ".." / "etc" / "passwd", what="doc")


def test_a_path_escape_is_an_input_error(tmp_path: Path) -> None:
    """One except clause catches it with the rest of the input family."""
    base = resolve_path(tmp_path / "inside")
    base.mkdir()
    outside = tmp_path / "elsewhere.json"

    with pytest.raises(InputError):
        resolve_within(base, outside, what="doc")
    with pytest.raises(ForeignAnalysisError):
        resolve_within(base, outside, what="doc")


def test_a_prefix_match_is_not_containment(tmp_path: Path) -> None:
    """`/scans/input-old` must not count as inside `/scans/input`."""
    base = resolve_path(tmp_path / "input")
    base.mkdir()
    decoy = tmp_path / "input-old"
    decoy.mkdir()

    with pytest.raises(PathEscapeError):
        resolve_within(base, decoy / "doc.json", what="doc")


# ---------------------------------------------------------------------------
# Discovery refuses to follow a link out of the input directory
# ---------------------------------------------------------------------------


def test_a_symlinked_document_leaving_the_input_directory_is_refused(
    tmp_path: Path,
) -> None:
    """The threat this exists for: a scan directory someone else produced."""
    if not symlinks_work(tmp_path):
        pytest.skip("this platform or account cannot create symlinks")

    secret = tmp_path / "secret.json"
    secret.write_bytes(PAYLOAD)

    inbox = tmp_path / "input"
    inbox.mkdir()
    (inbox / "innocent.json").symlink_to(secret)

    with pytest.raises(PathEscapeError, match="outside"):
        discover_inputs(inbox)


def test_a_symlink_staying_inside_the_input_directory_is_fine(tmp_path: Path) -> None:
    """Containment is the rule, not a ban on symlinks."""
    if not symlinks_work(tmp_path):
        pytest.skip("this platform or account cannot create symlinks")

    inbox = tmp_path / "input"
    (inbox / "real").mkdir(parents=True)
    target = inbox / "real" / "doc.json"
    target.write_bytes(PAYLOAD)
    (inbox / "alias.json").symlink_to(target)

    sources = discover_inputs(inbox)

    assert len(sources) == 2


def test_ordinary_discovery_is_unaffected(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_bytes(PAYLOAD)
    nested = tmp_path / "owner"
    nested.mkdir()
    (nested / "b.json").write_bytes(PAYLOAD)

    assert len(discover_inputs(tmp_path)) == 2
