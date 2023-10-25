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


def get_works(args: argparse.Namespace) -> str:
    # query author
    # see: https://docs.openalex.org/api-entities/authors/author-object

    results = []
    query = "https://api.openalex.org/authors?search=" + "%20".join(args.name).strip().lower() + "&cursor="
    cursor = "*"
    while cursor is not None:
        response = requests.get(query + cursor).json()
        results.extend(response["results"])
        cursor = response["meta"]["next_cursor"]
    assert len(results) > 0, f"no results found for {args.name}"

    filtered_results = [result for result in results if result["works_count"] > 0 and result["cited_by_count"] > 0]
    assert len(filtered_results) > 0, f"no results with at least one work or citation"
    LOG.info(f"found {len(results)} results, {len(filtered_results)} of which have at least one work and citation")

    for result in filtered_results:
        display_name = result["display_name"]
        institution = result["last_known_institution"]["display_name"]
        altnames = result["display_name_alternatives"]

        # name match
        name_disp_score = fuzz.partial_token_sort_ratio(args.name, display_name)
        alias_disp_score = 0 if args.alias is None else fuzz.partial_token_sort_ratio(args.alias, display_name)

        # hint: institution
        inst_score = 0 if args.institution is None else fuzz.partial_token_sort_ratio(args.institution, institution)

        # hint: alternative names
        avg_name_altnames_score = 0 if args.alias is None else sum([fuzz.partial_token_sort_ratio(args.name, altname) for altname in altnames]) / len(altnames)
        avg_alias_altnames_score = 0 if args.alias is None else sum([fuzz.partial_token_sort_ratio(args.alias, altname) for altname in altnames]) / len(altnames)

        total_score = name_disp_score + alias_disp_score + inst_score + avg_name_altnames_score + avg_alias_altnames_score
        result["total_score"] = total_score
        LOG.info(f"\t[{str(total_score).zfill(3)} points]: '{display_name}' {('from ' + institution) if institution is not None else ''}")

    # get best match
    best_match = max(filtered_results, key=lambda result: result["total_score"])
    LOG.info(f"best match: '{best_match['display_name']}' with {best_match['total_score']} points")

    match_ids = best_match["ids"]
    match_works = best_match["works_api_url"]
    return match_works


if __name__ == "__main__":
    args: argparse.Namespace = get_args()
    LOG.info(f"user arguments: {args}")

    match_works = get_works(args)
    LOG.info(f"best match's works: {match_works}")

    response = requests.get(match_works).json()
    meta = response["meta"]
    LOG.info(f"found {meta['count']} works")

    results = response["results"]
    for work in results:
        ids = work["ids"]
        LOG.info(f"\t{work['title']}")
