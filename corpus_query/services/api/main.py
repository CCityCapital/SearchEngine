import logging
import random
from typing import List, Optional, Tuple

import wikipedia
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel

from corpus_query.services.ingestion.chunk import (
    ChunkingOptions,
    FileTypes,
    chunk_by_file_type,
)
from corpus_query.services.vector_db.client import ArticleSnippet, VectorDbClient

app = FastAPI()


class CorpusRequest(BaseModel):
    corpus: str


class QuestionRequest(BaseModel):
    question: str
    limit: Optional[int] = 5


class WikiRequest(BaseModel):
    article_names: List[str]


logging.basicConfig(level=logging.INFO)


def get_wikipedia_text(article_title) -> Optional[Tuple[str, str]]:
    try:
        try:
            article_content = wikipedia.page(article_title)
        except wikipedia.DisambiguationError as e:
            s = random.choice(e.options)
            article_content = wikipedia.page(s)

        return article_content.content, article_content.url

    except Exception as e:
        logging.error("error getting chunked content for %s", article_title)


@app.get("/")
def get_hello_world():
    return "Hello World"


@app.post("/load_wikipedia")
def load_wikipedia_corpus(corpus: WikiRequest, options: Optional[ChunkingOptions]):
    c = VectorDbClient()

    c.create_schema()

    article_titles = (wikipedia.search(article)[0] for article in corpus.article_names)

    chunked_contents = (
        (article.title(), get_wikipedia_text(article.title()))
        for article in article_titles
    )

    ret = []
    for article_title, content_pair in chunked_contents:
        if content_pair is None:
            ret.append(f"failed to get content for '{article_title}'")
            continue

        chunked_content, url = content_pair

        article_snippets = chunk_by_file_type(
            chunked_content, FileTypes.MARKDOWN, options
        )

        c.upload_data(
            [ArticleSnippet(article_title, s.page_content) for s in article_snippets]
        )

        ret.append(
            f"uploaded '{article_title}' ({url}) with {len(article_snippets)} snippets"
        )

    return {"message": ret}


@app.post("/corpus")
def add_corpus(
    file: UploadFile, file_type: FileTypes, options: Optional[ChunkingOptions] = None
):
    logging.info("received file: '%s'", file.filename)

    c = VectorDbClient()
    c.create_schema()

    article_snippets = list(
        ArticleSnippet(file.filename, snippet)
        for snippet in chunk_by_file_type(file.file.read().decode(), file_type, options)
    )

    logging.info("chunked file into %d lines", len(article_snippets))

    c.upload_data(article_snippets)
    return {
        "message": f"uploaded {file.filename} with {len(article_snippets)} snippets"
    }


@app.post("/corpus/question")
def ask_question(question: QuestionRequest):
    c = VectorDbClient()

    return c.query_from_string(question.question, limit=question.limit)
