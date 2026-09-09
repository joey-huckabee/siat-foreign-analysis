"""Path containment checks.

The three directories this tool works in come from the command line, and the
files it touches inside them do not. A document is found by walking the input
directory; a report is written to a fixed name under the output directory.
Both of those constructions have an invariant worth enforcing: **the file must
stay inside the directory it was found in or written to.**

That is not a theoretical concern for the input side. A scan directory, or a
``.tar.gz`` unpacked into one, arrives from somewhere else. A symlink inside
it pointing at ``../../../etc/passwd`` is followed by an ordinary read, and
the walk that found it would never notice. The archive reader already refuses
non-regular members for this reason; this closes the same hole for documents
already on disk.

The output side is a weaker claim - the report names are literal constants, so
nothing can escape unless the constants change - but checking it costs one
call and means a future report named from data cannot quietly become a write
anywhere on the filesystem.

None of this constrains where the *user* may point ``--input`` and
``--output``. Those are the user's own intent and are resolved, not policed.
"""

from __future__ import annotations

from pathlib import Path

from siat_foreign_analysis.errors import PathEscapeError


def resolve_path(path: Path | str) -> Path:
    """Return an absolute, symlink-free form of a path the user named.

    Resolving early means every later comparison is between two real paths,
    and that log lines and error messages name what was actually used rather
    than whatever relative fragment was typed.

    Args:
        path: The file or directory, as given.

    Returns:
        The resolved path. It need not exist.
    """
    return Path(path).resolve()


def resolve_within(base: Path, candidate: Path | str, *, what: str) -> Path:
    """Resolve ``candidate`` and confirm it stays inside ``base``.

    Both sides are fully resolved first, so a symlink is followed before the
    comparison rather than after it - the point of the check is to catch the
    link that leaves, and comparing unresolved paths would miss exactly that.

    Args:
        base: Directory the candidate must remain inside. Assumed already
            resolved by :func:`resolve_path`.
        candidate: The path to check.
        what: Short description of the candidate, for the error message.

    Returns:
        The resolved candidate.

    Raises:
        PathEscapeError: If the resolved candidate is outside ``base``.
    """
    resolved = Path(candidate).resolve()

    if resolved != base and base not in resolved.parents:
        raise PathEscapeError(
            f"{what} resolves to {resolved}, which is outside {base}. "
            f"A symlink leaving the directory is the usual cause."
        )

    return resolved
