from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
import logging

from corpus_query.services.ingestion.chunk import chunk_file_by_line

app = FastAPI()


class CorpusRequest(BaseModel):
    corpus: str


class QuestionRequest(BaseModel):
    question: str


logging.basicConfig(level=logging.INFO)


@app.post("/corpus")
def add_corpus(file: UploadFile):
    logging.info("received file: '%s'", file.filename)

    chunked_file_contents = list(chunk_file_by_line(file.file.read().decode()))

    logging.info("chunked file into %d lines", len(chunked_file_contents))

    print(chunked_file_contents)
    return {"filename": file.filename}


@app.post("/corpus/{corpus_id}/question")
def ask_question(corpus_id: int, question: QuestionRequest):
    pass
