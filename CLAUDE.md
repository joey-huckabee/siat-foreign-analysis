# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

siat-foreign-analysis scores the **adversarial contribution** in free and open
source repositories, from the per-repository JSON documents produced by
[GitHub-Metrics](https://github.com/joey-huckabee/GitHub-Metrics). The two
repositories are one pipeline and neither is much use without the other.

GitHub-Metrics emits `foreign`, `adversarial`, `foreign_contribution`,
`adversarial_contribution`, `foreign_percent` and `adversarial_percent` as
`null`. They are marked **TBD** in that project's `docs/METRICS.md` and
nothing upstream computes them. This package computes the adversarial half.
`foreign` is still nobody's job.

### The scoring split

- Five upstream components — `prevalence_score`, `stars_score`,
  `forks_score`, `maturity_score`, `last_update_score` — cap at **75**.
- The adversarial bonus computed here is worth **25**.
- `trusted_org_bonus` is a further **+10 on top**, so a total can exceed 100.
- Pass is **70 or more**, adversarial bonus included.

Both are configurable as `scoring.adversarial_weight` and
`scoring.pass_threshold`, defaulting to the historical literals still named in
`scoring.py` as `ADV_WEIGHT` and `PASS_THRESHOLD`.

### Two reports, one of which leaves the building

`score_report` is **releasable** and carries only the verdict and the
unclassified component. `detailed_score_report` carries the total and the
per-nation breakdown and is **not**. When adding a field, decide which report
it belongs in before writing it — the releasable one withholds the adversarial
score deliberately, even though that score decided its verdict.

## Common Commands

```bash
# Setup
poetry install --with dev
poetry run pre-commit install

# The gate. `make check` is exactly what CI runs.
make check     # lint + types + tests + dead code
make format    # black, isort, ruff --fix
make lint      # black, isort, ruff, pylint (no writes)
make types     # mypy --strict
make test      # pytest, coverage always on, 95% floor
make dead      # vulture
make run       # score input/ into output/

# Without make. Git Bash on Windows has no `make`; these are the same thing.
poetry run black --check --diff . && poetry run isort --check-only --diff .
poetry run ruff check . && poetry run pylint siat_foreign_analysis tests
poetry run mypy --config-file mypy.ini
poetry run pytest
poetry run vulture
poetry run siat-foreign-analysis --input input --output output
```

## Architecture

One package, nine modules, no runtime dependencies. The standard library is
the whole dependency list and it should stay that way — this reads documents
from a classified-adjacent pipeline, so every dependency added is one more
thing to account for. That is why the CLI is `argparse` and not `click`.

| Module | Holds |
|---|---|
| `cli.py` | Argument parsing, the run loop, exit codes |
| `config.py` | Loading and validating `country_config.json` |
| `scoring.py` | The bands, the denominator, `calculate_adv` |
| `models.py` | Every typed value passed between stages |
| `inputs.py` | Discovery, bounded reads, the archive walker |
| `reports.py` | Building and writing the four output files |
| `errors.py` | The exception hierarchy |
| `paths.py` | Path containment checks |
| `exit_codes.py` | Process exit codes |
| `logger.py` | Logging setup |

### Conventions that will bite you

**Country codes are lower case.** GitHub-Metrics emits ISO 3166-1 alpha-2 in
lower case, and both sides are case-folded before comparison since 1.3.0, so
an upper-case configuration matches rather than silently reporting every
repository clean. It did exactly that once — see CHANGELOG 1.0.0. The reports
key on the folded code, so do not assume the report key matches the spelling
in the configuration file.

**The published bytes are an interface.** Key order, column order, `True`
rather than `true`, four-space indentation, no trailing newline, CRLF row
endings, and integer `25` beside float `22.5` for `advScore`. All of it is
load-bearing and all of it is pinned by `tests/test_baseline.py`.

**`models.AdversarialResult.to_details()` deliberately preserves defects.**
`advPercent` is omitted entirely rather than set to zero when the denominator
was zero (item 7), and `advScore` is integer `25` in the top band and a float
in every other. Each is annotated with the roadmap item that owns it. Do not
tidy these away as a side effect of another change — take the item.

**Anything read from `--input` must resolve inside it.** A scan directory
arrives from elsewhere, so a symlink in it pointing out is a real escape, and
`paths.resolve_within` is what stops it. Use it for any new path built from
discovered data. Do not weaken it to make a test convenient.

**Nothing is suppressed in `sonar-project.properties`.** A finding this
project disagrees with stays open and gets argued in review. An exclusion
added to green a dashboard outlives its reason, and the next person cannot
tell a decision from an expedient.

Three `S8572` findings in `cli.py` are open on purpose. Sonar wants
`logging.exception()` in an `except` block; the rule's concern is that the
traceback is discarded, and it is not — the one-line message goes to the user
at ERROR and the traceback to DEBUG, so `--verbose` has it. Inflicting a stack
trace on someone who mistyped a path is worse than the finding. Leave them
open; do not silence them.

**Diagnostics go to stderr.** Nothing writes to stdout. The package logger
does not propagate, which means `caplog` cannot see it once
`configure_logging` has run — read `capsys.readouterr().err` in tests that
exercise the CLI.

## Testing

`tests/fixtures/expected/` holds the reports the package is expected to
produce, and `tests/test_baseline.py` compares against them byte for byte.
This is the most important thing in the test suite.

They started as output recorded from the 1.1.0 script, which is how 1.2.0
proved it moved nothing. Each release since has re-recorded only the files a
roadmap item deliberately changed, with that diff reviewed as part of the
change. Their authority is that reviewed history, not the file contents.

When a roadmap item is taken and a number is *supposed* to move, those tests
fail. That is the design: re-record the fixtures deliberately, as part of the
change, and the diff on the recorded files becomes the release note. Never
re-record them to make a red suite go green without first knowing exactly
which numbers moved and why.

The five fixture documents under `tests/fixtures/documents/` are synthetic and
chosen to reach every interesting path: the top band, a middle band, past the
last band, a contributor list that never arrived, and one where nobody could
be located. `mixed.json` additionally carries a bot with commits and an
empty-string country code, so roadmap items 1 and 3 are pinned by a golden
file rather than only described.

## Roadmap and standing decisions

`docs/ROADMAP.md` is the list of everything known to be wrong or undecided,
ordered by whether it corrupts published numbers, crashes, or muddles detail.
`CHANGELOG.md` is the release history.

**The standing decision is that scoring behaviour does not change without a
decision recorded first.** 1.2.0 restructured the whole project and moved not
one published number, on purpose, so that the correctness items could be taken
afterwards against a suite that can prove what each one changed.

Several roadmap items are **policy, not bugs**, and are not yours to settle:

- whether a bot's commits count as human contribution (item 1)
- whether a repository with no usable contributor data is penalised maximally
  or not at all (items 7, 8) — note the two current defaults contradict each
  other
- whether `badcountry` / `bc` is test scaffolding or a real entry (item 5)

Raise these; do not decide them.
