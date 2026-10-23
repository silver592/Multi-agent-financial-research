import streamlit as st
import pandas as pd
from api_client import APIClient

st.set_page_config(
    page_title="Financial Research AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if "api_url" not in st.session_state:
    st.session_state["api_url"] = "http://127.0.0.1:8000"

if "current_session_id" not in st.session_state:
    st.session_state["current_session_id"] = "8b14afa0-9d0a-4487-8c2f-ff6f9588c276"  # Reliance Research

if "current_session_name" not in st.session_state:
    st.session_state["current_session_name"] = "Reliance Financial Research"

if "current_document_id" not in st.session_state:
    st.session_state["current_document_id"] = "87bee45d-2ab7-4ee9-8724-8635305692be"

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

if "session_documents" not in st.session_state:
    st.session_state["session_documents"] = []

client = APIClient(st.session_state["api_url"])

# ----------------------------------------------------
# SIDEBAR
# ----------------------------------------------------
with st.sidebar:
    st.title("📊 Financial Research AI")
    st.caption("Multi-Agent AI Analysis System for Financial Research and Business Insights")
    st.divider()

    # Backend Connection
    st.subheader("⚙️ Backend Configuration")
    api_input = st.text_input("FastAPI Base URL", value=st.session_state["api_url"])
    if api_input != st.session_state["api_url"]:
        st.session_state["api_url"] = api_input
        client = APIClient(api_input)
        st.rerun()

    is_connected, conn_msg = client.check_health()
    if is_connected:
        st.success(f"🟢 {conn_msg}")
    else:
        st.error(f"🔴 {conn_msg}")

    st.divider()

    # Session Management
    st.subheader("📁 Session Management")
    st.write(f"**Current Session:** `{st.session_state['current_session_id'][:8]}...`" if st.session_state['current_session_id'] else "**No Session Selected**")
    if st.session_state.get("current_session_name"):
        st.caption(f"Name: {st.session_state['current_session_name']}")

    # Start new session
    with st.expander("➕ Create New Session"):
        new_sess_name = st.text_input("Session Name", placeholder="e.g. Q4 Competitor Analysis")
        if st.button("Create Session", use_container_width=True):
            if new_sess_name.strip():
                sess_data, err = client.create_session(new_sess_name.strip())
                if sess_data:
                    st.session_state["current_session_id"] = sess_data["id"]
                    st.session_state["current_session_name"] = sess_data["name"]
                    st.session_state["current_document_id"] = None
                    st.session_state["chat_history"] = []
                    st.session_state["session_documents"] = []
                    st.success("Session created!")
                    st.rerun()
                else:
                    st.error(f"Failed: {err}")
            else:
                st.warning("Please enter a session name.")

    # Select existing session
    with st.expander("🔍 Switch Session ID"):
        manual_sess_id = st.text_input("Enter Session ID", value=st.session_state["current_session_id"] or "")
        if st.button("Load Session", use_container_width=True):
            if manual_sess_id.strip():
                sess_data, err = client.get_session(manual_sess_id.strip())
                if sess_data:
                    st.session_state["current_session_id"] = sess_data["id"]
                    st.session_state["current_session_name"] = sess_data["name"]
                    st.session_state["chat_history"] = []
                    # Load docs for this session
                    docs, _ = client.list_documents(sess_data["id"])
                    st.session_state["session_documents"] = docs or []
                    if docs:
                        st.session_state["current_document_id"] = docs[-1]["id"]
                    else:
                        st.session_state["current_document_id"] = None
                    st.success("Loaded session!")
                    st.rerun()
                else:
                    st.error(f"Session not found: {err}")

    # Active Document Selection in Session
    if st.session_state["current_session_id"] and is_connected:
        docs, _ = client.list_documents(st.session_state["current_session_id"])
        if docs:
            st.session_state["session_documents"] = docs
            doc_options = {d["id"]: f"{d['filename']} ({d['id'][:8]}...)" for d in docs}
            curr_id = st.session_state["current_document_id"]
            if curr_id not in doc_options:
                curr_id = docs[-1]["id"]
                st.session_state["current_document_id"] = curr_id

            selected_doc_id = st.selectbox(
                "Active Document",
                options=list(doc_options.keys()),
                format_func=lambda x: doc_options[x],
                index=list(doc_options.keys()).index(curr_id) if curr_id in doc_options else 0,
            )
            st.session_state["current_document_id"] = selected_doc_id
        else:
            st.info("No documents uploaded in this session yet.")
            st.session_state["current_document_id"] = None

    st.divider()

    # Navigation
    nav_selection = st.radio(
        "Navigation",
        [
            "🏠 Home",
            "📤 Document Upload",
            "💬 Research Chat",
            "🚩 Red Flag Analysis",
            "⚖️ Company Comparison",
            "📄 Reports",
        ],
        index=0,
    )


# ----------------------------------------------------
# 1. HOME
# ----------------------------------------------------
if nav_selection == "🏠 Home":
    st.title("Financial Research AI")
    st.subheader("Multi-Agent AI Analysis System for Financial Research and Business Insights")
    st.write(
        """
        Welcome to the Financial Research AI workspace. This platform orchestrates specialized autonomous agents
        to analyze corporate financial reports (10-K, annual reports, financial statements) deterministically and with
        strict evidence grounding.
        """
    )

    st.info(
        f"**Active Session:** `{st.session_state['current_session_id'] or 'None'}` | "
        f"**Active Document:** `{st.session_state['current_document_id'] or 'None'}`"
    )

    st.markdown("### 🚀 Core Agent Capabilities")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 1. Document & Extraction Agent")
        st.write("Parses PDF tables and chunks financial reports with PyMuPDF, ChromaDB embeddings, and regularized table extractors.")
    with col2:
        st.markdown("#### 2. Research & Red Flag Agent")
        st.write("Answers natural language questions with source page citations and detects year-over-year revenue declines with severity ratings.")
    with col3:
        st.markdown("#### 3. Comparison & Report Agent")
        st.write("Computes absolute & signed differences across corporate annual reports, compiles Executive Summaries, and builds Key Financials.")

    st.markdown("---")
    st.markdown("### 📋 Recommended Workflow")
    st.markdown(
        """
        1. **Document Upload**: Upload an annual report PDF with company name, year, and statement type.
        2. **Research Chat**: Ask natural language financial questions. View citations showing page numbers and chunks.
        3. **Red Flag Analysis**: Run automated checks for financial concerns and revenue contractions.
        4. **Company Comparison**: Compare two or more annual reports across revenue and net profit.
        5. **Reports**: Generate an Executive Summary and Key Financials report for the active document.
        """
    )


# ----------------------------------------------------
# 2. DOCUMENT UPLOAD
# ----------------------------------------------------
elif nav_selection == "📤 Document Upload":
    st.title("📤 Financial Document Upload")
    st.caption("Upload annual reports and financial statements to index with Document & Extraction Agents.")

    if not st.session_state["current_session_id"]:
        st.warning("Please create or select a Research Session from the sidebar first.")
    else:
        st.write(f"Target Session: `{st.session_state['current_session_id']}` ({st.session_state.get('current_session_name', '')})")

        uploaded_file = st.file_uploader("Select Financial Report (PDF)", type=["pdf"])

        col1, col2, col3 = st.columns(3)
        with col1:
            company_input = st.text_input("Company Name", placeholder="e.g. Reliance Industries Limited")
        with col2:
            doc_type_input = st.selectbox("Document Type", ["Annual Report", "10-K", "Quarterly Report", "Financial Statement"])
        with col3:
            year_input = st.number_input("Financial Year", min_value=2000, max_value=2030, value=2025)

        if uploaded_file is not None:
            st.write(f"📁 **File:** `{uploaded_file.name}` ({round(uploaded_file.size / (1024*1024), 2)} MB)")

            if st.button("🚀 Upload and Process Document", type="primary"):
                if not company_input.strip():
                    st.warning("Please specify the Company Name.")
                else:
                    with st.spinner("Processing PDF: parsing pages, chunking text, generating embeddings, and extracting revenue... (this may take 20-40 seconds)"):
                        file_bytes = uploaded_file.read()
                        result, err = client.upload_document(
                            session_id=st.session_state["current_session_id"],
                            file_bytes=file_bytes,
                            filename=uploaded_file.name,
                            company=company_input.strip(),
                            document_type=doc_type_input,
                            year=int(year_input),
                        )

                        if result:
                            new_doc_id = result.get("document", {}).get("id")
                            st.session_state["current_document_id"] = new_doc_id
                            st.success(f"Document uploaded and processed successfully! Document ID: `{new_doc_id}`")

                            analysis = result.get("analysis", {})
                            st.markdown("#### Initial Pipeline Analysis Summary:")
                            doc_meta = analysis.get("document", {})
                            st.write(f"- **Pages processed:** {doc_meta.get('pages')}")
                            st.write(f"- **Chunks embedded:** {doc_meta.get('chunks')}")
                            st.write(f"- **Revenue candidates found:** {analysis.get('revenue_extraction', {}).get('candidates_found')}")
                            st.write(f"- **Red flags detected:** {analysis.get('red_flags', {}).get('red_flag_count')}")

                            # Refresh documents list
                            docs, _ = client.list_documents(st.session_state["current_session_id"])
                            st.session_state["session_documents"] = docs or []
                        else:
                            st.error(f"Upload failed: {err}")


# ----------------------------------------------------
# 3. RESEARCH CHAT
# ----------------------------------------------------
elif nav_selection == "💬 Research Chat":
    st.title("💬 Conversational Financial Research")
    st.caption("Ask natural language financial questions. Answers are deterministically grounded with exact PDF citations.")

    if not st.session_state["current_session_id"]:
        st.warning("Please create or select a Research Session from the sidebar first.")
    else:
        st.info(f"Session: `{st.session_state['current_session_id']}` | Active Document: `{st.session_state['current_document_id'] or 'None'}`")

        # Display Chat History
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if msg.get("citations"):
                    with st.expander("📚 Source Citations & Evidence"):
                        for idx, cite in enumerate(msg["citations"], 1):
                            st.markdown(f"**Citation {idx}:**")
                            st.write(f"- **Document ID:** `{cite.get('document_id')}`")
                            st.write(f"- **Page Number:** {cite.get('page_number')}")
                            st.write(f"- **Statement Type:** {cite.get('statement_type') or 'N/A'}")
                            st.write(f"- **Chunk ID:** `{cite.get('chunk_id') or 'N/A'}`")
                            if cite.get("source_text"):
                                st.caption(f"Excerpt: {cite['source_text'][:300]}...")
                if msg.get("limitations"):
                    st.warning("Limitations: " + "; ".join(msg["limitations"]))

        # Chat Input
        user_query = st.chat_input("e.g. What was the consolidated revenue in FY 2024-25 and FY 2023-24, and what was the percentage change?")
        if user_query:
            # Append User message
            st.session_state["chat_history"].append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.write(user_query)

            # Query Backend
            with st.chat_message("assistant"):
                with st.spinner("Analyzing financial report, extracting verified figures, and checking citations..."):
                    res, err = client.research_session(
                        session_id=st.session_state["current_session_id"],
                        question=user_query,
                        document_id=st.session_state["current_document_id"],
                    )

                    if res:
                        ans_text = res.get("answer", "No answer returned.")
                        citations = res.get("citations", [])
                        limitations = res.get("limitations", [])

                        st.write(ans_text)

                        if citations:
                            with st.expander("📚 Source Citations & Evidence"):
                                for idx, cite in enumerate(citations, 1):
                                    st.markdown(f"**Citation {idx}:**")
                                    st.write(f"- **Document ID:** `{cite.get('document_id')}`")
                                    st.write(f"- **Page Number:** {cite.get('page_number')}")
                                    st.write(f"- **Statement Type:** {cite.get('statement_type') or 'N/A'}")
                                    st.write(f"- **Chunk ID:** `{cite.get('chunk_id') or 'N/A'}`")
                                    if cite.get("source_text"):
                                        st.caption(f"Excerpt: {cite['source_text'][:300]}...")

                        if limitations:
                            st.warning("Limitations: " + "; ".join(limitations))

                        st.session_state["chat_history"].append({
                            "role": "assistant",
                            "content": ans_text,
                            "citations": citations,
                            "limitations": limitations,
                        })
                    else:
                        st.error(f"Research failed: {err}")


# ----------------------------------------------------
# 4. RED FLAG ANALYSIS
# ----------------------------------------------------
elif nav_selection == "🚩 Red Flag Analysis":
    st.title("🚩 Red Flag Analysis")
    st.caption("Evaluates extracted financial statement lines to identify qualifying year-over-year revenue contractions.")

    target_doc = st.session_state["current_document_id"]
    st.text_input("Target Document ID", value=target_doc or "", key="rf_target_doc")

    if st.button("🔍 Run Red Flag Analysis", type="primary"):
        doc_id = st.session_state["rf_target_doc"]
        if not doc_id:
            st.warning("Please provide a valid Document ID.")
        else:
            with st.spinner("Analyzing revenue candidates for decline warnings..."):
                res, err = client.analyze_red_flags(doc_id.strip())
                if res:
                    st.success("Analysis complete.")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Analyzed Statements", res.get("analyzed_candidates", 0))
                    c2.metric("Red Flags Detected", res.get("red_flag_count", 0))
                    c3.metric("Skipped Rows", res.get("skipped_candidates", 0))

                    flags = res.get("red_flags", [])
                    if flags:
                        st.markdown("### ⚠️ Identified Concerns")
                        for f in flags:
                            sev = f.get("severity", "medium").upper()
                            alert_box = st.error if sev == "HIGH" else st.warning
                            with alert_box(f"**{f.get('flag_id')} [{sev} SEVERITY]: {f.get('title')}**"):
                                st.write(f.get("description"))
                                ev = f.get("evidence", {})
                                if ev:
                                    st.write(f"- **Current Value:** {ev.get('current_value'):,} {ev.get('unit')}")
                                    st.write(f"- **Previous Value:** {ev.get('previous_value'):,} {ev.get('unit')}")
                                    st.write(f"- **Decline Percentage:** `{ev.get('change_percent')}%`")
                                cit = f.get("citation", {})
                                if cit:
                                    st.caption(f"Source: Page {cit.get('page_number')}, Statement: {cit.get('statement_type')}")
                    else:
                        st.info("✅ No revenue decline red flags were identified across analyzed statements.")
                else:
                    st.error(f"Analysis failed: {err}")


# ----------------------------------------------------
# 5. COMPANY COMPARISON
# ----------------------------------------------------
elif nav_selection == "⚖️ Company Comparison":
    st.title("⚖️ Company & Document Comparison")
    st.caption("Compares financial metrics (revenue and net profit) across multiple indexed documents.")

    col1, col2 = st.columns(2)
    with col1:
        doc1_input = st.text_input("Document ID 1 (e.g. Reliance Industries)", value="87bee45d-2ab7-4ee9-8724-8635305692be")
    with col2:
        doc2_input = st.text_input("Document ID 2 (e.g. Infosys)", value="40b20e4f-dc46-421b-808d-d219a0b96460")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        fy_input = st.selectbox("Financial Year", ["FY 2024-25", "FY 2023-24"])
    with col_b:
        basis_input = st.selectbox("Reporting Basis", ["consolidated", "standalone"])
    with col_c:
        ref_doc_choice = st.selectbox("Reference Document for % Diff", ["Document 1", "Document 2"])
        ref_doc_id = doc1_input if ref_doc_choice == "Document 1" else doc2_input

    metrics_selected = st.multiselect("Metrics to Compare", ["revenue", "net_profit"], default=["revenue", "net_profit"])

    if st.button("⚖️ Compare Financial Metrics", type="primary"):
        if not doc1_input or not doc2_input:
            st.warning("Please supply two distinct document IDs.")
        elif doc1_input.strip() == doc2_input.strip():
            st.warning("Please supply two different document IDs.")
        else:
            with st.spinner("Comparing metrics across documents with strict document isolation..."):
                res, err = client.compare_documents(
                    document_ids=[doc1_input.strip(), doc2_input.strip()],
                    financial_year=fy_input,
                    reporting_basis=basis_input,
                    metrics=metrics_selected,
                    reference_document_id=ref_doc_id.strip(),
                )

                if res:
                    st.success("Comparison completed.")
                    for item in res.get("metrics", []):
                        st.subheader(f"Metric: `{item.get('metric').upper()}` ({item.get('financial_year')}, {item.get('reporting_basis')})")
                        st.write(f"Status: `{item.get('status')}` | Unit: `{item.get('unit')}`")

                        vals = item.get("values", [])
                        if vals:
                            table_rows = []
                            for v in vals:
                                table_rows.append({
                                    "Company": v.get("company"),
                                    "Value": f"{v.get('value'):,}",
                                    "Unit": v.get("unit"),
                                    "Page": v.get("page"),
                                    "Document ID": v.get("document_id")[:8] + "...",
                                })
                            st.table(pd.DataFrame(table_rows))

                        diff_col1, diff_col2, diff_col3 = st.columns(3)
                        diff_col1.metric("Absolute Difference", f"{item.get('absolute_difference'):,}" if item.get('absolute_difference') is not None else "N/A")
                        diff_col2.metric("Signed Difference", f"{item.get('signed_difference'):,}" if item.get('signed_difference') is not None else "N/A")
                        diff_col3.metric("Percentage Difference", f"{item.get('percentage_difference')}%" if item.get('percentage_difference') is not None else "N/A")
                        st.caption(f"Percentage Reference: `{item.get('percentage_reference')}`")
                        st.divider()

                    if res.get("limitations"):
                        st.info("Limitations: " + "; ".join(res["limitations"]))
                else:
                    st.error(f"Comparison failed: {err}")


# ----------------------------------------------------
# 6. REPORTS
# ----------------------------------------------------
elif nav_selection == "📄 Reports":
    st.title("📄 Financial Report Generator")
    st.caption("Assembles Executive Summary and Key Financials into a structured initial financial report.")

    col1, col2 = st.columns(2)
    with col1:
        rep_doc = st.text_input("Document ID", value=st.session_state["current_document_id"] or "87bee45d-2ab7-4ee9-8724-8635305692be")
    with col2:
        rep_basis = st.selectbox("Reporting Basis", ["consolidated", "standalone"], index=0)

    if st.button("📑 Generate Report", type="primary"):
        if not rep_doc:
            st.warning("Please specify a Document ID.")
        else:
            with st.spinner("Extracting verified metrics, building Executive Summary, and assembling report..."):
                res, err = client.generate_document_report(
                    document_id=rep_doc.strip(),
                    reporting_basis=rep_basis,
                )

                if res:
                    st.success("Report Generated!")
                    st.subheader(f"Report for {res.get('company', 'Company')} ({res.get('reporting_basis', '').capitalize()})")
                    st.caption(f"Report ID: `{res.get('report_id')}` | Document ID: `{res.get('document_id')}`")

                    # Executive Summary
                    exec_sum = res.get("executive_summary", {})
                    st.markdown("### 📌 Executive Summary")
                    st.write(exec_sum.get("summary_text", ""))

                    if exec_sum.get("highlights"):
                        st.markdown("#### 🌟 Key Highlights:")
                        for h in exec_sum["highlights"]:
                            st.write(f"- {h}")

                    if exec_sum.get("red_flags"):
                        st.markdown("#### 🚩 Red Flag Summary:")
                        for rf in exec_sum["red_flags"]:
                            st.write(f"- {rf}")

                    # Key Financials
                    st.markdown("### 📊 Key Financials")
                    kf = res.get("key_financials", [])
                    if kf:
                        kf_table = []
                        for row in kf:
                            kf_table.append({
                                "Metric": row.get("metric").capitalize(),
                                "Financial Year": row.get("financial_year"),
                                "Value": f"{row.get('value'):,}",
                                "Unit": row.get("unit"),
                                "Basis": row.get("reporting_basis"),
                                "Page": row.get("page"),
                                "Chunk ID": row.get("chunk_id"),
                            })
                        st.table(pd.DataFrame(kf_table))
                    else:
                        st.info("No key financials found for this reporting basis.")

                    # Citations
                    cits = res.get("citations", [])
                    if cits:
                        with st.expander("📚 Source Citations"):
                            for idx, c in enumerate(cits, 1):
                                st.write(f"**Citation {idx}:** Page {c.get('page_number')} ({c.get('statement_type')}) - `{c.get('chunk_id')}`")
                                if c.get("source_text"):
                                    st.caption(f"Excerpt: {c['source_text'][:250]}...")

                    if res.get("limitations"):
                        st.warning("Limitations: " + "; ".join(res["limitations"]))
                else:
                    st.error(f"Report generation failed: {err}")
