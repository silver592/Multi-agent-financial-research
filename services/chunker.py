#services/chunker.py --> Chunking divides a large document into smaller pieces that can be independently embedded and retrieved

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 300


def chunk_page(text, page_number):

    chunks = []

    start = 0
    chunk_number = 1

    while start < len(text):

        end = start + CHUNK_SIZE

        chunk = text[start:end].strip()

        if chunk:
            chunks.append({
                "text": chunk,
                "page_number": page_number,
                "chunk_number": chunk_number
            })

            chunk_number += 1

        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks
#Done