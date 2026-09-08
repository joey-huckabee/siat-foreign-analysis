import json
import csv
from pathlib import Path

def calculate_adv(cc_list, commits_list, adv_cc_list):
    print("\nEntering calculate_adv function")

    # Create an adversarial dictionary
    details = {}
    details["countries"] = {}
    for cc in adv_cc_list:
        details["countries"][cc] = {
            "commits": 0,
            "commitPercent": 0
        }
    # print(cc)

    # Count up the total number of adversarial commits
    adv_commits = 0
    total_commits = 0
    top_contributor_found = False
    for i in range(len(cc_list)):
        if cc_list[i] in adv_cc_list:
            adv_commits += commits_list[i]
            details["countries"][cc_list[i]]["commits"] += commits_list[i]
            if not top_contributor_found:
                details["topAdvContributorCountry"] = cc_list[i]
                details["topAdvContributorCountry"] = i+1
                top_contributor_found = True
        total_commits += commits_list[i]

    # Calculate the percent of commits
    print("Calculate the percent of commits")
    adv_percent = adv_commits * 100.0 / total_commits
    for cc in adv_cc_list:
        details["countries"][cc]["commitsPercent"] = details["countries"][cc]["commits"] * 100.0 / total_commits

    # Adversarial percentage
    details["advPercent"] = adv_percent

    # Adversarial weighting
    adv_weight = 25

    # Cases
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

if __name__ == "__main__":

    print("\n\n\n\n")
    print("****************************************************************************************************")
    print("Software Impact Analysis Tool - Foreign Analysis")
    print("****************************************************************************************************")
    print("\n\n\n\n")

    # Open JSON file for the adversarial countries
    f = Path("country_config.json").open(encoding='utf-8')
    config = json.loads(f.read())
    adversarial_cc = []

    print("--------------------------------------------------")
    print("Adversarial Nations List used for Processing:")
    print("--------------------------------------------------")

    for nation in config["adversarial_nations"]:
        adversarial_cc.append(nation["country_code"])
        print(nation["country_code"] + ": " + nation["name"])

    # Create a score report
    score_report = {}
    detailed_score_report = {}

    # Iterate through all files
    valid_paths = [p for p in Path("input").glob('*.json')]
    for path in valid_paths:
        print("\n\n")
        print("--------------------------------------------------")
        print("Processing input file: " + str(path))
        print("--------------------------------------------------")
        f = path.open(encoding='utf-8')
        data = json.loads(f.read())
        # If you don't close the file you will have to close python to break the connection
        f.close()

        # Get all the country codes
        country_codes = []
        commits = []

        contributor_country_none_count = 0
        contributor_country_total_count = 0
        contributor_country_data_quality_percentage = 0

        total_contributor_none_count = 0
        total_contributor_count = 0
        total_contributor_quality_percentage = 0

        for contributor in data["contributors"]:
            cc = contributor.get("internal_address", {}).get("country_code")
            if cc is None:
                contributor_country_none_count += 1
                print("Contributor Country: " + str(cc))
            if cc is not None:
                country_codes.append(cc)
                commits.append(contributor.get("contribution"))
                print("Contributor Country: " + str(cc) + "\t\t\tCommits: " + str(contributor.get("contribution")))
            contributor_country_total_count += 1
        contributor_country_data_quality_percentage = round((((contributor_country_total_count - contributor_country_none_count) / (contributor_country_total_count))*100) , 2)

        print("")
        print("contributor_country_total_count = " + str(contributor_country_total_count))
        print("contributor_country_none_count = " + str(contributor_country_none_count))
        print("Contributor Country Data Quality = " + str(contributor_country_data_quality_percentage) + "%")

        # Add up all the country data quality values
        total_contributor_none_count = total_contributor_none_count + contributor_country_none_count
        total_contributor_count = total_contributor_count + contributor_country_total_count

        # Calculate adversarial score
        adv_details = calculate_adv(country_codes, commits, adversarial_cc)

        # Initialize score report
        repo_report = {}
        det_repo_report = {}

        # Calculate total score
        unclass_score = data["trusted_org_bonus"] + data["stars_score"] + data["forks_score"] + data["last_update_score"] + data["prevalence_score"] + data["maturity_score"]
        total_score = unclass_score + adv_details["advScore"]
        repo_report["unclass_score"] = unclass_score
        repo_report["is_passing"] = total_score >= 70.0
        score_report[data["name"]] = repo_report

        # Attach score report
        det_repo_report["is_passing"] = repo_report["is_passing"]
        det_repo_report["score"] = total_score
        det_repo_report["details"] = adv_details
        detailed_score_report[data["name"]] = det_repo_report

        total_contributor_quality_percentage = round((((total_contributor_count - total_contributor_none_count) / (total_contributor_count))* 100) , 2)
        print("")
        print("total_contributor_count = " + str(total_contributor_count))
        print("total_contributor_none_count = " + str(total_contributor_none_count))
        print("Contributor Data Quality: " + str(contributor_country_data_quality_percentage) + "%")

    ##################################################
    # GENERATE score_report OUTPUT FILES
    ##################################################

    print("\nCreateing Score Report JSON File")

    # Open JSON file for the repo
    output_file = open("output/score_report.json", "w")
    output_file.write(json.dumps(score_report, indent=4))
    output_file.close()

    print("\nCreating Score Report CSV File")

    # Open CSV file for the repo
    csv_columns = ["package_name", "is_passing", "unclass_score"]
    output_file = open("output/score_report.csv", "w", newline='', encoding='utf-8')
    csv_write = csv.DictWriter(output_file, fieldnames=csv_columns)
    csv_write.writeheader()
    data_dict = {}
    for scr in score_report:
        data_dict['package_name'] = scr
        print("data_dict['package_name'] " + str(data_dict['package_name']))
        data_dict.update(score_report[scr])
        csv_write.writerow(data_dict)
    output_file.close()

    ##################################################
    # GENERATE detailed_score_report OUTPUT FILES
    ##################################################

    print("\nCreating Detailed Score Report JSON FIle")

    # Open JSON file for the repo
    output_file = open("output/detailed_score_report.json", "w")
    output_file.write(json.dumps(detailed_score_report, indent=4))
    output_file.close()

    print("\nCreating Detailed Score Report CSV File")

    # Open CSV file for the repo
    csv_columns = ["package_name" , "is_passing", "unclass_score", "adversarial_score", "total_score"]
    output_file = open("output/detailed_score_report.csv", "w", newline='', encoding='utf-8')
    csv_writer = csv.DictWriter(output_file, fieldnames=csv_columns)
    csv_writer.writeheader()
    data_dict = {}
    csv_data_dict = {}
    for scr in detailed_score_report:
        data_dict['package_name'] = scr
        csv_data_dict['package_name'] = scr
        print("data_dict['package_name'] " + str(data_dict['package_name']))
        data_dict.update(detailed_score_report[scr])

        # Build new Data Dictionary with the fields we need
        csv_data_dict["is_passing"] = data_dict["is_passing"]
        csv_data_dict["unclass_score"] = data_dict["score"] - data_dict["details"]["advScore"]
        csv_data_dict["adversarial_score"] = data_dict["details"]["advScore"]
        csv_data_dict["total_score"] = data_dict["score"]

        csv_writer.writerow(csv_data_dict)
    output_file.close()
