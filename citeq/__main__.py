from thefuzz import fuzz
from typing import Tuple
import requests
import argparse
import json
import os
import hashlib
import asyncio
import time
from PyPDF2 import PdfReader
from db import Researcher, Paper, Authorship, Citation, engine
from sqlalchemy.orm import Session
from types import SimpleNamespace
import backoff
from dotenv import load_dotenv
import logging
from tqdm import tqdm

from logger import LOG_SINGLETON as LOG, trace
from llm_classifier import LlmClassifier, SentimentClass


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CiteQ: a citation analysis tool")
    parser.add_argument("-n", "--name", nargs="+", help="the researcher's name", type=str)
    parser.add_argument("-a", "--alias", nargs="+", help="the researcher's alternative names", type=str)
    parser.add_argument("-i", "--institution", nargs="+", help="the researcher's last known institution", type=str)
    parser.add_argument("-d", "--download-pdfs", help="download pdfs of papers that cite the researcher's papers", type=bool, default=False)
    parser.add_argument("-s", "--ss-id", help="the semantic scholar id of the researcher", type=int, default=None)
    parser.add_argument("-f", "--file", help="file to read the profs from", type=str, default=None)
    parser.add_argument("-c", "--llm-classify", help="Classify the citatiations using llm", action=argparse.BooleanOptionalAction, type=bool, default=False)
    parser.add_argument("--start", help="start value", type=int, default=None)
    parser.add_argument("--end", help="end value", type=int, default=None)
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


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=8)
def get_url(url, headers=None):
    r = requests.get(url, headers=headers)

    if r.status_code == 404:
        LOG.warning(f"could not find resource at {url}")
        return r
    if r.status_code != 200:
        LOG.warning(f"request failed with status code {r.status_code} - retrying")
        raise requests.exceptions.RequestException

    return r


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_tries=8)
def post_url(url, params, json):
    r = requests.post(url, params=params, json=json)

    if r.status_code != 200:
        LOG.warning(f"request failed with status code {r.status_code} - retrying")
        raise requests.exceptions.RequestException

    return r


class OpenAlexClient:
    @staticmethod
    def get_researcher_obj(_name: str, _alias: str, _institution: str) -> dict:
        # see: https://docs.openalex.org/api-entities/authors/author-object
        # to understand the cursor, see: https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/paging#cursor-paging
        LOG.info(f"fetching researcher with name: {_name}")
        results = []
        query = "https://api.openalex.org/authors?search=" + "%20".join(_name).strip().lower() + "?&per-page=200&cursor="
        cursor = "*"
        while cursor is not None:
            response = requests.get(query + cursor).json()
            results.extend(response["results"])
            cursor = response["meta"]["next_cursor"]

        if len(results) <= 0:
            LOG.info(f"no results found for {_name}")
            return None

        filtered_results = [result for result in results if result["works_count"] > 0 and result["cited_by_count"] > 0]

        if len(filtered_results) <= 0:
            LOG.info(f"no results with at least one work or citation")
            return None

        LOG.info(f"found {len(results)} matching researchers, {len(filtered_results)} of which have at least one work and citation")

        for result in filtered_results:
            display_name = result["display_name"]
            institution = result["last_known_institution"]["display_name"] if result.get("last_known_institution") else None
            altnames = result["display_name_alternatives"]

            # name match
            name_disp_score = fuzz.partial_token_sort_ratio(_name, display_name)
            alias_disp_score = 0 if _alias is None else fuzz.partial_token_sort_ratio(_alias, display_name)

            # hint: institution
            inst_score = 0 if (_institution is None) or (institution is None) else fuzz.partial_token_sort_ratio(_institution, institution)

            # hint: alternative names
            avg_name_altnames_score = 0 if (_alias is None) or (altnames is None) else sum([fuzz.partial_token_sort_ratio(_name, altname) for altname in altnames]) / len(altnames)
            avg_alias_altnames_score = 0 if (_alias is None) or (altnames is None) else sum([fuzz.partial_token_sort_ratio(_alias, altname) for altname in altnames]) / len(altnames)

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
        if total <= 0:
            LOG.info(f"no results found for {args.name}")
            return None

        data = response["data"]
        data = [elem for elem in data if elem["paperCount"] > 0 and elem["citationCount"] > 0]

        if len(data) <= 0:
            LOG.info(f"no results with at least one work or citation")
            return None
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
    def get_researcher_from_ss_id(ss_id: int) -> dict:
        query = f"https://api.semanticscholar.org/graph/v1/author/{ss_id}?fields=name,hIndex,affiliations,paperCount"
        response = get_url(query).json()
        return response

    @staticmethod
    def get_papers_of_researcher(db, ss_researcher_obj: dict) -> list:
        id = ss_researcher_obj["authorId"]
        LOG.info(f"fetching papers")
        query = f"https://api.semanticscholar.org/graph/v1/author/{id}/papers?limit=1000"

        # fetch papers
        papers = []
        offset = None
        while (offset is None) or (offset != 0):
            response = requests.get(query + ("" if offset is None else f"&offset={offset}")).json()
            papers.extend(response["data"])
            offset = response["offset"]

        ##print(len(papers))
        ##assert ss_researcher_obj["paperCount"] == len(papers), f"paper count mismatch"
        LOG.info(f"\tfound {len(papers)} papers")

        # get details of papers
        # send requests in batches of 400
        paper_details = []
        for i in range(0, len(papers), 400):
            paper_ids = [paper["paperId"] for paper in papers[i : i + 400]]
            r = post_url("https://api.semanticscholar.org/graph/v1/paper/batch", params={"fields": "title,year,venue,externalIds,citationCount,authors"}, json={"ids": paper_ids}).json()
            paper_details.extend(r)

        # get the author data
        authors = []
        for paper in paper_details:
            authors.extend(paper["authors"])
        author_ids_set = set([author["authorId"] for author in authors if author["authorId"] is not None])
        author_ids = list(author_ids_set)
        author_details = post_url("https://api.semanticscholar.org/graph/v1/author/batch", params={"fields": "name,hIndex,affiliations"}, json={"ids": author_ids}).json()

        # add authors to db
        for author in author_details:
            if author is None or author["authorId"] is None:
                continue
            # check if author already exists
            db_author = db.session.query(Researcher).filter(Researcher.semantic_scholar_id == author["authorId"]).first()
            if db_author is not None:
                continue

            db.add_researcher(author)

        # add papers to db
        for paper in paper_details:
            db_paper = db.add_paper(
                paper["paperId"],
                paper["title"],
                paper["year"],
                paper["venue"],
                paper["citationCount"],
                paper["externalIds"]["DOI"] if paper.get("externalIds") and paper["externalIds"].get("DOI") else None,
            )
            for i, author in enumerate(paper["authors"]):
                if author["authorId"] is None:
                    continue
                db_researcher = db.session.query(Researcher).filter(Researcher.semantic_scholar_id == author["authorId"]).first()
                if db_researcher is None:
                    # query the author
                    query = f"https://api.semanticscholar.org/graph/v1/author/{author['authorId']}?fields=name,hIndex,affiliations"
                    result = get_url(query)
                    if result.status_code == 404:
                        continue
                    ss_researcher_obj = result.json()

                    db_researcher = db.add_researcher(ss_researcher_obj)

                db.add_authorship(db_researcher, db_paper, i)

        return papers

    @staticmethod
    def get_citations(db, ss_researcher_obj: dict):
        # fetch papers
        papers = db.session.query(Paper).filter(Paper.citations_added == False).all()
        headers = {"x-api-key": os.getenv("S2_API_KEY")} if os.getenv("S2_API_KEY") else None

        LOG.info(f"fetching citations")
        # fetch citations of papers
        # see: https://api.semanticscholar.org/api-docs/#tag/Paper-Data/operation/get_graph_get_paper_citations
        c = 0
        for paper in papers:
            citations = []
            id = paper.semantic_scholar_id
            paper_query = f"https://api.semanticscholar.org/graph/v1/paper/{id}/citations?fields=contexts,intents,paperId"

            # paginate through citations (also avoid rate limit)
            offset: None | int = 0
            while offset is not None:
                ppquery = paper_query + ("" if offset == 0 else f"&offset={offset}")
                response = get_url(ppquery, headers=headers).json()
                assert response
                citations.extend(response["data"])
                offset = response.get("next")

            # add citations to db
            for citation in citations:
                if citation.get("citingPaper") is None or citation["citingPaper"].get("paperId") is None:
                    continue
                for i, context in enumerate(citation["contexts"]):
                    db_citation = db.add_citation(citation["citingPaper"]["paperId"], id, context, citation["intents"][0] if len(citation["intents"]) > 0 else None)

            db.update_paper_citations_added(paper)
            LOG.info(f"\tprogress: {c}/{len(papers)}")
            c += 1

    @staticmethod
    def get_references(db, ss_researcher_obj: dict):
        # fetch papers
        papers = db.session.query(Paper).filter(Paper.references_added == False).all()
        headers = {"x-api-key": os.getenv("S2_API_KEY")} if os.getenv("S2_API_KEY") else None

        LOG.info(f"fetching references")
        # fetch references of papers
        c = 0
        for paper in papers:
            references = []
            id = paper.semantic_scholar_id
            paper_query = f"https://api.semanticscholar.org/graph/v1/paper/{id}/references?fields=contexts,intents,paperId"

            # paginate through references (also avoid rate limit)
            offset: None | int = 0
            while offset is not None:
                ppquery = paper_query + ("" if offset == 0 else f"&offset={offset}")
                response = get_url(ppquery, headers=headers).json()
                assert response
                references.extend(response["data"])
                offset = response.get("next")

            # add references to db
            for reference in references:
                if reference.get("citedPaper") is None or reference["citedPaper"].get("paperId") is None:
                    continue
                for i, context in enumerate(reference["contexts"]):
                    db_citation = db.add_citation(id, reference["citedPaper"]["paperId"], context, reference["intents"][0] if len(reference["intents"]) > 0 else None)

            db.update_paper_references_added(paper)
            LOG.info(f"\tprogress: {c}/{len(papers)}")
            c += 1


class OllamaSentimentClassifier:
    @staticmethod
    def classify(db, start=0, end=-1, to_csv=False):
        row_count = db.session.query(Citation.id).count()
        LOG.info(f"total citations: {row_count}")
        LOG.info(f"start: {start}")
        LOG.info(f"end: {end}")

        if end == -1:
            end = row_count
        # fetch citations
        batch_size = 100
        with tqdm(total=(end - start)) as tq:
            for i in range(start, end, batch_size):
                citations = db.session.query(Citation).offset(i).limit(batch_size).all()
                for citation in citations:
                    if citation.llm_purpose is not None:
                        continue
                    llm_purpose = LlmClassifier.get_sentiment_class(citation.context)
                    if to_csv:
                        with open("llm_purpose.csv", "a") as f:
                            f.write(f"{citation.id},{llm_purpose.name}\n")
                    else:
                        db.update_llm_purpose(citation, llm_purpose.name)
                    tq.update(1)


class DatabaseClient:
    def __init__(self):
        self.session = Session(engine)

    def add_researcher(self, ss_researcher_obj: dict) -> Researcher:
        researcher = Researcher(
            semantic_scholar_id=ss_researcher_obj["authorId"],
            name=ss_researcher_obj["name"],
            h_index=ss_researcher_obj["hIndex"],
            institution=ss_researcher_obj["affiliations"][0] if ss_researcher_obj.get("affiliations") is not None and len(ss_researcher_obj["affiliations"]) > 0 else None,
        )
        try:
            self.session.add(researcher)
            self.session.commit()
        except Exception as e:
            # duplicate entry
            print(e)
            LOG.info(f"researcher already exists")
            self.session.rollback()
            researcher = self.session.query(Researcher).filter(Researcher.semantic_scholar_id == ss_researcher_obj["authorId"]).first()
        return researcher

    def add_paper(self, ss_paper_id, title, year, venue, citation_count, doi) -> Paper:
        paper = Paper(
            semantic_scholar_id=ss_paper_id,
            title=title,
            year=year,
            venue=venue,
            citation_count=citation_count,
            doi=doi,
            citations_added=False,
            references_added=False,
        )
        try:
            self.session.add(paper)
            self.session.commit()
        except Exception as e:
            # duplicate entry
            LOG.info(f"paper already exists")
            self.session.rollback()
            paper = self.session.query(Paper).filter(Paper.semantic_scholar_id == ss_paper_id).first()
            if paper is None:
                print(e)
        return paper

    def add_authorship(self, researcher: Researcher, paper: Paper, author_order: int) -> Authorship:
        authorship = self.session.query(Authorship).filter(Authorship.researcher_id == researcher.id, Authorship.paper_id == paper.id).first()
        if authorship is not None:
            LOG.info(f"authorship already exists")
            return authorship
        authorship = Authorship(researcher_id=researcher.id, paper_id=paper.id, author_order=author_order)
        self.session.add(authorship)
        self.session.commit()
        return authorship

    def add_citation(self, citing_paper_ss_id: str, cited_paper_ss_id: str, context: str, intent: str) -> Citation:
        citation = self.session.query(Citation).filter(Citation.citing_paper_id == citing_paper_ss_id, Citation.cited_paper_id == cited_paper_ss_id, Citation.context == context).first()
        if citation is not None:
            LOG.info(f"citation already exists")
            return citation
        citation = Citation(citing_paper_id=citing_paper_ss_id, cited_paper_id=cited_paper_ss_id, context=context, intent=intent, llm_purpose=None, sentiment=None)
        self.session.add(citation)
        self.session.commit()
        return citation

    def update_llm_purpose(self, citation: Citation, llm_purpose: str) -> Citation:
        citation.llm_purpose = llm_purpose
        self.session.commit()
        return citation

    def update_citation(self, citation: Citation, llm_purpose: str, sentiment: str) -> Citation:
        citation.llm_purpose = llm_purpose
        citation.sentiment = sentiment
        self.session.commit()
        return citation

    def update_paper_citations_added(self, paper: Paper) -> Paper:
        paper.citations_added = True
        self.session.commit()
        return paper

    def update_paper_references_added(self, paper: Paper) -> Paper:
        paper.references_added = True
        self.session.commit()
        return paper

    def session_close(self):
        self.session.close()


def main():
    load_dotenv()
    args = get_args()
    LOG.info(f"args: {args}")
    db = DatabaseClient()

    if args.llm_classify:
        OllamaSentimentClassifier.classify(db, start=args.start, end=args.end, to_csv=True)
        return

    if args.file is not None:
        LOG.setLevel(logging.DEBUG)
        with open(args.file, "r") as f:
            for line in f.readlines():
                try:
                    name, ss_id = line.split(",")
                    ss_id = int(ss_id.strip())
                    ss_researcher_obj = SemanticScholarClient.get_researcher_from_ss_id(ss_id)
                    LOG.warning(f"researcher: {ss_researcher_obj}")
                    db_researcher = db.add_researcher(ss_researcher_obj)
                    SemanticScholarClient.get_papers_of_researcher(db, ss_researcher_obj)
                    SemanticScholarClient.get_citations(db, ss_researcher_obj)
                    SemanticScholarClient.get_references(db, ss_researcher_obj)
                except Exception as e:
                    LOG.warning(f"error: {e}")
                    LOG.warning(f"skipping line: {line}")
                    with open("errors.txt", "a") as f:
                        f.write(line)
        return

    if args.ss_id is not None:
        ss_researcher_obj = SemanticScholarClient.get_researcher_from_ss_id(args.ss_id)
    else:
        # find researcher in openalex
        oa_researcher_obj = OpenAlexClient.get_researcher_obj(args.name, args.alias, args.institution)
        ss_researcher_obj = SemanticScholarClient.match(args, oa_researcher_obj)

    LOG.info(f"researcher: {ss_researcher_obj}")
    db_researcher = db.add_researcher(ss_researcher_obj)
    # print(json.dumps(oa_researcher_obj))

    # print(json.dumps(ss_researcher_obj))
    # # find citations on semantic scholar
    SemanticScholarClient.get_papers_of_researcher(db, ss_researcher_obj)
    SemanticScholarClient.get_citations(db, ss_researcher_obj)
    SemanticScholarClient.get_references(db, ss_researcher_obj)

    LOG.info(f"Done: Researcher: {ss_researcher_obj}")


if __name__ == "__main__":
    main()
