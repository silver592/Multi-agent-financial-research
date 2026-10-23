# agents/report_agent.py
# Milestone 3 - Phase 7: Report Agent
# Responsible for generating Executive Summary and Key Financials sections,
# and assembling them into a structured, evidence-grounded initial report.

import uuid
from typing import Optional, Any

from agents.extraction_agent import extract_revenue
from agents.comparison_agent import extract_net_profit, normalize_financial_year, normalize_unit
from agents.red_flag_agent import analyze_revenue_candidates


def build_key_financials(
    document_id: str,
    reporting_basis: str = "consolidated",
    target_year: Optional[str] = None,
    revenue_candidates: Optional[list[dict]] = None,
    profit_candidates: Optional[list[dict]] = None,
) -> tuple[list[dict], list[dict], list[str]]:
    """
    Builds the Key Financials section by retrieving revenue and net profit
    candidates for the specified reporting basis and financial periods.
    Preserves original numerical figures and source metadata.

    Returns:
        (metrics_list, citations_list, limitations_list)
    """
    target_basis = (reporting_basis or "consolidated").strip().lower()
    if target_basis not in ("consolidated", "standalone"):
        target_basis = "consolidated"

    rev_cands = revenue_candidates if revenue_candidates is not None else extract_revenue(document_id)
    np_cands = profit_candidates if profit_candidates is not None else extract_net_profit(document_id)

    metrics = []
    citations = []
    limitations = []

    seen_citations = set()

    def add_citation(source: dict, company: Optional[str], statement_type: Optional[str]):
        page = source.get("page_number")
        chunk_id = source.get("chunk_id")
        key = (page, chunk_id, statement_type)
        if key not in seen_citations:
            seen_citations.add(key)
            citations.append({
                "document_id": document_id,
                "company": company,
                "page_number": page,
                "chunk_id": chunk_id,
                "statement_type": statement_type,
                "source_text": source.get("original_text") or "",
            })

    # 1. Process Revenue
    scoped_rev = [c for c in rev_cands if c.get("statement_type") == target_basis]
    if not scoped_rev:
        limitations.append(f"No {target_basis} revenue candidates found for document {document_id}.")
    else:
        for cand in scoped_rev:
            years = cand.get("financial_years_found", [])
            values = cand.get("values_found", [])
            unit = normalize_unit(cand.get("unit"))
            company = cand.get("company")
            source = cand.get("source", {})

            for y, val in zip(years, values):
                if target_year and normalize_financial_year(y) != normalize_financial_year(target_year):
                    continue
                metrics.append({
                    "metric": "revenue",
                    "value": float(val),
                    "financial_year": y,
                    "unit": unit,
                    "reporting_basis": target_basis,
                    "page": source.get("page_number"),
                    "chunk_id": source.get("chunk_id"),
                    "source_text": source.get("original_text") or "",
                })
                add_citation(source, company, target_basis)

    # 2. Process Net Profit
    scoped_np = [c for c in np_cands if c.get("statement_type") == target_basis]
    if not scoped_np:
        limitations.append(f"No {target_basis} net profit candidates found for document {document_id}.")
    else:
        for cand in scoped_np:
            years = cand.get("financial_years_found", [])
            values = cand.get("values_found", [])
            unit = normalize_unit(cand.get("unit"))
            company = cand.get("company")
            source = cand.get("source", {})

            for y, val in zip(years, values):
                if target_year and normalize_financial_year(y) != normalize_financial_year(target_year):
                    continue
                metrics.append({
                    "metric": "net_profit",
                    "value": float(val),
                    "financial_year": y,
                    "unit": unit,
                    "reporting_basis": target_basis,
                    "page": source.get("page_number"),
                    "chunk_id": source.get("chunk_id"),
                    "source_text": source.get("original_text") or "",
                })
                add_citation(source, company, target_basis)

    return metrics, citations, limitations


def build_executive_summary(
    document_id: str,
    reporting_basis: str = "consolidated",
    target_year: Optional[str] = None,
    revenue_candidates: Optional[list[dict]] = None,
    profit_candidates: Optional[list[dict]] = None,
) -> dict:
    """
    Builds the Executive Summary section:
    - Identifies company name and primary reporting periods.
    - Highlights major revenue & net profit performance and YoY percentage growth/decline.
    - Summarizes potential red flags identified by the Red Flag Agent.
    - Notes any missing data transparently.
    """
    target_basis = (reporting_basis or "consolidated").strip().lower()
    if target_basis not in ("consolidated", "standalone"):
        target_basis = "consolidated"

    rev_cands = revenue_candidates if revenue_candidates is not None else extract_revenue(document_id)
    np_cands = profit_candidates if profit_candidates is not None else extract_net_profit(document_id)

    company_name = None
    for c in rev_cands + np_cands:
        if c.get("company"):
            company_name = c["company"]
            break

    scoped_rev = [c for c in rev_cands if c.get("statement_type") == target_basis]
    scoped_np = [c for c in np_cands if c.get("statement_type") == target_basis]

    highlights = []
    red_flag_texts = []
    summary_sentences = []
    reporting_periods_found = []

    # Revenue overview
    if scoped_rev:
        cand = scoped_rev[0]
        years = cand.get("financial_years_found", [])
        values = cand.get("values_found", [])
        unit = normalize_unit(cand.get("unit"))
        reporting_periods_found.extend(years)

        if len(values) >= 2:
            curr_y, prev_y = years[0], years[1]
            curr_v, prev_v = values[0], values[1]
            pct = round(((curr_v - prev_v) / prev_v) * 100, 2)
            direction = "increased" if pct >= 0 else "decreased"
            h_text = (
                f"{target_basis.capitalize()} revenue was {unit} {curr_v:,.0f} in {curr_y} "
                f"compared to {unit} {prev_v:,.0f} in {prev_y} ({direction} by {abs(pct):.2f}%)."
            )
            highlights.append(h_text)
            summary_sentences.append(h_text)
        elif len(values) == 1:
            h_text = f"{target_basis.capitalize()} revenue was reported at {unit} {values[0]:,.0f} for {years[0]}."
            highlights.append(h_text)
            summary_sentences.append(h_text)
    else:
        summary_sentences.append(f"No {target_basis} revenue data was identified in the document.")

    # Net Profit overview
    if scoped_np:
        cand = scoped_np[0]
        years = cand.get("financial_years_found", [])
        values = cand.get("values_found", [])
        unit = normalize_unit(cand.get("unit"))
        reporting_periods_found.extend(years)

        if len(values) >= 2:
            curr_y, prev_y = years[0], years[1]
            curr_v, prev_v = values[0], values[1]
            pct = round(((curr_v - prev_v) / prev_v) * 100, 2)
            direction = "increased" if pct >= 0 else "decreased"
            h_text = (
                f"{target_basis.capitalize()} net profit was {unit} {curr_v:,.0f} in {curr_y} "
                f"compared to {unit} {prev_v:,.0f} in {prev_y} ({direction} by {abs(pct):.2f}%)."
            )
            highlights.append(h_text)
            summary_sentences.append(h_text)
        elif len(values) == 1:
            h_text = f"{target_basis.capitalize()} net profit was reported at {unit} {values[0]:,.0f} for {years[0]}."
            highlights.append(h_text)
            summary_sentences.append(h_text)

    # Red Flag Agent integration
    rf_analysis = analyze_revenue_candidates(document_id, rev_cands)
    rf_count = rf_analysis.get("red_flag_count", 0)
    red_flags = rf_analysis.get("red_flags", [])

    if rf_count > 0:
        for rf in red_flags:
            rf_desc = f"{rf.get('flag_id')} ({rf.get('severity')} severity): {rf.get('description')}"
            red_flag_texts.append(rf_desc)
        summary_sentences.append(
            f"The Red Flag Agent identified {rf_count} potential revenue decline concern(s)."
        )
    else:
        red_flag_texts.append("No revenue decline red flags were identified across analyzed statements.")
        summary_sentences.append("No revenue decline red flags were detected by the Red Flag Agent.")

    primary_period = None
    if reporting_periods_found:
        unique_periods = []
        for p in reporting_periods_found:
            if p not in unique_periods:
                unique_periods.append(p)
        primary_period = ", ".join(unique_periods[:2])

    comp_name_str = company_name or "The company"
    intro = f"Executive financial overview for {comp_name_str} ({target_basis} basis)."
    full_summary = f"{intro} {' '.join(summary_sentences)}"

    return {
        "company": company_name,
        "reporting_period": primary_period,
        "reporting_basis": target_basis,
        "summary_text": full_summary,
        "highlights": highlights,
        "red_flags": red_flag_texts,
    }


def generate_initial_report(
    document_id: str,
    session_id: Optional[str] = None,
    reporting_basis: Optional[str] = "consolidated",
    financial_year: Optional[str] = None,
    revenue_candidates: Optional[list[dict]] = None,
    profit_candidates: Optional[list[dict]] = None,
) -> dict:
    """
    Orchestrates the generation of the initial financial report:
    1. Extracts/reuses supported financial candidates (Revenue and Net Profit).
    2. Builds the Key Financials section with source citations.
    3. Builds the Executive Summary section with highlights and Red Flag integration.
    4. Combines both sections into a clean, structured JSON response.
    """
    target_basis = (reporting_basis or "consolidated").strip().lower()
    if target_basis not in ("consolidated", "standalone"):
        target_basis = "consolidated"

    rev_cands = revenue_candidates if revenue_candidates is not None else extract_revenue(document_id)
    np_cands = profit_candidates if profit_candidates is not None else extract_net_profit(document_id)

    # 1. Build Key Financials
    metrics, citations, kf_limitations = build_key_financials(
        document_id=document_id,
        reporting_basis=target_basis,
        target_year=financial_year,
        revenue_candidates=rev_cands,
        profit_candidates=np_cands,
    )

    # 2. Build Executive Summary
    exec_summary = build_executive_summary(
        document_id=document_id,
        reporting_basis=target_basis,
        target_year=financial_year,
        revenue_candidates=rev_cands,
        profit_candidates=np_cands,
    )

    company = exec_summary.get("company")
    all_limitations = list(kf_limitations)
    if not metrics:
        all_limitations.append("Insufficient financial evidence found to construct key financials.")

    report_id = f"rpt_{uuid.uuid4().hex[:12]}"

    return {
        "report_id": report_id,
        "session_id": session_id,
        "document_id": document_id,
        "company": company,
        "reporting_basis": target_basis,
        "financial_year": financial_year,
        "executive_summary": exec_summary,
        "key_financials": metrics,
        "citations": citations,
        "limitations": all_limitations,
    }
