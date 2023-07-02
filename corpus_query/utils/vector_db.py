import json
import weaviate
import requests


def create_data(client: weaviate.Client):
    # Class definition object. Weaviate's autoschema feature will infer properties when importing.
    class_obj = {
        "class": "Question",
        "vectorizer": "text2vec-transformers",
    }

    # Add the class to the schema
    client.schema.create_class(class_obj)

    url = "https://raw.githubusercontent.com/weaviate-tutorials/quickstart/main/data/jeopardy_tiny+vectors.json"
    resp = requests.get(url)
    data = json.loads(resp.text)

    # Configure a batch process
    with client.batch as batch:
        batch.batch_size = 100
        # Batch import all Questions
        for i, d in enumerate(data):
            print(f"importing question: {i+1}")

            properties = {
                "answer": d["Answer"],
                "question": d["Question"],
                "category": d["Category"],
            }

            client.batch.add_data_object(properties, "Question")


def query_from_string(client: weaviate.Client, q: str):
    # Execute the query
    response = (
        client.query.get("Question", ["question", "answer"])
        .with_near_text({"concepts": [q]})
        .with_limit(2)
        .with_additional(["distance"])
        .do()
    )

    # Print the results
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    client = weaviate.Client("http://localhost:8080")
    query_from_string(client, "steel")
