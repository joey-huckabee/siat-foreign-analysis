# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Known defects and undecided policy are tracked in [`docs/ROADMAP.md`](docs/ROADMAP.md).

## [1.1.0] - 2026-09-08

### Added

- Read repository documents from `*.tar.gz` archives in `input/`, alongside
  bare `*.json` files. `read_json` performs bounded reads with a 25 MB
  ceiling, rejects non-regular members, and reads one byte past the limit to
  catch a member whose declared size understates its stream.
- `scoring.include_unattributed_in_denominator` in `country_config.json`.
  When `true`, commits from contributors with no attributed country enter the
  adversarial-percentage denominator. Defaults to `false`, which is 1.0.0
  behaviour.
- Cumulative contributor data-quality summary across every input file, printed
  once at the end of a run.
- Type annotations throughout, a module docstring, and docstrings on every
  function.
- Development tooling: `.pylintrc`, `mypy.ini`, `pyproject.toml` (black,
  isort, pyright, vulture), `requirements-dev.txt`, `sonar-project.properties`
  and `.vscode/` launch, settings and extension recommendations.
- `docs/ROADMAP.md` and this changelog.

### Changed

- The entry point is now a `main()` function rather than code under
  `if __name__ == "__main__"`.
- `calculate_adv` takes `total_commits` as a parameter instead of summing it
  internally, so the denominator is decided by the caller and the toggle above
  can change it.
- `output/` is created if it does not exist, rather than requiring it to be
  present.
- `ROADMAP.md` moved to `docs/ROADMAP.md`.

### Fixed

- `topAdvContributorCountry` reported an index rather than a country: the
  country was assigned and then immediately overwritten with `i + 1`. It now
  names the adversarial country with the most commits, or `None` when there
  are none.
- A repository whose contributors all lacked a resolved location raised
  `ZeroDivisionError`, losing the entire run rather than one repository,
  because reports are written only after every input is processed.
- The cumulative contributor counters were reset inside the per-file loop, so
  the "total" data-quality figure described only the last file processed.
- Output files are written through context managers, so a failure mid-write no
  longer leaks a handle or leaves a truncated report.
- Every output file is opened with an explicit encoding.

## [1.0.0] - 2026-09-07

Initial release, mirroring the historical project. Scores the adversarial
contribution that GitHub-Metrics deliberately leaves `null` — `foreign`,
`adversarial` and the four contribution aggregates are marked TBD in that
project's `docs/METRICS.md`, and nothing upstream computes them.

### Added

- Reads GitHub-Metrics per-repository JSON documents from `input/` and writes
  `score_report` and `detailed_score_report` to `output/`, each as JSON and
  CSV.
- Adversarial nations configured in `country_config.json`.
- Tiered adversarial scoring worth up to 25 points, zeroing at 25% adversarial
  commits.

### Fixed

The script was hand-transcribed against a schema that did not match what
GitHub-Metrics emits. The following were corrected so that it would run at
all; everything else was left as written so this release mirrors the
historical project.

- Seven document keys did not exist: `cpntributors`, `trustedorgbonus`,
  `starscore`, `forksscore`, `lastupdatescore`, `prevalancescore` and
  `maturityscore` became `contributors`, `trusted_org_bonus`, `stars_score`,
  `forks_score`, `last_update_score`, `prevalence_score` and `maturity_score`.
- `json.load(f.read())` raised on the configuration file; corrected to
  `json.loads`.
- `csv.DisctWriter` raised `AttributeError`; corrected to `csv.DictWriter`.
- `calculate_adv` returned from inside its `for cc in adv_cc_list` loop, so
  only the first adversarial country was ever initialised and the percent loop
  raised `KeyError`. The body was moved out of that loop.
- Adversarial country codes in `country_config.json` were upper case, while
  GitHub-Metrics emits ISO 3166-1 alpha-2 in lower case, so no contributor
  ever matched. A repository whose top contributor was Russian scored a clean
  25 of 25. Codes lowercased.

[1.1.0]: https://github.com/joey-huckabee/siat-foreign-analysis/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/joey-huckabee/siat-foreign-analysis/releases/tag/v1.0.0
