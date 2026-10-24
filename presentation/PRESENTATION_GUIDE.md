# PowerPoint Presentation Guide & Viva Speaking Notes

**Project Title:** Multi-Agent AI Analysis System for Financial Research and Business Insights  
**Internship:** Infosys Springboard AI Virtual Internship (2026)  
**Editable Presentation File:** `presentation/Infosys_Springboard_Financial_Research_AI.pptx`

---

## 🎨 Slide Design Overview
- **Aspect Ratio:** 16:9 Widescreen (13.333" x 7.5")
- **Color Palette:**
  - Background: Clean White (`#FFFFFF`) with Soft Card Backgrounds (`#F8FAFC`)
  - Primary Corporate Brand: Dark Navy Blue (`#0F2240`)
  - Accent / Highlights: Royal Accent Blue (`#1E5AA0`)
  - Body Text: Charcoal Slate (`#1E293B`) and Muted Grey (`#64748B`)
  - Border Lines: Soft Slate (`#E2E8F0`)
- **Total Slides:** 8 concise, professional slides.

---

## 🗣️ Slide-by-Slide Walkthrough & Viva Script

### Slide 1: Title Slide
- **Title:** Multi-Agent AI Analysis System for Financial Research and Business Insights
- **Subtitle:** An evidence-grounded agentic platform for corporate annual report analysis and competitor benchmarking
- **Metadata Cards:**
  - Intern / Developer: `[Your Name / Intern ID]` (Infosys Springboard Virtual Internship)
  - Project Domain: Agentic AI & Financial Analytics (Document Extraction, RAG & Risk Detection)
  - Mentorship: `[Mentor Name / Infosys Mentor]`, Year 2026
- **What to Say:**
  > *"Good morning respected mentors. Today, I am presenting my Infosys Springboard AI internship project titled 'Multi-Agent AI Analysis System for Financial Research and Business Insights'. In this project, I designed and developed an autonomous, multi-agent AI system that reads complex corporate annual reports, extracts key financial metrics, detects revenue decline risks, and performs cross-company comparisons—with 100% of claims grounded in verified PDF page citations."*

---

### Slide 2: Problem Statement & Project Objectives
- **Left Column (The Problem):**
  - **Information Overload:** Corporate annual reports (10-Ks, Integrated Reports) often span 300 to 500 pages, making manual analysis slow and prone to oversight.
  - **Hallucination in Generic AI:** Standard generative chatbots frequently invent financial numbers or make arithmetic mistakes when computing growth rates.
  - **Reporting Basis Confusion:** Existing tools mix consolidated (group-level) and standalone (parent-only) statements.
  - **Lack of Traceability:** Financial analysts cannot rely on AI outputs without exact source page citations.
- **Right Column (Project Objectives):**
  - **Automated Ingestion:** Parse PDFs page-by-page using PyMuPDF and generate local ChromaDB vector embeddings.
  - **Deterministic Extraction:** Reliably extract Revenue from Operations and Net Profit across multiple years.
  - **Strict Evidence Grounding:** Answer natural language questions where every claim attaches the exact PDF page number and chunk ID.
  - **Automated Red-Flag Detection:** Detect year-over-year revenue contractions with severity ratings (medium vs. high).
  - **Competitor Benchmarking:** Align metrics across two or more corporate reports and compute absolute and percentage differences.
- **What to Say:**
  > *"The core problem we address is the unreliability of traditional AI in financial research. Annual reports are 400 pages long, and when analysts ask generic chatbots for revenue numbers, the models often hallucinate or mix consolidated group figures with standalone parent numbers. Our objective was to build a deterministic, multi-agent platform where every extracted number and calculation is verified, auditable, and cited directly from the PDF."*

---

### Slide 3: System Architecture & End-to-End Workflow
- **Horizontal Pipeline Diagram:**
  1. `1. INGESTION`: PDF Upload → PyMuPDF (`fitz`) Text Extraction.
  2. `2. CHUNKING`: 500-character overlapping chunks with page metadata.
  3. `3. EMBEDDING`: `all-MiniLM-L6-v2` generating 384-dimensional vectors stored in ChromaDB.
  4. `4. EXTRACTION`: Pattern rules locating verified P&L statement rows for Revenue and Net Profit.
  5. `5. AGENT LAYER`: Research Agent, Red Flag Agent, and Comparison Agent coordinating in memory.
  6. `6. SYNTHESIS`: Executive Summary & Key Financials assembled into JSON and displayed on Streamlit.
- **Key Architecture Cards:**
  - **Data Storage Layer:** SQLite with SQLAlchemy ORM for sessions and document records; ChromaDB for vector retrieval with document ID filtering.
  - **Deterministic Processing Layer:** Python arithmetic for zero-hallucination percentage changes; verified P&L anchoring for net profit.
- **What to Say:**
  > *"This slide illustrates our system architecture and data pipeline. When a user uploads a PDF, the Document Agent parses the text using PyMuPDF, chunks it, and creates vector embeddings using the local all-MiniLM-L6-v2 model in ChromaDB. The Extraction Agent identifies formal P&L statement pages to pull revenue and net profit figures. Downstream agents query these verified records, perform mathematical calculations in Python, and assemble the final output."*

---

### Slide 4: Multi-Agent System: Specialized Roles & Interactions
- **The 6 Modular Agents (Grid of 6 Cards):**
  1. **Document Agent (`services/parser.py`, `chunker.py`):** Coordinates text parsing, chunking, and ChromaDB vector indexing.
  2. **Extraction Agent (`agents/extraction_agent.py`):** Parses P&L statement rows, extracts revenue, and handles OCR character replacements (e.g. Greek symbols in OCR).
  3. **Red Flag Agent (`agents/red_flag_agent.py`):** Evaluates year-over-year revenue contractions and flags warnings (`medium` for <20% decline, `high` for >=20% decline).
  4. **Research Agent (`agents/research_agent.py`):** Answers conversational financial queries with document isolation and exact page citations.
  5. **Comparison Agent (`agents/comparison_agent.py`):** Compares metrics across multiple companies (e.g. Reliance vs. Infosys), computing absolute and percentage differences.
  6. **Report Agent (`agents/report_agent.py`):** Synthesizes outputs into an Executive Summary and Key Financials report.
- **What to Say:**
  > *"Instead of relying on a monolithic prompt, our system divides tasks across 6 specialized agents. Each agent has a single responsibility: the Document Agent manages vector search; the Extraction Agent parses financial tables; the Red Flag Agent evaluates risk heuristics; the Research Agent handles question answering; the Comparison Agent performs competitor benchmarking; and the Report Agent synthesizes the executive summary. This separation of concerns ensures that if extraction logic changes, the research and comparison agents remain unaffected."*

---

### Slide 5: Technology Stack & Technical Decisions
- **Three Core Pillars:**
  - **Backend Architecture:** Python 3.12, FastAPI (REST API with OpenAPI/Swagger docs), and SQLite with SQLAlchemy.
  - **Vector Retrieval & Parsing:** PyMuPDF (`fitz`) for fast text extraction; ChromaDB for vector storage with metadata filtering; SentenceTransformers (`all-MiniLM-L6-v2`) for local 384-dimensional dense vectors.
  - **Frontend & Testing:** Streamlit web application decoupled via an `APIClient` using Python `requests`; comprehensive `unittest` suite with 60 passing tests.
- **Key Decision Highlight:** Zero external cloud LLM dependencies for core extraction and arithmetic—meaning zero API costs, zero data privacy risks, and no hallucinated numbers.
- **What to Say:**
  > *"Our technology stack was selected for speed, privacy, and determinism. We chose FastAPI for its high-performance asynchronous endpoints and automatic Swagger documentation. For embeddings, we run SentenceTransformers locally on CPU, ensuring that confidential company documents never leave the local environment and eliminating recurring API costs. Finally, our test suite contains 60 automated unit and integration tests that validate all agents."*

---

### Slide 6: Implementation Results: Validated Financial Outputs
- **Dataset Context:** Reliance Industries Limited Integrated Annual Report 2024-25.
- **Result 1 (Consolidated Revenue Q&A):**
  - FY 2024-25: ₹980,136 Cr vs. FY 2023-24: ₹914,472 Cr.
  - Calculated Growth: `+7.18%`.
  - Citation: Page 100, Chunk `..._p100_c866`, Consolidated Financial Statements.
- **Result 2 (Red Flag Detection - Standalone Contraction):**
  - FY 2024-25: ₹532,792 Cr vs. FY 2023-24: ₹547,942 Cr.
  - Calculated Decline: `-2.76%` → Triggered `RF001 (Medium Severity)`.
  - Citation: Page 58, Chunk `..._p58_c546`, Standalone Financial Statements.
- **Result 3 (Report Agent & Competitor Benchmarking):**
  - Reliance vs. Infosys: ₹980,136 Cr vs. ₹162,990 Cr (Absolute Diff: ₹817,146 Cr, `-83.37%`).
  - TCS Benchmark: ₹255,324 Cr (Page 181).
- **What to Say:**
  > *"Here are actual outputs from our implementation tested on the Reliance Industries 2024-25 annual report. When asked for consolidated revenue, the Research Agent returned ₹980,136 crore for FY25 and ₹914,472 crore for FY24, calculating a 7.18% increase and citing Page 100. Furthermore, when analyzing standalone statements, the Red Flag Agent caught a 2.76% revenue contraction from ₹547,942 crore down to ₹532,792 crore, triggering a Medium-severity warning citing Page 58. We also benchmarked Reliance against Infosys and TCS."*

---

### Slide 7: Project Limitations & Future Enhancements
- **Current Limitations:**
  - **Scoped Metrics:** Extraction focuses on core Income Statement figures (Revenue and Net Profit); Balance Sheet items (Total Debt, Cash Flow) require additional extractor patterns.
  - **Text-Based PDF Dependency:** PyMuPDF extracts embedded text layers; scanned image-only PDFs without OCR text require pre-processing.
  - **Local Embedding Latency:** Ingesting very large reports (400+ pages) takes ~25–40 seconds on local CPU.
- **Future Roadmap:**
  - **Deep Learning Table Extraction:** Integrate LayoutLM or Table Transformers for complex, multi-header bordered tables.
  - **Expanded Metrics:** Add EBITDA, Operating Margin, Earnings Per Share (EPS), and Free Cash Flow extraction.
  - **Automated PDF Export:** Add a one-click downloadable PDF report generator with automated charts.
  - **Enterprise Scaling:** Transition SQLite to PostgreSQL and deploy ChromaDB as a distributed cluster.
- **What to Say:**
  > *"While the core system is fully functional, we acknowledge specific technical boundaries. Currently, we extract revenue and net profit from income statements; expanding to debt and cash flows is the next step. In the future roadmap, we plan to incorporate vision-based table transformers for complex borderless tables and add automated PDF report exports with visual trend charts."*

---

### Slide 8: Conclusion & Project Summary
- **Key Takeaways:**
  - **Deterministic Accuracy:** Zero-hallucination calculations by executing math in Python rather than generative LLM text prediction.
  - **Complete Audit Trail:** Every factual claim links to an exact PDF page number and text excerpt.
  - **Specialized Multi-Agent Synergy:** 6 modular agents communicate via clean Pydantic schemas.
  - **Software Engineering Standards:** Backed by 60 passing tests, clean REST API endpoints in FastAPI, and a full Streamlit interface.
- **Closing Statement:** *"Thank you! Open for Questions & Viva Discussion."*
- **What to Say:**
  > *"In conclusion, this project demonstrates how Agentic AI can solve the reliability and hallucination challenges of corporate financial research. By combining modular agents, local vector retrieval, and deterministic arithmetic, we have built a dependable research assistant that delivers audited, cited financial insights in seconds. Thank you mentors, I am now ready for your questions."*

---

## 🎯 Top 5 Viva Questions to Expect & How to Answer

1. **Q: Why did you not use an external LLM like GPT-4 or Gemini for the calculations?**
   - **A:** *"Generative LLMs predict text based on statistical probabilities and frequently make arithmetic errors when computing percentages. By parsing the exact figures into Python and executing the arithmetic deterministically, we guarantee 100% calculation accuracy with zero hallucination."*

2. **Q: How does the system distinguish between Consolidated and Standalone statements?**
   - **A:** *"Our Extraction Agent scans the page header context and structural tokens across chunks. If a page contains 'Standalone Financial Statements', it flags candidates as standalone; if it contains 'Consolidated Financial Statements', it isolates them as consolidated. This ensures parent company and group numbers are never mixed."*

3. **Q: What is the purpose of ChromaDB in your project?**
   - **A:** *"ChromaDB serves as our local vector database. When a PDF is chunked into 500-character segments, we generate 384-dimensional embeddings using SentenceTransformers. ChromaDB indexes these embeddings along with metadata like document ID and page number, enabling sub-second similarity search while strictly isolating documents from different companies."*

4. **Q: How do you evaluate that an agent did not produce an invented citation?**
   - **A:** *"Our test suite includes specific tests (like `test_citation_preservation` and `test_missing_metadata_does_not_fabricate`). When an agent outputs a citation, we assert that the page number, chunk ID, and source text correspond to an actual chunk in the vector store. If metadata is missing from the PDF, the agent leaves the citation field as `None` rather than fabricating fake page numbers."*

5. **Q: How does the Streamlit frontend interact with the backend?**
   - **A:** *"The Streamlit frontend is completely decoupled from backend processing. We built an `APIClient` class in `api_client.py` using Python `requests`. When the user uploads a document or sends a chat message, Streamlit makes an HTTP POST request to FastAPI (`http://127.0.0.1:8000`), receives the structured JSON response, and renders it using native Streamlit chat bubbles, metric cards, and tables."*
