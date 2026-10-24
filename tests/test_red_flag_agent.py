
from agents.red_flag_agent import analyze_revenue_candidates

sample_candidates = [
    {
        "metric": "revenue_from_operations",
        "statement_type": "consolidated",
        "values_found": [800, 1000],
        "financial_years_found": ["2024-25"],
        "company": "Sample Company",
        "unit": "crore",
        "source": {
            "document_id": "test_doc",
            "page_number": 82,
            "chunk_id": "test_doc_p82_c14",
        },
    }
]

result = analyze_revenue_candidates(
    document_id="test_doc",
    candidates=sample_candidates,
)

print(result)
