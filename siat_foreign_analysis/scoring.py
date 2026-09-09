"""Adversarial scoring.

Five components computed by GitHub-Metrics cap at 75 points, with
``trusted_org_bonus`` a further 10 on top. This package supplies the missing
25: a tiered bonus that is full for a repository with no adversarial
contribution and zero once adversarial commits reach a quarter of the total.

The bands, the weight and the pass threshold in this module are the whole of
the scoring policy, and all three are literals. Moving them into
``country_config.json`` beside the nation list is roadmap item 14.
"""

from __future__ import annotations

from typing import Any, Final

from siat_foreign_analysis.errors import MissingFieldError
from siat_foreign_analysis.logger import get_logger
from siat_foreign_analysis.models import (
    AdversarialResult,
    Config,
    ContributorCoverage,
    CountryCommits,
    RepositoryScore,
)

logger = get_logger(__name__)

ADV_WEIGHT: Final = 25
"""Points a repository with no adversarial contribution is awarded."""

PASS_THRESHOLD: Final = 70.0
"""Total score, adversarial bonus included, at which a repository passes."""

UPSTREAM_SCORE_FIELDS: Final = (
    "trusted_org_bonus",
    "stars_score",
    "forks_score",
    "last_update_score",
    "prevalence_score",
    "maturity_score",
)
"""The six components summed into the unclassified score.

The document also publishes ``total_score``, which upstream computes from the
same parts and caps at 85. Reading that instead of re-adding these would
remove a place for the two to drift; it is roadmap item 12.
"""

BANDS: Final[tuple[tuple[float, float], ...]] = (
    (0.5, 1),
    (1.0, 0.9),
    (2.0, 0.8),
    (5.0, 0.7),
    (10.0, 0.5),
    (15.0, 0.4),
    (20.0, 0.3),
    (25.0, 0.2),
)
"""``(exclusive upper bound, multiplier)`` pairs, in ascending order.

An adversarial percentage at or above the last bound scores zero.

The first multiplier is the integer ``1`` rather than ``1.0`` on purpose. It
makes a clean repository score integer ``25`` where every other band produces
a float, and that difference is visible in the published JSON - ``25`` beside
``22.5``. Normalising it would change output this release is not changing.
"""


def calculate_adv(
    cc_list: list[str],
    country_commits: list[int],
    total_commits: int,
    adv_cc_list: tuple[str, ...] | list[str],
) -> AdversarialResult:
    """Compute the adversarial finding for a single repository.

    Args:
        cc_list: Country code per attributed contributor.
        country_commits: Commit count per attributed contributor, parallel to
            ``cc_list``.
        total_commits: The denominator, decided by the caller so that
            ``include_unattributed_in_denominator`` can change it.
        adv_cc_list: Configured adversarial country codes, in configuration
            order.

    Returns:
        The finding, including per-country counts for every configured
        country whether or not it contributed.
    """
    logger.debug("Entering calculate_adv")

    # Pre-populate with zeros so the report shape is stable across
    # repositories: a country absent from this repository still appears.
    commits_by_country: dict[str, int] = dict.fromkeys(adv_cc_list, 0)

    # Country codes are compared exactly as configured. An upper-case entry
    # matches no contributor and reports a clean repository; case-folding
    # both sides is roadmap item 4.
    adv_commits = 0
    for code, commits in zip(cc_list, country_commits, strict=True):
        if code in commits_by_country:
            adv_commits += commits
            commits_by_country[code] += commits

    # Tie broken by first occurrence, which is insertion order, which is
    # configuration order.
    contributing = {code: count for code, count in commits_by_country.items() if count > 0}
    top_country = max(contributing, key=lambda code: contributing[code]) if contributing else None

    # A package can have zero contributors after an upstream pull error.
    # Returning here awards `advScore = 0` - the full penalty - to a
    # repository whose contributor list simply failed to arrive, and leaves
    # `advPercent` unset. Roadmap items 7 and 8 own both halves of that.
    if total_commits == 0:
        logger.warning("Unable to process contributors - zero contributors")
        return AdversarialResult(
            countries={
                code: CountryCommits(commits=count) for code, count in commits_by_country.items()
            },
            top_country=top_country,
            adv_score=0,
            adv_percent=None,
        )

    adv_percent = adv_commits * 100.0 / total_commits
    countries = {
        code: CountryCommits(commits=count, commits_percent=count * 100.0 / total_commits)
        for code, count in commits_by_country.items()
    }

    return AdversarialResult(
        countries=countries,
        top_country=top_country,
        adv_score=score_for_percent(adv_percent),
        adv_percent=adv_percent,
    )


def score_for_percent(adv_percent: float) -> float:
    """Return the tiered bonus for an adversarial percentage.

    Args:
        adv_percent: Adversarial commits as a percentage of the denominator.

    Returns:
        The bonus, from :data:`ADV_WEIGHT` down to zero.
    """
    for bound, multiplier in BANDS:
        if adv_percent < bound:
            return multiplier * ADV_WEIGHT
    return 0.0 * ADV_WEIGHT


def collect_contributions(
    document: Any,
    *,
    include_unattributed: bool,
    source: str,
) -> tuple[list[str], list[int], int, ContributorCoverage]:
    """Walk a document's contributors, splitting attributed from not.

    Args:
        document: A decoded GitHub-Metrics repository document.
        include_unattributed: Whether commits with no attributed country
            enter the denominator.
        source: Identity of the document, for error messages.

    Returns:
        Country codes, their parallel commit counts, the denominator, and the
        attribution coverage.

    Raises:
        MissingFieldError: The document has no ``contributors`` list.
    """
    if "contributors" not in document:
        raise MissingFieldError("contributors", source)

    country_codes: list[str] = []
    country_commits: list[int] = []
    total_commits = 0
    seen = 0
    unattributed = 0

    for contributor in document["contributors"]:
        code = contributor.get("internal_address", {}).get("country_code")
        contribution = contributor.get("contribution")

        # `is_bot` is published on every contributor record and is not read
        # here. Bots miss this calculation only because they publish no
        # location; one that carried a location would be scored as a person,
        # and with `include_unattributed` set they enter the denominator
        # outright. Roadmap item 1.
        #
        # An empty-string country code is treated as attributed, because only
        # `None` is tested. Roadmap item 3.
        #
        # `contribution` is typed `int | None` upstream. A null raises
        # TypeError here and loses the whole run, because reports are written
        # only after every input is processed. Roadmap item 6.
        if code is None:
            unattributed += 1
            if include_unattributed:
                total_commits += contribution
            logger.debug("Contributor Country: %s", code)
        else:
            country_codes.append(code)
            country_commits.append(contribution)
            total_commits += contribution
            logger.debug("Contributor Country: %s\t\t\tCommits: %s", code, contribution)

        seen += 1

    return (
        country_codes,
        country_commits,
        total_commits,
        ContributorCoverage(total=seen, unattributed=unattributed),
    )


def unclassified_score(document: Any, source: str) -> float:
    """Sum the six upstream-computed score components.

    Args:
        document: A decoded GitHub-Metrics repository document.
        source: Identity of the document, for error messages.

    Returns:
        The unclassified component of the score.

    Raises:
        MissingFieldError: A component is absent from the document.
    """
    total = 0.0
    for name in UPSTREAM_SCORE_FIELDS:
        if name not in document:
            raise MissingFieldError(name, source)
        total += document[name]
    return total


def score_repository(document: Any, config: Config, source: str) -> RepositoryScore:
    """Score one repository document end to end.

    Args:
        document: A decoded GitHub-Metrics repository document.
        config: The adversarial nations and scoring policy.
        source: Identity of the document, for error messages.

    Returns:
        The repository's scores and the adversarial finding behind them.

    Raises:
        MissingFieldError: The document lacks ``name``, ``contributors``, or
            one of the six score components.
    """
    if "name" not in document:
        raise MissingFieldError("name", source)

    codes, commits, total_commits, coverage = collect_contributions(
        document,
        include_unattributed=config.scoring.include_unattributed_in_denominator,
        source=source,
    )

    logger.info("contributor_country_total_count = %d", coverage.total)
    logger.info("contributor_country_none_count = %d", coverage.unattributed)
    logger.info("Contributor Country Data Quality = %s%%", coverage.percentage)

    adversarial = calculate_adv(codes, commits, total_commits, config.adversarial_country_codes)
    unclassified = unclassified_score(document, source)
    total_score = unclassified + adversarial.adv_score

    # Keyed on the bare repository name, so two repositories with the same
    # name from different owners overwrite each other. Roadmap item 13.
    return RepositoryScore(
        name=document["name"],
        unclass_score=unclassified,
        total_score=total_score,
        is_passing=total_score >= PASS_THRESHOLD,
        adversarial=adversarial,
        coverage=coverage,
    )
