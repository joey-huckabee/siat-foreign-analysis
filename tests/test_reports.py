"""Building and writing the four reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from siat_foreign_analysis.errors import OutputError
from siat_foreign_analysis.models import (
    AdversarialResult,
    ContributorCoverage,
    CountryCommits,
    RepositoryScore,
)
from siat_foreign_analysis.reports import (
    DETAILED_REPORT_COLUMNS,
    SCORE_REPORT_COLUMNS,
    build_detailed_report,
    build_score_report,
    write_reports,
)


def score(name: str = "example", *, adv_score: float = 25, passing: bool = True) -> RepositoryScore:
    """Build a RepositoryScore for report tests."""
    return RepositoryScore(
        name=name,
        unclass_score=67.0,
        total_score=67.0 + adv_score,
        is_passing=passing,
        adversarial=AdversarialResult(
            countries={"ru": CountryCommits(commits=0, commits_percent=0.0)},
            top_country=None,
            adv_score=adv_score,
            adv_percent=0.0,
        ),
        coverage=ContributorCoverage(total=10, unattributed=2),
    )


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------


def test_the_releasable_report_withholds_the_adversarial_score() -> None:
    """The bonus decides is_passing but is not itself released."""
    entry = build_score_report([score()])["example"]

    assert list(entry) == ["unclass_score", "is_passing"]
    assert "advScore" not in json.dumps(entry)
    assert "adversarial" not in json.dumps(entry)


def test_the_detailed_report_carries_the_breakdown() -> None:
    entry = build_detailed_report([score()])["example"]

    assert list(entry) == ["is_passing", "score", "details"]
    assert entry["details"]["countries"]["ru"]["commits"] == 0


def test_coverage_reaches_neither_report() -> None:
    """Roadmap item 2: computed for every repository and published nowhere."""
    scores = [score()]

    assert "coverage" not in json.dumps(build_score_report(scores))
    assert "coverage" not in json.dumps(build_detailed_report(scores))


def test_repositories_sharing_a_name_overwrite_each_other() -> None:
    """Roadmap item 13: the reports are keyed on the bare name."""
    report = build_score_report([score("bcrypt"), score("bcrypt", adv_score=0.0, passing=False)])

    assert len(report) == 1
    assert report["bcrypt"]["is_passing"] is False


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def test_writes_all_four_reports(tmp_path: Path) -> None:
    written = write_reports([score()], tmp_path)

    assert [path.name for path in written] == [
        "score_report.json",
        "score_report.csv",
        "detailed_score_report.json",
        "detailed_score_report.csv",
    ]
    assert all(path.is_file() for path in written)


def test_creates_a_missing_output_directory(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "output"

    write_reports([score()], target)

    assert (target / "score_report.json").is_file()


def test_csv_headers_are_in_the_published_order(tmp_path: Path) -> None:
    write_reports([score()], tmp_path)

    with (tmp_path / "score_report.csv").open(newline="", encoding="UTF-8") as handle:
        assert next(csv.reader(handle)) == list(SCORE_REPORT_COLUMNS)
    with (tmp_path / "detailed_score_report.csv").open(newline="", encoding="UTF-8") as handle:
        assert next(csv.reader(handle)) == list(DETAILED_REPORT_COLUMNS)


def test_detailed_csv_recovers_the_unclassified_score(tmp_path: Path) -> None:
    write_reports([score(adv_score=12.5)], tmp_path)

    with (tmp_path / "detailed_score_report.csv").open(newline="", encoding="UTF-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["total_score"] == "79.5"
    assert row["adversarial_score"] == "12.5"
    assert row["unclass_score"] == "67.0"


def test_booleans_are_written_python_style(tmp_path: Path) -> None:
    """`True`, not `true` - csv writes str(), and consumers parse that."""
    write_reports([score()], tmp_path)

    assert "True" in (tmp_path / "score_report.csv").read_text(encoding="UTF-8")


def test_an_empty_run_still_writes_four_reports(tmp_path: Path) -> None:
    """An empty input directory produces empty reports, not a crash."""
    written = write_reports([], tmp_path)

    assert len(written) == 4
    assert json.loads((tmp_path / "score_report.json").read_text(encoding="UTF-8")) == {}


def test_an_unwritable_output_directory_is_reported(tmp_path: Path) -> None:
    blocker = tmp_path / "output"
    blocker.write_text("I am a file, not a directory", encoding="UTF-8")

    with pytest.raises(OutputError, match="output directory"):
        write_reports([score()], blocker)


def test_an_unwritable_report_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Path.open is called with keyword arguments, so the stub must take them.
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "open", refuse)

    with pytest.raises(OutputError, match="Could not write"):
        write_reports([score()], tmp_path)


def test_a_failing_csv_write_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The JSON reports write first, so this reaches the CSV path alone."""

    # A stand-in for csv.DictWriter that fails on first use. Too small to
    # want docstrings, and its methods are methods because the real class's
    # are.
    class Refusing:  # pylint: disable=missing-class-docstring,missing-function-docstring,no-self-use
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def writeheader(self) -> None:
            raise OSError("disk full")

    monkeypatch.setattr(csv, "DictWriter", Refusing)

    with pytest.raises(OutputError, match="Could not write"):
        write_reports([score()], tmp_path)
