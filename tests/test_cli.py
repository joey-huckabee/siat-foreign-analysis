"""Argument parsing, exit codes, and running end to end."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from siat_foreign_analysis import __version__
from siat_foreign_analysis.cli import build_parser, main
from siat_foreign_analysis.exit_codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    EXIT_OUTPUT_ERROR,
)
from siat_foreign_analysis.inputs import DEFAULT_INPUT_DIR
from siat_foreign_analysis.reports import DEFAULT_OUTPUT_DIR

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_defaults_match_the_pre_package_paths() -> None:
    args = build_parser().parse_args([])

    assert args.input == DEFAULT_INPUT_DIR
    assert args.output == DEFAULT_OUTPUT_DIR
    assert args.config == Path("country_config.json")
    assert args.verbose is False
    assert args.quiet is False


def test_paths_are_parsed_as_paths() -> None:
    args = build_parser().parse_args(["-i", "in", "-o", "out", "-c", "cfg.json"])

    assert args.input == Path("in")
    assert args.output == Path("out")
    assert args.config == Path("cfg.json")


def test_verbose_and_quiet_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["-v", "-q"])


def test_version_is_reported(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        build_parser().parse_args(["--version"])

    assert caught.value.code == 0
    assert __version__ in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def run(tmp_path: Path, documents: Path, config: Path, *extra: str) -> int:
    """Invoke main() with the standard three paths."""
    return main(
        ["-i", str(documents), "-o", str(tmp_path), "-c", str(config), *extra],
    )


def test_a_full_run_succeeds(tmp_path: Path, documents_dir: Path, config_path: Path) -> None:
    assert run(tmp_path, documents_dir, config_path, "-q") == EXIT_OK

    report = json.loads((tmp_path / "score_report.json").read_text(encoding="UTF-8"))
    assert set(report) == {"clean", "hostile", "mixed", "no-contributors", "unattributed"}


def test_output_directory_is_created(
    tmp_path: Path, documents_dir: Path, config_path: Path
) -> None:
    target = tmp_path / "does" / "not" / "exist"

    assert run(target, documents_dir, config_path, "-q") == EXIT_OK
    assert (target / "score_report.csv").is_file()


def test_a_missing_configuration_exits_with_the_config_code(
    tmp_path: Path, documents_dir: Path
) -> None:
    assert run(tmp_path, documents_dir, tmp_path / "absent.json", "-q") == EXIT_CONFIG_ERROR


def test_a_malformed_configuration_exits_with_the_config_code(
    tmp_path: Path, documents_dir: Path
) -> None:
    config = tmp_path / "bad.json"
    config.write_text("{not json", encoding="UTF-8")

    assert run(tmp_path, documents_dir, config, "-q") == EXIT_CONFIG_ERROR


def test_a_malformed_document_exits_with_the_input_code(tmp_path: Path, config_path: Path) -> None:
    documents = tmp_path / "input"
    documents.mkdir()
    (documents / "broken.json").write_text("{not json", encoding="UTF-8")

    assert run(tmp_path / "out", documents, config_path, "-q") == EXIT_INPUT_ERROR


def test_a_document_missing_a_field_exits_with_the_input_code(
    tmp_path: Path, config_path: Path
) -> None:
    documents = tmp_path / "input"
    documents.mkdir()
    (documents / "thin.json").write_text(json.dumps({"name": "x"}), encoding="UTF-8")

    assert run(tmp_path / "out", documents, config_path, "-q") == EXIT_INPUT_ERROR


def test_one_bad_document_loses_the_whole_run(tmp_path: Path, config_path: Path) -> None:
    """Roadmap items 6 and 10: reports are written only after every input.

    The good document here is scored and then thrown away, because the run
    aborts before anything is written.
    """
    documents = tmp_path / "input"
    documents.mkdir()
    (documents / "a-good.json").write_text(
        json.dumps(
            {
                "name": "good",
                "trusted_org_bonus": 0.0,
                "stars_score": 10.0,
                "forks_score": 15.0,
                "last_update_score": 15.0,
                "prevalence_score": 12.0,
                "maturity_score": 15.0,
                "contributors": [],
            }
        ),
        encoding="UTF-8",
    )
    (documents / "b-bad.json").write_text("{not json", encoding="UTF-8")

    output = tmp_path / "out"
    assert run(output, documents, config_path, "-q") == EXIT_INPUT_ERROR
    assert not (output / "score_report.json").exists()


def test_an_unwritable_output_exits_with_the_output_code(
    tmp_path: Path, documents_dir: Path, config_path: Path
) -> None:
    blocker = tmp_path / "output"
    blocker.write_text("not a directory", encoding="UTF-8")

    assert run(blocker, documents_dir, config_path, "-q") == EXIT_OUTPUT_ERROR


def test_an_empty_input_directory_still_writes_reports(tmp_path: Path, config_path: Path) -> None:
    """Roadmap item 9: no input is not an error, which is how a wrongly
    shaped scan directory produces an empty report and exit 0."""
    documents = tmp_path / "input"
    documents.mkdir()
    output = tmp_path / "out"

    assert run(output, documents, config_path, "-q") == EXIT_OK
    assert json.loads((output / "score_report.json").read_text(encoding="UTF-8")) == {}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_verbose_logs_every_contributor(
    tmp_path: Path, documents_dir: Path, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Read stderr, not caplog: the package logger does not propagate."""
    run(tmp_path, documents_dir, config_path, "-v")

    assert "Contributor Country" in capsys.readouterr().err


def test_quiet_suppresses_the_banner(
    tmp_path: Path, documents_dir: Path, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(tmp_path, documents_dir, config_path, "-q")

    assert "Software Impact Analysis Tool" not in capsys.readouterr().err


def test_the_default_level_reports_progress(
    tmp_path: Path, documents_dir: Path, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(tmp_path, documents_dir, config_path)

    err = capsys.readouterr().err
    assert "Software Impact Analysis Tool" in err
    assert "Contributor Country:" not in err


def test_diagnostics_go_to_stderr_leaving_stdout_clean(
    tmp_path: Path, documents_dir: Path, config_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(tmp_path, documents_dir, config_path)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err != ""
