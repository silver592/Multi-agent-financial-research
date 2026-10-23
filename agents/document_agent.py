#agents/document_agent.py --> "This is the Document Agent. Its job is to connect all the smaller services together (Parser,Chunker,Metadata,Embedder,Vector Store) and run the complete document-ingestion pipeline."

from services.parser import parse_pdf
from services.chunker import chunk_page
from services.embedder import create_embeddings
from services.vector_store import store_chunks


def process_document(
    file_path,
    document_id,
    company,
    document_type,
    year
):
    """
    Complete document ingestion pipeline:

    PDF
    -> Parse
    -> Chunk
    -> Metadata
    -> Embeddings
    -> ChromaDB
    """

    # --------------------------------
    # 1. Parse
    # --------------------------------

    pages = parse_pdf(file_path)

    # --------------------------------
    # 2. Chunk
    # --------------------------------

    all_chunks = []

    for page in pages:

        page_chunks = chunk_page(
            page["text"],
            page["page_number"]
        )

        all_chunks.extend(page_chunks)

    # --------------------------------
    # 3. Prepare metadata
    # --------------------------------

    documents = []
    ids = []
    metadatas = []

    for index, chunk in enumerate(all_chunks, start=1):

        chunk_id = (
            f"{document_id}"
            f"_p{chunk['page_number']}"
            f"_c{index}"
        )

        metadata = {
            "document_id": str(document_id),
            "company": company,
            "document_type": document_type,
            "year": int(year),
            "page_number": int(chunk["page_number"]),
            "chunk_id": chunk_id,
            "chunk_text": chunk["text"]
        }

        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append(metadata)

    # --------------------------------
    # 4. Create embeddings
    # --------------------------------

    embeddings = create_embeddings(documents)

    # --------------------------------
    # 5. Store in ChromaDB
    # --------------------------------

    store_chunks(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    # --------------------------------
    # Return processing summary
    # --------------------------------

    return {
        "document_id": document_id,
        "pages_processed": len(pages),
        "chunks_created": len(documents)
    }