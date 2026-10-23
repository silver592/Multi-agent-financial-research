# agents/research_agent.py
# Milestone 3 - Phase 4: Research Agent
# Coordinates multi-part financial questions, evidence retrieval from ChromaDB,
# deterministic percentage change calculations, and integration with the
# Extraction Agent and Red Flag Agent.

import re
from typing import Optional, Any

from services.vector_store import get_document_chunks, search_chunks
from services.embedder import create_embedding
from agents.extraction_agent import extract_revenue
from agents.red_flag_agent import analyze_revenue_candidates

# Stopwords and common question framing words to isolate key subject terms
GENERIC_STOPWORDS = {
    "what", "was", "were", "the", "in", "two", "reported", "financial", "years",
    "did", "identify", "company", "companies", "firm", "corporation", "for", "on", "at", "of", "by", "is", "are",
    "with", "and", "or", "an", "a", "to", "this", "that", "these", "those",
    "from", "as", "it", "its", "has", "have", "had", "be", "been", "being",
    "do", "does", "done", "which", "who", "whom", "whose", "when", "where",
    "why", "how", "any", "all", "each", "every", "both", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "can", "will", "just", "should", "now", "also", "tell", "give", "show",
    "find", "explain", "describe", "discuss", "details", "information", "report",
    "agent", "red", "flag", "warning", "decline", "operation", "operations"
}

# Generic metric terms
FINANCIAL_METRIC_WORDS = {
    "revenue", "turnover", "sales", "income", "profit", "loss", "ebitda",
    "margin", "margins", "change", "growth", "increase", "decrease", "decline",
    "difference", "percent", "percentage", "rate", "warning", "warnings",
    "flag", "flags", "alert", "alerts", "risk", "risks", "figure", "figures",
    "amount", "amounts", "value", "values", "crore", "lakh", "million", "billion"
}

# Statement type markers
STATEMENT_TYPE_WORDS = {
    "consolidated", "standalone", "statement", "statements"
}

# Year and reporting period markers
YEAR_AND_PERIOD_WORDS = {
    "fy", "year", "years", "annual", "period", "quarter", "q1", "q2", "q3", "q4"
}


def parse_question_intents(question: str, company_name: Optional[str] = None) -> dict:
    """
    Decomposes the incoming user question into information requirements:
    - Company-level revenue in reported financial years
    - Target statement scope ('consolidated', 'standalone', or 'both')
    - Percentage change / growth
    - Red Flag Agent warnings
    - Specific topic terms for targeted document chunk search
    """
    q_clean = question.strip()
    q_lower = q_clean.lower()

    # Company name tokens to exclude from general topic searches
    company_words = set()
    if company_name:
        for w in re.findall(r"\b[a-z0-9]{2,}\b", company_name.lower()):
            company_words.add(w)
    company_words.update([
        "reliance", "industries", "ril", "tcs", "tata", "consultancy",
        "services", "infosys", "infy", "ltd", "limited"
    ])

    raw_words = re.findall(r"\b[a-z0-9]{2,}\b", q_lower)

    # Detect if user specifically requested consolidated or standalone
    wants_consolidated = "consolidated" in raw_words
    wants_standalone = "standalone" in raw_words

    statement_scope = "both"
    if wants_consolidated and not wants_standalone:
        statement_scope = "consolidated"
    elif wants_standalone and not wants_consolidated:
        statement_scope = "standalone"

    # Isolate substantive topic words that are not stopwords, metrics, years, or company tokens
    topic_words = []
    for w in raw_words:
        if (
            w in GENERIC_STOPWORDS
            or w in FINANCIAL_METRIC_WORDS
            or w in STATEMENT_TYPE_WORDS
            or w in YEAR_AND_PERIOD_WORDS
            or w in company_words
            or re.match(r"^\d+$", w)
        ):
            continue
        topic_words.append(w)

    # Check if question asks for company-level revenue from operations
    asks_company_revenue = bool(re.search(
        r"\b(company'?s?\s+revenue|revenue\s+from\s+operations|annual\s+revenue|total\s+revenue|reported\s+financial\s+years?|two\s+financial\s+years?|consolidated\s+revenue|standalone\s+revenue)\b",
        q_lower
    )) or (
        bool(re.search(r"\b(revenue|turnover|sales)\b", q_lower)) and not topic_words
    )

    # Check if question asks for percentage change
    asks_percentage = bool(re.search(
        r"\b(percentage\s+change|percent\s+change|percentage\s+growth|growth\s+rate|percentage|growth|increase|decrease|decline\s+percentage)\b",
        q_lower
    ))

    # Check if question asks for Red Flag Agent status / warnings
    asks_red_flags = bool(re.search(
        r"\b(red\s*flag|warning|warnings|decline\s+warning|risk\s+flag|alert|alerts)\b",
        q_lower
    ))

    return {
        "asks_company_revenue": asks_company_revenue,
        "asks_percentage": asks_percentage,
        "asks_red_flags": asks_red_flags,
        "statement_scope": statement_scope,
        "topic_words": topic_words,
    }


def calculate_percentage_change(current: float, previous: float) -> tuple[float, str]:
    """
    Deterministically calculates year-on-year percentage change in Python:
    ((current - previous) / previous) * 100
    """
    if previous <= 0:
        raise ValueError("Previous year value must be greater than zero for percentage calculation.")

    change_percent = ((current - previous) / previous) * 100.0
    change_rounded = round(change_percent, 2)

    formula = f"(({current:,} - {previous:,}) / {previous:,}) * 100 = {change_rounded:+.2f}%"
    return change_rounded, formula


def is_chunk_supporting_evidence(chunk_text: str, topic_words: list[str]) -> tuple[bool, list[str]]:
    """
    Evaluates whether a chunk provides genuine whole-word supporting evidence
    for the topic words, rather than substring or incidental fragments.
    """
    if not topic_words or not chunk_text:
        return False, []

    c_lower = chunk_text.lower()
    matched_words = []

    for w in topic_words:
        # Match as complete whole word using regex word boundaries
        if re.search(rf"\b{re.escape(w)}\b", c_lower):
            matched_words.append(w)

    # Relevance criteria:
    # 1. If 1 topic word: must match that exact whole word.
    # 2. If 2 topic words: both must match as whole words (e.g. 'sky' AND 'blue').
    # 3. If >= 3 topic words: at least 2 distinct words or >= 50% must match.
    if len(topic_words) == 1 and len(matched_words) == 1:
        return True, matched_words
    elif len(topic_words) == 2 and len(matched_words) == 2:
        return True, matched_words
    elif len(topic_words) >= 3 and len(matched_words) >= max(2, (len(topic_words) + 1) // 2):
        return True, matched_words

    return False, matched_words



def answer_research_question(document_id: str, question: str) -> dict:
    """
    Main entry point for the Research Agent.

    Workflow:
    1. Validates inputs.
    2. Identifies question requirements (revenue, percentage change, red flags, topics).
    3. Reuses Extraction Agent and Red Flag Agent for verified financial data.
    4. Performs targeted vector retrieval with strict document isolation.
    5. Calculates arithmetic deterministically.
    6. Formulates an evidence-grounded response with page and chunk-level citations.
    7. Documents any limitations where evidence is insufficient.
    """
    if not document_id or not str(document_id).strip():
        raise ValueError("Document ID cannot be empty.")

    if not question or not str(question).strip():
        raise ValueError("Question cannot be empty.")

    doc_id = str(document_id).strip()
    q_clean = question.strip()

    # Step 1: Check document chunks in ChromaDB and retrieve company name
    doc_chunks = get_document_chunks(doc_id)
    company = None
    if doc_chunks:
        company = doc_chunks[0].get("metadata", {}).get("company")

    intents = parse_question_intents(q_clean, company)
    asks_revenue = intents["asks_company_revenue"]
    asks_percentage = intents["asks_percentage"]
    asks_red_flags = intents["asks_red_flags"]
    statement_scope = intents["statement_scope"]
    topic_words = intents["topic_words"]

    findings = []
    citations = []
    limitations = []
    answer_parts = []

    # Step 2: Fetch revenue candidates if financial figures or red flags are needed
    all_candidates = []
    if asks_revenue or asks_percentage or asks_red_flags:
        all_candidates = extract_revenue(doc_id)
        if all_candidates and not company:
            company = all_candidates[0].get("company")

    # Scope candidates to specifically requested statement type ('consolidated' or 'standalone')
    candidates = all_candidates
    if statement_scope in ("consolidated", "standalone") and all_candidates:
        scoped = [c for c in all_candidates if c.get("statement_type") == statement_scope]
        if scoped:
            candidates = scoped

    def register_citation(source_meta: dict, statement_type: Optional[str] = None) -> dict:
        """Helper to create, enrich, and deduplicate structured citations."""
        chunk_id = source_meta.get("chunk_id")
        page_num = source_meta.get("page_number")

        # 1. Start with any source text present in source_meta
        src_text = (
            source_meta.get("source_text")
            or source_meta.get("original_text")
            or source_meta.get("chunk_text")
            or ""
        )

        # 2. Look up previously registered citations with the same chunk_id
        if not src_text and chunk_id:
            for existing in citations:
                if existing.get("chunk_id") == chunk_id and existing.get("source_text"):
                    src_text = existing["source_text"]
                    break

        # 3. Look up Extraction Agent candidates with the same chunk_id or page_number
        if not src_text and all_candidates:
            for cand in all_candidates:
                cand_src = cand.get("source", {})
                if chunk_id and cand_src.get("chunk_id") == chunk_id and cand_src.get("original_text"):
                    src_text = cand_src["original_text"]
                    break
                elif page_num and cand_src.get("page_number") == page_num and cand_src.get("original_text"):
                    src_text = cand_src["original_text"]
                    break

        # 4. Look up in doc_chunks by chunk_id or page_number
        if not src_text and doc_chunks:
            for dc in doc_chunks:
                if chunk_id and dc.get("chunk_id") == chunk_id and dc.get("chunk_text"):
                    src_text = dc["chunk_text"]
                    break
                elif page_num and dc.get("metadata", {}).get("page_number") == page_num and dc.get("chunk_text"):
                    src_text = dc["chunk_text"]
                    break

        citation_obj = {
            "document_id": source_meta.get("document_id", doc_id),
            "company": company or source_meta.get("company"),
            "page_number": page_num,
            "chunk_id": chunk_id,
            "statement_type": statement_type or source_meta.get("statement_type"),
            "source_text": src_text,
        }

        # Deduplicate citations by chunk_id, ensuring source_text is preserved
        for existing in citations:
            if existing.get("chunk_id") == chunk_id:
                if not existing.get("source_text") and src_text:
                    existing["source_text"] = src_text
                if not existing.get("statement_type") and citation_obj["statement_type"]:
                    existing["statement_type"] = citation_obj["statement_type"]
                return existing

        citations.append(citation_obj)
        return citation_obj

    # Step 3: Handle Revenue in reported financial years
    if asks_revenue:
        if candidates:
            rev_descriptions = []
            for cand in candidates:
                st_type = cand.get("statement_type", "unspecified")
                vals = cand.get("values_found", [])
                years = cand.get("financial_years_found", [])
                unit = cand.get("unit", "crore")
                source = cand.get("source", {})
                cite = register_citation(source, statement_type=st_type)

                if len(vals) >= 2 and len(years) >= 2:
                    desc = f"{st_type.capitalize()} revenue: Rs. {vals[0]:,} {unit} in FY {years[0]} vs Rs. {vals[1]:,} {unit} in FY {years[1]}"
                elif len(vals) >= 2:
                    desc = f"{st_type.capitalize()} revenue: Rs. {vals[0]:,} {unit} (current) vs Rs. {vals[1]:,} {unit} (previous)"
                elif len(vals) == 1:
                    desc = f"{st_type.capitalize()} revenue: Rs. {vals[0]:,} {unit}"
                else:
                    desc = f"{st_type.capitalize()} revenue: figures not parsed"

                rev_descriptions.append(desc)

                findings.append({
                    "part": "Revenue in reported financial years",
                    "claim": f"{st_type.capitalize()} revenue from operations was reported at {desc}.",
                    "evidence": f"Values found: {vals}; Financial years: {years}; Unit: {unit} (Source page {source.get('page_number')}).",
                    "citation": cite,
                    "figures": {
                        "statement_type": st_type,
                        "values": vals,
                        "financial_years": years,
                        "unit": unit,
                    },
                })

            company_label = f"For {company}, " if company else ""
            answer_parts.append(f"{company_label}" + "; ".join(rev_descriptions) + ".")
        else:
            limitations.append("Revenue from operations figures could not be extracted from the document.")
            findings.append({
                "part": "Revenue in reported financial years",
                "claim": "Revenue from operations figures were not detected in the formal financial statements.",
                "evidence": "Extraction Agent returned 0 verified revenue candidates for this document.",
                "citation": None,
                "figures": None,
            })
            answer_parts.append("Revenue from operations figures could not be extracted from the formal financial statements in this document.")

    # Step 4: Handle Percentage Change calculation
    if asks_percentage:
        if candidates:
            pct_descriptions = []
            for cand in candidates:
                st_type = cand.get("statement_type", "unspecified")
                vals = cand.get("values_found", [])
                years = cand.get("financial_years_found", [])
                unit = cand.get("unit", "crore")
                source = cand.get("source", {})
                cite = register_citation(source, statement_type=st_type)

                if (
                    len(vals) >= 2
                    and isinstance(vals[0], (int, float))
                    and isinstance(vals[1], (int, float))
                    and vals[1] > 0
                ):
                    curr, prev = vals[0], vals[1]
                    pct_round, formula_str = calculate_percentage_change(curr, prev)
                    direction = "increased" if pct_round > 0 else "decreased" if pct_round < 0 else "remained unchanged"
                    pct_str = f"{abs(pct_round):.2f}%"

                    desc = f"{st_type.capitalize()} revenue {direction} by {pct_str} ({formula_str})"
                    pct_descriptions.append(desc)

                    findings.append({
                        "part": "Percentage change calculation",
                        "claim": f"{st_type.capitalize()} revenue {direction} by {pct_str}.",
                        "evidence": f"Deterministic Python calculation: {formula_str} based on figures from page {source.get('page_number')}.",
                        "citation": cite,
                        "figures": {
                            "statement_type": st_type,
                            "current_value": curr,
                            "previous_value": prev,
                            "change_percent": pct_round,
                            "formula": formula_str,
                            "unit": unit,
                        },
                    })
                else:
                    limitations.append(f"Insufficient historical data to compute percentage change for {st_type} revenue.")

            if pct_descriptions:
                answer_parts.append("Percentage change: " + "; ".join(pct_descriptions) + ".")
        else:
            limitations.append("Cannot calculate percentage change because verified revenue figures were not found.")
            answer_parts.append("Percentage change could not be calculated due to lack of verified revenue figures.")

    # Step 5: Handle Red Flag Agent analysis
    if asks_red_flags:
        if candidates:
            red_flag_data = analyze_revenue_candidates(doc_id, candidates)
            rf_count = red_flag_data.get("red_flag_count", 0)
            red_flags = red_flag_data.get("red_flags", [])

            if rf_count > 0:
                flag_summaries = []
                for rf in red_flags:
                    rf_ev = rf.get("evidence", {})
                    rf_cit = rf.get("citation", {})
                    cite = register_citation(rf_cit, statement_type=rf_cit.get("statement_type"))
                    flag_summary = f"{rf.get('flag_id')} ({rf.get('severity')} severity): {rf.get('description')}"
                    flag_summaries.append(flag_summary)

                    findings.append({
                        "part": "Red Flag Agent analysis",
                        "claim": f"Red Flag Agent detected warning: {rf.get('title')} ({rf.get('severity')} severity).",
                        "evidence": f"{rf.get('description')} (Details: {rf_ev}, Citation: Page {rf_cit.get('page_number')}).",
                        "citation": cite,
                        "figures": rf_ev,
                    })
                answer_parts.append(
                    f"Red Flag Agent Status: Identified {rf_count} revenue-decline warning(s): "
                    + "; ".join(flag_summaries)
                    + "."
                )
            else:
                findings.append({
                    "part": "Red Flag Agent analysis",
                    "claim": "No revenue-decline warnings were identified by the Red Flag Agent.",
                    "evidence": "analyze_revenue_candidates evaluated all extracted statement rows; 0 qualifying revenue declines were detected.",
                    "citation": citations[0] if citations else None,
                    "figures": {"red_flag_count": 0},
                })
                answer_parts.append("Red Flag Agent Status: No revenue-decline warning was identified (all analyzed statements showed revenue growth or no qualifying decline).")
        else:
            limitations.append("Red Flag Agent analysis could not be conducted because no revenue candidates were found.")
            answer_parts.append("Red Flag Agent analysis could not be conducted as no revenue candidates were available.")

    # Step 6: Targeted vector search for specific topic terms or general queries
    if topic_words or (not asks_revenue and not asks_percentage and not asks_red_flags):
        target_query = " ".join(topic_words) if topic_words else q_clean
        query_embedding = create_embedding(target_query)
        search_results = search_chunks(query_embedding, top_k=3, document_id=doc_id)

        # Enforce strict document isolation defensively
        isolated_results = [
            r for r in search_results
            if str(r.get("metadata", {}).get("document_id")) == str(doc_id)
        ]

        # Verify whether retrieved chunks actually provide genuine supporting evidence
        relevant_chunks = []
        for r in isolated_results:
            c_text = r.get("chunk_text", "")
            is_supp, matched = is_chunk_supporting_evidence(c_text, topic_words)
            if is_supp:
                relevant_chunks.append((r, matched))

        if relevant_chunks:
            for rc, matched_words in relevant_chunks:
                rc_meta = rc.get("metadata", {})
                cite = register_citation(rc_meta)
                snippet = rc.get("chunk_text", "").strip()[:200].replace("\n", " ")
                findings.append({
                    "part": f"Document context for '{target_query}'",
                    "claim": f"Supporting evidence found on page {rc_meta.get('page_number')} matching concepts: {', '.join(matched_words)}.",
                    "evidence": snippet + "...",
                    "citation": cite,
                    "figures": None,
                })
            page_numbers = sorted(list({str(c[0]["metadata"].get("page_number")) for c in relevant_chunks if c[0]["metadata"].get("page_number")}))
            answer_parts.append(f"Additional evidence on '{target_query}' was retrieved from page(s) {', '.join(page_numbers)}.")
        elif not asks_revenue and not asks_percentage and not asks_red_flags:
            # Query did not ask for revenue/red flags and no relevant topic evidence was found
            limitations.append(f"No relevant evidence found in the document for query: '{q_clean}'.")
            answer_parts.append(
                f"Insufficient evidence found in the document to answer the question: '{q_clean}'. "
                f"The document does not contain relevant supporting information on this topic."
            )
        elif topic_words:
            limitations.append(f"No relevant evidence found in the document for topic: '{target_query}'.")
            answer_parts.append(f"However, the document does not contain supporting evidence regarding '{target_query}'.")

    # Step 7: Combine final answer narrative
    final_answer = " ".join(answer_parts) if answer_parts else "Insufficient evidence found in the document to answer the question."

    return {
        "question": q_clean,
        "document_id": doc_id,
        "company": company,
        "answer": final_answer,
        "findings": findings,
        "citations": citations,
        "limitations": limitations,
    }
