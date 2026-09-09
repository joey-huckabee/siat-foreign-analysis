"""Loading and validating country_config.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from siat_foreign_analysis.config import load_config, log_config
from siat_foreign_analysis.errors import ConfigError, ConfigInvalidError, ConfigNotFoundError

VALID = {
    "adversarial_nations": [
        {"name": "russia", "country_code": "ru"},
        {"name": "badcountry", "country_code": "bc"},
    ]
}


def write(tmp_path: Path, payload: object) -> Path:
    """Write a configuration file and return its path."""
    path = tmp_path / "country_config.json"
    path.write_text(json.dumps(payload), encoding="UTF-8")
    return path


def test_loads_the_shipped_configuration(config_path: Path) -> None:
    config = load_config(config_path)

    assert config.adversarial_country_codes == ("ru", "bc")
    assert config.scoring.include_unattributed_in_denominator is False


def test_the_toggle_is_read(include_unattributed_config_path: Path) -> None:
    config = load_config(include_unattributed_config_path)

    assert config.scoring.include_unattributed_in_denominator is True


def test_a_missing_scoring_block_defaults_conservatively(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, VALID))

    assert config.scoring.include_unattributed_in_denominator is False


def test_a_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ConfigNotFoundError, match="not found"):
        load_config(tmp_path / "absent.json")


def test_malformed_json_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "country_config.json"
    path.write_text("{not json", encoding="UTF-8")

    with pytest.raises(ConfigInvalidError, match="not valid JSON"):
        load_config(path)


def test_a_non_object_configuration_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigInvalidError, match="must be a JSON object"):
        load_config(write(tmp_path, ["ru"]))


def test_an_absent_nation_list_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigInvalidError, match="no 'adversarial_nations'"):
        load_config(write(tmp_path, {"scoring": {}}))


def test_a_nation_list_of_the_wrong_type_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigInvalidError, match="must be a list"):
        load_config(write(tmp_path, {"adversarial_nations": "ru"}))


def test_an_empty_nation_list_is_refused(tmp_path: Path) -> None:
    """Nothing could ever be scored adversarial, so this is a mistake."""
    with pytest.raises(ConfigInvalidError, match="is empty"):
        load_config(write(tmp_path, {"adversarial_nations": []}))


@pytest.mark.parametrize(
    "entry",
    [
        "ru",
        {"name": "russia"},
        {"country_code": "ru"},
        {"name": "russia", "country_code": ""},
        {"name": "", "country_code": "ru"},
        {"name": "russia", "country_code": 7},
    ],
)
def test_a_malformed_nation_entry_is_refused(tmp_path: Path, entry: object) -> None:
    with pytest.raises(ConfigInvalidError):
        load_config(write(tmp_path, {"adversarial_nations": [entry]}))


def test_a_malformed_entry_names_its_position(tmp_path: Path) -> None:
    payload = {"adversarial_nations": [VALID["adversarial_nations"][0], {"name": "x"}]}

    with pytest.raises(ConfigInvalidError, match=r"adversarial_nations\[1\]"):
        load_config(write(tmp_path, payload))


def test_a_non_boolean_toggle_is_refused(tmp_path: Path) -> None:
    payload = {**VALID, "scoring": {"include_unattributed_in_denominator": "yes"}}

    with pytest.raises(ConfigInvalidError, match="must be true or false"):
        load_config(write(tmp_path, payload))


def test_a_non_object_scoring_block_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigInvalidError, match="must be a JSON object"):
        load_config(write(tmp_path, {**VALID, "scoring": []}))


def test_an_uppercase_country_code_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Roadmap item 4: it loads, matches nothing, and reports clean."""
    payload = {"adversarial_nations": [{"name": "russia", "country_code": "RU"}]}

    with caplog.at_level("WARNING"):
        config = load_config(write(tmp_path, payload))

    assert config.adversarial_country_codes == ("RU",)
    assert "not lower case" in caplog.text


def test_every_configuration_failure_is_a_config_error(tmp_path: Path) -> None:
    """One except clause catches the whole family."""
    with pytest.raises(ConfigError):
        load_config(tmp_path / "absent.json")
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, {"adversarial_nations": []}))


def test_log_config_announces_every_nation(
    config_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO"):
        log_config(load_config(config_path))

    assert "ru: russia" in caplog.text
    assert "bc: badcountry" in caplog.text
    assert "include_unattributed_in_denominator: False" in caplog.text
