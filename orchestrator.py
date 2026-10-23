
# orchestrator.py
# Coordinates the Document, Extraction, and Red Flag Agents.

from agents.document_agent import process_document
from agents.extraction_agent import extract_revenue
from agents.red_flag_agent import analyze_revenue_candidates


def run_analysis_pipeline(
    file_path: str,
    document_id: str,
    company: str,
    document_type: str,
    year: int,
) -> dict:
    """
    Runs the three agents sequentially for one uploaded PDF.
    """

    # Step 1: Process and index the PDF.
    try:
        document_result = process_document(
            file_path=file_path,
            document_id=document_id,
            company=company,
            document_type=document_type,
            year=year,
        )

        if not document_result:
            raise ValueError("Document Agent returned no result.")

    except Exception as exc:
        return {
            "document_id": document_id,
            "status": "failed",
            "failed_agent": "Document Agent",
            "error": str(exc),
        }

    # Step 2: Extract revenue from this document.
    try:
        candidates = extract_revenue(document_id)

        if candidates is None:
            raise ValueError("Extraction Agent returned no result.")

    except Exception as exc:
        return {
            "document_id": document_id,
            "status": "failed",
            "failed_agent": "Extraction Agent",
            "document_result": document_result,
            "error": str(exc),
        }

    # Step 3: Analyze the extracted revenue candidates.
    try:
        red_flag_result = analyze_revenue_candidates(
            document_id=document_id,
            candidates=candidates,
        )

    except Exception as exc:
        return {
            "document_id": document_id,
            "status": "failed",
            "failed_agent": "Red Flag Agent",
            "document_result": document_result,
            "candidates_found": len(candidates),
            "error": str(exc),
        }

    # Step 4: Combine the results.
    return {
        "document_id": document_id,
        "status": "success",
        "document_processing": document_result,
        "extraction": {
            "metric": "revenue",
            "candidates_found": len(candidates),
            "candidates": candidates,
        },
        "red_flag_analysis": red_flag_result,
    }
