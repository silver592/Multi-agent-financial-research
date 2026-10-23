#services/embedder.py --> This file is responsible for creating embeddings from our text.

from sentence_transformers import SentenceTransformer


# Load embedding model once
model = SentenceTransformer("all-MiniLM-L6-v2")


def create_embedding(text):
    """
    Convert text into a numerical vector.
    """

    embedding = model.encode(text)

    return embedding.tolist()


def create_embeddings(texts):
    """
    Convert multiple text chunks into embeddings.
    """

    embeddings = model.encode(texts)

    return embeddings.tolist()