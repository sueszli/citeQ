import argparse
import json
from logger import LOG_SINGLETON as LOG, trace
import requests


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CiteQ: a citation analysis tool")
    parser.add_argument("name", nargs="+", help="the researchers name", type=str)
    parser.add_argument("university", nargs="?", help="the researchers university", type=str)
    parser.add_argument("field", nargs="?", help="the researchers field of study", type=str)

    args = parser.parse_args()

    # query author
    # see: https://docs.openalex.org/api-entities/authors/author-object
    oa_query = "https://api.openalex.org/authors?search=" + "%20".join(args.name).strip().lower()
    oa_response = requests.get(oa_query).json()
    oa_response_pre = json.dumps(oa_response, indent=2)

    oa_meta = oa_response["meta"]
    total = oa_meta["count"]
    assert total > 0, f"no results found for {args.name}"
    LOG.info(f"found {total} results in openalex")

    oa_results = oa_response["results"]
    for result in oa_results:
        ids = result["ids"]
        id = result["id"]
        orcid = result["orcid"]
        display_name = result["display_name"]
        LOG.info(f"found {display_name}:")

        # must have papers and citations
        works_count = result["works_count"]
        cited_by_count = result["cited_by_count"]
        if works_count == 0 or cited_by_count == 0:
            LOG.info(f"\tskipping due to 0 works or citations")
            continue

        # hint
        display_name_alternatives = result["display_name_alternatives"]

        # hint
        last_known_institution = result["last_known_institution"]  # very valuable

        # add to stack if matches
        works_api_url = result["works_api_url"]  # list of all papers
        LOG.info(f"\t see:{works_api_url}")
