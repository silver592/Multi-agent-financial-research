# agents/comparison_agent.py
# Milestone 3 - Phase 5: Comparison Agent
# Handles cross-company financial comparisons, metric alignment, unit compatibility,
# deterministic arithmetic differences, and citation preservation.

import re
import uuid
from typing import Optional, Any

from services.vector_store import get_document_chunks
from agents.extraction_agent import extract_revenue

SUPPORTED_METRIC_SYNONYMS = {
    "revenue": "revenue",
    "revenue_from_operations": "revenue",
    "sales": "revenue",
    "turnover": "revenue",
    "net_profit": "net_profit",
    "profit": "net_profit",
    "profit_for_the_year": "net_profit",
    "profit_for_the_period": "net_profit",
    "profit_after_tax": "net_profit",
}


def normalize_metric_name(metric: str) -> Optional[str]:
    """
    Normalizes obvious metric naming variants to standard keys:
    - 'revenue'
    - 'net_profit'
    Returns None if metric is not recognized.
    """
    if not metric:
        return None
    cleaned = metric.strip().lower().replace(" ", "_")
    return SUPPORTED_METRIC_SYNONYMS.get(cleaned)


def normalize_financial_year(fy_str: Optional[str]) -> str:
    """
    Normalizes financial year strings like 'FY 2024-25', '2024-25', or 'FY25'
    into standard '2024-25' format. Defaults to '2024-25'.
    """
    if not fy_str or not str(fy_str).strip():
        return "2024-25"

    match = re.search(r"\b(20\d{2})\s*[-–]\s*(\d{2,4})\b", fy_str)
    if match:
        start, end = match.groups()
        end_short = end if len(end) == 2 else end[-2:]
        return f"{start}-{end_short}"

    # Handle 'FY25' or '2025'
    match_single = re.search(r"\b20?(\d{2})\b", fy_str)
    if match_single:
        end_val = int(match_single.group(1))
        start_val = 2000 + end_val - 1
        return f"{start_val}-{end_val:02d}"

    return str(fy_str).strip()


def normalize_unit(unit_str: Optional[str]) -> str:
    """
    Normalizes reporting currency units to standard display representation.
    """
    if not unit_str:
        return "INR crore"
    u_lower = unit_str.lower().strip()
    if "crore" in u_lower:
        return "INR crore"
    if "lakh" in u_lower:
        return "INR lakh"
    if "usd" in u_lower or "$" in u_lower:
        return "USD"
    return unit_str.strip()


def extract_net_profit(document_id: str) -> list[dict]:
    """
    Extracts company-level net profit ('Profit for the year' / 'Profit for the period')
    from formal financial statement chunks for the given document.
    Reuses verified P&L statement pages identified by revenue extraction.
    """
    chunks = get_document_chunks(document_id)
    if not chunks:
        return []

    rev_candidates = extract_revenue(document_id)
    verified_pages = {c["source"]["page_number"]: c for c in rev_candidates}

    amount_pattern = re.compile(
        r"(?<!\d)\d{1,3}(?:\s*,\s*\d(?:\s*\d){1,2})+(?!\d)"
    )

    profit_candidates = []

    for chunk in chunks:
        page_number = chunk["metadata"].get("page_number")
        if page_number not in verified_pages:
            continue

        matching_rev = verified_pages[page_number]
        statement_type = matching_rev.get("statement_type", "unspecified")
        years = matching_rev.get("financial_years_found", [])
        unit = matching_rev.get("unit", "crore")
        company = matching_rev.get("company")

        text = chunk["chunk_text"]
        lines = text.splitlines()

        for idx, line in enumerate(lines):
            normalized_line = re.sub(r"\s+", " ", line.strip().lower())

            # Match formal net profit lines while excluding non-controlling interest or share of associates
            if (
                any(p in normalized_line for p in [
                    "profit for the year",
                    "profit for the period",
                    "profit for the y ear",
                    "profit after tax",
                ])
                and not any(ex in normalized_line for ex in [
                    "share of profit",
                    "reclassified",
                    "attributable to",
                    "before tax",
                    "before exceptional",
                ])
            ):
                row_text = line
                if not amount_pattern.search(row_text) and idx + 1 < len(lines):
                    row_text += " " + lines[idx + 1]

                normalized_row = (
                    row_text
                    .replace("ϰ", "4")
                    .replace("Ϭ", "0")
                    .replace("ϵ", "9")
                )

                matches = amount_pattern.findall(normalized_row)
                if len(matches) >= 2:
                    values = []
                    orig_values = []
                    for m in matches[:2]:
                        clean = re.sub(r"\s+", "", m)
                        orig_values.append(clean)
                        values.append(int(clean.replace(",", "")))

                    # Avoid duplicate candidates for the same statement type and page
                    if any(
                        p["source"]["page_number"] == page_number
                        and p["statement_type"] == statement_type
                        for p in profit_candidates
                    ):
                        continue

                    profit_candidates.append({
                        "metric": "net_profit",
                        "statement_type": statement_type,
                        "values_found": values,
                        "original_values": orig_values,
                        "financial_years_found": years,
                        "company": company,
                        "unit": unit,
                        "source": {
                            "document_id": document_id,
                            "page_number": page_number,
                            "chunk_id": chunk["chunk_id"],
                            "original_text": text,
                        },
                    })

    return profit_candidates


def get_candidates_for_document(document_id: str, metric: str) -> list[dict]:
    """
    Retrieves extracted financial candidates for a specific document and metric.
    """
    norm_metric = normalize_metric_name(metric)
    if norm_metric == "revenue":
        return extract_revenue(document_id)
    elif norm_metric == "net_profit":
        return extract_net_profit(document_id)
    return []


def select_company_metric_value(
    candidates: list[dict],
    target_year: str,
    reporting_basis: str,
    expected_doc_id: str,
) -> tuple[Optional[dict], str, Optional[str]]:
    """
    Selects a single comparable metric value for a specific company and document.
    Enforces document isolation, reporting basis matching, and year alignment.
    Returns: (metric_value_dict, status, limitation_note)
    """
    # Defensive document isolation check
    isolated_candidates = [
        c for c in candidates
        if str(c.get("source", {}).get("document_id")) == str(expected_doc_id)
    ]

    if not isolated_candidates:
        return None, "missing_data", f"No extracted candidates found for document {expected_doc_id}."

    # Filter by reporting basis (consolidated vs standalone)
    scoped_candidates = [
        c for c in isolated_candidates
        if c.get("statement_type") == reporting_basis
    ]

    if not scoped_candidates:
        available_bases = list({c.get("statement_type") for c in isolated_candidates if c.get("statement_type")})
        return None, "mismatched_reporting_basis", (
            f"Requested {reporting_basis} figures, but document {expected_doc_id} only has: {available_bases}."
        )

    # Locate candidate matching target_year
    matching_values = []
    for cand in scoped_candidates:
        years = cand.get("financial_years_found", [])
        values = cand.get("values_found", [])

        # Match year index
        year_idx = None
        for i, y in enumerate(years):
            if normalize_financial_year(y) == normalize_financial_year(target_year):
                year_idx = i
                break

        if year_idx is not None and year_idx < len(values):
            matching_values.append({
                "value": float(values[year_idx]),
                "candidate": cand,
                "year_matched": years[year_idx],
            })

    if not matching_values:
        return None, "mismatched_years", (
            f"Financial year '{target_year}' was not found in extracted statements for document {expected_doc_id}."
        )

    # Ambiguity check: if multiple distinct figures are found for the same basis and year
    distinct_figures = {item["value"] for item in matching_values}
    if len(distinct_figures) > 1:
        return None, "ambiguous", (
            f"Ambiguous conflicting figures found for document {expected_doc_id} in {reporting_basis} {target_year}: {distinct_figures}."
        )

    chosen = matching_values[0]
    cand = chosen["candidate"]
    source = cand.get("source", {})

    value_obj = {
        "company": cand.get("company") or "Unknown Company",
        "document_id": expected_doc_id,
        "value": chosen["value"],
        "unit": normalize_unit(cand.get("unit")),
        "financial_year": chosen["year_matched"],
        "reporting_basis": reporting_basis,
        "page": source.get("page_number"),
        "chunk_id": source.get("chunk_id"),
        "source_text": source.get("original_text") or "",
    }

    return value_obj, "comparable", None


def compare_company_metrics(
    document_ids: list[str],
    financial_year: Optional[str] = "FY 2024-25",
    reporting_basis: Optional[str] = "consolidated",
    metrics: Optional[list[str]] = None,
    reference_document_id: Optional[str] = None,
    candidates_by_doc: Optional[dict] = None,
    document_metadata_map: Optional[dict] = None,
) -> dict:
    """
    Main Comparison Agent logic:
    1. Validates document IDs and reference document.
    2. Groups and aligns equivalent financial metrics.
    3. Calculates deterministic absolute, signed, and percentage differences.
    4. Enforces document isolation and citation preservation.
    """
    if not document_ids or len(document_ids) < 2:
        raise ValueError("At least two distinct document IDs are required for comparison.")

    # Duplicate document IDs check
    if len(document_ids) != len(set(document_ids)):
        raise ValueError(f"Duplicate document IDs are not permitted: {document_ids}")

    # Reference document validation
    ref_doc_id = reference_document_id or document_ids[1]
    if ref_doc_id not in document_ids:
        raise ValueError(
            f"reference_document_id '{ref_doc_id}' must be one of the requested document_ids: {document_ids}"
        )

    target_year = normalize_financial_year(financial_year)
    target_basis = (reporting_basis or "consolidated").strip().lower()
    if target_basis not in ("consolidated", "standalone"):
        raise ValueError(f"Invalid reporting_basis '{reporting_basis}'. Must be 'consolidated' or 'standalone'.")

    metric_list = metrics or ["revenue"]
    comparison_id = f"cmp_{uuid.uuid4().hex[:12]}"

    metric_results = []
    limitations = []

    for raw_metric in metric_list:
        norm_metric = normalize_metric_name(raw_metric)
        if not norm_metric:
            limitations.append(f"Metric '{raw_metric}' is not supported. Supported metrics are 'revenue' and 'net_profit'.")
            metric_results.append({
                "metric": raw_metric,
                "financial_year": target_year,
                "reporting_basis": target_basis,
                "unit": "unknown",
                "values": [],
                "absolute_difference": None,
                "signed_difference": None,
                "percentage_difference": None,
                "percentage_reference": ref_doc_id,
                "status": "unsupported_metric",
                "notes": f"Metric '{raw_metric}' is not supported.",
            })
            continue

        company_values = []
        metric_status = "comparable"
        metric_notes = []

        # Collect aligned values for each document
        for doc_id in document_ids:
            # Retrieve candidates (either passed in for synthetic testing or extracted via services)
            if candidates_by_doc is not None and doc_id in candidates_by_doc:
                raw = candidates_by_doc[doc_id]
                # Accept two formats:
                # - metric-keyed dict: {"revenue": [...], "net_profit": [...]}
                # - flat list of candidate dicts (legacy)
                if isinstance(raw, dict):
                    doc_candidates = raw.get(norm_metric, []) or []
                else:
                    doc_candidates = [
                        c for c in raw
                        if normalize_metric_name(c.get("metric")) == norm_metric
                    ]
            else:
                doc_candidates = get_candidates_for_document(doc_id, norm_metric)

            val_obj, val_status, note = select_company_metric_value(
                candidates=doc_candidates,
                target_year=target_year,
                reporting_basis=target_basis,
                expected_doc_id=doc_id,
            )

            if val_obj:
                # If document metadata map provided company name, ensure it is consistent
                if document_metadata_map and doc_id in document_metadata_map:
                    val_obj["company"] = document_metadata_map[doc_id].get("company", val_obj["company"])
                company_values.append(val_obj)
            else:
                metric_status = val_status
                if note:
                    metric_notes.append(note)
                    limitations.append(note)

        # Check unit compatibility among gathered values
        resolved_unit = "INR crore"
        if company_values:
            resolved_unit = company_values[0]["unit"]
            for cv in company_values[1:]:
                if cv["unit"] != resolved_unit:
                    metric_status = "incompatible_units"
                    note = f"Incompatible units across companies: {resolved_unit} vs {cv['unit']}."
                    metric_notes.append(note)
                    limitations.append(note)
                    break

        # If any company value is missing or status is not comparable, differences cannot be computed
        abs_diff = None
        signed_diff = None
        pct_diff = None
        pct_ref_label = ref_doc_id  # default; overridden when full comparison is possible

        if len(company_values) == len(document_ids) and metric_status == "comparable":
            # For 2-company comparison: Company A (document_ids[0]) vs Company B (ref_doc_id)
            # Locate reference value
            ref_entry = next((cv for cv in company_values if cv["document_id"] == ref_doc_id), None)
            other_entry = next((cv for cv in company_values if cv["document_id"] != ref_doc_id), None)

            if ref_entry and other_entry:
                val_other = other_entry["value"]
                val_ref = ref_entry["value"]

                abs_diff = round(abs(val_other - val_ref), 2)
                signed_diff = round(val_other - val_ref, 2)

                if val_ref > 0:
                    pct_diff = round(((val_other - val_ref) / val_ref) * 100.0, 2)
                elif val_ref < 0:
                    pct_diff = round(((val_other - val_ref) / abs(val_ref)) * 100.0, 2)
                else:
                    pct_diff = None
                    note = (
                        f"Percentage difference cannot be computed because reference value "
                        f"for {ref_entry['company']} (document {ref_doc_id}) is zero."
                    )
                    metric_notes.append(note)
                    limitations.append(note)

                # Upgrade status from 'comparable' to 'compared' once differences are calculated
                metric_status = "compared"

                # Build a human-readable percentage_reference label (company name + doc_id)
                ref_company = ref_entry["company"]
                pct_ref_label = f"{ref_company} ({ref_doc_id})"
        elif len(company_values) < len(document_ids) and metric_status not in ("incompatible_units",):
            # One or more companies had missing, mismatched year, or mismatched basis data
            # Normalise all these to 'partial_data' for a clear, consistent status contract
            metric_status = "partial_data"

        metric_results.append({
            "metric": norm_metric,
            "financial_year": target_year,
            "reporting_basis": target_basis,
            "unit": resolved_unit,
            "values": company_values,
            "absolute_difference": abs_diff,
            "signed_difference": signed_diff,
            "percentage_difference": pct_diff,
            "percentage_reference": pct_ref_label,
            "status": metric_status,
            "notes": "; ".join(metric_notes) if metric_notes else None,
        })

    return {
        "comparison_id": comparison_id,
        "financial_year": target_year,
        "reporting_basis": target_basis,
        "metrics": metric_results,
        "limitations": sorted(list(set(limitations))),
    }
