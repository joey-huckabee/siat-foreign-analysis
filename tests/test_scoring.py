"""Scoring: the bands, the denominator, and what reaches them."""

from __future__ import annotations

from typing import Any

import pytest

from siat_foreign_analysis.errors import MissingFieldError
from siat_foreign_analysis.models import AdversarialNation, Config, ScoringConfig
from siat_foreign_analysis.scoring import (
    ADV_WEIGHT,
    BANDS,
    PASS_THRESHOLD,
    calculate_adv,
    collect_contributions,
    score_for_percent,
    score_repository,
    unclassified_score,
)
from tests.conftest import make_contributor

ADVERSARIAL = ("ru", "bc")


def config(*, include_unattributed: bool = False, codes: tuple[str, ...] = ADVERSARIAL) -> Config:
    """Build a configuration with the given adversarial codes."""
    return Config(
        adversarial_nations=tuple(
            AdversarialNation(name=code, country_code=code) for code in codes
        ),
        scoring=ScoringConfig(include_unattributed_in_denominator=include_unattributed),
    )


# ---------------------------------------------------------------------------
# Bands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("percent", "expected"),
    [
        (0.0, 25),
        (0.49, 25),
        (0.5, 22.5),
        (0.99, 22.5),
        (1.0, 20.0),
        (1.99, 20.0),
        (2.0, 17.5),
        (4.99, 17.5),
        (5.0, 12.5),
        (9.99, 12.5),
        (10.0, 10.0),
        (14.99, 10.0),
        (15.0, 7.5),
        (19.99, 7.5),
        (20.0, 5.0),
        (24.99, 5.0),
        (25.0, 0.0),
        (100.0, 0.0),
    ],
)
def test_every_band_boundary(percent: float, expected: float) -> None:
    """Each bound is exclusive, so the value at the bound drops a band."""
    assert score_for_percent(percent) == expected


def test_a_clean_repository_scores_an_integer() -> None:
    """The top band multiplies by int 1, which is visible in the JSON."""
    result = score_for_percent(0.0)
    assert result == ADV_WEIGHT
    assert isinstance(result, int)


def test_every_other_band_scores_a_float() -> None:
    for bound, _ in BANDS[1:]:
        assert isinstance(score_for_percent(bound), float)


def test_bands_are_ascending_and_decreasing() -> None:
    """A higher adversarial percentage can never score better than a lower."""
    bounds = [bound for bound, _ in BANDS]
    multipliers = [multiplier for _, multiplier in BANDS]
    assert bounds == sorted(bounds)
    assert multipliers == sorted(multipliers, reverse=True)


# ---------------------------------------------------------------------------
# calculate_adv
# ---------------------------------------------------------------------------


def test_every_configured_country_appears_even_with_no_commits() -> None:
    """The report shape is stable across repositories."""
    result = calculate_adv(["us"], [10], 10, ADVERSARIAL)

    assert set(result.countries) == set(ADVERSARIAL)
    assert all(entry.commits == 0 for entry in result.countries.values())
    assert result.top_country is None
    assert result.adv_percent == 0.0


def test_country_order_follows_the_configuration() -> None:
    assert list(calculate_adv([], [], 1, ("bc", "ru")).countries) == ["bc", "ru"]


def test_adversarial_commits_are_aggregated_per_country() -> None:
    result = calculate_adv(["ru", "us", "ru"], [3, 90, 7], 100, ADVERSARIAL)

    assert result.countries["ru"].commits == 10
    assert result.countries["ru"].commits_percent == 10.0
    assert result.adv_percent == 10.0
    assert result.top_country == "ru"


def test_top_country_is_the_one_with_most_commits() -> None:
    result = calculate_adv(["ru", "bc"], [5, 20], 100, ADVERSARIAL)
    assert result.top_country == "bc"


def test_top_country_ties_break_on_configuration_order() -> None:
    result = calculate_adv(["ru", "bc"], [10, 10], 100, ADVERSARIAL)
    assert result.top_country == "ru"


def test_zero_denominator_returns_the_full_penalty_and_no_percent() -> None:
    """Roadmap items 7 and 8: the harshest reading of missing data."""
    result = calculate_adv([], [], 0, ADVERSARIAL)

    assert result.adv_score == 0
    assert result.adv_percent is None
    assert "advPercent" not in result.to_details()


def test_country_codes_are_matched_case_sensitively() -> None:
    """Roadmap item 4: an upper-case config silently matches nothing."""
    result = calculate_adv(["ru"], [50], 100, ("RU",))

    assert result.countries["RU"].commits == 0
    assert result.adv_percent == 0.0
    assert result.adv_score == ADV_WEIGHT


def test_parallel_lists_must_be_the_same_length() -> None:
    with pytest.raises(ValueError, match="argument"):
        calculate_adv(["ru", "us"], [1], 1, ADVERSARIAL)


# ---------------------------------------------------------------------------
# collect_contributions
# ---------------------------------------------------------------------------


def test_unattributed_commits_stay_out_of_the_denominator(document: dict[str, Any]) -> None:
    document["contributors"] = [
        make_contributor("ru", 10),
        make_contributor(None, 990),
    ]

    _, _, total, coverage = collect_contributions(
        document, include_unattributed=False, source="test"
    )

    assert total == 10
    assert coverage.total == 2
    assert coverage.unattributed == 1


def test_the_toggle_puts_unattributed_commits_back(document: dict[str, Any]) -> None:
    document["contributors"] = [
        make_contributor("ru", 10),
        make_contributor(None, 990),
    ]

    _, _, total, _ = collect_contributions(document, include_unattributed=True, source="test")

    assert total == 1000


def test_a_bot_is_counted_as_a_contributor(document: dict[str, Any]) -> None:
    """Roadmap item 1: is_bot is published and never read."""
    document["contributors"] = [make_contributor("ru", 100, is_bot=True)]

    codes, commits, total, coverage = collect_contributions(
        document, include_unattributed=False, source="test"
    )

    assert codes == ["ru"]
    assert commits == [100]
    assert total == 100
    assert coverage.unattributed == 0


def test_an_empty_country_code_counts_as_attributed(document: dict[str, Any]) -> None:
    """Roadmap item 3: only None is tested, so "" reaches the denominator."""
    document["contributors"] = [make_contributor("", 9)]

    codes, _, total, coverage = collect_contributions(
        document, include_unattributed=False, source="test"
    )

    assert codes == [""]
    assert total == 9
    assert coverage.unattributed == 0


def test_a_null_contribution_raises(document: dict[str, Any]) -> None:
    """Roadmap item 6: upstream types contribution `int | None`."""
    document["contributors"] = [make_contributor("ru", None)]

    with pytest.raises(TypeError):
        collect_contributions(document, include_unattributed=False, source="test")


def test_a_document_without_contributors_is_named(document: dict[str, Any]) -> None:
    del document["contributors"]

    with pytest.raises(MissingFieldError) as caught:
        collect_contributions(document, include_unattributed=False, source="bcrypt.json")

    assert "bcrypt.json" in str(caught.value)
    assert "contributors" in str(caught.value)


# ---------------------------------------------------------------------------
# unclassified_score and score_repository
# ---------------------------------------------------------------------------


def test_unclassified_score_sums_the_six_components(document: dict[str, Any]) -> None:
    assert unclassified_score(document, "test") == 67.0


@pytest.mark.parametrize(
    "field",
    [
        "trusted_org_bonus",
        "stars_score",
        "forks_score",
        "last_update_score",
        "prevalence_score",
        "maturity_score",
    ],
)
def test_a_missing_score_component_names_itself(document: dict[str, Any], field: str) -> None:
    del document[field]

    with pytest.raises(MissingFieldError) as caught:
        unclassified_score(document, "example.json")

    assert field in str(caught.value)
    assert "example.json" in str(caught.value)


def test_score_repository_adds_the_bonus_to_the_upstream_total(document: dict[str, Any]) -> None:
    document["contributors"] = [make_contributor("us", 100)]

    score = score_repository(document, config(), "test")

    assert score.unclass_score == 67.0
    assert score.adversarial.adv_score == 25
    assert score.total_score == 92.0
    assert score.is_passing is True


def test_a_hostile_repository_loses_the_whole_bonus(document: dict[str, Any]) -> None:
    document["contributors"] = [make_contributor("ru", 40), make_contributor("us", 60)]

    score = score_repository(document, config(), "test")

    assert score.adversarial.adv_percent == 40.0
    assert score.adversarial.adv_score == 0.0
    assert score.total_score == 67.0
    assert score.is_passing is False


def test_the_pass_threshold_is_inclusive(document: dict[str, Any]) -> None:
    document["maturity_score"] = 15.0 - (92.0 - PASS_THRESHOLD)
    document["contributors"] = [make_contributor("us", 1)]

    score = score_repository(document, config(), "test")

    assert score.total_score == PASS_THRESHOLD
    assert score.is_passing is True


def test_a_document_without_a_name_is_named(document: dict[str, Any]) -> None:
    del document["name"]

    with pytest.raises(MissingFieldError) as caught:
        score_repository(document, config(), "somewhere.json")

    assert "somewhere.json" in str(caught.value)
