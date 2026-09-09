# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Known defects and undecided policy are tracked in [`docs/ROADMAP.md`](docs/ROADMAP.md).

## [1.3.0] - unreleased

Takes four roadmap items that harden paths real input has not yet walked.
**No published number moves**: the byte comparison against the recorded 1.1.0
reports stayed green through all four, which is what says so rather than a
claim in a commit message.

Item 1 (bot commits) is deferred by decision — whether a bot's commits count
as human contribution is policy, and it is not settled.

### Added

- `scoring.adversarial_weight` and `scoring.pass_threshold` in
  `country_config.json` (roadmap item 14). Both were literals in the code.
  They default to `25` and `70.0`, so a configuration that omits the block
  scores exactly as before. A weight of `0` scores the five upstream
  components alone without editing code.
- Both are validated as non-negative numbers. `bool` is rejected explicitly:
  it subclasses `int` in Python, so `"pass_threshold": true` would otherwise
  be read as a threshold of 1 and pass every repository.
- A configuration listing the same country code twice in different cases is
  refused. The two entries would collapse into one report key and only the
  last name would be announced.

### Fixed

- Country codes are compared case-insensitively (roadmap item 4). An
  upper-case entry in `country_config.json` used to match nothing at all,
  which did not fail — it reported the repository as clean and awarded a full
  25. This had already happened once; see 1.0.0. Both sides are folded, so
  neither the configuration nor an upper-case code from upstream can
  reintroduce it, and the reports key on the folded code.
- A `null` contribution counts as zero commits instead of raising `TypeError`
  (roadmap item 6). Upstream types the field `int | None`. One null used to
  lose the entire run, because the reports are written only after every input
  is processed. The substitution is logged with the contributor and document
  named. Zero is the only value that does not invent a number.
- Documents nested by owner are found (roadmap item 9). GitHub-Metrics writes
  `<output>/<owner>/<repoid>.json`, and matching only the top level meant a
  scan directory copied across verbatim produced an empty report and exit 0 —
  no result and no error. Both bare documents and archives are now found at
  any depth, and discovery is sorted so report key order is stable across
  runs.

### Changed

- `LICENSE` matches GitHub-Metrics exactly again; the copyright line filled in
  during 1.2.0 is back to the upstream placeholder.

## [1.2.0] - 2026-09-08

Restructures the project without moving a single published number. The four
reports are byte-for-byte identical to 1.1.0 for the same input, which is
asserted rather than asserted-to: `tests/test_baseline.py` compares against
reports recorded by running the 1.1.0 script itself.

That was the point of the release. The correctness items in
[`docs/ROADMAP.md`](docs/ROADMAP.md) can now be taken one at a time against a
suite that can prove exactly which numbers each one moves.

### Added

- A test suite: 185 tests at 99.66% coverage, with a 95% floor enforced by
  `pytest-cov`. Includes five synthetic GitHub-Metrics documents chosen to
  reach every scoring band, both denominator settings, and the paths for a
  contributor list that never arrived and a repository nobody could be
  located in (roadmap items 16 and 25).
- `tests/fixtures/expected/`: reports recorded from the 1.1.0 script, compared
  byte for byte. A change that moves a published number now fails a test
  instead of going unnoticed.
- Continuous integration (roadmap item 22): `ci.yml` runs the linters, the
  type checker and the suite across Python 3.10 to 3.14 on Linux plus Windows
  and macOS, then builds and smoke-tests the wheel; `codeql.yml`; and
  `sonarcloud.yml`, which skips with a notice rather than failing when its
  three secrets are absent.
- `.pre-commit-config.yaml`, running the fast half of `make check`.
- A `Makefile`. `make check` is exactly what CI runs.
- `LICENSE` (Apache-2.0, matching GitHub-Metrics), `CONTRIBUTING.md`,
  `CLAUDE.md`, `AGENTS.md` and `.editorconfig` (roadmap items 19, 21, 24).
- A command line interface. `--input`, `--output` and `--config` were hard
  coded relative to the working directory, so running from anywhere else
  found nothing and wrote an empty report in silence. Built on `argparse`;
  the package still has **no runtime dependencies**.
- `--verbose`, `--quiet` and `--version`.
- Distinct exit codes for configuration, input and output failures.
- An exception hierarchy under `ForeignAnalysisError`. Each leaf also inherits
  the built-in the script raised at the same point, so existing `except`
  clauses keep working.
- `MissingFieldError` names the document as well as the absent field. A bare
  `KeyError` said which key was missing and nothing about which of the inputs
  lacked it.
- Validation of `country_config.json`, reported against the file's path: bad
  JSON, a missing or empty `adversarial_nations` list, a malformed entry, and
  a non-boolean toggle are each named. An upper-case country code now warns
  that it will match nothing (roadmap item 4 is still open; this only warns).
- A JSON document found below the top level of the input directory is
  reported rather than passed over, which is how a GitHub-Metrics scan
  directory copied across verbatim used to produce an empty report (roadmap
  item 9 remains open; discovery is still non-recursive).

### Changed

- The script is now a package, `siat_foreign_analysis`, split into `cli`,
  `config`, `scoring`, `models`, `inputs`, `reports`, `errors`, `exit_codes`
  and `logger`.
- `python foreign_analysis.py` is replaced by the `siat-foreign-analysis`
  console script, or `python -m siat_foreign_analysis`. **This is breaking for
  anything invoking the script by path.**
- All 39 `print()` calls became logging. Per-contributor detail is `DEBUG`,
  progress is `INFO`. Diagnostics go to **stderr**, leaving stdout clean.
- `pyproject.toml` carries project metadata and a version, and declares the
  development dependencies that `requirements-dev.txt` used to list unpinned
  (roadmap items 20 and 23).
- `mypy.ini`, `.pylintrc` and `sonar-project.properties` retargeted at the
  package and the tests.
- `[tool.pyright]` dropped. Pyright was configured and never installed;
  Pylance reads `python.analysis.typeCheckingMode` from `.vscode/settings.json`
  instead, and mypy is the type checker CI runs.

### Fixed

- An archived document was logged as `input\docs.tar.gz/bcrypt.json`, joining
  a native path to a POSIX one with a literal separator. Archive and member
  are now separated by `::` (roadmap item 15).
- The linters, the type checker and the dead-code check had never been run
  against the code. All of them now pass, and CI keeps it that way (roadmap
  item 17).
- `README.md` was one line. It now covers what the tool consumes, how to
  populate `input/` in both accepted shapes, how to run it, what the four
  outputs mean, the `country_config.json` schema, and the link to
  GitHub-Metrics that made the pipeline visible from neither end (roadmap
  item 18).

### Deprecated

- `requirements-dev.txt` is removed. Use `poetry install --with dev`.

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

[1.3.0]: https://github.com/joey-huckabee/siat-foreign-analysis/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/joey-huckabee/siat-foreign-analysis/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/joey-huckabee/siat-foreign-analysis/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/joey-huckabee/siat-foreign-analysis/releases/tag/v1.0.0
