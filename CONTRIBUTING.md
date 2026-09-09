# Contributing

## Setup

```bash
poetry install --with dev
poetry run pre-commit install
```

Python 3.10 or newer. The package has no runtime dependencies; everything
installed is a development tool.

## Before you push

```bash
make check
```

`make check` is exactly what CI runs — black, isort, ruff, pylint, mypy
(`strict`), the test suite with a 95% coverage floor, and vulture. The
pre-commit hooks are the fast half of the same set, so a hook that disagrees
with CI is a bug in one of the two and worth reporting.

## Changing what the reports say

The four output files are a published interface, and the test suite compares
them byte for byte against reports recorded from the previous release
(`tests/fixtures/expected/`, asserted by `tests/test_baseline.py`).

If your change moves a published number, those tests fail. That is the point.
The process is:

1. Confirm the change is one the roadmap or an issue has already agreed to.
   Scoring behaviour does not change without a recorded decision.
2. Work out **exactly which numbers moved and why**, before touching the
   recorded files.
3. Re-record the fixtures deliberately and commit the diff. Reviewers read
   that diff as the release note.
4. Say so in `CHANGELOG.md`, under `Changed` or `Fixed`, naming the roadmap
   item.

Never re-record fixtures to turn a red suite green.

## Style

- 100 columns. Configured in every tool; do not fight it.
- Google-convention docstrings on every public module, class and function.
  `ruff` enforces this.
- Type annotations throughout. `mypy` runs `strict`.
- Comments explain **why**, not what. The codebase leans on this heavily —
  several deliberately-preserved defects are only distinguishable from
  accidents by their comment naming the roadmap item that owns them. Keep
  that up.

## Roadmap items that are not yours to decide

`docs/ROADMAP.md` mixes defects with open policy questions. These are policy:

- whether a bot's commits count as human contribution (item 1)
- whether missing contributor data is penalised maximally or not at all
  (items 7 and 8)
- whether `badcountry` / `bc` is scaffolding or a real entry (item 5)

Raise them in an issue rather than settling them in a pull request.

## Commits and pull requests

- Branch from `main`.
- One concern per pull request. A restructure and a behaviour change in the
  same diff makes it impossible to tell which one moved a number.
- Reference the roadmap item number where there is one.
