import logging
import os
from typing import List

import weaviate
from fastapi import FastAPI, UploadFile
from langchain.document_loaders import PyPDFLoader
from llama_index import (
    Document,
    ServiceContext,
    StorageContext,
    VectorStoreIndex,
    set_global_service_context,
)
from llama_index.llms import OpenAI
from llama_index.node_parser import SimpleNodeParser
from llama_index.schema import BaseNode
from llama_index.vector_stores import WeaviateVectorStore
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)

# connect to your weaviate instance
# define LLM
llm = OpenAI(
    model="gpt-4",
    temperature=0,
    max_tokens=256,
    api_key=os.getenv("OPENAI_API_KEY"),
)

# configure service context
service_context = ServiceContext.from_defaults(llm=llm)
set_global_service_context(service_context)

client = weaviate.Client(
    url=os.getenv("VECTOR_DB_URL"),
    # embedded_options=weaviate.embedded.EmbeddedOptions(),
    additional_headers={"X-OpenAI-Api-Key": os.getenv("OPENAI_API_KEY")},
)


# construct vector store
vector_store = WeaviateVectorStore(
    weaviate_client=client, index_name="BlogPost", text_key="content"
)

# setting up the storage for the embeddings
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# set up the index
index = VectorStoreIndex.from_vector_store(vector_store)


app = FastAPI()


def chunk_by_file_type(docs: List[Document]) -> List[BaseNode]:
    parser = SimpleNodeParser.from_defaults()
    return parser.get_nodes_from_documents(docs)


class QuestionRequest(BaseModel):
    question: str


class WikiRequest(BaseModel):
    article_names: List[str]


@app.get("/")
def get_hello_world():
    return "Hello World"


@app.post("/load_wikipedia")
def load_wikipedia_corpus(corpus: WikiRequest):
    """Input a list of wikipedia article names and load them into the vector db.

    Args:
        corpus (WikiRequest): List of article names i.e. the content after 'https://en.wikipedia.org/wiki/' in the wikipedia title
        options (Optional[ChunkingOptions]): chunking options. 250, 50 is a good setup

    Returns:
        Dict: Response document
    """

    global index
    ret = []

    for article_title in corpus.article_names:
        try:
            query = f"https://en.wikipedia.org/api/rest_v1/page/pdf/{article_title}"
            logging.info("loading '%s'", query)
            loader = PyPDFLoader(query)

            documents = loader.load_and_split()
            logging.info("loaded '%s'", query)
            snippets = chunk_by_file_type(
                [Document(text=doc.page_content) for doc in documents]
            )
            logging.info("snipped '%s'", query)

            logging.info("done w/ '%s'", query)

            ret.append(
                f"uploaded '{article_title}' ({query}) with {len(snippets)} snippets"
            )

        except Exception as e:
            logging.exception(e)
            ret.append(f"failed to upload '{article_title}' using ({query})")

    return {"message": ret}


@app.post("/corpus")
def add_corpus(file: UploadFile):
    global index
    logging.info("received file: '%s'", file.filename)

    d = Document(text=file.file.read().decode())

    snippets = chunk_by_file_type([d])

    logging.info("chunked file into %d lines", len(snippets))

    index.insert_nodes(snippets)

    return {"message": f"uploaded {file.filename} with {len(snippets)} snippets"}


@app.post("/corpus/question")
def ask_question(question: QuestionRequest):
    global index
    query_engine = index.as_query_engine()

    return {"response": str(query_engine.query(question.question))}
