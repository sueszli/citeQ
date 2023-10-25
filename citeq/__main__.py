# 1. get researcher's papers (that have open access)
# 2. get paper's citations
# 3. classify type of citations: criticism, comparison, use, substantiation, basis, neutral (other)

# apis to read from:
# - openalex: https://docs.openalex.org/how-to-use-the-api/api-overview -> https://github.com/J535D165/pyalex
# - semantic scholar: https://api.semanticscholar.org/api-docs/graph -> https://github.com/allenai/s2-folks/blob/main/examples/python/self_citations_on_a_paper/main.py

import argparse
from logger import LOG_SINGLETON as LOG, trace


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CiteQ: a citation analysis tool")
    parser.add_argument("name", nargs="+", help="the researchers name", type=str)
    parser.add_argument("university", nargs="?", help="the researchers university", type=str)
    parser.add_argument("field", nargs="?", help="the researchers field of study", type=str)

    args = parser.parse_args()
