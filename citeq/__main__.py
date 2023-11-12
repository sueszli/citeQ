from thefuzz import fuzz, process
from typing import Tuple
import requests
import argparse
import json
import os
import hashlib

from logger import LOG_SINGLETON as LOG, trace


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CiteQ: a citation analysis tool")
    parser.add_argument("name", nargs="+", help="the researcher's name", type=str)
    parser.add_argument("-a", "--alias", nargs="+", help="the researcher's alternative names", type=str)
    parser.add_argument("-i", "--institution", nargs="+", help="the researcher's last known institution", type=str)
    return parser.parse_args()


def get_researcher_obj(args: argparse.Namespace) -> dict:
    # query author
    # see: https://docs.openalex.org/api-entities/authors/author-object
    # to understand cursor, see: https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/paging#cursor-paging

    results = []
    query = "https://api.openalex.org/authors?search=" + "%20".join(args.name).strip().lower() + "?&per-page=200&cursor="
    cursor = "*"
    while cursor is not None:
        response = requests.get(query + cursor).json()
        results.extend(response["results"])
        cursor = response["meta"]["next_cursor"]
    assert len(results) > 0, f"no results found for {args.name}"

    filtered_results = [result for result in results if result["works_count"] > 0 and result["cited_by_count"] > 0]
    assert len(filtered_results) > 0, f"no results with at least one work or citation"
    LOG.info(f"found {len(results)} matching researchers, {len(filtered_results)} of which have at least one work and citation")

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

    best_match = max(filtered_results, key=lambda result: result["total_score"])
    LOG.info(f"\tbest matching researcher: '{best_match['display_name']}' with {best_match['total_score']} points")
    return best_match


def get_paper_urls(researcher_obj: dict) -> list:
    LOG.info(f"fetching all papers of researcher")
    match_works = researcher_obj["works_api_url"]
    query = match_works + "?&per-page=200&cursor="

    total = requests.get(query).json()["meta"]["count"]
    results = []
    cursor = "*"
    while cursor is not None:
        response = requests.get(query + cursor).json()
        results.extend(response["results"])
        cursor = response["meta"]["next_cursor"]
        LOG.info(f"\tprogress: {len(results)}/{total}")
    assert len(results) > 0

    cited_papers = [paper for paper in results if paper["cited_by_count"] > 0]
    LOG.info(f"\tfound published {len(results)} papers, {len(cited_papers)} of which have at least one citation")
    assert len(cited_papers) > 0

    return cited_papers


def is_cached_get_path(researcher_obj: dict, filename: str) -> Tuple[bool, str]:
    CACHE_DIR_NAME = ".cache"

    name = researcher_obj["display_name"]
    hashlib_str = hashlib.sha256(name.encode()).hexdigest().lower()[0:24]

    # check if .cache exists – if not, create it
    cache_dir = os.path.join(os.getcwd(), CACHE_DIR_NAME)
    cache_dir_exists = os.path.isdir(cache_dir)
    if not cache_dir_exists:
        os.mkdir(cache_dir)

    # check if ./cache/<hash_str> exists – if not, create it
    researcher_cache_dir = os.path.join(cache_dir, hashlib_str)
    researcher_cache_dir_exists = os.path.isdir(researcher_cache_dir)
    if not researcher_cache_dir_exists:
        os.mkdir(researcher_cache_dir)
        LOG.info(f"created cache directory for researcher at './{CACHE_DIR_NAME}/{hashlib_str}'")

    # check if ./cache/<hash_str>/<filename> exists – get path to read/write at
    filepath = os.path.join(researcher_cache_dir, filename)
    is_cached = os.path.isfile(filepath)
    return is_cached, filepath


def get_citing_paper_pdf_urls(researcher_obj: dict, paper_urls: list) -> list:
    LOG.info(f"fetching all citing papers (papers that cite the researcher's papers)")

    filename = "cited-paper-urls.json"
    is_cached, filepath = is_cached_get_path(researcher_obj, filename)
    if is_cached:
        LOG.info(f"found cited paper urls in cache: '{filepath}'")
        return json.load(open(filepath, "r"))

    # get citing papers, for each paper
    # see: https://docs.openalex.org/api-entities/works/work-object#cited_by_api_url
    output = []

    queries = [paper["cited_by_api_url"] for paper in paper_urls]
    for i, query in enumerate(queries):
        sub_query = query + "?&per-page=200&cursor="
        num_citations = requests.get(sub_query).json()["meta"]["count"]
        LOG.info(f"\tprogress: {i}/{len(paper_urls)}")

        cursor = "*"
        while cursor is not None:
            response = requests.get(sub_query + cursor).json()
            cursor = response["meta"]["next_cursor"]
            links = [r["open_access"]["oa_url"] for r in response["results"] if r["open_access"]["oa_url"] is not None]
            output.append(links)

    # cache results
    json.dump(output, open(filepath, "w"))
    LOG.info(f"{len(output)} of {len(paper_urls)} papers have a url to download from (open access url) - cached at '{filepath}'")
    return output


if __name__ == "__main__":
    args: argparse.Namespace = get_args()
    LOG.info(f"user arguments: {args}")

    researcher_obj = get_researcher_obj(args)
    paper_urls = get_paper_urls(researcher_obj)
    citing_papers = get_citing_paper_pdf_urls(researcher_obj, paper_urls)

    # next steps:
    # - download from all links
    # - use pdfminer to extract all citations from the citing papers
    # - cluster the citations with ollama docker image
