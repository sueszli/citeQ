# 0. user enters researcher's name
# 1. get researcher's papers (that have open access)
# 2. get paper's citations
# 3. classify type of citations: criticism, comparison, use, substantiation, basis, neutral (other)

# apis to read from:
# - openalex: https://docs.openalex.org/
# - semantic scholar: https://www.semanticscholar.org/

import argparse
from logger import LOG_SINGLETON as LOG, trace


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CiteQ: a citation analysis tool")
    parser.add_argument("name", nargs="+", help="the researchers name", type=str)
    name_arr: list = parser.parse_args().name
    assert name_arr is not None and len(name_arr) > 0

    LOG.info(f"user requested search for: {name_arr}")
