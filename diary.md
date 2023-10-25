_user flow_:

0. enter researcher's name (and some hints)
1. get researcher's papers (that have open access)
2. get other papers that cite the researchers papers
3. classify citations: criticism, comparison, use, substantiation, basis, neutral (other)

<br>

_searching the researcher's name_:

1.  semantic scholar: https://www.semanticscholar.org/product/api

    has more results, but also more duplicates and to little meta data about authors - so you can only guess which one is the right one

    ```bash
    curl -s "https://api.semanticscholar.org/graph/v1/author/search?query=jimmy+lin&fields=authorId,externalIds,url,name,aliases,affiliations,homepage" | jq .
    ```

    is way more popular and has a bunch of nice wrappers:

    -   docs: https://api.semanticscholar.org/api-docs
    -   https://github.com/danielnsilva/semanticscholar (⭐️ 185)
    -   https://github.com/allenai/s2-folks/blob/main/examples/python/self_citations_on_a_paper/main.py (⭐️ 70)

2.  openalex: https://docs.openalex.org/

    has one wrapper that always returns fewer results than the website:

    -   https://github.com/J535D165/pyalex (⭐️ 58)

<br>

_fuzzy string matching_:

-   fuzzywuzzy: https://github.com/seatgeek/fuzzywuzzy (⭐️ 9k) → has been moved to "thefuzz"
-   thefuzz: https://github.com/seatgeek/thefuzz (⭐️ 2k)
