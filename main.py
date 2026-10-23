#main.py --> This is where our actual API will live.

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pathlib import Path
import uuid
import shutil

from database import engine, SessionLocal, Base
from models import ResearchSession, Document
from schemas import (
    SessionCreate,
    SessionResponse,
    DocumentResponse,
    ResearchRequest,
    ResearchResponse,
    ComparisonRequest,
    ComparisonResponse,
    ReportRequest,
    ReportResponse,
)

from agents.document_agent import process_document
from services.embedder import create_embedding
from services.vector_store import search_chunks

from agents.extraction_agent import extract_revenue
from agents.red_flag_agent import analyze_revenue_candidates
from agents.research_agent import answer_research_question
from agents.comparison_agent import compare_company_metrics
from agents.report_agent import generate_initial_report

from orchestrator import run_analysis_pipeline



# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Financial Research Workspace API"
)


# Database dependency
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# Create uploads folder
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# --------------------------------------------------
# 1. CREATE SESSION
# --------------------------------------------------

@app.post("/sessions", response_model=SessionResponse)
def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db)
):
    new_session = ResearchSession(
        id=str(uuid.uuid4()),
        name=session_data.name
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return new_session


# --------------------------------------------------
# 2. GET SESSION
# --------------------------------------------------

@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    session = db.query(ResearchSession).filter(
        ResearchSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Research session not found"
        )

    return session


# --------------------------------------------------
# 3. UPLOAD DOCUMENT
# --------------------------------------------------

@app.post("/sessions/{session_id}/documents")

def upload_document(
    session_id: str,
    file: UploadFile = File(...),
    company: str = Form(...),
    document_type: str = Form(...),
    year: int = Form(...),
    db: Session = Depends(get_db)
):
    # Check that session exists
    session = db.query(ResearchSession).filter(
        ResearchSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Research session not found"
        )

    # Generate document ID
    document_id = str(uuid.uuid4())

    # Save file
    file_path = UPLOAD_DIR / f"{document_id}_{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create document database record
    new_document = Document(
        id=document_id,
        session_id=session_id,
        filename=file.filename
    )

    db.add(new_document)
    db.commit()
    db.refresh(new_document)

    # --------------------------------
    # Process document using Document Agent
    # --------------------------------

        # Run all three agents through the orchestration layer.
    pipeline_result = run_analysis_pipeline(
        file_path=str(file_path),
        document_id=document_id,
        company=company,
        document_type=document_type,
        year=year,
    )

    # Return the document record and the pipeline result.
    return {
        "document": {
            "id": new_document.id,
            "session_id": new_document.session_id,
            "filename": new_document.filename,
        },
        "analysis": pipeline_result,
    }


# --------------------------------------------------
# 4. LIST DOCUMENTS
# --------------------------------------------------

@app.get(
    "/sessions/{session_id}/documents",
    response_model=list[DocumentResponse]
)
def list_documents(
    session_id: str,
    db: Session = Depends(get_db)
):
    # Check that session exists
    session = db.query(ResearchSession).filter(
        ResearchSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Research session not found"
        )

    documents = db.query(Document).filter(
        Document.session_id == session_id
    ).all()

    return documents


# --------------------------------------------------
# 5. SEARCH DOCUMENTS
# --------------------------------------------------

@app.get("/documents/search")
def search_documents(
    query: str,
    top_k: int = 3
):
    # Convert query into embedding
    query_embedding = create_embedding(query)

    # Search ChromaDB
    results = search_chunks(
        query_embedding=query_embedding,
        top_k=top_k
    )

    return {
        "query": query,
        "results": results
    }


# --------------------------------------------------
# 6. EXTRACT REVENUE
# --------------------------------------------------

@app.get("/documents/{document_id}/extract/revenue")
def extract_document_revenue(document_id: str):
    candidates = extract_revenue(document_id)

    return {
        "document_id": document_id,
        "metric": "revenue",
        "candidates_found": len(candidates),
        "candidates": candidates
    }


# --------------------------------------------------
# 7. ANALYZE RED FLAGS
# --------------------------------------------------

@app.get("/documents/{document_id}/analyze/red-flags")
def analyze_document_red_flags(document_id: str):
    # Step 1: Extract revenue candidates from the document.
    candidates = extract_revenue(document_id)

    # Step 2: Analyse candidates for potential warning signs.
    result = analyze_revenue_candidates(
        document_id=document_id,
        candidates=candidates
    )

    # Step 3: Return the structured analysis.
    return result


# --------------------------------------------------
# 8. RESEARCH AGENT
# --------------------------------------------------

@app.post(
    "/documents/{document_id}/research",
    response_model=ResearchResponse
)
def research_document(
    document_id: str,
    request: ResearchRequest,
    db: Session = Depends(get_db)
):
    """
    Research Agent endpoint:
    Accepts a financial question for a specific document, retrieves evidence
    with strict document isolation, calculates percentage changes deterministically,
    integrates Extraction Agent and Red Flag Agent findings, and returns an
    evidence-grounded answer with source citations.
    """
    # Validate document exists in database
    document = db.query(Document).filter(
        Document.id == document_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document with ID '{document_id}' not found."
        )

    # Validate non-empty question
    if not request.question or not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    try:
        response = answer_research_question(
            document_id=document_id,
            question=request.question.strip()
        )
        if isinstance(response, dict) and document:
            response['session_id'] = document.session_id
        return response
    except ValueError as val_err:
        raise HTTPException(
            status_code=400,
            detail=str(val_err)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Research Agent processing failed: {str(exc)}"
        )


# --------------------------------------------------
# 8b. SESSION CONVERSATIONAL RESEARCH
# --------------------------------------------------

@app.post(
    "/sessions/{session_id}/research",
    response_model=ResearchResponse
)
def research_session(
    session_id: str,
    request: ResearchRequest,
    db: Session = Depends(get_db)
):
    """
    Conversational Research Agent endpoint at Session level:
    Accepts follow-up or initial financial questions within a session.
    Preserves session context and routes to the selected document or the
    session's document. Enforces document isolation and returns grounded answers
    with source citations, session_id, and document_id.
    """
    # Validate session exists
    session = db.query(ResearchSession).filter(
        ResearchSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Research session with ID '{session_id}' not found."
        )

    # Validate non-empty question
    if not request.question or not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    # Resolve document context
    session_docs = db.query(Document).filter(
        Document.session_id == session_id
    ).all()

    if not session_docs:
        raise HTTPException(
            status_code=400,
            detail=f"Research session '{session_id}' has no uploaded documents. Please upload a document first."
        )

    target_doc_id = request.document_id
    if target_doc_id:
        # Verify that the specified document belongs to this session
        matched_doc = next((d for d in session_docs if d.id == target_doc_id), None)
        if not matched_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{target_doc_id}' does not belong to session '{session_id}'."
            )
    else:
        # Default to the most recently uploaded document in the session
        matched_doc = session_docs[-1]
        target_doc_id = matched_doc.id

    try:
        response = answer_research_question(
            document_id=target_doc_id,
            question=request.question.strip()
        )
        if isinstance(response, dict):
            response['session_id'] = session_id
        return response
    except ValueError as val_err:
        raise HTTPException(
            status_code=400,
            detail=str(val_err)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Conversational Research Agent processing failed: {str(exc)}"
        )


# --------------------------------------------------
# 9. COMPARISON AGENT
# --------------------------------------------------

@app.post(
    "/documents/compare",
    response_model=ComparisonResponse
)
def compare_documents(
    request: ComparisonRequest,
    db: Session = Depends(get_db)
):
    """
    Comparison Agent endpoint:
    Compares financial metrics (e.g. revenue, net profit) across two or more documents
    for a specified financial year and reporting basis.
    Enforces document isolation, deterministic metric difference and percentage difference
    calculations relative to a reference document, unit compatibility checking,
    and returns source citations (page, chunk ID, source text) or explicit limitation notes.
    """
    # Validate minimum document count
    if not request.document_ids or len(request.document_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least two document IDs are required for comparison."
        )

    # Validate no duplicate document IDs
    if len(request.document_ids) != len(set(request.document_ids)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate document IDs are not permitted."
        )

    # Validate that all requested documents exist in the database
    for doc_id in request.document_ids:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document with ID '{doc_id}' not found."
            )

    # Validate reference_document_id if supplied
    if request.reference_document_id and request.reference_document_id not in request.document_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Reference document ID '{request.reference_document_id}' must be one of the requested document IDs."
        )

    try:
        response = compare_company_metrics(
            document_ids=request.document_ids,
            financial_year=request.financial_year or "FY 2024-25",
            reporting_basis=request.reporting_basis or "consolidated",
            metrics=request.metrics or ["revenue"],
            reference_document_id=request.reference_document_id
        )
        return response
    except ValueError as val_err:
        raise HTTPException(
            status_code=400,
            detail=str(val_err)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Comparison Agent processing failed: {str(exc)}"
        )

# --------------------------------------------------
# 10. REPORT AGENT
# --------------------------------------------------

@app.post(
    "/sessions/{session_id}/report",
    response_model=ReportResponse
)
def generate_session_report(
    session_id: str,
    request: ReportRequest = ReportRequest(),
    db: Session = Depends(get_db)
):
    """
    Report Agent endpoint at Session level:
    Generates an initial structured financial report (Executive Summary and Key Financials)
    for the active or specified document within the given research session.
    Preserves verified citations, reporting periods, units, and integrates Red Flag warnings.
    """
    # Validate session exists
    session = db.query(ResearchSession).filter(
        ResearchSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Research session with ID '{session_id}' not found."
        )

    # Resolve document context
    session_docs = db.query(Document).filter(
        Document.session_id == session_id
    ).all()

    if not session_docs:
        raise HTTPException(
            status_code=400,
            detail=f"Research session '{session_id}' has no uploaded documents. Please upload a document first."
        )

    target_doc_id = request.document_id
    if target_doc_id:
        matched_doc = next((d for d in session_docs if d.id == target_doc_id), None)
        if not matched_doc:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{target_doc_id}' does not belong to session '{session_id}'."
            )
    else:
        matched_doc = session_docs[-1]
        target_doc_id = matched_doc.id

    try:
        report = generate_initial_report(
            document_id=target_doc_id,
            session_id=session_id,
            reporting_basis=request.reporting_basis or "consolidated",
            financial_year=request.financial_year
        )
        return report
    except ValueError as val_err:
        raise HTTPException(
            status_code=400,
            detail=str(val_err)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Report Agent generation failed: {str(exc)}"
        )


@app.post(
    "/documents/{document_id}/report",
    response_model=ReportResponse
)
def generate_document_report(
    document_id: str,
    request: ReportRequest = ReportRequest(),
    db: Session = Depends(get_db)
):
    """
    Report Agent endpoint for a specific document ID directly.
    """
    document = db.query(Document).filter(
        Document.id == document_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document with ID '{document_id}' not found."
        )

    try:
        report = generate_initial_report(
            document_id=document_id,
            session_id=document.session_id,
            reporting_basis=request.reporting_basis or "consolidated",
            financial_year=request.financial_year
        )
        return report
    except ValueError as val_err:
        raise HTTPException(
            status_code=400,
            detail=str(val_err)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Report Agent generation failed: {str(exc)}"
        )
