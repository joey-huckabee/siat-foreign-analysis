"""Shared fixtures.

``tests/fixtures/documents`` holds five synthetic GitHub-Metrics documents,
shaped exactly like the real ones and chosen between them to reach every
interesting path: the top band, a middle band, past the last band, a
repository whose contributor list never arrived, and one where nobody could
be located.

``tests/fixtures/expected`` holds the reports the package is expected to
produce from those documents, and ``test_baseline.py`` compares against them
byte for byte. A change to scoring shows up as a failing comparison rather
than as a number nobody noticed moving.

They began as output **recorded from the 1.1.0 script**, so 1.2.0 could prove
it moved nothing. Since then they have been re-recorded only where a roadmap
item deliberately changed a number, and the diff on these files was reviewed
as part of that change. ``CHANGELOG.md`` says which release moved what. Their
authority is that reviewed history: never re-record them to turn a red suite
green.
"""

from __future__ import annotations

import io
import json
import logging
import tarfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from siat_foreign_analysis.logger import PACKAGE_LOGGER_NAME

FIXTURES = Path(__file__).parent / "fixtures"
DOCUMENTS = FIXTURES / "documents"
EXPECTED = FIXTURES / "expected"

DOCUMENT_NAMES = ("clean", "hostile", "mixed", "no-contributors", "unattributed")


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return the fixtures root."""
    return FIXTURES


@pytest.fixture(scope="session")
def documents_dir() -> Path:
    """Return the directory of synthetic repository documents."""
    return DOCUMENTS


@pytest.fixture(scope="session")
def config_path() -> Path:
    """Return the country configuration the golden reports were made with."""
    return FIXTURES / "country_config.json"


@pytest.fixture(scope="session")
def include_unattributed_config_path() -> Path:
    """Return the configuration with the denominator toggle switched on."""
    return FIXTURES / "country_config_include_unattributed.json"


@pytest.fixture
def document() -> dict[str, Any]:
    """Return a minimal, valid repository document.

    Every score component is present and the contributor list is empty, so a
    test can add exactly the contributors it cares about.
    """
    return {
        "name": "example",
        "owner": "example-org",
        "trusted_org_bonus": 0.0,
        "stars_score": 10.0,
        "forks_score": 15.0,
        "last_update_score": 15.0,
        "prevalence_score": 12.0,
        "maturity_score": 15.0,
        "contributors": [],
    }


def make_contributor(
    country_code: str | None,
    contribution: int | None,
    *,
    is_bot: bool = False,
) -> dict[str, Any]:
    """Build one contributor record.

    Args:
        country_code: The resolved country, ``None`` for unattributed, or
            ``""`` for a lookup that ran and found no country component.
        contribution: Commit count, or ``None`` as upstream may emit.
        is_bot: Whether upstream flagged this account as automation.

    Returns:
        A contributor record with the fields this package reads.
    """
    return {
        "name": "someone",
        "internal_address": {"country_code": country_code},
        "contribution": contribution,
        "is_bot": is_bot,
    }


def write_tar_gz(path: Path, members: dict[str, bytes]) -> Path:
    """Write a gzipped tar containing the given members.

    Args:
        path: Archive to create.
        members: Member name to its bytes. Names may contain ``/`` to nest.

    Returns:
        The archive path, for chaining.
    """
    with tarfile.open(path, mode="w:gz") as handle:
        for name, payload in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            handle.addfile(info, io.BytesIO(payload))
    return path


@pytest.fixture
def tar_gz_factory(tmp_path: Path) -> Callable[[str, dict[str, bytes]], Path]:
    """Return a factory building archives in a temporary directory."""

    def build(name: str, members: dict[str, bytes]) -> Path:
        return write_tar_gz(tmp_path / name, members)

    return build


@pytest.fixture
def documents_archive(tmp_path: Path) -> Path:
    """Return an archive of every synthetic document, nested two deep.

    GitHub-Metrics writes documents as ``<owner>/<repoid>.json``, so nesting
    them here is what a real scan directory looks like once it is packed.
    """
    members = {
        f"scan/example/{name}.json": (DOCUMENTS / f"{name}.json").read_bytes()
        for name in DOCUMENT_NAMES
    }
    return write_tar_gz(tmp_path / "documents.tar.gz", members)


def read_document(name: str) -> Any:
    """Load one synthetic document by name.

    Args:
        name: Base name, without the ``.json`` suffix.

    Returns:
        The decoded document.
    """
    return json.loads((DOCUMENTS / f"{name}.json").read_text(encoding="UTF-8"))


@pytest.fixture(autouse=True)
def isolated_package_logger() -> Iterator[None]:
    """Return the package logger to a clean state around every test.

    ``configure_logging`` attaches a handler and switches propagation off, so
    a test that runs the CLI would otherwise leave ``caplog`` - which listens
    on the root logger - deaf for every test that followed it. The failure
    that produces depends on test order, which is the worst kind to chase.
    """
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)

    def reset() -> None:
        while logger.handlers:
            handler = logger.handlers[0]
            logger.removeHandler(handler)
            handler.close()
        logger.setLevel(logging.NOTSET)
        logger.propagate = True

    reset()
    yield
    reset()
