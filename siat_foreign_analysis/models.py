"""Typed values passed between the stages of the pipeline.

The report writers serialise these, and the JSON they produce is a published
interface. :meth:`AdversarialResult.to_details` is therefore written against
the *observed* output of the pre-package script rather than against what the
shape arguably should be, down to which keys are absent and which numbers are
integers. Where that preserves a known defect, the defect is named with its
``docs/ROADMAP.md`` item so the two do not drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdversarialNation:
    """One entry from the ``adversarial_nations`` list."""

    name: str
    country_code: str


@dataclass(frozen=True)
class ScoringConfig:
    """The optional ``scoring`` block of the country configuration.

    Every field defaults to the value that was a literal in the code before
    roadmap item 14 moved it here, so a configuration that omits the block
    entirely scores exactly as 1.1.0 did.

    Attributes:
        include_unattributed_in_denominator: When true, commits by
            contributors with no attributed country enter the
            adversarial-percentage denominator. Defaults to false, which is
            1.0.0 behaviour: missing attribution does not deflate the
            adversarial percentage.
        adversarial_weight: Points a repository with no adversarial
            contribution is awarded. The bands scale with it.
        pass_threshold: Total score, adversarial bonus included, at which a
            repository passes.
    """

    include_unattributed_in_denominator: bool = False
    adversarial_weight: float = 25
    pass_threshold: float = 70.0


@dataclass(frozen=True)
class Config:
    """A parsed ``country_config.json``."""

    adversarial_nations: tuple[AdversarialNation, ...]
    scoring: ScoringConfig = field(default_factory=ScoringConfig)

    @property
    def adversarial_country_codes(self) -> tuple[str, ...]:
        """Return the configured country codes, case-folded, in config order.

        Order is load-bearing: it decides the key order of the per-country
        block in the detailed report, and it breaks ties when two adversarial
        countries have an equal number of commits.

        Codes are case-folded here and contributor codes are case-folded
        where they are compared, so a configuration written ``RU`` matches
        and reports under ``ru`` rather than matching nothing and calling the
        repository clean (roadmap item 4).
        """
        return tuple(nation.country_code.casefold() for nation in self.adversarial_nations)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CountryCommits:
    """Commits attributed to one adversarial country in one repository.

    Attributes:
        commits: Number of commits attributed to this country.
        commits_percent: Those commits as a percentage of the denominator, or
            ``None`` when the denominator was zero and no percentage is
            defined.
    """

    commits: int = 0
    commits_percent: float | None = None


@dataclass(frozen=True)
class AdversarialResult:
    """The adversarial finding for a single repository.

    Attributes:
        countries: Every configured adversarial country, present whether or
            not it contributed, so the report shape is stable across
            repositories.
        top_country: The adversarial country with the most commits, or
            ``None`` when no adversarial commits were found.
        adv_score: The tiered bonus, 0 to 25 points.
        adv_percent: Adversarial commits as a percentage of the denominator,
            or ``None`` when the denominator was zero.
    """

    countries: Mapping[str, CountryCommits]
    top_country: str | None
    adv_score: float
    adv_percent: float | None = None

    def to_details(self) -> dict[str, Any]:
        """Render the legacy ``details`` block written to the detailed report.

        Two things here are still wrong and are deliberately left alone until
        the roadmap item that owns each is taken:

        - ``advPercent`` is **omitted entirely** rather than set to zero when
          the denominator was zero, because the pre-package function returned
          before assigning it (roadmap item 7).
        - ``advScore`` is integer 25 for a clean repository and a float for
          every other band, because the top band multiplies by ``1`` and the
          rest by a float. That difference is visible in the JSON (``25``
          against ``22.5``), so it is preserved rather than normalised.

        ``commitPercent`` was removed in 1.3.0 (roadmap item 11). It sat
        beside the real ``commitsPercent``, was initialised and never
        assigned, and so read integer zero for every country of every
        repository ever scored.

        Returns:
            The ``details`` mapping, with keys in the order the pre-package
            script produced them.
        """
        countries: dict[str, dict[str, Any]] = {}
        for code, entry in self.countries.items():
            block: dict[str, Any] = {"commits": entry.commits}
            if entry.commits_percent is not None:
                block["commitsPercent"] = entry.commits_percent
            countries[code] = block

        details: dict[str, Any] = {
            "countries": countries,
            "topAdvContributorCountry": self.top_country,
        }
        if self.adv_percent is not None:
            details["advPercent"] = self.adv_percent
        details["advScore"] = self.adv_score
        return details


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContributorCoverage:
    """How many contributors carried an attributed country code.

    Attributes:
        total: Contributors seen.
        unattributed: Of those, how many had no country code.
    """

    total: int = 0
    unattributed: int = 0

    @property
    def attributed(self) -> int:
        """Return the number of contributors that carried a country code."""
        return self.total - self.unattributed

    @property
    def percentage(self) -> float:
        """Return attributed contributors as a percentage, rounded to 2dp.

        Zero when no contributors were seen. A repository nobody could be
        located in and a repository with no contributors at all both report
        ``0.0``; distinguishing them is roadmap item 2.
        """
        if self.total == 0:
            return 0.0
        return round((self.attributed / self.total) * 100, 2)

    def __add__(self, other: ContributorCoverage) -> ContributorCoverage:
        """Combine two coverage counts, for accumulating across a run."""
        if not isinstance(other, ContributorCoverage):  # pragma: no cover - defensive
            return NotImplemented
        return ContributorCoverage(
            total=self.total + other.total,
            unattributed=self.unattributed + other.unattributed,
        )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepositoryScore:
    """One repository's place in both reports.

    Attributes:
        name: The repository name, which is also its key in both reports.
            Two repositories sharing a name overwrite each other; owner
            qualification is roadmap item 13.
        unclass_score: Sum of the six upstream-computed components.
        total_score: ``unclass_score`` plus the adversarial bonus.
        is_passing: Whether ``total_score`` reaches the pass threshold.
        adversarial: The adversarial finding backing ``total_score``.
        coverage: Contributor attribution coverage for this repository.
            Computed and not yet published; roadmap item 2.
    """

    name: str
    unclass_score: float
    total_score: float
    is_passing: bool
    adversarial: AdversarialResult
    coverage: ContributorCoverage
