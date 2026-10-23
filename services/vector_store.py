
# services/vector_store.py
# This file stores chunks and embeddings in ChromaDB
# and retrieves relevant chunks from financial documents.

import chromadb

# Persistent local ChromaDB
client = chromadb.PersistentClient(
    path="./data/chroma_db"
)

collection = client.get_or_create_collection(
    name="financial_documents"
)


def store_chunks(
    ids,
    documents,
    embeddings,
    metadatas
):
    """
    Store or update document chunks and their embeddings.
    """

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )


def search_chunks(query_embedding, top_k=3, document_id=None):
    """
    Search for relevant chunks using semantic similarity.

    If document_id is provided, search only that document.
    Otherwise, search across all stored documents.
    """

    search_options = {
        "query_embeddings": [query_embedding],
        "n_results": top_k
    }

    # Restrict the search to a specific document when requested.
    if document_id:
        search_options["where"] = {
            "document_id": document_id
        }

    results = collection.query(**search_options)

    retrieved = []

    if not results["documents"] or not results["documents"][0]:
        return retrieved

    for i in range(len(results["documents"][0])):
        retrieved.append({
            "chunk_id": results["ids"][0][i],
            "chunk_text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i]
        })

    return retrieved


def get_document_chunks(document_id: str):
    """
    Retrieve ALL stored chunks for one document.

    Unlike search_chunks(), this function does not rank
    chunks by similarity or limit the results to top_k.

    It can be used for reports from Reliance, TCS, Infosys,
    or any other company stored with the correct document_id.
    """

    results = collection.get(
        where={
            "document_id": document_id
        },
        include=[
            "documents",
            "metadatas"
        ]
    )

    retrieved = []

    for i in range(len(results["ids"])):
        retrieved.append({
            "chunk_id": results["ids"][i],
            "chunk_text": results["documents"][i],
            "metadata": results["metadatas"][i]
        })

    return retrieved
