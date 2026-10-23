# Multi-Agent AI Analysis System for Financial Research and Business Insights

**Infosys Springboard AI Internship Project**

An automated, evidence-grounded research platform for corporate annual reports and financial statements. The system coordinates specialized AI agents to extract financial metrics, detect year-over-year revenue decline red flags, compare competitor financials across companies, answer research questions with verifiable source page citations, and generate executive financial reports.

---

## 🌟 Key Features

1. **Document Ingestion & Chunking**: Parses large annual report PDFs (Form 10-K, Integrated Reports) with PyMuPDF (`fitz`), segments text with metadata, and generates local vector embeddings stored in ChromaDB.
2. **Deterministic Financial Extraction**: Extracts company revenue and net profit numbers while maintaining strict separation between **consolidated** and **standalone** reporting bases.
3. **Conversational Research with Citations**: Answers natural language questions via session-based research, returning exact citations (PDF page number, chunk ID, statement type, and text snippet).
4. **Automated Red Flag Detection**: Identifies qualifying year-over-year revenue declines and assigns severity levels (`medium` for <20% decline, `high` for ≥20% decline).
5. **Cross-Company Comparison**: Aligns financial metrics across multiple corporate annual reports (e.g., Reliance vs. Infosys vs. TCS), computing absolute and percentage differences relative to a chosen reference baseline.
6. **Executive Report Generation**: Automatically compiles an Executive Summary narrative and structured Key Financials table with verified source citations.
7. **Interactive Streamlit Web Interface**: Complete browser-based UI for document uploading, research chatting, red flag analysis, company comparisons, and report viewing.

---

## 🏗️ Multi-Agent Architecture

```
User / Streamlit UI (app.py)
         │
         ▼  (HTTP REST)
FastAPI Backend (main.py)
   ├── SQLite Database (sessions & document metadata)
   └── ChromaDB (chunk embeddings via all-MiniLM-L6-v2)
         │
         ├── Document Agent (services/parser.py, chunker.py, embedder.py, vector_store.py)
         ├── Extraction Agent (agents/extraction_agent.py)
         ├── Red Flag Agent (agents/red_flag_agent.py)
         ├── Research Agent (agents/research_agent.py)
         ├── Comparison Agent (agents/comparison_agent.py)
         └── Report Agent (agents/report_agent.py)
```

---

## 🛠️ Technology Stack

- **Python**: 3.12
- **Backend API**: FastAPI, Uvicorn, Pydantic
- **Database & Vector Store**: SQLite (SQLAlchemy ORM), ChromaDB
- **NLP & Embeddings**: SentenceTransformers (`all-MiniLM-L6-v2`)
- **PDF Processing**: PyMuPDF (`fitz`)
- **Frontend**: Streamlit, Requests, Pandas
- **Testing**: Python standard library `unittest` (60 passing tests)

---

## 📋 Prerequisites

- Windows 10/11, Linux, or macOS
- Python 3.12 installed
- Git installed

---

## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/<YOUR_USERNAME>/<YOUR_REPOSITORY_NAME>.git
cd <YOUR_REPOSITORY_NAME>
```

### 2. Create and Activate Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Copy `.env.example` to `.env` (optional, default fallback is `http://127.0.0.1:8000`):
```bash
cp .env.example .env
```

---

## 💻 Running the Application

The system runs as two processes: the **FastAPI backend** and the **Streamlit frontend**. Open two separate terminal windows.

### Terminal 1: Start FastAPI Backend
```bash
# Activate virtual environment
.\venv\Scripts\activate

# Start server on http://127.0.0.1:8000
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
*API documentation and Swagger UI are accessible at `http://127.0.0.1:8000/docs`.*

### Terminal 2: Start Streamlit Frontend
```bash
# Activate virtual environment
.\venv\Scripts\activate

# Launch UI
streamlit run app.py
```
*Streamlit web application will open automatically at `http://localhost:8501`.*

---

## 🧪 Running Automated Tests

Run the full automated test suite (60 unit and integration tests covering all agents and endpoints):

```bash
.\venv\Scripts\activate
python -m unittest discover -p "test_*.py" -v
```

All 60 tests execute deterministically against real and synthetic financial datasets.

---

## 📁 Repository Structure

```
├── agents/
│   ├── comparison_agent.py       # Cross-company metric comparisons & differences
│   ├── document_agent.py         # PDF processing coordination
│   ├── extraction_agent.py       # P&L statement parsing & revenue extraction
│   ├── red_flag_agent.py         # Year-over-year revenue decline detection
│   ├── report_agent.py           # Executive Summary & Key Financials assembly
│   └── research_agent.py         # Grounded question answering with citations
├── services/
│   ├── chunker.py                # Overlapping text chunk generation
│   ├── embedder.py               # SentenceTransformers embedding generation
│   ├── parser.py                 # PyMuPDF text & page extraction
│   └── vector_store.py           # ChromaDB search & collection management
├── api_client.py                 # Frontend HTTP client for FastAPI communication
├── app.py                        # Streamlit web application
├── database.py                   # SQLite connection & session management
├── main.py                       # FastAPI application & API endpoints
├── models.py                     # SQLAlchemy database models (Sessions, Documents)
├── orchestrator.py               # Document ingestion pipeline orchestration
├── requirements.txt              # Project runtime dependencies
├── schemas.py                    # Pydantic request and response models
├── test_comparison_agent.py      # Unit & integration tests for Comparison Agent
├── test_conversational_api.py    # Unit & integration tests for Conversational API
├── test_red_flag_agent.py        # Unit tests for Red Flag Agent
├── test_report_agent.py          # Unit & integration tests for Report Agent
└── test_research_agent.py        # Unit & integration tests for Research Agent
```

---

## 🔒 Security & Privacy

- **Local Execution**: Document processing, table extraction, vector storage, and all mathematical calculations execute locally on your machine.
- **Model Downloads & Offline Operation**: The SentenceTransformers embedding model (`all-MiniLM-L6-v2`) downloads its model weights from Hugging Face Hub on its initial first run and caches them locally; subsequent executions run fully offline on the local CPU without external API calls or transmitting document text to cloud LLMs.
- **Evidence-Grounded**: All financial math (growth rates, differences) is computed via deterministic Python arithmetic, eliminating hallucination risks.
- **Git Exclusions**: Heavy binary files, PDF uploads, local databases (`research.db`), and ChromaDB embeddings (`data/`) are excluded from version control via `.gitignore`.
