import logging
import random
from typing import List, Optional, Tuple

import wikipedia
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel

from corpus_query.services.ingestion.chunk import chunk_file_by_line
from corpus_query.services.vector_db.client import ArticleSnippet, VectorDbClient

app = FastAPI()


class CorpusRequest(BaseModel):
    corpus: str


class QuestionRequest(BaseModel):
    question: str


class WikiRequest(BaseModel):
    article_names: List[str]


logging.basicConfig(level=logging.INFO)


def get_chunked_contents(article_title) -> Optional[Tuple[List[str], str]]:
    try:
        try:
            article_content = wikipedia.page(article_title)
        except wikipedia.DisambiguationError as e:
            s = random.choice(e.options)
            article_content = wikipedia.page(s)

        chunked_content = list(chunk_file_by_line(article_content.content))

        return chunked_content, article_content.url

    except Exception as e:
        logging.error("error getting chunked content for %s", article_title)


@app.get("/")
def get_hello_world():
    return "Hello World"


@app.post("/load_wikipedia")
def load_wikipedia_corpus(corpus: WikiRequest):
    c = VectorDbClient()

    c.create_schema()

    article_titles = (wikipedia.search(article)[0] for article in corpus.article_names)

    chunked_contents = (
        (article.title(), get_chunked_contents(article.title()))
        for article in article_titles
    )

    ret = []
    for article_title, content_pair in chunked_contents:
        if content_pair is None:
            ret.append(f"failed to get content for '{article_title}'")
            continue

        chunked_content, url = content_pair
        article_snippets = [
            ArticleSnippet(article_title, snippet) for snippet in chunked_content
        ]

        c.upload_data(article_snippets)

        ret.append(
            f"uploaded '{article_title}' ({url}) with {len(article_snippets)} snippets"
        )

    return {"message": ret}


@app.post("/corpus")
def add_corpus(file: UploadFile):
    logging.info("received file: '%s'", file.filename)

    c = VectorDbClient()
    c.create_schema()

    article_snippets = list(
        ArticleSnippet(file.filename, snippet)
        for snippet in chunk_file_by_line(file.file.read().decode())
    )

    logging.info("chunked file into %d lines", len(article_snippets))

    c.upload_data(article_snippets)
    return {
        "message": f"uploaded {file.filename} with {len(article_snippets)} snippets"
    }


@app.post("/corpus/question")
def ask_question(question: QuestionRequest):
    c = VectorDbClient()

    return c.query_from_string(question.question, limit=5)
