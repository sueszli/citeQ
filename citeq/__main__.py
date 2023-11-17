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
    parser.add_argument("-d", "--download-pdfs", help="download pdfs of papers that cite the researcher's papers", type=bool, default=False)
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
        # see: https://docs.openalex.org/api-entities/authors/author-object
        # to understand the cursor, see: https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/paging#cursor-paging

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
        LOG.info(f"\tbest matching researcher: '{best_match['display_name']}' with {best_match['total_score']} points → validate: {best_match['id']}")
        return best_match

    @staticmethod
    def get_paper_urls(cache_key: str, researcher_obj: dict) -> list:
        LOG.info(f"fetching paper urls")

        filename = "oa-paper-urls.json"
        is_cached, filepath = is_cached_get_path(cache_key, filename)
        if is_cached:
            LOG.info(f"found papers in cache: '{filepath}'")
            return json.load(open(filepath, "r"))

        match_works = researcher_obj["works_api_url"]
        query = match_works + "?&per-page=200&cursor="

        total = requests.get(query).json()["meta"]["count"]
        papers = []
        cursor = "*"
        while cursor is not None:
            response = requests.get(query + cursor).json()
            papers.extend(response["papers"])
            cursor = response["meta"]["next_cursor"]
            LOG.info(f"\tprogress: {len(papers)}/{total}")
        assert len(papers) > 0

        cited_papers = [paper for paper in papers if paper["cited_by_count"] > 0]
        LOG.info(f"\tfound published {len(papers)} papers, {len(cited_papers)} of which have at least one citation")
        assert len(cited_papers) > 0

        # cache results
        json.dump(cited_papers, open(filepath, "w"))
        LOG.info(f"{len(cited_papers)} paper urls cached at '{filepath}'")
        return cited_papers

    @staticmethod
    def get_citing_paper_objs(cache_key: str, paper_urls: list) -> list:
        LOG.info(f"fetching citations")

        filename = "oa-citing-papers.json"
        is_cached, filepath = is_cached_get_path(cache_key, filename)
        if is_cached:
            LOG.info(f"found citing papers in cache: '{filepath}'")
            return json.load(open(filepath, "r"))

        # for each paper, get citing papers
        # see: https://docs.openalex.org/api-entities/works/work-object#cited_by_api_url
        output = []

        LOG.info(f"fetching citing papers")
        queries = [paper["cited_by_api_url"] for paper in paper_urls]
        for i, query in enumerate(queries):
            sub_query = query + "?&per-page=200&cursor="
            LOG.info(f"\tprogress: {i}/{len(paper_urls)}")

            cursor = "*"
            while cursor is not None:
                response = requests.get(sub_query + cursor).json()  # citing paper
                output.append(response)
                cursor = response["meta"]["next_cursor"]

        # cache results
        json.dump(output, open(filepath, "w"))
        LOG.info(f"{len(output)} citations cached at '{filepath}'")
        return output


class OpenAlexPdfCrawler:
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
            OpenAlexPdfCrawler.COUNTER += 1  # will lead to race condition, but that's okay
            LOG.info(f"\tprogress: {OpenAlexPdfCrawler.COUNTER}/{OpenAlexPdfCrawler.TOTAL} - downloaded")
        except requests.exceptions.Timeout:
            LOG.critical(f"\tprogress: {OpenAlexPdfCrawler.COUNTER}/{OpenAlexPdfCrawler.TOTAL} - timed out")

    @staticmethod
    def download_pdfs(cache_key, citing_paper_objs: list):
        urls = []
        for citing_paper in citing_paper_objs:
            urls.append([r["open_access"]["oa_url"] for r in citing_paper["results"] if r["open_access"]["oa_url"] is not None])
        urls = [url for sublist in urls for url in sublist]

        dir_exists, dir_path = is_cached_get_path(cache_key, OpenAlexPdfCrawler.CACHE_DIR_NAME)
        if not dir_exists:
            os.mkdir(dir_path)
            LOG.info(f"created directory for pdfs in cache")

        LOG.info(f"concurrently downloading {len(urls)} pdfs")
        OpenAlexPdfCrawler.TOTAL = len(urls)

        for url in urls:
            filename_len = 10
            filename = hashlib.sha256(url.encode()).hexdigest().lower()[0:filename_len] + ".pdf"
            filepath = os.path.join(dir_path, filename)

            is_cached = os.path.isfile(filepath)
            if is_cached:
                OpenAlexPdfCrawler.COUNTER += 0
                LOG.info(f"\tprogress: {OpenAlexPdfCrawler.COUNTER}/{OpenAlexPdfCrawler.TOTAL} - found in cache")
                continue

            OpenAlexPdfCrawler.download(url, filepath)

    @staticmethod
    def convert_pdf_to_txt(cache_key):
        TXT_CACHE_DIR_NAME = "txts"

        pdf_dir_exists, pdf_dir_path = is_cached_get_path(cache_key, OpenAlexPdfCrawler.CACHE_DIR_NAME)
        assert pdf_dir_exists, f"no pdfs found in cache"

        txt_dir_exists, txt_dir_path = is_cached_get_path(cache_key, TXT_CACHE_DIR_NAME)
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


class SemanticScholarClient:
    @staticmethod
    def match(args: argparse.Namespace, oa_researcher_obj: dict) -> dict:
        # open alex researcher obj:
        oa_num_publications = oa_researcher_obj["works_count"]
        oa_publications_dict = {elem["year"]: [elem["works_count"], elem["cited_by_count"]] for elem in oa_researcher_obj["counts_by_year"]}  # {year: {num_publications, num_citations}}
        oa_i10_index = oa_researcher_obj["summary_stats"]["i10_index"]
        oa_h_index = oa_researcher_obj["summary_stats"]["h_index"]
        assert oa_num_publications > 0, f"no publications found for {args.name}"

        # semantic scholar researcher query:
        # see: https://api.semanticscholar.org/api-docs/#tag/Author-Data/operation/get_graph_get_author_search
        query = (
            "https://api.semanticscholar.org/graph/v1/author/search?query="
            + "+".join(args.name).strip().lower()
            + "&fields=authorId,url,name,aliases,paperCount,citationCount,hIndex,papers.year&limit=1000"
        )
        response = requests.get(query).json()
        total = response["total"]
        assert total > 0, f"no results found for {args.name}"
        data = response["data"]
        data = [elem for elem in data if elem["paperCount"] > 0 and elem["citationCount"] > 0]
        assert len(data) > 0, f"no results with at least one work or citation"
        LOG.info(f"found {total} matching researchers on semantic-scholar, {len(data)} of which have at least one publication")

        for elem in data:
            # name match
            display_name = elem["name"]
            name_disp_score = fuzz.partial_token_sort_ratio(args.name, display_name)
            alias_disp_score = 0 if args.alias is None else fuzz.partial_token_sort_ratio(args.alias, display_name)

            # hint: alternative names
            altnames = elem["aliases"]
            avg_name_altnames_score = 0 if args.alias is None else sum([fuzz.partial_token_sort_ratio(args.name, altname) for altname in altnames]) / len(altnames)
            avg_alias_altnames_score = 0 if args.alias is None else sum([fuzz.partial_token_sort_ratio(args.alias, altname) for altname in altnames]) / len(altnames)

            # rough paper metrics
            total_paper_count_diff = abs(elem["paperCount"] - oa_num_publications)
            h_index_diff = abs(elem["hIndex"] - oa_h_index)
            yearly_citation_count_diff = 0
            ss_publications_dict = {p["year"]: elem["papers"].count(p) for p in elem["papers"] if p}
            for year in ss_publications_dict.keys():
                if year not in oa_publications_dict.keys():
                    continue
                # get num_publications in set {year: {num_publications, num_citations}}
                oa_pubs: int = oa_publications_dict[year][0]
                ss_pubs: int = ss_publications_dict[year]
                yearly_citation_count_diff += abs(oa_pubs - ss_pubs)

            total_score = name_disp_score + alias_disp_score + avg_name_altnames_score + avg_alias_altnames_score
            total_score -= total_paper_count_diff + h_index_diff + yearly_citation_count_diff
            elem["total_score"] = total_score
            LOG.info(f"\t[{str(total_score).zfill(3)} points]: '{display_name}'")

        best_match = max(data, key=lambda result: result["total_score"])
        LOG.info(f"\tbest matching researcher: '{best_match['name']}' with {best_match['total_score']} points → validate: {best_match['url']}")
        return best_match

    @staticmethod
    def get_citations(cache_key: str, ss_researcher_obj: dict) -> list:
        filename = "ss-citations.json"
        is_cached, filepath = is_cached_get_path(cache_key, filename)
        if is_cached:
            LOG.info(f"found citing papers in cache: '{filepath}'")
            return json.load(open(filepath, "r"))

        id = ss_researcher_obj["authorId"]
        LOG.info(f"fetching citations")
        query = f"https://api.semanticscholar.org/graph/v1/author/{id}/papers?limit=1000"

        # fetch papers
        papers = []
        offset = None
        while (offset is None) or (offset != 0):
            response = requests.get(query + ("" if offset is None else f"&offset={offset}")).json()
            papers.extend(response["data"])
            offset = response["offset"]
            LOG.info(f"\t\tprogress: {len(papers)}/{ss_researcher_obj['paperCount']}")
        assert ss_researcher_obj["paperCount"] == len(papers), f"paper count mismatch"
        LOG.info(f"\tfound {len(papers)} papers")

        # fetch citations of papers
        # see: https://api.semanticscholar.org/api-docs/#tag/Paper-Data/operation/get_graph_get_paper_citations
        citations = []
        c = 0
        for paper in papers:
            id = paper["paperId"]
            paper_query = f"https://api.semanticscholar.org/graph/v1/paper/{id}/citations?limit=1000&fields=contexts"

            offset = None
            while (offset is None) or (offset != 0):
                response = requests.get(paper_query + ("" if offset is None else f"&offset={offset}")).json()
                citations.extend(response["data"])
                offset = response["offset"]
                LOG.info(f"\t\tprogress: {c}/{len(papers)}")
                c += 1

        # TODO: fix rate limit - https://github.com/tomasbasham/ratelimit

        # cache results
        json.dump(citations, open(filepath, "w"))
        LOG.info(f"{len(citations)} citations cached at '{filepath}'")
        return citations


class OllamaSentimentClassifier:
    def __init__(self):
        # ollama: "Label the citation purpose of the following text in terms of 'Criticizing', 'Comparison', 'Use', 'Substantiating', 'Basis', and 'Neutral(Other)': \"{text}\" (Note: you should only choose one label for the text"
        pass


def main():
    args = get_args()
    LOG.info(f"args: {args}")

    # find researcher in openalex
    oa_researcher_obj = OpenAlexClient.get_researcher_obj(args)
    cache_key = hashlib.sha256(json.dumps(oa_researcher_obj).encode()).hexdigest().lower()[0:24]

    # optional: download all citing papers
    if args.download_pdfs:
        paper_urls = OpenAlexClient.get_paper_urls(cache_key, oa_researcher_obj)
        citing_paper_objs = OpenAlexClient.get_citing_paper_objs(cache_key, paper_urls)
        OpenAlexPdfCrawler.download_pdfs(cache_key, citing_paper_objs)
        OpenAlexPdfCrawler.convert_pdf_to_txt(cache_key)

    # match with researcher in semantic scholar
    ss_researcher_obj = SemanticScholarClient.match(args, oa_researcher_obj)

    # find citations on semantic scholar
    citations = SemanticScholarClient.get_citations(cache_key, ss_researcher_obj)


if __name__ == "__main__":
    main()
