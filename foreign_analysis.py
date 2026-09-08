"""
Software Impact Analysis Tool - Foreign Analysis

Reads per-repository contributor data from input/ (either bare *.json files
or *.json members inside *.tar.gz archives) and produces two pairs of
reports in output/:

  - score_report.{json,csv}          - releasable pass/fail summary
  - detailed_score_report.{json,csv} - classified report including
                                       adversarial country breakdown

The releasable report is intended to be transferable to the unclassified
side; the detailed report is not.
"""

import csv
import json
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple, Union

# Visual banner used to bracket the program-name announcement at startup
BANNER_SEPARATOR = "*" * 100


def read_json(
    json_path: Union[str, Path, PurePosixPath],
    *,
    tar_gz_path: Optional[Union[str, Path]] = None,
    encoding: str = "UTF-8",
    strict_utf8: bool = False,
    max_json_bytes: int = 25 * 1024 * 1024,  # 25 MB safety limit
) -> Any:
    """Load a JSON document from disk or from inside a .tar.gz archive.

    Provides bounded reads, existence checks, and configurable UTF-8
    strictness. When tar_gz_path is None, json_path is treated as a path
    on the local filesystem; otherwise json_path is the member name
    inside the archive at tar_gz_path.
    """

    errors_mode = "strict" if strict_utf8 else "replace"

    # JSON file is not inside a .tar.gz archive.
    if tar_gz_path is None:
        p = Path(json_path)
        if not p.is_file():
            raise FileNotFoundError(f"JSON file not found: {p}")

        size = p.stat().st_size
        if size > max_json_bytes:
            raise ValueError(f"JSON file too large ({size} bytes): {p}")

        raw = p.read_bytes()
        text = raw.decode(encoding, errors=errors_mode)
        return json.loads(text)

    # JSON is inside a .tar.gz archive
    tar_path = Path(tar_gz_path)
    member_name = str(json_path)

    with tarfile.open(tar_path, mode="r:gz") as tf:
        try:
            member = tf.getmember(member_name)
        except KeyError as e:
            raise FileNotFoundError(f"JSON member not found in archive: {member_name}") from e

        # Reject directories, symlinks, hardlinks, etc. - only regular files
        if not member.isfile():
            raise IsADirectoryError(f"Member is not a regular file: {member_name}")

        # Reject oversized member before extraction
        if member.size > max_json_bytes:
            raise ValueError(f"JSON member too large ({member.size} bytes): {member_name}")

        f = tf.extractfile(member)
        if f is None:
            raise OSError(f"Unable to extract member: {member_name}")

        # Read one byte beyond the limit to detect mismatches between
        # the declared member size and the actual stream length
        raw = f.read(max_json_bytes + 1)
        if len(raw) > max_json_bytes:
            raise ValueError(f"JSON member exceeded max_json_bytes while reading: {member_name}")

    text = raw.decode(encoding, errors_mode)

    return json.loads(text)


def get_json_member_paths_in_tar_gz(
    tar_gz_path: Union[str, Path],
    *,
    case_insensitive: bool = True,
    only_regular_files: bool = True,
) -> List[Tuple[Path, PurePosixPath]]:
    """Enumerate JSON members inside a .tar.gz archive.

    Returns a list of (archive_path, member_path) tuples. PurePosixPath
    is used for the member path because tar member names always use "/"
    separators regardless of host OS.
    """

    tar_gz_path = Path(tar_gz_path)
    results: List[Tuple[Path, PurePosixPath]] = []

    with tarfile.open(tar_gz_path, mode="r:gz") as tf:
        for m in tf.getmembers():
            if only_regular_files and not m.isfile():
                continue

            name = m.name
            check = name.lower() if case_insensitive else name
            if check.endswith(".json"):
                results.append((tar_gz_path, PurePosixPath(name)))

    return results


def calculate_adv(
    cc_list: List[str],
    country_commits: List[int],
    total_commits: int,
    adv_cc_list: List[str],
) -> Dict[str, Any]:
    """Compute the adversarial-percentage bonus for a single repository.

    Returns a dict containing per-country commit counts and percentages,
    the overall adversarial percentage, the top adversarial contributor
    country, and the tiered advScore (0-25 points). Lower adversarial
    percentage yields a higher bonus; >= 25% yields zero.
    """
    print("\nEntering calculate_adv function")

    # Pre-populate the per-country dict with zeros so the report shape is
    # stable even when a repository has no commits from a given adversarial
    # country.
    details = {}
    details["countries"] = {}
    for cc in adv_cc_list:
        details["countries"][cc] = {"commits": 0, "commitPercent": 0}

    # Aggregate adversarial commits per country, cc_list and country_commits
    # are parallel lists built together by the the main loop, so zip walks them
    # in lockstep without needing an index.
    adv_commits = 0
    for cc, commits in zip(cc_list, country_commits):
        if cc in adv_cc_list:
            adv_commits += commits
            details["countries"][cc]["commits"] += commits

    # Identify the adversarial country with the most commits, None when
    # no adversarial commits are present in this repository, max() with
    # a key function tie-breaks by first occurrence in the dict which
    # is insertion order (matches adv_cc_list order from country_config).
    adv_country_commits: Dict[str, int] = {
        cc: info["commits"] for cc, info in details["countries"].items() if info["commits"] > 0
    }
    if adv_country_commits:
        details["topAdvContributorCountry"] = max(
            adv_country_commits, key=lambda cc: adv_country_commits[cc]
        )
    else:
        details["topAdvContributorCountry"] = None

    # Calculate the percent of commits
    print("Calculate the percent of commits")

    # Returning early to prevent divide-by-zero errors. Sometimes a package
    # has zero contributors due to an upstream pull error.
    if total_commits == 0:
        print("Unable to process contributors - zero contributors")
        details["advScore"] = 0
        return details

    adv_percent = adv_commits * 100.0 / total_commits
    for cc in adv_cc_list:
        details["countries"][cc]["commitsPercent"] = (
            details["countries"][cc]["commits"] * 100.0 / total_commits
        )

    # Adversarial percentage
    details["advPercent"] = adv_percent

    # Adversarial weighting: max points awarded for a clean repo.
    adv_weight = 25

    # Tiered scoring, Lower adversarial percentage -> higher bonus,
    # Once adversarial commits reach 25% of the total, the bonus zeros out.
    if adv_percent < 0.5:
        details["advScore"] = 1 * adv_weight
    elif adv_percent < 1.0:
        details["advScore"] = 0.9 * adv_weight
    elif adv_percent < 2.0:
        details["advScore"] = 0.8 * adv_weight
    elif adv_percent < 5.0:
        details["advScore"] = 0.7 * adv_weight
    elif adv_percent < 10.0:
        details["advScore"] = 0.5 * adv_weight
    elif adv_percent < 15.0:
        details["advScore"] = 0.4 * adv_weight
    elif adv_percent < 20.0:
        details["advScore"] = 0.3 * adv_weight
    elif adv_percent < 25.0:
        details["advScore"] = 0.2 * adv_weight
    else:
        details["advScore"] = 0.0 * adv_weight

    return details


def main() -> None:
    """Run the foreign-analysis pipeline end to end."""

    print("\n\n\n\n")
    print(BANNER_SEPARATOR)
    print("Software Impact Analysis Tool - Foreign Analysis")
    print(BANNER_SEPARATOR)
    print("\n\n\n\n")

    # Load the adversarial-country list from the configuration file.
    with Path("country_config.json").open(encoding="UTF-8") as f:
        config = json.loads(f.read())
        adversarial_cc: List[str] = []

    # Optional scoring configuration, Missing keys fall back to the
    # conservative default (1.0.0 semantics): unattributed contributors
    # do not count in the adversarial-percentage denominator.
    scoring_config = config.get("scoring", {})
    include_unattributed: bool = scoring_config.get("include_unattributed_in_denominator", False)

    print("--------------------------------------------------")
    print("Scoring Configuration:")
    print("--------------------------------------------------")
    print(f"include_unattributed_in_denominator: {include_unattributed}")

    print("--------------------------------------------------")
    print("Adversarial Nations List used for Processing:")
    print("--------------------------------------------------")

    for nation in config["adversarial_nations"]:
        adversarial_cc.append(nation["country_code"])
        print(nation["country_code"] + ": " + nation["name"])

    # Top-level report accumulators, score_report is the releasable summary;
    # detailed_score_report includes adversarial country breakdown and is
    # classified.
    score_report: Dict[str, Dict[str, Any]] = {}
    detailed_score_report: dict[str, Dict[str, Any]] = {}

    # Per-input-file path list, First element of each tuple is the parent
    # archive (None when the file lives directly in input/); second is the
    # JSON path within the archive (or the on-disk path when no archive).
    valid_paths: List[Tuple[Optional[Path], PurePosixPath]] = []

    # Discover JSON members inside any .tar.gz archives in input/.
    tar_gz_file_paths = list(Path("input").glob("*.tar.gz"))
    for archive_path in tar_gz_file_paths:
        valid_paths.extend(get_json_member_paths_in_tar_gz(tar_gz_path=archive_path))

    # Discover bare JSON files in input/.
    direct_json_paths = list(Path("input").glob("*.json"))
    for direct_path in direct_json_paths:
        valid_paths.append((None, PurePosixPath(direct_path.as_posix())))

    # Cumulative contributor counts across all input files. Initialized
    # once here so the post-loop summary genuinely reflects the full run.
    total_contributor_none_count = 0
    total_contributor_count = 0

    for tar_gz_path, json_path in valid_paths:
        print("\n\n")
        print("--------------------------------------------------")
        print(f"Processing input file: {tar_gz_path or ''}/{json_path}")
        print("--------------------------------------------------")

        data = read_json(json_path=json_path, tar_gz_path=tar_gz_path)

        # per-file collectors for the current repository
        country_codes: List[str] = []
        country_commits: List[int] = []
        total_commits = 0

        contributor_country_none_count = 0
        contributor_country_total_count = 0
        contributor_country_data_quality_percentage: float = 0.0

        # Walk the contributor list, Pull country code and commit count;
        # track contributors with no attributed country as a data-quality
        # signal. Whether unattributed commits count toward total_commits
        # is controlled by include_unattributed_in_denominator (default
        # False; unattributed commits do not deflate adversarial percent).
        for contributor in data["contributors"]:
            cc = contributor.get("internal_address", {}).get("country_code")
            contribution = contributor.get("contribution")
            if cc is None:
                contributor_country_none_count += 1
                if include_unattributed:
                    total_commits += contribution
                print("Contributor Country: " + str(cc))
            else:
                country_codes.append(cc)
                country_commits.append(contribution)
                total_commits += contribution
                print("Contributor Country: " + str(cc) + "\t\t\tCommits: " + str(contribution))
            contributor_country_total_count += 1

        # Data-quality percentage: fraction of contributors with an
        # attributed country code. Guard against the empty-contributor
        # case to mirror calculate_adv()'s zero-guard convention.
        if contributor_country_total_count == 0:
            contributor_country_data_quality_percentage = 0.0
        else:
            contributor_country_data_quality_percentage = round(
                (
                    (
                        (contributor_country_total_count - contributor_country_none_count)
                        / (contributor_country_total_count)
                    )
                    * 100
                ),
                2,
            )

        print("")
        print("contributor_country_total_count = " + str(contributor_country_total_count))
        print("contributor_country_none_count = " + str(contributor_country_none_count))
        print(
            "Contributor Country Data Quality = "
            + str(contributor_country_data_quality_percentage)
            + "%"
        )

        # Add up all the country data quality values
        total_contributor_none_count = total_contributor_none_count + contributor_country_none_count
        total_contributor_count = total_contributor_count + contributor_country_total_count

        # Calculate adversarial score
        adv_details = calculate_adv(country_codes, country_commits, total_commits, adversarial_cc)

        # Initialize score report
        repo_report: Dict[str, Any] = {}
        det_repo_report: Dict[str, Any] = {}

        # The unclassified component of the score is the sum of six
        # upstream-computed scores. The total adds the adversarial bonus
        # on top. Pass/fail is computed from the total, but only the
        # unclassified component is published in the releasable report.
        unclass_score = (
            data["trusted_org_bonus"]
            + data["stars_score"]
            + data["forks_score"]
            + data["last_update_score"]
            + data["prevalence_score"]
            + data["maturity_score"]
        )
        total_score = unclass_score + adv_details["advScore"]
        repo_report["unclass_score"] = unclass_score
        repo_report["is_passing"] = total_score >= 70.0
        score_report[data["name"]] = repo_report

        # Attach score report
        det_repo_report["is_passing"] = repo_report["is_passing"]
        det_repo_report["score"] = total_score
        det_repo_report["details"] = adv_details
        detailed_score_report[data["name"]] = det_repo_report

    ##################################################
    # GENERATE score_report OUTPUT FILES
    ##################################################

    # Cumulative data quality summary across all input files. Guard the
    # zero case for the same reason as the per-file calculation: an empty
    # input/ folder, or all-empty contributor lists, would otherwise raise.
    if total_contributor_count == 0:
        total_contributor_quality_percentage = 0.0
    else:
        total_contributor_quality_percentage = round(
            ((total_contributor_count - total_contributor_none_count) / total_contributor_count)
            * 100,
            2,
        )
    print("")
    print("--------------------------------------------------")
    print("Cumulative Contributor Data Quality")
    print("--------------------------------------------------")
    print("total_contributor_count = " + str(total_contributor_count))
    print("total_contributor_none_count = " + str(total_contributor_none_count))
    print("total_contributor_quality_percentage = " + str(total_contributor_quality_percentage))

    # Ensure the output directory exists. Idempotent on re-runs;
    # parents=True allows nested output paths if parameterized later.
    Path("output").mkdir(parents=True, exist_ok=True)

    print("\nCreating Score Report JSON File")

    # Releasable JSON report
    with open("output/score_report.json", "w", encoding="UTF-8") as output_file:
        output_file.write(json.dumps(score_report, indent=4))

    print("\nCreating Score Report CSV File")

    # Releasable CSV report
    csv_columns = ["package_name", "is_passing", "unclass_score"]
    with open("output/score_report.csv", "w", newline="", encoding="UTF-8") as output_file:
        csv_write = csv.DictWriter(output_file, fieldnames=csv_columns)
        csv_write.writeheader()
        for package_name, package_report in score_report.items():
            # Fresh dict per row to prevent state leakage between iterations.
            row = {"package_name": package_name, **package_report}
            print(f"Writing CSV row for: {package_name}")
            csv_write.writerow(row)

    ##################################################
    # GENERATE detailed_score_report OUTPUT FILES
    ##################################################

    print("\nCreating Detailed Score Report JSON FIle")

    # Classified JSON report - includes adversarial country breakdown
    with open("output/detailed_score_report.json", "w", encoding="UTF-8") as output_file:
        output_file.write(json.dumps(detailed_score_report, indent=4))

    print("\nCreating Detailed Score Report CSV File")

    # Classified CSV report
    csv_columns = [
        "package_name",
        "is_passing",
        "unclass_score",
        "adversarial_score",
        "total_score",
    ]
    with open("output/detailed_score_report.csv", "w", newline="", encoding="utf-8") as output_file:
        csv_writer = csv.DictWriter(output_file, fieldnames=csv_columns)
        csv_writer.writeheader()
        for package_name, entry in detailed_score_report.items():
            # Fresh dict per row to prevent state leakage between iterations.
            adv_score = entry["details"]["advScore"]
            row = {
                "package_name": package_name,
                "is_passing": entry["is_passing"],
                "unclass_score": entry["score"] - adv_score,
                "adversarial_score": adv_score,
                "total_score": entry["score"],
            }
            print(f"Writing CSV row for: {package_name}")
            csv_writer.writerow(row)


if __name__ == "__main__":
    main()
