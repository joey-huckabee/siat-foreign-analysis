"""The package must reproduce the 1.1.0 script exactly.

1.2.0 moved a 452-line script into a package, split it nine ways and put its
output through a logger. None of that is meant to change a single published
number, and "meant to" is worth nothing without something that checks.

The expected files under ``tests/fixtures/expected`` were produced by running
the 1.1.0 script itself over ``tests/fixtures/documents``. These tests compare
the package's output against them **byte for byte** - not field by field,
because the comparison has to catch ``25`` becoming ``25.0``, a key changing
position, ``True`` becoming ``true``, and CRLF becoming LF, none of which a
value comparison would notice and every one of which changes a file a
consumer parses.

When a roadmap item is taken and a number is *supposed* to move, these tests
fail, and the recorded files are re-made deliberately as part of that change.
That is the point: the failure is the release note.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from siat_foreign_analysis.cli import main
from siat_foreign_analysis.exit_codes import EXIT_OK

REPORTS = (
    "score_report.json",
    "score_report.csv",
    "detailed_score_report.json",
    "detailed_score_report.csv",
)


def run_into(output_dir: Path, documents_dir: Path, config: Path) -> int:
    """Run the CLI over the fixture documents.

    Args:
        output_dir: Where reports are written.
        documents_dir: Directory of documents to score.
        config: Country configuration to score with.

    Returns:
        The process exit code.
    """
    return main(
        [
            "--input",
            str(documents_dir),
            "--output",
            str(output_dir),
            "--config",
            str(config),
            "--quiet",
        ]
    )


@pytest.mark.baseline
@pytest.mark.parametrize("report", REPORTS)
def test_default_config_reproduces_1_1_0(
    report: str,
    tmp_path: Path,
    documents_dir: Path,
    config_path: Path,
    fixtures_dir: Path,
) -> None:
    assert run_into(tmp_path, documents_dir, config_path) == EXIT_OK

    expected = (fixtures_dir / "expected" / "default" / report).read_bytes()
    actual = (tmp_path / report).read_bytes()
    assert actual == expected, f"{report} no longer matches the 1.1.0 output"


@pytest.mark.baseline
@pytest.mark.parametrize("report", REPORTS)
def test_include_unattributed_reproduces_1_1_0(
    report: str,
    tmp_path: Path,
    documents_dir: Path,
    include_unattributed_config_path: Path,
    fixtures_dir: Path,
) -> None:
    assert run_into(tmp_path, documents_dir, include_unattributed_config_path) == EXIT_OK

    expected = (fixtures_dir / "expected" / "include-unattributed" / report).read_bytes()
    actual = (tmp_path / report).read_bytes()
    assert actual == expected, f"{report} no longer matches the 1.1.0 output"


@pytest.mark.baseline
def test_csv_rows_end_with_crlf(tmp_path: Path, documents_dir: Path, config_path: Path) -> None:
    """The csv module terminates rows with CRLF, and consumers rely on it."""
    run_into(tmp_path, documents_dir, config_path)

    raw = (tmp_path / "score_report.csv").read_bytes()
    assert b"\r\n" in raw
    assert b"\r\r\n" not in raw, "the text layer translated on top of csv's own terminator"


@pytest.mark.baseline
def test_json_reports_have_no_trailing_newline(
    tmp_path: Path, documents_dir: Path, config_path: Path
) -> None:
    """json.dumps is written straight out, so there is no trailing newline."""
    run_into(tmp_path, documents_dir, config_path)

    for report in ("score_report.json", "detailed_score_report.json"):
        assert not (tmp_path / report).read_bytes().endswith(b"\n")


@pytest.mark.baseline
def test_archived_documents_score_the_same_as_bare_ones(
    tmp_path: Path,
    documents_archive: Path,
    config_path: Path,
    fixtures_dir: Path,
) -> None:
    """A scan packed into a .tar.gz scores identically to one unpacked.

    The archive nests its members two directories deep, which the archive
    walker handles and the bare-file glob does not - see roadmap item 9.
    """
    archive_input = tmp_path / "input"
    archive_input.mkdir()
    documents_archive.rename(archive_input / documents_archive.name)

    output = tmp_path / "output"
    assert run_into(output, archive_input, config_path) == EXIT_OK

    for report in REPORTS:
        expected = (fixtures_dir / "expected" / "default" / report).read_bytes()
        assert (output / report).read_bytes() == expected
