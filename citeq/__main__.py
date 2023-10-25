import argparse
import json
from logger import LOG_SINGLETON as LOG, trace
import requests


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CiteQ: a citation analysis tool")
    parser.add_argument("name", nargs="+", help="the researcher's name", type=str)
    parser.add_argument("-a", "--alias", nargs="+", help="the researcher's alternative names", type=str)
    parser.add_argument("-i", "--institution", nargs="+", help="the researcher's last known institution", type=str)
    return parser.parse_args()


if __name__ == "__main__":
    args: argparse.Namespace = get_args()

    # query author
    # see: https://docs.openalex.org/api-entities/authors/author-object
    oa_query = "https://api.openalex.org/authors?search=" + "%20".join(args.name).strip().lower()
    oa_response: dict = requests.get(oa_query).json()
    oa_response_prettified = json.dumps(oa_response, indent=2)

    oa_meta = oa_response["meta"]
    total = oa_meta["count"]
    assert total > 0, f"no results found for {args.name}"
    LOG.info(f"found {total} results in total")

    oa_results = oa_response["results"]
    oa_filtered_results = [result for result in oa_results if result["works_count"] > 0 and result["cited_by_count"] > 0]
    LOG.info(f"{total} of which have at least one work or citation")

    for result in oa_filtered_results:
        ids = result["ids"]
        display_name = result["display_name"]
        LOG.info(f"found {display_name}:")

        # hint
        institution = result["last_known_institution"]["display_name"]
        LOG.info(f"\tinstitution: {institution}")

        # hint
        aliases = result["display_name_alternatives"]
        LOG.info(f"\taliases:{aliases}")

        # add list of papers to stack if matches
        works = result["works_api_url"]
