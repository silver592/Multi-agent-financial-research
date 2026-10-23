# test_report_agent.py
# Comprehensive test suite for Milestone 3 - Phase 7: Report Agent
# Tests Executive Summary generation, Key Financials construction,
# citation preservation, Red Flag integration, missing data handling,
# and FastAPI endpoints (/sessions/{session_id}/report and /documents/{document_id}/report).

import unittest
from fastapi.testclient import TestClient

from main import app
from agents.report_agent import (
    build_key_financials,
    build_executive_summary,
    generate_initial_report,
)


class TestReportAgentUnit(unittest.TestCase):
    """Unit tests with synthetic candidate data for Report Agent."""

    def setUp(self):
        self.doc_id = "test_doc_alpha_123"
        self.synthetic_rev_cands = [
            {
                "metric": "revenue_from_operations",
                "statement_type": "consolidated",
                "company": "Alpha Corp",
                "values_found": [120000.0, 100000.0],
                "financial_years_found": ["2024-25", "2023-24"],
                "unit": "crore",
                "source": {
                    "document_id": self.doc_id,
                    "page_number": 50,
                    "chunk_id": f"{self.doc_id}_p50_c1",
                    "original_text": "Revenue from operations: 120000 in 2024-25, 100000 in 2023-24",
                },
            },
            {
                "metric": "revenue_from_operations",
                "statement_type": "standalone",
                "company": "Alpha Corp",
                "values_found": [70000.0, 80000.0],
                "financial_years_found": ["2024-25", "2023-24"],
                "unit": "crore",
                "source": {
                    "document_id": self.doc_id,
                    "page_number": 20,
                    "chunk_id": f"{self.doc_id}_p20_c1",
                    "original_text": "Standalone revenue: 70000 in 2024-25 vs 80000 in 2023-24",
                },
            },
        ]

        self.synthetic_np_cands = [
            {
                "metric": "net_profit",
                "statement_type": "consolidated",
                "company": "Alpha Corp",
                "values_found": [25000.0, 20000.0],
                "financial_years_found": ["2024-25", "2023-24"],
                "unit": "crore",
                "source": {
                    "document_id": self.doc_id,
                    "page_number": 50,
                    "chunk_id": f"{self.doc_id}_p50_c2",
                    "original_text": "Profit for the year: 25000 in 2024-25, 20000 in 2023-24",
                },
            }
        ]

    # 1. Valid financial metrics with valid citations
    def test_build_key_financials_preserves_values_and_citations(self):
        metrics, citations, limitations = build_key_financials(
            document_id=self.doc_id,
            reporting_basis="consolidated",
            revenue_candidates=self.synthetic_rev_cands,
            profit_candidates=self.synthetic_np_cands,
        )
        self.assertEqual(len(metrics), 4)  # 2 revenue + 2 net profit periods
        self.assertEqual(len(limitations), 0)

        # Revenue for 2024-25
        rev_2025 = next(m for m in metrics if m["metric"] == "revenue" and m["financial_year"] == "2024-25")
        self.assertEqual(rev_2025["value"], 120000.0)
        self.assertEqual(rev_2025["unit"], "INR crore")
        self.assertEqual(rev_2025["page"], 50)
        self.assertEqual(rev_2025["chunk_id"], f"{self.doc_id}_p50_c1")
        self.assertIn("Revenue from operations", rev_2025["source_text"])

        # Check citations
        self.assertTrue(len(citations) >= 1)
        self.assertEqual(citations[0]["page_number"], 50)
        self.assertEqual(citations[0]["document_id"], self.doc_id)

    # 2. Executive Summary includes supported findings and YoY calculations
    def test_executive_summary_supported_findings(self):
        summary = build_executive_summary(
            document_id=self.doc_id,
            reporting_basis="consolidated",
            revenue_candidates=self.synthetic_rev_cands,
            profit_candidates=self.synthetic_np_cands,
        )
        self.assertEqual(summary["company"], "Alpha Corp")
        self.assertEqual(summary["reporting_basis"], "consolidated")
        self.assertTrue(len(summary["highlights"]) >= 2)

        # Revenue growth: (120000 - 100000) / 100000 = +20.00%
        self.assertIn("increased by 20.00%", summary["highlights"][0])
        self.assertIn("Alpha Corp", summary["summary_text"])

    # 3. Relevant Red Flag Agent findings are represented accurately
    def test_executive_summary_red_flag_representation(self):
        # Standalone has revenue decline from 80000 to 70000 (-12.5% decline -> RF medium)
        summary = build_executive_summary(
            document_id=self.doc_id,
            reporting_basis="standalone",
            revenue_candidates=self.synthetic_rev_cands,
            profit_candidates=self.synthetic_np_cands,
        )
        self.assertEqual(summary["reporting_basis"], "standalone")
        # Highlights report decline
        self.assertIn("decreased by 12.50%", summary["highlights"][0])
        # Red flags captured
        self.assertTrue(any("RF001" in rf or "decreased by 12.50%" in rf for rf in summary["red_flags"]))

    # 4. Key Financials preserves financial years, units, and reporting basis
    def test_key_financials_filters_by_target_year(self):
        metrics, citations, limitations = build_key_financials(
            document_id=self.doc_id,
            reporting_basis="consolidated",
            target_year="2024-25",
            revenue_candidates=self.synthetic_rev_cands,
            profit_candidates=self.synthetic_np_cands,
        )
        self.assertEqual(len(metrics), 2)  # 1 rev + 1 profit for 2024-25
        for m in metrics:
            self.assertEqual(m["financial_year"], "2024-25")
            self.assertEqual(m["reporting_basis"], "consolidated")

    # 5. Missing metrics are handled without invented values
    def test_missing_metrics_handled_transparently(self):
        # Doc with revenue but NO net profit
        metrics, citations, limitations = build_key_financials(
            document_id=self.doc_id,
            reporting_basis="consolidated",
            revenue_candidates=self.synthetic_rev_cands,
            profit_candidates=[],
        )
        self.assertEqual(len(metrics), 2)  # Only revenue items
        self.assertTrue(all(m["metric"] == "revenue" for m in metrics))
        self.assertTrue(any("net profit" in lim for lim in limitations))

    # 6. Missing citation metadata is handled transparently without fabrication
    def test_missing_citation_metadata_not_fabricated(self):
        cands_no_meta = [
            {
                "metric": "revenue_from_operations",
                "statement_type": "consolidated",
                "values_found": [50000.0],
                "financial_years_found": ["2024-25"],
                "unit": "crore",
                "source": {
                    "document_id": self.doc_id,
                    "page_number": None,
                    "chunk_id": None,
                    "original_text": None,
                },
            }
        ]
        metrics, citations, limitations = build_key_financials(
            document_id=self.doc_id,
            reporting_basis="consolidated",
            revenue_candidates=cands_no_meta,
            profit_candidates=[],
        )
        self.assertEqual(len(metrics), 1)
        self.assertIsNone(metrics[0]["page"])
        self.assertIsNone(metrics[0]["chunk_id"])
        self.assertEqual(metrics[0]["source_text"], "")

    # 7. Empty or insufficient evidence produces an appropriate response
    def test_empty_evidence_produces_limitation(self):
        report = generate_initial_report(
            document_id=self.doc_id,
            revenue_candidates=[],
            profit_candidates=[],
        )
        self.assertEqual(len(report["key_financials"]), 0)
        self.assertTrue(len(report["limitations"]) > 0)
        self.assertTrue(any("insufficient" in lim.lower() or "no consolidated" in lim.lower() for lim in report["limitations"]))


class TestReportAgentIntegration(unittest.TestCase):
    """Integration tests running against real indexed documents via FastAPI endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.reliance_session_id = "8b14afa0-9d0a-4487-8c2f-ff6f9588c276"
        cls.reliance_doc_id = "87bee45d-2ab7-4ee9-8724-8635305692be"

    # 8. Valid report request on Reliance session
    def test_session_report_endpoint_reliance(self):
        response = self.client.post(
            f"/sessions/{self.reliance_session_id}/report",
            json={"reporting_basis": "consolidated"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("report_id", data)
        self.assertEqual(data["session_id"], self.reliance_session_id)
        self.assertEqual(data["document_id"], self.reliance_doc_id)
        self.assertEqual(data["company"], "Reliance Industries")
        self.assertEqual(data["reporting_basis"], "consolidated")

        # Executive summary
        exec_sum = data["executive_summary"]
        self.assertIn("Reliance Industries", exec_sum["company"])
        self.assertTrue(len(exec_sum["highlights"]) >= 2)
        # Revenue was 980,136 vs 914,472 (increased by 7.18%)
        self.assertTrue(any("980,136" in h and "7.18%" in h for h in exec_sum["highlights"]))

        # Key financials
        kf = data["key_financials"]
        self.assertEqual(len(kf), 4)  # 2 revenue + 2 net profit
        rev_2025 = next(m for m in kf if m["metric"] == "revenue" and m["financial_year"] == "2024-25")
        self.assertEqual(rev_2025["value"], 980136.0)
        self.assertEqual(rev_2025["page"], 100)

        # Citations
        citations = data["citations"]
        self.assertTrue(len(citations) >= 1)
        cite_pages = [c["page_number"] for c in citations]
        self.assertIn(100, cite_pages)

    # 9. Invalid session is rejected (404)
    def test_invalid_session_rejected_returns_404(self):
        response = self.client.post(
            "/sessions/non-existent-session-xyz/report",
            json={}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    # 10. Invalid or foreign document ID in session is rejected (404)
    def test_foreign_document_id_in_session_rejected(self):
        # Pass non-existent doc ID
        response = self.client.post(
            f"/sessions/{self.reliance_session_id}/report",
            json={"document_id": "invalid-foreign-doc-id-123"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("does not belong to session", response.json()["detail"].lower())

    # 11. Direct document report endpoint works
    def test_direct_document_report_endpoint(self):
        response = self.client.post(
            f"/documents/{self.reliance_doc_id}/report",
            json={"reporting_basis": "standalone"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reporting_basis"], "standalone")
        # Red flag RF001 for standalone revenue decline of 2.76%
        red_flags = data["executive_summary"]["red_flags"]
        self.assertTrue(any("RF001" in rf or "2.76%" in rf for rf in red_flags))


if __name__ == "__main__":
    unittest.main()
