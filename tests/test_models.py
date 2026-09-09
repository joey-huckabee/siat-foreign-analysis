"""The shapes the reports are serialised from."""

from __future__ import annotations

import json

import pytest

from siat_foreign_analysis.models import (
    AdversarialNation,
    AdversarialResult,
    Config,
    ContributorCoverage,
    CountryCommits,
    ScoringConfig,
)


def result(**overrides: object) -> AdversarialResult:
    """Build an AdversarialResult with sensible defaults."""
    defaults: dict[str, object] = {
        "countries": {"ru": CountryCommits(commits=10, commits_percent=10.0)},
        "top_country": "ru",
        "adv_score": 10.0,
        "adv_percent": 10.0,
    }
    defaults.update(overrides)
    return AdversarialResult(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# to_details
# ---------------------------------------------------------------------------


def test_details_key_order_is_the_published_order() -> None:
    assert list(result().to_details()) == [
        "countries",
        "topAdvContributorCountry",
        "advPercent",
        "advScore",
    ]


def test_details_omits_adv_percent_when_it_is_not_measurable() -> None:
    """Roadmap item 7: the key is absent, not null and not zero."""
    details = result(adv_percent=None, adv_score=0).to_details()

    assert "advPercent" not in details
    assert list(details) == ["countries", "topAdvContributorCountry", "advScore"]


def test_country_block_carries_both_percent_keys() -> None:
    """Roadmap item 11: commitPercent is a typo of commitsPercent."""
    block = result().to_details()["countries"]["ru"]

    assert list(block) == ["commits", "commitPercent", "commitsPercent"]
    assert block["commitPercent"] == 0
    assert block["commitsPercent"] == 10.0


def test_country_block_omits_commits_percent_when_unmeasurable() -> None:
    details = result(
        countries={"ru": CountryCommits(commits=0)}, adv_percent=None, adv_score=0
    ).to_details()

    assert list(details["countries"]["ru"]) == ["commits", "commitPercent"]


def test_details_survive_a_json_round_trip() -> None:
    details = result().to_details()
    assert json.loads(json.dumps(details)) == details


def test_an_integer_score_stays_an_integer_through_json() -> None:
    """`25` and `25.0` are different bytes in the report."""
    assert json.dumps(result(adv_score=25).to_details()).count('"advScore": 25') == 1
    assert '"advScore": 25.0' in json.dumps(result(adv_score=25.0).to_details())


# ---------------------------------------------------------------------------
# ContributorCoverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("total", "unattributed", "expected"),
    [
        (0, 0, 0.0),
        (39, 19, 51.28),
        (42, 15, 64.29),
        (81, 34, 58.02),
        (10, 0, 100.0),
        (10, 10, 0.0),
    ],
)
def test_coverage_percentage(total: int, unattributed: int, expected: float) -> None:
    assert ContributorCoverage(total=total, unattributed=unattributed).percentage == expected


def test_coverage_accumulates() -> None:
    run = ContributorCoverage() + ContributorCoverage(39, 19) + ContributorCoverage(42, 15)

    assert run.total == 81
    assert run.unattributed == 34
    assert run.attributed == 47
    assert run.percentage == 58.02


def test_coverage_of_an_empty_run_is_zero_not_an_error() -> None:
    assert ContributorCoverage().percentage == 0.0


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_country_codes_keep_configuration_order() -> None:
    config = Config(
        adversarial_nations=(
            AdversarialNation("russia", "ru"),
            AdversarialNation("badcountry", "bc"),
        )
    )
    assert config.adversarial_country_codes == ("ru", "bc")


def test_scoring_defaults_to_the_conservative_denominator() -> None:
    assert ScoringConfig().include_unattributed_in_denominator is False
    assert Config(adversarial_nations=()).scoring.include_unattributed_in_denominator is False
