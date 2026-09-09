# siat-foreign-analysis — Roadmap

Everything known to be wrong, or known to be undecided, in the package and
its configuration.

**Item numbers are stable and are referenced from code comments and tests.**
A resolved item keeps its number and is marked rather than removed, so
`# Roadmap item 7` in `models.py` always means the same thing. Line numbers
quoted below are against the 1.1.0 script and are kept for provenance; the
code has since moved into `siat_foreign_analysis/`.

Verified against GitHub-Metrics 0.6.2, scan
`595344b7-0919-4da5-88e2-0376bab8db6b`, over `pyca/bcrypt` and
`pallets/itsdangerous`. Figures quoted below come from that scan.

Items are ordered by whether they corrupt published numbers, crash, or muddle
detail.

**Status as of 1.2.0.** Items 1 to 14 are all open: 1.2.0 restructured the
project and deliberately moved no published number, so every scoring defect
below is exactly as it was. Item 15 and the project items 16 to 25 are done.
Items 4 and 9 now warn at runtime but are otherwise unchanged.

| | Items | State |
|---|---|---|
| High | 1, 2, 3, 5 | Open |
| High | 4 | **Done in 1.3.0** |
| Medium | 7, 8, 10 | Open |
| Medium | 6, 9 | **Done in 1.3.0** |
| Low | 11, 12, 13 | Open |
| Low | 14 | **Done in 1.3.0** |
| Low | 15 | **Done in 1.2.0** |
| Project | 16-25 | **Done in 1.2.0** |

Item 1 is deferred by decision rather than by difficulty: whether a bot's
commits count as human contribution is policy, and it is not settled.

Items 4, 6, 9 and 14 were taken in 1.3.0 and moved **no published number** —
the byte comparison in `tests/test_baseline.py` stayed green through all
four, which is what says so. Each hardens a path that had not yet been walked
by real input rather than correcting a number the tool has actually
published.

There is now a test suite pinning the published bytes against the previous
release, so taking any remaining item produces a failing comparison that names
exactly which numbers moved. See `tests/test_baseline.py`.

---

## High — produces wrong numbers without failing

### 1. Bot commits are counted as human contribution

`is_bot` is published on every contributor record and is never read. In
`pyca/bcrypt`, `dependabot[bot]` accounts for **679 of 1043 commits** — 65% of
`contribution_total`. Any percentage taken over that total is dominated by
automation.

Bots currently miss the adversarial calculation only by accident: they publish
no location, so they land in the unattributed bucket. A bot that did carry a
location would be scored as a person. With
`include_unattributed_in_denominator` set to `true` they enter the denominator
directly.

Decide whether a bot's commits count, then apply it in both the denominator
and the data-quality figure.

### 2. Contributor coverage is computed and then discarded

`contributor_country_data_quality_percentage` (line 314) and
`total_contributor_quality_percentage` (line 378) are printed and reach
neither report. Coverage was **51.28%** for bcrypt, **64.29%** for
itsdangerous, **58.02%** across the run.

A consumer reading `score_report.csv` cannot tell a genuinely clean repository
from one where half the contributors were never located. Carry both figures
into the reports as columns.

### 3. An empty country code is treated as a real country

`country_code` has three states: `null` (no lookup ran), `""` (the lookup ran
and returned no country component at that resolution), and a real code. Line
296 tests only `is None`, so `""` is appended to `country_codes` and its
commits enter the denominator as though attributed. `itsdangerous` has **9
commits** in that bucket.

### 4. Country-code case is matched by convention, not enforced - DONE in 1.3.0

GitHub-Metrics emits `country_code` as lower-case ISO 3166-1 alpha-2. The
config was uppercase at first, so nothing ever matched.

Verified: with an uppercase config, a repository whose top contributor is
Russian reported `advPercent 0.0, advScore 25` — clean and passing. The config
is lower-case now, but nothing enforces it, and a future edit that types `RU`
reintroduces the same **silent false negative**.

Casefold both sides where they are compared, rather than relying on the config
being written correctly.

*Fixed: `Config.adversarial_country_codes` case-folds the configuration and
`calculate_adv` case-folds each contributor code before comparing, so neither
side can be written in a case that silently matches nothing. The reports key
on the folded code. A configuration that lists the same code twice in
different cases is now refused rather than quietly losing one of the two.*

### 5. `bc` is not a real country code

`country_config.json` ships `badcountry` / `bc` beside `russia` / `ru`. `BC`
is unassigned in ISO 3166-1, so it is a placeholder that can never match. It
is harmless but it ships in the adversarial nations list printed at startup
and in every `details.countries` block. Decide whether it is test scaffolding
or a real entry.

---

## Medium — crashes, or silently omits data, on input not yet seen

### 6. `contribution` may be `null` - DONE in 1.3.0

Upstream types it `int | None`. Lines 299 and 304 do `total_commits +=
contribution` with no guard, and `None` raises `TypeError`. Every repository
processed before it is lost, because the reports are written only after the
loop completes.

*Fixed: a null contribution counts as zero commits and is logged as a warning
naming the contributor and the document. Zero is the only substitution that
does not invent a number. Note this does not fix the wider problem the item
describes — one bad document still loses the whole run, which is items 6 and
10 together and remains open as item 10.*

### 7. `advPercent` is absent on the zero-contributor path

The early return at line 168 sets `advScore` and returns without setting
`advPercent`, so `details` lacks the key entirely. The detailed CSV survives
because it reads only `advScore`; anything reading `advPercent` raises
`KeyError`. Set it to `0.0`, or to `None` if "not measurable" is the intended
meaning.

### 8. A repository with no contributors scores zero adversarial points

The same early return awards `advScore = 0` — the **full 25-point penalty** —
to a repository whose contributor list failed to come across. That is the
harshest possible reading of missing data.

It also contradicts the neighbouring default:
`include_unattributed_in_denominator` defaults to `false` specifically so that
unattributed commits do not deflate the adversarial percentage. One default
declines to penalise missing data; the other penalises it maximally. Pick one
policy and apply it to both.

### 9. Documents nested by owner are not found - DONE in 1.3.0

GitHub-Metrics writes its documents as `<output>/<owner>/<repoid>.json`. Line
262 globs `input/*.json`, non-recursively, so a scan directory copied across
verbatim yields **zero inputs and an empty report** rather than an error.

Note the archive path does not share this defect:
`get_json_member_paths_in_tar_gz` walks every member at any depth. Only bare
files on disk must be flattened. Use `rglob`, or document the requirement.

*Fixed: `discover_inputs` uses `rglob` for both bare documents and archives,
so a scan directory copied across verbatim is read where it stands. Results
are sorted, so discovery order — and therefore report key order — is stable
across runs.*

### 10. Repositories that failed collection are invisible

A repository GitHub-Metrics could not read produces a CSV row but **no
document**, so it is absent from the score report entirely rather than
reported as a failure. Reconcile against `githubmetrics.csv` or
`statistics.json` so the report names what it could not score.

---

## Low — correctness of detail, not of score

### 11. `commitPercent` is initialised and never written

Line 141 creates `commitPercent`; line 178 writes `commitsPercent`. Both ship
in `details.countries`, and the first is always `0`.

### 12. `unclass_score` is recomputed rather than read

Line 349 re-adds the six upstream components, which the document already
publishes as `total_score` (verified equal: 67.0 and 63.0). Reading it removes
a place for the two to drift. Note upstream caps `total_score` at 85, which
the recomputation does not reproduce.

### 13. Reports are keyed by repository name alone

Lines 360 and 366 key on `data["name"]`, not owner-qualified, so two
repositories with the same name from different owners silently overwrite each
other. The document carries `owner` and `url`; either disambiguates.

### 14. Pass threshold and adversarial weight are literals - DONE in 1.3.0

`70.0` (line 359) and `adv_weight = 25` (line 186) are policy, and belong in
`country_config.json` beside the nation list and the scoring block that is
already there.

*Fixed: both are `scoring.pass_threshold` and `scoring.adversarial_weight`,
validated as non-negative numbers, defaulting to the historical literals so an
omitted block scores exactly as before. `bool` is rejected explicitly because
it subclasses `int` in Python, and `"pass_threshold": true` would otherwise
mean a threshold of 1 and pass everything.*

### 15. Mixed path separators in the progress line - DONE in 1.2.0

Line 271 renders an archive member as `input\docs.tar.gz/bcrypt.json` —
`Path`'s native separator joined to a `PurePosixPath` with a literal `/`.
Cosmetic, but it appears on every line of a long run.

*Fixed: `InputSource.describe()` renders the archive natively and separates it
from the member with `::`.*

---

## Project

### 16. There is no test suite - DONE in 1.2.0

Nothing is exercised automatically. The archive reader, the scoring bands, the
zero-guards and the denominator toggle are all verified only by hand. The
bands in particular are pure arithmetic over a single input and are the
cheapest thing in the file to test.

`pytest` is not in `requirements-dev.txt`, and `.vscode/settings.json` has
test discovery switched off until there is something to discover.

### 17. The linters are configured but have never been run - DONE in 1.2.0

`.pylintrc`, `mypy.ini` and `pyproject.toml` (black, isort, vulture) are all
in place and none has been run against the file. `mypy` is configured
`strict`, so it will report on every unannotated local; that is expected
rather than a fault in the config, but the baseline is unknown until it runs.

### 18. `README.md` is one line - DONE in 1.2.0

It names the project and says nothing else — not what it consumes, not how to
populate `input/`, not how to run it, and not what the four outputs mean. The
archive support and the scoring toggle are undiscoverable without reading the
source.

It needs, at minimum:

- what the tool does and what it consumes
- **a link to [GitHub-Metrics](https://github.com/joey-huckabee/GitHub-Metrics)**,
  which produces the documents this reads. Neither repository currently names
  the other, so the pipeline is invisible from either end.
- how to populate `input/`, both as bare `*.json` and as `*.tar.gz`
- how to run it, and what the four outputs in `output/` mean
- the `country_config.json` schema, including the `scoring` block

### 19. There is no `CLAUDE.md` or `AGENTS.md` - DONE in 1.2.0

Both should carry the project's working context so it does not have to be
rediscovered each session: the relationship to GitHub-Metrics and the document
schema it emits, the scoring split (five upstream components capping at 75,
adversarial worth 25, `trusted_org_bonus` a +10 on top), the lower-case
`country_code` convention, the layout of `input/` and `output/`, how to run
the script, and the standing decision to defer everything in this file until
the historical baseline is established.

### 20. Dev dependencies are not declared in `pyproject.toml` - DONE in 1.2.0

`requirements-dev.txt` lists five tools as bare names with no version pins,
while `pyproject.toml` carries only `[tool.*]` configuration. The two should
be consolidated: declare the development dependencies in `pyproject.toml`
alongside the settings for the same tools, so one file describes the toolchain.

The list is also incomplete and unpinned:

- `pytest` is absent, though a test suite is item 16
- `pyright` is absent, though `[tool.pyright]` configures it
- nothing is version-pinned, so two machines can run different rule sets
  against the same code and disagree

### 21. There is no `LICENSE` - DONE in 1.2.0

The repository is public and carries no licence file, which under default
copyright means nobody may use, copy or modify it. GitHub-Metrics ships
Apache-2.0; matching it would make the pipeline consistent.

### 22. There is no CI - DONE in 1.2.0

`sonar-project.properties` is configured and nothing runs it — there is no
`.github/workflows/` at all. Neither the linters, the type checker, nor Sonar
runs on a push, so every check in this repository is manual and therefore
optional in practice.

### 23. `pyproject.toml` declares no project metadata - DONE in 1.2.0

There is no `[project]` table, so the repository contains no version string.
The git tag and `CHANGELOG.md` are the only record of what version the code
is, and the script cannot report its own version.

### 24. There is no `.editorconfig` - DONE in 1.2.0

`.gitattributes` enforces LF at the git boundary and `.vscode/settings.json`
sets it for VS Code, but an editor that reads neither has nothing to go on.
GitHub-Metrics ships one, and `.vscode/extensions.json` here deliberately
omits the EditorConfig extension for want of the file.

### 25. No test fixtures are committed - DONE in 1.2.0

`input/.gitignore` and `output/.gitignore` exclude everything, so the sample
documents a run needs are not in the repository. Anyone cloning it must
produce their own GitHub-Metrics scan before the script can be run at all,
and there is no fixture for the `.tar.gz` reader. A small `tests/fixtures/`
directory would make item 16 possible.


---

## Resolved

What each item became, for anyone reading an old reference.

### 1.3.0 — no published number moved

| Item | Resolution |
|---|---|
| 4 | Both sides case-folded; duplicate codes refused |
| 6 | A null contribution counts as zero and warns |
| 9 | `rglob` for documents and archives; sorted for stable order |
| 14 | `scoring.adversarial_weight` and `scoring.pass_threshold` |

### 1.2.0

| Item | Resolution |
|---|---|
| 15 | `InputSource.describe()`; archive and member separated by `::` |
| 16 | `tests/`, 185 tests, 99.66% coverage, 95% floor enforced |
| 17 | black, isort, ruff, pylint, mypy `strict` and vulture all pass, and run in CI |
| 18 | `README.md` rewritten, including the GitHub-Metrics link |
| 19 | `CLAUDE.md`, with `AGENTS.md` pointing at it |
| 20 | `requirements-dev.txt` removed; dev group in `pyproject.toml` |
| 21 | `LICENSE`, Apache-2.0, matching GitHub-Metrics |
| 22 | `.github/workflows/{ci,codeql,sonarcloud}.yml` and `dependabot.yml` |
| 23 | `[project]` table with a version; `--version` reports it |
| 24 | `.editorconfig`, matching GitHub-Metrics |
| 25 | `tests/fixtures/documents/` and `tests/fixtures/expected/` |
