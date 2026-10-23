
def analyze_revenue_candidates(document_id: str, candidates: list) -> dict:
    """
    Analyse extracted revenue candidates and identify potential
    revenue-decline warnings.

    Reuses the Extraction Agent's existing output and source metadata.
    """

    red_flags = []
    analyzed = 0
    skipped = 0

    for candidate in candidates:
        values = candidate.get("values_found", [])
        source = candidate.get("source", {})

        # We need two values: current year and previous year.
        if len(values) < 2:
            skipped += 1
            continue

        current_value = values[0]
        previous_value = values[1]

        # Validate the values before calculating a percentage.
        if not isinstance(current_value, (int, float)):
            skipped += 1
            continue

        if not isinstance(previous_value, (int, float)):
            skipped += 1
            continue

        if previous_value <= 0:
            skipped += 1
            continue

        if current_value < 0:
            skipped += 1
            continue

        # Do not compare results from an unknown statement type.
        statement_type = candidate.get("statement_type")

        if statement_type not in ("standalone", "consolidated"):
            skipped += 1
            continue

        # Calculate year-on-year percentage change.
        change_percent = (
            (current_value - previous_value)
            / previous_value
        ) * 100

        analyzed += 1

        # A revenue increase does not trigger a decline warning.
        if change_percent >= 0:
            continue

        # Assign a simple severity based on the size of the decline.
        severity = "high" if change_percent <= -20 else "medium"

        red_flags.append({
            "flag_id": f"RF{len(red_flags) + 1:03d}",
            "metric": candidate.get("metric", "revenue"),
            "flag_type": "revenue_decline",
            "severity": severity,
            "title": "Revenue declined",
            "description": (
                f"{statement_type.capitalize()} revenue decreased "
                f"by {abs(change_percent):.2f}% compared with "
                f"the previous reported value."
            ),
            "evidence": {
                "current_value": current_value,
                "previous_value": previous_value,
                "unit": candidate.get("unit"),
                "change_percent": round(change_percent, 2),
                "financial_years_found": candidate.get(
                    "financial_years_found", []
                ),
            },
            "citation": {
                "document_id": source.get(
                    "document_id", document_id
                ),
                "page_number": source.get("page_number"),
                "chunk_id": source.get("chunk_id"),
                "statement_type": statement_type,
            },
        })

    return {
        "document_id": document_id,
        "analyzed_candidates": analyzed,
        "skipped_candidates": skipped,
        "red_flag_count": len(red_flags),
        "red_flags": red_flags,
    }
