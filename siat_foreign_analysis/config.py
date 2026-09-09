"""Loading and validation of ``country_config.json``.

The pre-package script read this file inline and indexed straight into it, so
a missing ``adversarial_nations`` key raised a bare :class:`KeyError` naming
the key and nothing about the file it came from. Loading is a stage of its
own here, and every way the file can be wrong is reported against its path.

Nothing in this module decides policy. The pass threshold and the adversarial
weight are still literals in :mod:`siat_foreign_analysis.scoring`; moving them
here beside the nation list is roadmap item 14.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from siat_foreign_analysis.errors import ConfigInvalidError, ConfigNotFoundError
from siat_foreign_analysis.logger import get_logger
from siat_foreign_analysis.models import AdversarialNation, Config, ScoringConfig

logger = get_logger(__name__)

DEFAULT_CONFIG_PATH = Path("country_config.json")
"""Where the configuration is looked for when no path is given."""


def _require_mapping(value: Any, path: Path, what: str) -> dict[str, Any]:
    """Return ``value`` as a mapping, or raise naming what was expected.

    Args:
        value: The decoded value to check.
        path: Configuration file the value came from, for the message.
        what: Human-readable description of the element being checked.

    Returns:
        The value, narrowed to a dictionary.

    Raises:
        ConfigInvalidError: If the value is not a JSON object.
    """
    if not isinstance(value, dict):
        raise ConfigInvalidError(
            f"{path}: {what} must be a JSON object, got {type(value).__name__}"
        )
    return value


def _parse_nation(entry: Any, path: Path, index: int) -> AdversarialNation:
    """Build one :class:`AdversarialNation` from a configuration entry.

    Args:
        entry: The decoded list element.
        path: Configuration file the entry came from, for the message.
        index: Position in the list, so a message names the offending entry.

    Returns:
        The parsed nation.

    Raises:
        ConfigInvalidError: If the entry is not an object, or does not carry
            both ``name`` and ``country_code`` as non-empty strings.
    """
    block = _require_mapping(entry, path, f"adversarial_nations[{index}]")

    for key in ("name", "country_code"):
        value = block.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigInvalidError(
                f"{path}: adversarial_nations[{index}] needs a non-empty string {key!r}, "
                f"got {value!r}"
            )

    return AdversarialNation(name=block["name"], country_code=block["country_code"])


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Config:
    """Read and validate the country configuration.

    Country codes are taken exactly as written. GitHub-Metrics emits
    ``country_code`` as lower-case ISO 3166-1 alpha-2, and a configuration
    written in upper case matches nothing at all - which is not an error here
    but a silent false negative in the score. Case-folding both sides is
    roadmap item 4; until it is taken, this function only warns.

    Args:
        path: Path to the configuration file.

    Returns:
        The parsed configuration.

    Raises:
        ConfigNotFoundError: If the file does not exist.
        ConfigInvalidError: If the file is not valid JSON, is not an object,
            or carries an ``adversarial_nations`` list that is absent, empty,
            or malformed.
    """
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigNotFoundError(f"Country configuration not found: {config_path}")

    try:
        decoded = json.loads(config_path.read_text(encoding="UTF-8"))
    except json.JSONDecodeError as exc:
        raise ConfigInvalidError(f"{config_path}: not valid JSON: {exc}") from exc

    document = _require_mapping(decoded, config_path, "the configuration")

    nations_raw = document.get("adversarial_nations")
    if nations_raw is None:
        raise ConfigInvalidError(f"{config_path}: no 'adversarial_nations' list")
    if not isinstance(nations_raw, list):
        raise ConfigInvalidError(
            f"{config_path}: 'adversarial_nations' must be a list, "
            f"got {type(nations_raw).__name__}"
        )
    if not nations_raw:
        raise ConfigInvalidError(
            f"{config_path}: 'adversarial_nations' is empty, so nothing can ever be scored "
            f"as adversarial"
        )

    nations = tuple(
        _parse_nation(entry, config_path, index) for index, entry in enumerate(nations_raw)
    )

    for nation in nations:
        if nation.country_code != nation.country_code.lower():
            logger.warning(
                "Country code %r for %r is not lower case. GitHub-Metrics emits lower-case "
                "ISO 3166-1 alpha-2, so this entry will never match a contributor.",
                nation.country_code,
                nation.name,
            )

    scoring_raw = document.get("scoring", {})
    scoring_block = _require_mapping(scoring_raw, config_path, "'scoring'")
    include_unattributed = scoring_block.get("include_unattributed_in_denominator", False)
    if not isinstance(include_unattributed, bool):
        raise ConfigInvalidError(
            f"{config_path}: 'scoring.include_unattributed_in_denominator' must be true or "
            f"false, got {include_unattributed!r}"
        )

    return Config(
        adversarial_nations=nations,
        scoring=ScoringConfig(include_unattributed_in_denominator=include_unattributed),
    )


def log_config(config: Config) -> None:
    """Announce the loaded configuration, as the pre-package script did.

    Args:
        config: The configuration to describe.
    """
    logger.info("%s", "-" * 50)
    logger.info("Scoring Configuration:")
    logger.info("%s", "-" * 50)
    logger.info(
        "include_unattributed_in_denominator: %s",
        config.scoring.include_unattributed_in_denominator,
    )
    logger.info("%s", "-" * 50)
    logger.info("Adversarial Nations List used for Processing:")
    logger.info("%s", "-" * 50)
    for nation in config.adversarial_nations:
        logger.info("%s: %s", nation.country_code, nation.name)
