from thefuzz import fuzz, process
import requests
import argparse
import json

from logger import LOG_SINGLETON as LOG, trace


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CiteQ: a citation analysis tool")
    parser.add_argument("name", nargs="+", help="the researcher's name", type=str)
    parser.add_argument("-a", "--alias", nargs="+", help="the researcher's alternative names", type=str)
    parser.add_argument("-i", "--institution", nargs="+", help="the researcher's last known institution", type=str)
    return parser.parse_args()


if __name__ == "__main__":
    args: argparse.Namespace = get_args()
    LOG.info(f"searching for '{' '.join(args.name)}'")

    # query author
    # see: https://docs.openalex.org/api-entities/authors/author-object
    oa_query = "https://api.openalex.org/authors?search=" + "%20".join(args.name).strip().lower()
    oa_response: dict = requests.get(oa_query).json()
    oa_response_prettified = json.dumps(oa_response, indent=2)

    oa_meta = oa_response["meta"]
    total_count = oa_meta["count"]
    assert total_count > 0, f"no results found for {args.name}"

    oa_results = oa_response["results"]
    oa_filtered_results = [result for result in oa_results if result["works_count"] > 0 and result["cited_by_count"] > 0]
    filtered_count = len(oa_filtered_results)
    assert filtered_count > 0, f"no results with at least one work or citation"
    LOG.info(f"found {total_count} results, {filtered_count} of which have at least one work and citation")

    for result in oa_filtered_results:
        display_name = result["display_name"]
        institution = result["last_known_institution"]["display_name"]
        altnames = result["display_name_alternatives"]
        ids = result["ids"]
        works = result["works_api_url"]

        LOG.info(f"found '{display_name}' {('from ' + institution) if institution is not None else ''}")

        # name match
        name_disp_score = fuzz.partial_token_sort_ratio(args.name, display_name)
        alias_disp_score = fuzz.partial_token_sort_ratio(args.alias, display_name)
        LOG.info(f"\tname vs. display name: {name_disp_score}")
        LOG.info(f"\talias vs. display name: {alias_disp_score}")

        # hint: institution
        if args.instition is not None:
            inst_score = fuzz.partial_token_sort_ratio(args.institution, institution) if args.institution is not None else 0
            LOG.info(f"\tinstitution: {inst_score}")

        # hint: alternative names
        if args.alias is not None:
            avg_name_altnames_score = sum([fuzz.partial_token_sort_ratio(args.name, altname) for altname in altnames]) / len(altnames)
            avg_alias_altnames_score = sum([fuzz.partial_token_sort_ratio(args.alias, altname) for altname in altnames]) / len(altnames)
            LOG.info(f"\tname vs. alternative names: {avg_name_altnames_score}")
            LOG.info(f"\talias vs. alternative names: {avg_alias_altnames_score}")
