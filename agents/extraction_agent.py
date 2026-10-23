
# agents/extraction_agent.py--->

import re

from services.vector_store import get_document_chunks


def extract_revenue(document_id: str):
    """
    Extract company-level revenue from financial report chunks.

    Uses page-level context to identify standalone and consolidated
    financial statements, handles common OCR spacing issues, and
    preserves source information for each extracted candidate.
    """

    chunks = get_document_chunks(document_id)
    candidates = []

    # Match comma-separated financial amounts, including OCR spacing.
    # Examples: 9,80,136 and 255, 3 24.
    amount_pattern = re.compile(
        r"(?<!\d)\d{1,3}(?:\s*,\s*\d(?:\s*\d){1,2})+(?!\d)"
    )

    year_pattern = re.compile(
        r"\b(20\d{2})\s*[-–]\s*(\d{2,4})\b"
    )

    # Combine all chunks belonging to each PDF page.
    # Headings and financial rows can occur in different chunks.
    page_texts = {}

    for chunk in chunks:
        page_number = chunk["metadata"].get("page_number")

        page_texts.setdefault(page_number, []).append(
            chunk["chunk_text"]
        )

    page_texts = {
        page: re.sub(r"\s+", " ", " ".join(texts)).lower()
        for page, texts in page_texts.items()
    }

    for chunk in chunks:
        text = chunk["chunk_text"]
        metadata = chunk["metadata"]
        lower_text = text.lower()

        normalized_text = re.sub(r"\s+", " ", lower_text)

        page_number = metadata.get("page_number")
        page_context = page_texts.get(page_number, "")

        # Normalize OCR text by removing spaces and punctuation.
        # Example: "ST ANDALONE FINANCIAL ST A TEMENTS"
        # becomes "standalonefinancialstatements".
        statement_context = re.sub(
            r"[^a-z]",
            "",
            page_context.lower(),
        )

        # Skip related-party transaction chunks.
        related_party_terms = [
            "related parties",
            "related party",
            "related-parties",
            "related party transaction",
            "related party transactions",
            "transactions with related parties",
            "material related party transactions",
        ]

        if any(
            term in normalized_text
            for term in related_party_terms
        ):
            continue

        # Exclude unrelated revenue metrics and segment tables.
        excluded_terms = [
            "energy intensity",
            "water intensity",
            "waste intensity",
            "revenue from operations adjusted",
            "segment revenue",
            "segment result",
            "segment results",
            "segment information",
            "information regarding geographical revenue",
            "geographical revenue",
            "disaggregated revenue",
        ]

        if any(
            term in normalized_text
            for term in excluded_terms
        ):
            continue

        # Determine statement type using the entire page.
        if (
            "consolidatedstatementofprofitandloss"
            in statement_context
            or "consolidatedfinancialresults"
            in statement_context
            or "consolidatedfinancialstatements"
            in statement_context
        ):
            statement_type = "consolidated"

        elif (
            "standalonestatementofprofitandloss"
            in statement_context
            or "standalonefinancialresults"
            in statement_context
            or "standalonefinancialstatements"
            in statement_context
        ):
            statement_type = "standalone"

        else:
            statement_type = "unspecified"

        # Accept revenue rows only when the page has financial-table
        # context. Page-level context handles headings in other chunks.
        table_context = any(
            phrase in page_context
            for phrase in [
                "financial results",
                "statement of profit and loss",
                "statement of profit or loss",
                "financial statements",
                "financial performance",
            ]
        ) or any(
            phrase in statement_context
            for phrase in [
                "financialresults",
                "statementofprofitandloss",
                "statementofprofitorloss",
                "financialstatements",
                "financialperformance",
            ]
        )

        if not table_context:
            continue

        lines = text.splitlines()

        for index, line in enumerate(lines):
            if not re.search(
                r"revenue\s+from\s+operations",
                line,
                re.IGNORECASE,
            ):
                continue

            # If the amounts are on the next line, include that line.
            row_text = line

            if not amount_pattern.search(row_text):
                if index + 1 < len(lines):
                    row_text += " " + lines[index + 1]

            # Correct common OCR character substitutions.
            normalized_row = (
                row_text
                .replace("ϰ", "4")
                .replace("Ϭ", "0")
                .replace("ϵ", "9")
            )

            matches = amount_pattern.findall(normalized_row)

            # Require at least two comma-formatted amounts.
            if len(matches) < 2:
                continue

            values = []
            original_values = []

            for match in matches[:2]:
                cleaned = re.sub(r"\s+", "", match)

                original_values.append(cleaned)
                values.append(
                    int(cleaned.replace(",", ""))
                )

            # Ignore implausibly small revenue amounts.
            if any(value < 1000 for value in values):
                continue

            # Avoid duplicate candidates for the same page and type.
            if any(
                item["source"]["page_number"] == page_number
                and item["statement_type"] == statement_type
                for item in candidates
            ):
                continue


            # Extract years in compact form, e.g. 2024-25,
            # and from headings such as "March 31, 2024".
            page_context = page_texts.get(page_number, "")

            compact_years = year_pattern.findall(page_context)
            formatted_years = []

            for start, end in compact_years:
                end_year = (
                    end if len(end) == 4
                    else start[:2] + end
                )
                formatted_year = f"{start}-{end_year[-2:]}"

                if formatted_year not in formatted_years:
                    formatted_years.append(formatted_year)

            # TCS-style statements may list each year separately.
            if len(formatted_years) < 2:
                individual_years = re.findall(
                    r"\b20\d{2}\b",
                    page_context,
                )

                for year in individual_years:
                    if len(formatted_years) >= 2:
                        break

                    formatted_year = (
                        f"{int(year) - 1}-{year[-2:]}"
                    )

                    if formatted_year not in formatted_years:
                        formatted_years.append(formatted_year)


            # Determine the currency unit from the source chunk/page.
            unit_context = text + " " + page_context

            unit = (
                "crore"
                if re.search(
                    r"\bC\s+in\s+crore\b|\b₹?\s*crore\b",
                    unit_context,
                    re.IGNORECASE,
                )
                else "check source document"
            )

            candidates.append({
                "metric": "revenue_from_operations",
                "statement_type": statement_type,
                "values_found": values,
                "original_values": original_values,
                "financial_years_found": formatted_years,
                "company": metadata.get("company"),
                "unit": unit,
                "source": {
                    "document_id": metadata.get("document_id"),
                    "page_number": page_number,
                    "chunk_id": chunk["chunk_id"],
                    "original_text": text,
                },
            })

    # Keep only candidates from formal statements of profit and loss.
    # OCR-tolerant matching checks the entire page.
    formal_candidates = [
        candidate
        for candidate in candidates
        if (
            "statementofprofitandloss"
            in re.sub(
                r"[^a-z]",
                "",
                page_texts.get(
                    candidate["source"]["page_number"], ""
                ).lower(),
            )
            and candidate["statement_type"]
            in ("standalone", "consolidated")
        )
    ]

    if formal_candidates:
        return formal_candidates

    # If formal statements were not detected, prefer explicitly
    # labelled standalone or consolidated financial results.
    labelled_candidates = [
        candidate
        for candidate in candidates
        if candidate["statement_type"]
        in ("standalone", "consolidated")
    ]

    if labelled_candidates:
        return labelled_candidates

    # Last resort: return candidates if no preferred result exists.
    return candidates
