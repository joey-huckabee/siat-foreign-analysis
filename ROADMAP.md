# siat-foreign-analysis — Roadmap

Known issues in `foreign_analysis.py`, recorded during the first integration
against real GitHub-Metrics output (tool version 0.6.2, scan
`595344b7-0919-4da5-88e2-0376bab8db6b`, repos `pyca/bcrypt` and
`pallets/itsdangerous`).

Nothing here is fixed. The release deliberately ships the script close to as
written; these are deferred until the historical baseline is established. Line
numbers are against the post-integration file.

## Already fixed (for reference)

These were corrected to make the script run at all:

- The seven hand-transcribed `data[...]` keys now match the document schema
  (`contributors`, `trusted_org_bonus`, `stars_score`, `forks_score`,
  `last_update_score`, `prevalence_score`, `maturity_score`).
- `json.load(f.read())` → `json.loads(f.read())`.
- `csv.DisctWriter` → `csv.DictWriter`.
- `calculate_adv` returned from inside its `for cc in adv_cc_list` loop, so
  only the first adversarial country was ever initialised in
  `details["countries"]` and the percent loop raised `KeyError`. The body was
  dedented out of that loop.
- `country_config.json` codes lowercased to match the document schema.

---

## High — produces wrong numbers without failing

### 1. Country-code case is matched by convention, not enforced

GitHub-Metrics emits `country_code` as **lower-case** ISO 3166-1 alpha-2. The
config was uppercase (`RU`), so no contributor ever matched.

Verified: patching bcrypt's top human contributor (171 of 342 resolved
commits) to `ru` gave `advPercent = 0.0, advScore = 25` — a repo half
Russian-authored reported clean and passing.

Fixed for now by lowercasing the config, but nothing enforces it. A future
edit that types `RU` reintroduces a **silent false negative**. Normalise at
the comparison instead: casefold both the config codes and the document value
when they are read.

### 2. Bot commits are counted as human contribution

`is_bot` is published per contributor and never read. In `pyca/bcrypt`,
`dependabot[bot]` accounts for **679 of 1043 commits** — 65% of
`contribution_total`. Any percentage over that total is dominated by
automation.

Bots currently fall out of the adversarial calculation only by accident: they
publish no location, so they land in the unresolved bucket. A bot that did
carry a location would be scored as a person.

### 3. The adversarial denominator is resolved-location commits, not total

`adv_percent` (line 33) divides by the sum over contributors whose location
resolved, not by `contribution_total`.

For bcrypt that is 342, against a `contribution_total` of 1043. The same
adversarial commit count therefore scores against roughly a third of the
repository. Decide explicitly which denominator the metric means, and record
it.

### 4. Data-quality percentage is computed and then discarded

`contributor_country_data_quality_percentage` is printed but reaches neither
report. Coverage was **51.28%** for bcrypt and **64.29%** for itsdangerous —
so roughly half of bcrypt's contributors are invisible to the analysis, and
nothing in the output says so. A consumer cannot tell a genuinely clean repo
from an unmeasured one.

Carry it into both reports as a column.

### 5. `total_contributor_*` accumulators reset every file

Lines 110–111 zero the running totals inside the per-file loop, so the
"total" figures only ever describe the last file processed. Move them above
the loop.

---

## Medium — crashes or silent gaps on inputs not yet seen

### 6. `ZeroDivisionError` when no location resolves

Line 33 divides by `total_commits` with no guard. A repository whose
contributors all lack a resolved location aborts the entire run — including
the repositories already processed, since the reports are written at the end.

### 7. Empty string treated as a valid country code

`country_code` has three states: `null` (no lookup ran), `""` (lookup ran, no
country component at that resolution), and a real code. Line 116 tests only
`is None`, so `""` is appended as if it were a country. `itsdangerous` has 9
commits in that bucket.

### 8. Nested input layout is not read

GitHub-Metrics writes documents as `<output>/<owner>/<repoid>.json`. Line 91
globs `input/*.json` non-recursively, so a directory copied across verbatim
yields zero inputs and an empty report rather than an error. Use `rglob`, or
document that inputs must be flattened.

### 9. Repositories that failed collection are invisible

A repository GitHub-Metrics could not read produces a CSV row but **no
document**. Such a repository is therefore absent from the score report
entirely, rather than appearing as a failure. Reconcile against
`githubmetrics.csv` or `statistics.json` so the report names what it could not
score.

### 10. `contribution` may be `null`

The model types it `int | None`. Line 121 appends it unguarded and
`adv_commits += None` would raise.

---

## Low — correctness of detail, not of score

### 11. `topAdvContributorCountry` is overwritten with an index

Lines 26–27 assign the country code and then immediately replace it with
`i+1`. The key never holds a country. Whether the intended value is the
country, the rank, or both under two keys needs deciding.

### 12. `commitPercent` vs `commitsPercent`

Line 13 initialises `commitPercent`; the percent loop writes `commitsPercent`.
Both ship in the output, one always zero.

### 13. `unclass_score` is recomputed rather than read

Line 143 re-adds the six components, which the document already publishes as
`total_score` (verified equal: 67.0 and 63.0). Reading it directly removes a
place for the two to drift — and GitHub-Metrics caps `total_score` at 85,
which the recomputation does not reproduce.

### 14. Reports are keyed by repository name alone

Lines 147 and 153 key on `data["name"]`, not owner-qualified. Two repositories
with the same name from different owners silently overwrite each other. The
document carries `owner` and `url`; either disambiguates.

### 15. Pass threshold and adversarial weight are magic numbers

`70.0` (line 146) and `adv_weight = 25` are literals. Both are policy and
belong in `country_config.json` alongside the nation list.

### 16. Files are opened without context managers

Throughout. A failure between `open` and `close` leaks the handle and, for the
output files, leaves a truncated report on disk. Line 168 also omits
`encoding` on a text write.
