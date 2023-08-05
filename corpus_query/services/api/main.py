from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
import logging

from corpus_query.services.ingestion.chunk import chunk_file_by_line
from corpus_query.services.vector_db.client import ArticleSnippet, VectorDbClient

app = FastAPI()


class CorpusRequest(BaseModel):
    corpus: str


class QuestionRequest(BaseModel):
    question: str


logging.basicConfig(level=logging.INFO)


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
