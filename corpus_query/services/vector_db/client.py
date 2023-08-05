import logging
import os
from dataclasses import asdict, dataclass, field, fields
from typing import List

import weaviate


@dataclass
class ArticleSnippet:
    title: str
    snippet: str


@dataclass
class VectorDbClient:
    url: field(default_factory=os.getenv("VECTOR_DB_URL"))

    def __post_init__(self):
        self.client = weaviate.Client(self.url)

    def create_schema(self, class_name: str):
        try:
            self.client.schema.get(class_name)

        except weaviate.exceptions.UnexpectedStatusCodeException as e:
            logging.info("class %s does not exist. creating ...", class_name)

            self.client.schema.create_class(
                {
                    "class": class_name,
                    "vectorizer": "text2vec-transformers",
                }
            )

    def upload_data(self, class_name: str, article_snippets: List[ArticleSnippet]):
        with self.client.batch as batch:
            batch.batch_size = 100
            for i, d in enumerate(article_snippets):
                logging.info(
                    "importing question (%d/%d): %s", i + 1, len(article_snippets), d
                )

                self.client.batch.add_data_object(asdict(d), class_name)

    def query_from_string(self, class_name: str, q: str, limit=2):
        # Execute the query
        response = (
            self.client.query.get(
                class_name, list(f.name for f in fields(ArticleSnippet))
            )
            .with_near_text({"concepts": [q]})
            .with_limit(limit)
            .with_additional(["distance"])
            .do()
        )

        return response
