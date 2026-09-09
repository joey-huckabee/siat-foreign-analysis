"""Loading and validation of ``country_config.json``.

The pre-package script read this file inline and indexed straight into it, so
a missing ``adversarial_nations`` key raised a bare :class:`KeyError` naming
the key and nothing about the file it came from. Loading is a stage of its
own here, and every way the file can be wrong is reported against its path.

The whole of the scoring policy is configurable from here: the adversarial
nations, whether unattributed commits count toward the denominator, the
adversarial weight and the pass threshold. Every setting defaults to the value
that was a literal in the code before roadmap item 14, so an omitted or
minimal configuration scores exactly as 1.1.0 did.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from siat_foreign_analysis.errors import ConfigInvalidError, ConfigNotFoundError
from siat_foreign_analysis.logger import get_logger
from siat_foreign_analysis.models import AdversarialNation, Config, ScoringConfig
from siat_foreign_analysis.paths import resolve_path

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

    GitHub-Metrics emits ``country_code`` as lower-case ISO 3166-1 alpha-2.
    Codes are compared case-insensitively, so a configuration written in upper
    case still matches - it used to match nothing at all and report every
    repository clean, which failed nothing and was wrong everywhere. A code
    that is not already lower case is warned about, because it does not match
    the shape of the data it is compared against.

    Args:
        path: Path to the configuration file.

    Returns:
        The parsed configuration.

    Raises:
        ConfigNotFoundError: If the file does not exist.
        ConfigInvalidError: If the file is not valid JSON, is not an object,
            carries an ``adversarial_nations`` list that is absent, empty,
            malformed or repeats a code, or carries a ``scoring`` block whose
            values are of the wrong type or negative.
    """
    # Resolved before use, so the path read is the path reported and a
    # relative fragment cannot mean two different files in one run.
    config_path = resolve_path(path)
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
        if nation.country_code != nation.country_code.casefold():
            logger.warning(
                "Country code %r for %r is not lower case; matching it as %r. GitHub-Metrics "
                "emits lower-case ISO 3166-1 alpha-2, and the reports key on the folded code.",
                nation.country_code,
                nation.name,
                nation.country_code.casefold(),
            )

    duplicates = _duplicate_codes(nations)
    if duplicates:
        raise ConfigInvalidError(
            f"{config_path}: 'adversarial_nations' lists {', '.join(duplicates)} more than once. "
            f"Codes are compared case-insensitively, so the entries would share one report key "
            f"and only the last name would be announced."
        )

    scoring_raw = document.get("scoring", {})
    scoring_block = _require_mapping(scoring_raw, config_path, "'scoring'")

    include_unattributed = scoring_block.get("include_unattributed_in_denominator", False)
    if not isinstance(include_unattributed, bool):
        raise ConfigInvalidError(
            f"{config_path}: 'scoring.include_unattributed_in_denominator' must be true or "
            f"false, got {include_unattributed!r}"
        )

    adversarial_weight = _require_non_negative_number(
        scoring_block, "adversarial_weight", ScoringConfig.adversarial_weight, config_path
    )
    pass_threshold = _require_non_negative_number(
        scoring_block, "pass_threshold", ScoringConfig.pass_threshold, config_path
    )

    return Config(
        adversarial_nations=nations,
        scoring=ScoringConfig(
            include_unattributed_in_denominator=include_unattributed,
            adversarial_weight=adversarial_weight,
            pass_threshold=pass_threshold,
        ),
    )


def _duplicate_codes(nations: tuple[AdversarialNation, ...]) -> list[str]:
    """Return case-folded country codes that appear more than once.

    Args:
        nations: The parsed nation entries.

    Returns:
        Each repeated code, in first-seen order.
    """
    seen: set[str] = set()
    repeated: list[str] = []
    for nation in nations:
        code = nation.country_code.casefold()
        if code in seen and code not in repeated:
            repeated.append(code)
        seen.add(code)
    return repeated


def _require_non_negative_number(
    block: dict[str, Any], key: str, default: float, path: Path
) -> float:
    """Read one numeric scoring setting, or return its default.

    ``bool`` is rejected explicitly: it is a subclass of ``int`` in Python, so
    ``"pass_threshold": true`` would otherwise be accepted as a threshold of 1
    and pass every repository.

    Args:
        block: The decoded ``scoring`` block.
        key: Setting to read.
        default: Value to use when the setting is absent.
        path: Configuration file, for the message.

    Returns:
        The configured value, or the default.

    Raises:
        ConfigInvalidError: If present but not a non-negative number.
    """
    if key not in block:
        return default

    value = block[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigInvalidError(f"{path}: 'scoring.{key}' must be a number, got {value!r}")
    if value < 0:
        raise ConfigInvalidError(f"{path}: 'scoring.{key}' must not be negative, got {value!r}")
    return value


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
    logger.info("adversarial_weight: %s", config.scoring.adversarial_weight)
    logger.info("pass_threshold: %s", config.scoring.pass_threshold)
    logger.info("%s", "-" * 50)
    logger.info("Adversarial Nations List used for Processing:")
    logger.info("%s", "-" * 50)
    for nation in config.adversarial_nations:
        logger.info("%s: %s", nation.country_code, nation.name)
