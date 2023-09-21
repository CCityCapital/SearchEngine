import logging
import random
from typing import List, Optional, Tuple

from fastapi import FastAPI, File, UploadFile
from langchain.document_loaders import PyPDFLoader
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


@app.get("/")
def get_hello_world():
    return "Hello World"


@app.post("/load_wikipedia")
def load_wikipedia_corpus(corpus: WikiRequest, options: Optional[ChunkingOptions]):
    c = VectorDbClient()
    c.create_schema()

    ret = []

    for article_title in corpus.article_names:
        query = f"https://en.wikipedia.org/api/rest_v1/page/pdf/{article_title}"
        logging.info("loading '%s'", query)
        loader = PyPDFLoader(query)

        documents = loader.load_and_split()

        logging.info("loaded '%s'", query)

        snippets = []
        for d in documents:
            for snippet in chunk_by_file_type(d.page_content, FileTypes.PDF, options):
                logging.info(snippet)
                snippets.append(snippet)

        logging.info("snipped '%s'", query)

        c.upload_data([ArticleSnippet(article_title, d.page_content) for d in snippets])
        logging.info("done w/ '%s'", query)

        ret.append(
            f"uploaded '{article_title}' ({query}) with {len(snippets)} snippets"
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
