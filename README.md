# siat-foreign-analysis

Scores the adversarial contribution in free and open source repositories, from
the per-repository documents produced by
[GitHub-Metrics](https://github.com/joey-huckabee/GitHub-Metrics).

GitHub-Metrics computes five popularity and maturity metrics and deliberately
leaves `foreign`, `adversarial` and their four aggregates as `null` — they are
marked TBD in that project's `docs/METRICS.md` and nothing upstream computes
them. This tool supplies the adversarial half.

```
GitHub-Metrics                          siat-foreign-analysis
──────────────                          ─────────────────────
scan a repository  ──▶  <repo>.json  ──▶  score adversarial  ──▶  score_report
five metrics, 75 pts    contributors      contribution, 25 pts    detailed_score_report
```

## What it does

Each repository is scored out of 100:

| Component | Points | Computed by |
|---|---|---|
| `prevalence_score`, `stars_score`, `forks_score`, `maturity_score`, `last_update_score` | up to 75 | GitHub-Metrics |
| Adversarial contribution | up to 25 | this tool |
| `trusted_org_bonus` | +10 on top | GitHub-Metrics |

A repository passes at **70 points or more**, adversarial bonus included.

The adversarial bonus is tiered on the percentage of commits from contributors
located in a configured adversarial nation. It is full for a clean repository
and zero once a quarter of the commits are adversarial:

| Adversarial commits | Bonus |
|---|---|
| under 0.5% | 25 |
| under 1% | 22.5 |
| under 2% | 20 |
| under 5% | 17.5 |
| under 10% | 12.5 |
| under 15% | 10 |
| under 20% | 7.5 |
| under 25% | 5 |
| 25% or more | 0 |

## Install

Needs Python 3.10 or newer. The package itself has **no runtime
dependencies** — everything it uses is in the standard library.

```bash
poetry install --with dev
poetry run pre-commit install     # optional, but it is what CI runs
```

## Populating `input/`

Two shapes are accepted, and both can be present at once.

**Bare documents.** Copy GitHub-Metrics' per-repository JSON directly into
`input/`:

```
input/
├── bcrypt.json
└── itsdangerous.json
```

Documents are found **at any depth**, so a GitHub-Metrics scan directory can
be copied across exactly as it was written — `<owner>/<repoid>.json` and all:

```
input/
└── scan-2026-09/
    ├── pyca/bcrypt.json
    └── pallets/itsdangerous.json
```

**Archives.** Drop the scan in as a `.tar.gz` and leave it packed. Archives
are found at any depth too, and JSON members inside them at any depth:

```
input/
└── scan-2026-09-08.tar.gz     ← contains pyca/bcrypt.json, pallets/itsdangerous.json, …
```

Reads are bounded at 25 MB per document, non-regular members (directories,
symlinks, hardlinks) are refused, and a member whose declared size understates
its stream is caught while reading rather than trusted.

## Running

```bash
poetry run siat-foreign-analysis          # input/ → output/
make run                                  # the same thing
```

Or point it anywhere:

```bash
poetry run siat-foreign-analysis \
    --input  /scans/2026-09 \
    --output /reports \
    --config country_config.json
```

| Option | Default | Meaning |
|---|---|---|
| `-i`, `--input` | `input` | Directory holding the documents to score |
| `-o`, `--output` | `output` | Where the four reports are written; created if absent |
| `-c`, `--config` | `country_config.json` | Adversarial nations and scoring policy |
| `-v`, `--verbose` | | Log every contributor as it is read |
| `-q`, `--quiet` | | Warnings and errors only |
| `--version` | | Print the version and exit |

Progress goes to **stderr**, so stdout stays clean.

| Exit code | Meaning |
|---|---|
| 0 | Every discovered input was scored and every report written |
| 2 | The country configuration was missing, malformed, or incomplete |
| 3 | An input document could not be read, decoded, or was missing a field |
| 4 | The output directory or one of the reports could not be written |

## The four outputs

Two reports, each as JSON and CSV.

**`score_report.{json,csv}` — releasable.** Intended to be transferable to the
unclassified side. It carries the pass/fail verdict and the unclassified
component of the score, and deliberately **withholds the adversarial score**
even though that score decided the verdict.

```csv
package_name,is_passing,unclass_score
bcrypt,True,67.0
```

**`detailed_score_report.{json,csv}` — not releasable.** The same verdict plus
the total score and the full adversarial breakdown: commits and percentage per
adversarial nation, and which nation contributed most.

```csv
package_name,is_passing,unclass_score,adversarial_score,total_score
bcrypt,True,67.0,25,92.0
```

## `country_config.json`

```json
{
    "adversarial_nations": [
        { "name": "russia", "country_code": "ru" }
    ],
    "scoring": {
        "include_unattributed_in_denominator": false,
        "adversarial_weight": 25,
        "pass_threshold": 70.0
    }
}
```

**`adversarial_nations`** (required, non-empty). Each entry needs a `name` and
a `country_code`. Order is load-bearing: it fixes the key order of the
per-country block in the detailed report, and breaks ties when two nations
have an equal number of commits.

Codes are compared case-insensitively, and the reports key on the lower-case
form. GitHub-Metrics emits lower-case ISO 3166-1 alpha-2, so writing them that
way matches the data and avoids a warning; writing `RU` still works. Listing
the same code twice in different cases is refused, because the two entries
would collapse into one report key.

The whole `scoring` block is optional, and every key in it defaults to the
value the tool used before it was configurable.

| Key | Default | Meaning |
|---|---|---|
| `include_unattributed_in_denominator` | `false` | Whether commits with no attributed country enter the adversarial-percentage denominator. Left out by default, so missing attribution does not deflate the percentage. |
| `adversarial_weight` | `25` | Points a clean repository is awarded. The bands scale with it; `0` removes the adversarial component and scores the upstream metrics alone. |
| `pass_threshold` | `70.0` | Total score, adversarial bonus included, at which a repository passes. |

Write `adversarial_weight` as a whole number unless you want fractional
points: an integer weight makes a clean repository score `25` in the JSON,
while `25.0` makes it `25.0`.

Coverage of contributor attribution is reported at the end of every run. It is
worth reading: a repository can score a clean 25 on a contributor list that was
only half resolved.

## Development

```bash
make check     # lint + types + tests + dead code. Exactly what CI runs.
make format    # black, isort, ruff --fix
make test      # pytest with coverage
make help      # every target
```

Git Bash on Windows ships no `make`. Every target is a short sequence of
`poetry run` calls and works without it:

```bash
poetry run black --check --diff . && poetry run isort --check-only --diff .
poetry run ruff check . && poetry run pylint siat_foreign_analysis tests
poetry run mypy --config-file mypy.ini
poetry run pytest
poetry run vulture
```

The test suite pins the reports against output recorded from the previous
release, compared byte for byte. See `tests/test_baseline.py` — a change that
moves a published number fails there by design.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
