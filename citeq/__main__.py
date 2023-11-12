from thefuzz import fuzz, process
from typing import Tuple
import requests
import argparse
import json
import os
import hashlib
import asyncio
from PyPDF2 import PdfReader


from logger import LOG_SINGLETON as LOG, trace


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CiteQ: a citation analysis tool")
    parser.add_argument("name", nargs="+", help="the researcher's name", type=str)
    parser.add_argument("-a", "--alias", nargs="+", help="the researcher's alternative names", type=str)
    parser.add_argument("-i", "--institution", nargs="+", help="the researcher's last known institution", type=str)
    return parser.parse_args()


def is_cached_get_path(cache_key: str, filename: str) -> Tuple[bool, str]:
    CACHE_DIR_NAME = ".cache"

    # check if .cache exists – if not, create it
    cache_dir = os.path.join(os.getcwd(), CACHE_DIR_NAME)
    cache_dir_exists = os.path.isdir(cache_dir)
    if not cache_dir_exists:
        os.mkdir(cache_dir)

    # check if ./cache/<cache_key> exists – if not, create it
    researcher_cache_dir = os.path.join(cache_dir, cache_key)
    researcher_cache_dir_exists = os.path.isdir(researcher_cache_dir)
    if not researcher_cache_dir_exists:
        os.mkdir(researcher_cache_dir)
        LOG.info(f"created cache directory for researcher at './{CACHE_DIR_NAME}/{cache_key}'")

    # check if ./cache/<cache_key>/<filename> exists – get path to read/write at
    filepath = os.path.join(researcher_cache_dir, filename)
    file_cache_exists = os.path.isfile(filepath)
    dir_cache_exists = os.path.isdir(filepath)
    is_cached = file_cache_exists or dir_cache_exists
    return is_cached, filepath


class OpenAlexClient:
    @staticmethod
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

    @staticmethod
    def get_paper_urls(cache_key: str, researcher_obj: dict) -> list:
        LOG.info(f"fetching all papers of researcher")

        filename = "paper-urls.json"
        is_cached, filepath = is_cached_get_path(cache_key, filename)
        if is_cached:
            LOG.info(f"found paper urls in cache: '{filepath}'")
            return json.load(open(filepath, "r"))

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

        # cache results
        json.dump(cited_papers, open(filepath, "w"))
        LOG.info(f"{len(cited_papers)} paper urls cached at '{filepath}'")
        return cited_papers

    @staticmethod
    def get_citing_paper_pdf_urls(cache_key: str, paper_urls: list) -> list:
        LOG.info(f"fetching urls for papers that cite the researcher's papers (citing papers):")

        filename = "cited-paper-urls.json"
        is_cached, filepath = is_cached_get_path(cache_key, filename)
        if is_cached:
            LOG.info(f"found cited paper urls in cache: '{filepath}'")
            return json.load(open(filepath, "r"))

        # get citing papers, for each paper
        # see: https://docs.openalex.org/api-entities/works/work-object#cited_by_api_url
        output = []

        queries = [paper["cited_by_api_url"] for paper in paper_urls]
        for i, query in enumerate(queries):
            sub_query = query + "?&per-page=200&cursor="
            LOG.info(f"\tprogress: {i}/{len(paper_urls)}")

            cursor = "*"
            while cursor is not None:
                response = requests.get(sub_query + cursor).json()
                cursor = response["meta"]["next_cursor"]
                links = [r["open_access"]["oa_url"] for r in response["results"] if r["open_access"]["oa_url"] is not None]
                for link in links:
                    output.append(link)

        # cache results
        json.dump(output, open(filepath, "w"))
        LOG.info(f"{len(output)} pdf urls to citing papers cached at '{filepath}'")
        return output


class PdfCrawler:
    CACHE_DIR_NAME = "pdfs"
    COUNTER = 0
    TOTAL = 0

    @staticmethod
    def background(f):
        def wrapped(*args, **kwargs):
            return asyncio.get_event_loop().run_in_executor(None, f, *args, **kwargs)

        return wrapped

    @staticmethod
    @background
    def download(url: str, filepath: str):
        try:
            response = requests.get(url, timeout=10)  # timeout in seconds
            with open(filepath, "wb") as f:
                f.write(response.content)
            PdfCrawler.COUNTER += 1
            LOG.info(f"\tprogress: {PdfCrawler.COUNTER}/{PdfCrawler.TOTAL} - downloaded")
        except requests.exceptions.Timeout:
            LOG.critical(f"\tprogress: {PdfCrawler.COUNTER}/{PdfCrawler.TOTAL} - timed out")

    @staticmethod
    def download_pdfs(cache_key, citing_paper_urls: list):
        dir_exists, dir_path = is_cached_get_path(cache_key, PdfCrawler.CACHE_DIR_NAME)
        if not dir_exists:
            os.mkdir(dir_path)
            LOG.info(f"created directory for pdfs in cache")

        LOG.info(f"concurrently downloading {len(citing_paper_urls)} pdfs")
        PdfCrawler.TOTAL = len(citing_paper_urls)

        for url in citing_paper_urls:
            filename_len = 10
            filename = hashlib.sha256(url.encode()).hexdigest().lower()[0:filename_len] + ".pdf"
            filepath = os.path.join(dir_path, filename)

            is_cached = os.path.isfile(filepath)
            if is_cached:
                PdfCrawler.COUNTER += 1
                LOG.info(f"\tprogress: {PdfCrawler.COUNTER}/{PdfCrawler.TOTAL} - found in cache")
                continue

            PdfCrawler.download(url, filepath)


class PdfParser:
    CACHE_DIR_NAME = "txts"

    @staticmethod
    def convert_pdf_to_txt(cache_key):
        pdf_dir_exists, pdf_dir_path = is_cached_get_path(cache_key, PdfCrawler.CACHE_DIR_NAME)
        assert pdf_dir_exists, f"no pdfs found in cache"

        txt_dir_exists, txt_dir_path = is_cached_get_path(cache_key, PdfParser.CACHE_DIR_NAME)
        if not txt_dir_exists:
            os.mkdir(txt_dir_path)
            LOG.info(f"created directory for txts in cache")

        pdf_paths = [os.path.join(pdf_dir_path, filename) for filename in os.listdir(pdf_dir_path)]
        for i, pdf in enumerate(pdf_paths):
            LOG.info(f"\tprogress: {i}/{len(pdf_paths)}")

            txt_name = os.path.basename(pdf).replace(".pdf", ".txt")
            txt_path = os.path.join(txt_dir_path, txt_name)

            is_cached = os.path.isfile(txt_path)
            if is_cached:
                LOG.info(f"\tprogress: {i}/{len(pdf_paths)} - found in cache")
                continue

            try:
                reader = PdfReader(pdf)
                for i in range(len(reader.pages)):
                    text = reader.pages[i].extract_text()
                    if text is None:
                        continue
                    with open(txt_path, "a") as f:
                        f.write(text)
            except Exception as e:
                LOG.critical(f"\tprogress: {i}/{len(pdf_paths)} - error: {e}")


if __name__ == "__main__":
    args = get_args()

    researcher_obj = OpenAlexClient.get_researcher_obj(args)
    cache_key = hashlib.sha256(researcher_obj["display_name"].encode()).hexdigest().lower()[0:24]

    paper_urls = OpenAlexClient.get_paper_urls(cache_key, researcher_obj)
    citing_paper_urls = OpenAlexClient.get_citing_paper_pdf_urls(cache_key, paper_urls)

    PdfCrawler.download_pdfs(cache_key, citing_paper_urls)

    # PdfParser.convert_pdf_to_txt(cache_key)

    # next step: feeding everything into the ollama docker image
