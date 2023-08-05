import json
import logging
import random
from typing import List
import wikipedia
from diskcache import Cache

from corpus_query.services.ingestion.chunk import chunk_file_by_line
from corpus_query.services.vector_db.client import ArticleSnippet, VectorDbClient

cache = Cache("./script_cache")


def get_chunked_contents(article_title) -> List[str]:
    if article_title in cache:
        logging.info("cache hit: %s", article_title)
        return cache[article_title]

    else:
        logging.info("cache miss: %s", article_title)
        logging.info("pulling: %s", article_title)

    try:
        article_content = wikipedia.page(article_title)
    except wikipedia.DisambiguationError as e:
        s = random.choice(e.options)
        article_content = wikipedia.page(s)

    chunked_content = list(chunk_file_by_line(article_content.content))

    cache[article_title] = chunked_content

    return chunked_content


logging.basicConfig(level=logging.INFO)
if __name__ == "__main__":
    c = VectorDbClient()

    c.create_schema()

    articles_to_index = [
        "Obama",
        "Crocodile",
        "Chicken",
        "England",
        "Spain",
        "France",
        "Cobalt",
    ]

    article_titles = (wikipedia.search(article)[0] for article in articles_to_index)

    chunked_contents = (
        (article.title(), get_chunked_contents(article.title()))
        for article in article_titles
    )

    ret = list(chunked_contents)
    print(len(ret))

    for article_title, chunked_content in ret:
        article_snippets = [
            ArticleSnippet(article_title, snippet) for snippet in chunked_content
        ]

        c.upload_data(article_snippets)

    print(
        json.dumps(
            c.query_from_string("When was bitcoin created?", limit=5),
            indent=2,
        )
    )
