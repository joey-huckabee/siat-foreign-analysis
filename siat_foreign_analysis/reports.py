"""Writing the four output files.

Two reports, each as JSON and CSV:

- ``score_report`` is the releasable pass/fail summary, intended to be
  transferable to the unclassified side.
- ``detailed_score_report`` carries the adversarial country breakdown and is
  not.

The exact bytes are a published interface, and they do not depend on the
platform the tool runs on: JSON is written with LF line endings and no
trailing newline, CSV with the carriage-return-linefeed row terminator that
:mod:`csv` writes. Key order in the JSON, column order in the CSV, ``True``
rather than ``true`` in the CSV, and four-space indentation are all as the
pre-package script produced them.

``tests/test_baseline.py`` compares against recorded copies byte for byte,
and CI runs it on Linux, macOS and Windows, so a difference between platforms
fails rather than going unnoticed. That is not hypothetical: it is how the
JSON line-ending difference was found, having been present since 1.0.0.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from siat_foreign_analysis.errors import OutputError
from siat_foreign_analysis.logger import get_logger
from siat_foreign_analysis.models import RepositoryScore
from siat_foreign_analysis.paths import resolve_path, resolve_within

logger = get_logger(__name__)

DEFAULT_OUTPUT_DIR = Path("output")
"""Where reports are written when no path is given."""

JSON_INDENT: Final = 4
"""Indentation of both JSON reports."""

SCORE_REPORT_COLUMNS: Final = ("package_name", "is_passing", "unclass_score")
"""Columns of ``score_report.csv``, in order."""

DETAILED_REPORT_COLUMNS: Final = (
    "package_name",
    "is_passing",
    "unclass_score",
    "adversarial_score",
    "total_score",
)
"""Columns of ``detailed_score_report.csv``, in order."""


def build_score_report(scores: list[RepositoryScore]) -> dict[str, dict[str, Any]]:
    """Build the releasable report.

    Only the unclassified component is published. The adversarial bonus
    decides ``is_passing`` but is not itself released.

    Args:
        scores: Every repository scored in this run.

    Returns:
        Repository name to its releasable entry.
    """
    return {
        score.name: {"unclass_score": score.unclass_score, "is_passing": score.is_passing}
        for score in scores
    }


def build_detailed_report(scores: list[RepositoryScore]) -> dict[str, dict[str, Any]]:
    """Build the classified report, including the adversarial breakdown.

    Args:
        scores: Every repository scored in this run.

    Returns:
        Repository name to its detailed entry.
    """
    return {
        score.name: {
            "is_passing": score.is_passing,
            "score": score.total_score,
            "details": score.adversarial.to_details(),
        }
        for score in scores
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    r"""Write one JSON report, with LF line endings on every platform.

    ``newline="\n"`` is not cosmetic. Without it the text layer translates
    ``json.dumps``' newlines to ``os.linesep``, so the same input produced a
    CRLF report on Windows and an LF one on Linux - the published bytes
    depended on who ran the tool. Two analysts comparing reports, or a
    checksum taken over one, would disagree for no reason either could see.

    LF is the choice because it is what the majority of consumers and every
    CI platform produce, and because ``.gitattributes`` normalises to it
    everywhere else in this repository.

    The CSV reports never had this problem: :mod:`csv` writes its own
    ``\r\n`` and ``_write_csv`` passes ``newline=""`` to stop the text layer
    translating on top of it.

    Args:
        path: File to write.
        payload: The report body.

    Raises:
        OutputError: The file could not be written.
    """
    try:
        with path.open("w", encoding="UTF-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=JSON_INDENT))
    except OSError as exc:
        raise OutputError(f"Could not write {path}: {exc}") from exc


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    r"""Write one CSV report.

    ``newline=""`` is required: :mod:`csv` writes its own ``\r\n`` row
    terminator, and letting the text layer translate as well produces
    ``\r\r\n``.

    Args:
        path: File to write.
        columns: Header, in order.
        rows: One mapping per row, keyed by column name.

    Raises:
        OutputError: The file could not be written.
    """
    try:
        with path.open("w", newline="", encoding="UTF-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(columns))
            writer.writeheader()
            for row in rows:
                logger.debug("Writing CSV row for: %s", row["package_name"])
                writer.writerow(row)
    except OSError as exc:
        raise OutputError(f"Could not write {path}: {exc}") from exc


def write_reports(
    scores: list[RepositoryScore],
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    """Write all four reports, creating the output directory if needed.

    Each report path is confirmed to resolve inside the output directory
    before it is opened. The four names are literal constants, so nothing can
    escape today; the check means a report named from data in future cannot
    quietly become a write anywhere on the filesystem.

    Args:
        scores: Every repository scored in this run.
        output_dir: Directory to write into.

    Returns:
        The four paths written, in the order they were written.

    Raises:
        OutputError: The directory or any of the four files could not be
            written.
        PathEscapeError: A report path resolves outside the output directory.
    """
    directory = resolve_path(output_dir)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputError(f"Could not create output directory {directory}: {exc}") from exc

    score_report = build_score_report(scores)
    detailed_report = build_detailed_report(scores)

    written: list[Path] = []

    logger.info("Creating Score Report JSON File")
    score_json = resolve_within(
        directory, directory / "score_report.json", what="score_report.json"
    )
    _write_json(score_json, score_report)
    written.append(score_json)

    logger.info("Creating Score Report CSV File")
    score_csv = resolve_within(directory, directory / "score_report.csv", what="score_report.csv")
    _write_csv(
        score_csv,
        SCORE_REPORT_COLUMNS,
        [{"package_name": name, **entry} for name, entry in score_report.items()],
    )
    written.append(score_csv)

    logger.info("Creating Detailed Score Report JSON File")
    detailed_json = resolve_within(
        directory, directory / "detailed_score_report.json", what="detailed_score_report.json"
    )
    _write_json(detailed_json, detailed_report)
    written.append(detailed_json)

    logger.info("Creating Detailed Score Report CSV File")
    detailed_csv = resolve_within(
        directory, directory / "detailed_score_report.csv", what="detailed_score_report.csv"
    )
    _write_csv(
        detailed_csv,
        DETAILED_REPORT_COLUMNS,
        [_detailed_row(name, entry) for name, entry in detailed_report.items()],
    )
    written.append(detailed_csv)

    return written


def _detailed_row(name: str, entry: Mapping[str, Any]) -> dict[str, Any]:
    """Build one row of the detailed CSV.

    ``unclass_score`` is recovered by subtracting the adversarial bonus from
    the total rather than carried through, which is what the pre-package
    script did and what makes the column a float even where the bonus is an
    integer.

    Args:
        name: Repository name.
        entry: That repository's detailed report entry.

    Returns:
        The row, keyed by column name.
    """
    adv_score = entry["details"]["advScore"]
    return {
        "package_name": name,
        "is_passing": entry["is_passing"],
        "unclass_score": entry["score"] - adv_score,
        "adversarial_score": adv_score,
        "total_score": entry["score"],
    }
