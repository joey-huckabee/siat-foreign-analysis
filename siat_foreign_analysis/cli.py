"""Command line interface for siat-foreign-analysis.

Built on :mod:`argparse` from the standard library. The package has no
runtime dependencies, and a scoring tool that installs a dependency tree to
parse three paths would be trading that away cheaply.

The three paths were hard-coded relative to the working directory before, so
running from anywhere else found no input and wrote an empty report without
saying so. They are options now, and they keep the old values as defaults.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from siat_foreign_analysis import __version__
from siat_foreign_analysis.config import DEFAULT_CONFIG_PATH, load_config, log_config
from siat_foreign_analysis.errors import ConfigError, DocumentError, InputError, OutputError
from siat_foreign_analysis.exit_codes import (
    EXIT_CONFIG_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_OK,
    EXIT_OUTPUT_ERROR,
)
from siat_foreign_analysis.inputs import DEFAULT_INPUT_DIR, discover_inputs, read_json
from siat_foreign_analysis.logger import configure_logging, get_logger
from siat_foreign_analysis.models import ContributorCoverage, RepositoryScore
from siat_foreign_analysis.reports import DEFAULT_OUTPUT_DIR, write_reports
from siat_foreign_analysis.scoring import score_repository

logger = get_logger(__name__)

BANNER_SEPARATOR: Final = "*" * 100
"""Visual banner bracketing the program-name announcement at startup."""

PROGRAM_TITLE: Final = "Software Impact Analysis Tool - Foreign Analysis"


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser.

    Returns:
        The parser, with defaults matching the pre-package working-directory
        relative paths.
    """
    parser = argparse.ArgumentParser(
        prog="siat-foreign-analysis",
        description=(
            "Score the adversarial contribution in GitHub-Metrics repository documents. "
            "Reads bare *.json files and *.json members of *.tar.gz archives from the input "
            "directory, and writes score_report and detailed_score_report as JSON and CSV."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        metavar="DIR",
        help="Directory holding the documents to score.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help="Directory the four reports are written to. Created if absent.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        metavar="FILE",
        help="Adversarial nations and scoring policy.",
    )

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log every contributor as it is read.",
    )
    verbosity.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Log warnings and errors only.",
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _log_level(args: argparse.Namespace) -> int:
    """Map the verbosity flags to a logging level.

    Args:
        args: Parsed arguments.

    Returns:
        The level to configure the package logger with.
    """
    if args.verbose:
        return logging.DEBUG
    if args.quiet:
        return logging.WARNING
    return logging.INFO


def _log_banner() -> None:
    """Announce the program, as the pre-package script did."""
    logger.info("%s", BANNER_SEPARATOR)
    logger.info("%s", PROGRAM_TITLE)
    logger.info("%s", BANNER_SEPARATOR)


def run(args: argparse.Namespace) -> int:
    """Execute one full run.

    A document that cannot be read or scored aborts the run, and no reports
    are written at all - the pre-package behaviour, because reports are built
    only after every input is processed. Reporting the failure per repository
    and carrying on is roadmap items 6 and 10.

    Args:
        args: Parsed arguments.

    Returns:
        A process exit code from :mod:`siat_foreign_analysis.exit_codes`.
    """
    _log_banner()

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        logger.error("%s", exc)
        return EXIT_CONFIG_ERROR

    log_config(config)

    scores: list[RepositoryScore] = []
    run_coverage = ContributorCoverage()

    try:
        sources = discover_inputs(args.input)
        for source in sources:
            logger.info("%s", "-" * 50)
            logger.info("Processing input file: %s", source.describe())
            logger.info("%s", "-" * 50)

            document = read_json(source.member, tar_gz_path=source.archive)
            score = score_repository(document, config, source.describe())

            scores.append(score)
            run_coverage = run_coverage + score.coverage
    except (InputError, DocumentError) as exc:
        logger.error("%s", exc)
        return EXIT_INPUT_ERROR

    _log_run_coverage(run_coverage)

    try:
        written = write_reports(scores, args.output)
    except OutputError as exc:
        logger.error("%s", exc)
        return EXIT_OUTPUT_ERROR

    logger.info("Scored %d repositor%s.", len(scores), "y" if len(scores) == 1 else "ies")
    for path in written:
        logger.info("Wrote %s", path)

    return EXIT_OK


def _log_run_coverage(coverage: ContributorCoverage) -> None:
    """Report contributor attribution coverage across the whole run.

    Computed and logged, and reaching neither report. Carrying it into the
    reports as a column is roadmap item 2.

    Args:
        coverage: Accumulated coverage for every repository scored.
    """
    logger.info("%s", "-" * 50)
    logger.info("Cumulative Contributor Data Quality")
    logger.info("%s", "-" * 50)
    logger.info("total_contributor_count = %d", coverage.total)
    logger.info("total_contributor_none_count = %d", coverage.unattributed)
    logger.info("total_contributor_quality_percentage = %s", coverage.percentage)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, configure logging, and run.

    Args:
        argv: Command line arguments, or ``None`` to read :data:`sys.argv`.

    Returns:
        A process exit code from :mod:`siat_foreign_analysis.exit_codes`.
    """
    args = build_parser().parse_args(argv)
    configure_logging(_log_level(args))
    return run(args)
