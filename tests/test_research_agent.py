# test_research_agent.py
# Comprehensive test suite for Milestone 3 - Phase 4: Research Agent.
# Covers all 8 core requirements and user refinements:
# 1. Supported question retrieving evidence and returning citations
# 2. Multi-part financial question (revenue, % change, Red Flag status)
# 3. Document isolation: strictly prevents cross-document data leakage
# 4. Unanswerable question: acknowledges insufficient evidence without hallucinating
# 5. Missing / invalid document ID (HTTP 404)
# 6. Missing / empty question (HTTP 400)
# 7. Missing source metadata or incomplete retrieval handling
# 8. Boundary conditions for percentage change & Red Flag Agent thresholds (0%, <20%, ==20%, >20%)
# 9. Arithmetic verification of Python deterministic calculation
# 10. FastAPI integration test via TestClient

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from agents.research_agent import (
    answer_research_question,
    calculate_percentage_change,
    parse_question_intents,
)
from agents.red_flag_agent import analyze_revenue_candidates


class TestResearchAgentUnit(unittest.TestCase):
    """Unit tests for deterministic calculations, boundary rules, and validation."""

    def test_arithmetic_verification(self):
        """Independently verifies that percentage calculation matches exact math."""
        # Reliance standalone: 532792 vs 547942
        curr, prev = 532792, 547942
        expected_pct = ((curr - prev) / prev) * 100.0  # -2.76489...
        pct, formula = calculate_percentage_change(curr, prev)
        self.assertEqual(pct, -2.76)
        self.assertAlmostEqual(pct, expected_pct, places=2)
        self.assertIn("((532,792 - 547,942) / 547,942) * 100 = -2.76%", formula)

        # Reliance consolidated: 980136 vs 914472
        curr_c, prev_c = 980136, 914472
        expected_pct_c = ((curr_c - prev_c) / prev_c) * 100.0  # +7.1805...
        pct_c, formula_c = calculate_percentage_change(curr_c, prev_c)
        self.assertEqual(pct_c, 7.18)
        self.assertAlmostEqual(pct_c, expected_pct_c, places=2)

    def test_zero_or_negative_denominator_handling(self):
        """Verifies that invalid or zero previous revenue raises ValueError."""
        with self.assertRaises(ValueError):
            calculate_percentage_change(1000, 0)
        with self.assertRaises(ValueError):
            calculate_percentage_change(1000, -500)

    def test_red_flag_agent_boundary_zero_percent_change(self):
        """Boundary test 1: 0% change must not trigger a decline warning."""
        candidates = [{
            "metric": "revenue_from_operations",
            "statement_type": "consolidated",
            "values_found": [1000, 1000],
            "financial_years_found": ["2024-25", "2023-24"],
            "unit": "crore",
            "source": {"document_id": "doc_zero", "page_number": 10, "chunk_id": "c1"},
        }]
        result = analyze_revenue_candidates("doc_zero", candidates)
        self.assertEqual(result["red_flag_count"], 0)
        self.assertEqual(len(result["red_flags"]), 0)

    def test_red_flag_agent_boundary_decline_below_20_percent(self):
        """Boundary test 2: Decline strictly less than 20% (e.g. -10%) triggers 'medium' severity."""
        candidates = [{
            "metric": "revenue_from_operations",
            "statement_type": "consolidated",
            "values_found": [900, 1000],  # -10% change
            "financial_years_found": ["2024-25", "2023-24"],
            "unit": "crore",
            "source": {"document_id": "doc_med", "page_number": 10, "chunk_id": "c2"},
        }]
        result = analyze_revenue_candidates("doc_med", candidates)
        self.assertEqual(result["red_flag_count"], 1)
        flag = result["red_flags"][0]
        self.assertEqual(flag["severity"], "medium")
        self.assertEqual(flag["evidence"]["change_percent"], -10.0)

    def test_red_flag_agent_boundary_exactly_20_percent_decline(self):
        """Boundary test 3: Decline of exactly 20% (-20.0%) triggers 'high' severity per <= -20 rule."""
        candidates = [{
            "metric": "revenue_from_operations",
            "statement_type": "consolidated",
            "values_found": [800, 1000],  # Exactly -20% change
            "financial_years_found": ["2024-25", "2023-24"],
            "unit": "crore",
            "source": {"document_id": "doc_exact20", "page_number": 10, "chunk_id": "c3"},
        }]
        result = analyze_revenue_candidates("doc_exact20", candidates)
        self.assertEqual(result["red_flag_count"], 1)
        flag = result["red_flags"][0]
        self.assertEqual(flag["severity"], "high")
        self.assertEqual(flag["evidence"]["change_percent"], -20.0)

    def test_red_flag_agent_boundary_decline_above_20_percent(self):
        """Boundary test 4: Decline greater than 20% (e.g. -25%) triggers 'high' severity."""
        candidates = [{
            "metric": "revenue_from_operations",
            "statement_type": "consolidated",
            "values_found": [750, 1000],  # -25% change
            "financial_years_found": ["2024-25", "2023-24"],
            "unit": "crore",
            "source": {"document_id": "doc_high", "page_number": 10, "chunk_id": "c4"},
        }]
        result = analyze_revenue_candidates("doc_high", candidates)
        self.assertEqual(result["red_flag_count"], 1)
        flag = result["red_flags"][0]
        self.assertEqual(flag["severity"], "high")
        self.assertEqual(flag["evidence"]["change_percent"], -25.0)

    def test_input_validation_empty_inputs(self):
        """Verifies that empty document_id or empty question raises ValueError."""
        with self.assertRaises(ValueError):
            answer_research_question("", "What is the revenue?")
        with self.assertRaises(ValueError):
            answer_research_question("   ", "What is the revenue?")
        with self.assertRaises(ValueError):
            answer_research_question("doc_123", "")
        with self.assertRaises(ValueError):
            answer_research_question("doc_123", "   \t\n")

    def test_missing_source_metadata_handling(self):
        """Verifies that incomplete metadata fields do not cause crashes."""
        with patch("agents.research_agent.get_document_chunks") as mock_chunks, \
             patch("agents.research_agent.extract_revenue") as mock_extract, \
             patch("agents.research_agent.analyze_revenue_candidates") as mock_rf:

            mock_chunks.return_value = [{"chunk_id": "c1", "chunk_text": "Text", "metadata": {}}]
            mock_extract.return_value = [{
                "statement_type": "consolidated",
                "values_found": [5000, 4000],
                "financial_years_found": [],
                "unit": "crore",
                "source": {}  # Missing page_number, chunk_id, etc.
            }]
            mock_rf.return_value = {"red_flag_count": 0, "red_flags": []}

            res = answer_research_question("doc_missing_meta", "What was the revenue and percentage change?")
            self.assertIn("Consolidated revenue: Rs. 5,000 crore (current) vs Rs. 4,000 crore (previous)", res["answer"])
            self.assertIn("+25.00%", res["answer"])

    def test_document_isolation_prevent_leakage(self):
        """Verifies that chunks from another document are strictly discarded."""
        with patch("agents.research_agent.get_document_chunks") as mock_chunks, \
             patch("agents.research_agent.search_chunks") as mock_search, \
             patch("agents.research_agent.create_embedding") as mock_emb:

            mock_chunks.return_value = []
            mock_emb.return_value = [0.1, 0.2]
            # Simulate a search that erroneously returned a foreign document chunk
            mock_search.return_value = [
                {
                    "chunk_id": "foreign_chunk_1",
                    "chunk_text": "Retail stores in foreign company",
                    "metadata": {"document_id": "foreign_doc_999", "page_number": 42}
                }
            ]

            res = answer_research_question("target_doc_111", "Tell me about retail stores.")
            # Because foreign_doc_999 does not match target_doc_111, it must be filtered out
            self.assertEqual(len(res["citations"]), 0)
            self.assertIn("Insufficient evidence", res["answer"])


class TestResearchAgentIntegration(unittest.TestCase):
    """Integration tests running against real indexed documents and FastAPI TestClient."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Real document IDs stored in SQLite & ChromaDB
        cls.reliance_doc_id = "87bee45d-2ab7-4ee9-8724-8635305692be"
        cls.tcs_doc_id = "2baf3782-7723-4e1e-bdcf-3a008164aa95"
        cls.infosys_doc_id = "40b20e4f-dc46-421b-808d-d219a0b96460"

    def test_endpoint_multipart_question_reliance(self):
        """
        Tests multi-part question on Reliance 2024-25:
        Revenue, percentage change, and Red Flag Agent warning.
        Reliance has 1 medium red flag (-2.76% standalone decline).
        """
        question = (
            "What was the company's revenue in the two reported financial years, "
            "what was the percentage change, and did the Red Flag Agent identify a revenue-decline warning?"
        )
        response = self.client.post(
            f"/documents/{self.reliance_doc_id}/research",
            json={"question": question}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["document_id"], self.reliance_doc_id)
        self.assertEqual(data["company"], "Reliance Industries")

        # Answer content checks
        answer = data["answer"]
        self.assertIn("532,792", answer)
        self.assertIn("980,136", answer)
        self.assertIn("-2.76%", answer)
        self.assertIn("+7.18%", answer)
        self.assertIn("RF001", answer)
        self.assertIn("medium severity", answer)

        # Findings checks
        self.assertGreaterEqual(len(data["findings"]), 3)
        parts = [f["part"] for f in data["findings"]]
        self.assertIn("Revenue in reported financial years", parts)
        self.assertIn("Percentage change calculation", parts)
        self.assertIn("Red Flag Agent analysis", parts)

        # Real citation checks
        citations = data["citations"]
        self.assertGreaterEqual(len(citations), 2)
        pages = [c["page_number"] for c in citations]
        self.assertIn(58, pages)   # Standalone statement page
        self.assertIn(100, pages)  # Consolidated statement page

        for c in citations:
            self.assertEqual(c["document_id"], self.reliance_doc_id)
            self.assertIsNotNone(c["chunk_id"])

    def test_endpoint_multipart_question_tcs(self):
        """
        Tests multi-part question on TCS 2024-25:
        TCS grew in both standalone (+6.17%) and consolidated (+5.99%).
        Red Flag Agent should report 0 warnings.
        """
        question = (
            "What was the company's revenue in the two reported financial years, "
            "what was the percentage change, and did the Red Flag Agent identify a revenue-decline warning?"
        )
        response = self.client.post(
            f"/documents/{self.tcs_doc_id}/research",
            json={"question": question}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["company"], "TCS")
        answer = data["answer"]
        self.assertIn("255,324", answer)
        self.assertIn("214,853", answer)
        self.assertIn("No revenue-decline warning was identified", answer)

    def test_endpoint_multipart_question_infosys(self):
        """
        Tests multi-part question on Infosys 2024-25:
        Revenue grew (+6.07%). Red flag count = 0.
        """
        question = (
            "What was the company's revenue in the two reported financial years, "
            "what was the percentage change, and did the Red Flag Agent identify a revenue-decline warning?"
        )
        response = self.client.post(
            f"/documents/{self.infosys_doc_id}/research",
            json={"question": question}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["company"], "Infosys")
        answer = data["answer"]
        self.assertIn("162,990", answer)
        self.assertIn("153,670", answer)
        self.assertIn("No revenue-decline warning was identified", answer)

    def test_endpoint_unanswerable_question(self):
        """
        Tests unanswerable question:
        Must acknowledge insufficient evidence, return empty citations, and record limitations.
        """
        question = "What were the sales figures for space tourism rockets in Mars in 2040?"
        response = self.client.post(
            f"/documents/{self.reliance_doc_id}/research",
            json={"question": question}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("Insufficient evidence found in the document", data["answer"])
        self.assertEqual(len(data["citations"]), 0)
        self.assertGreater(len(data["limitations"]), 0)

    def test_endpoint_invalid_document_id_returns_404(self):
        """Tests that a non-existent document ID returns HTTP 404."""
        response = self.client.post(
            "/documents/non_existent_document_id_12345/research",
            json={"question": "What was the revenue?"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_endpoint_empty_question_returns_400(self):
        """Tests that an empty or whitespace question returns HTTP 400."""
        response = self.client.post(
            f"/documents/{self.reliance_doc_id}/research",
            json={"question": "   "}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be empty", response.json()["detail"].lower())

        response_none = self.client.post(
            f"/documents/{self.reliance_doc_id}/research",
            json={"question": ""}
        )
        self.assertEqual(response_none.status_code, 400)

    def test_endpoint_unsupported_sky_blue_returns_insufficient_evidence(self):
        """
        Regression test:
        'Why is the sky blue?' must return an explicit insufficient evidence answer,
        no citations, and a meaningful limitation entry for Reliance annual report.
        """
        response = self.client.post(
            f"/documents/{self.reliance_doc_id}/research",
            json={"question": "Why is the sky blue?"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("Insufficient evidence found in the document", data["answer"])
        self.assertEqual(len(data["citations"]), 0)
        self.assertEqual(len(data["findings"]), 0)
        self.assertGreater(len(data["limitations"]), 0)
        self.assertTrue(any("sky blue" in lim for lim in data["limitations"]))

    def test_endpoint_valid_topical_financial_question(self):
        """
        Tests that legitimate non-revenue financial report questions (e.g. dividend on equity shares)
        still successfully retrieve evidence, return answers, and provide citations.
        """
        response = self.client.post(
            f"/documents/{self.reliance_doc_id}/research",
            json={"question": "What is the dividend recommended for equity shares?"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("Additional evidence on", data["answer"])
        self.assertGreater(len(data["findings"]), 0)
        self.assertGreater(len(data["citations"]), 0)
        # Check citations have valid source text and page numbers
        for c in data["citations"]:
            self.assertEqual(c["document_id"], self.reliance_doc_id)
            self.assertIsNotNone(c["page_number"])
            self.assertGreater(len(c.get("source_text", "")), 0)

    def test_red_flag_finding_citation_has_non_empty_source_text(self):
        """
        Verifies that the Red Flag Agent finding's citation is populated with real,
        non-empty source text from the matching candidate and chunk.
        """
        question = (
            "What was the company's revenue in the two reported financial years, "
            "what was the percentage change, and did the Red Flag Agent identify a revenue-decline warning?"
        )
        response = self.client.post(
            f"/documents/{self.reliance_doc_id}/research",
            json={"question": question}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        rf_findings = [f for f in data["findings"] if f["part"] == "Red Flag Agent analysis"]
        self.assertGreaterEqual(len(rf_findings), 1)

        rf_finding = rf_findings[0]
        citation = rf_finding["citation"]
        self.assertIsNotNone(citation)
        self.assertEqual(citation["document_id"], self.reliance_doc_id)
        self.assertEqual(citation["page_number"], 58)
        self.assertEqual(citation["chunk_id"], "87bee45d-2ab7-4ee9-8724-8635305692be_p58_c546")
        # Ensure source_text is non-empty and contains real financial statement text
        source_text = citation.get("source_text", "")
        self.assertGreater(len(source_text), 0)
        self.assertIn("Revenue from Operations", source_text)

    def test_endpoint_consolidated_revenue_excludes_irrelevant_page_5(self):
        """
        Regression test:
        For 'What was Reliance Industries' consolidated revenue in FY 2024-25 and FY 2023-24,
        and what was the percentage change?':
        - Returns correct consolidated revenue figures (980,136 and 914,472)
        - Returns correct percentage change (+7.18%)
        - Cites page 100
        - Strictly does NOT cite or include page 5 as supporting evidence
        """
        question = (
            "What was Reliance Industries' consolidated revenue in FY 2024-25 and FY 2023-24, "
            "and what was the percentage change?"
        )
        response = self.client.post(
            f"/documents/{self.reliance_doc_id}/research",
            json={"question": question}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        answer = data["answer"]
        self.assertIn("980,136", answer)
        self.assertIn("914,472", answer)
        self.assertIn("+7.18%", answer)
        # Standalone revenue was not requested, so answer should focus on consolidated
        self.assertIn("Consolidated revenue", answer)

        # Check citations
        citations = data["citations"]
        page_numbers = [c["page_number"] for c in citations]
        self.assertIn(100, page_numbers)
        self.assertNotIn(5, page_numbers, "Page 5 must not be included as supporting evidence for consolidated revenue calculation")

        # Check findings
        finding_pages = [
            f["citation"]["page_number"]
            for f in data["findings"]
            if f.get("citation") and f["citation"].get("page_number")
        ]
        self.assertIn(100, finding_pages)
        self.assertNotIn(5, finding_pages, "Page 5 must not be present in findings for consolidated revenue calculation")


if __name__ == "__main__":
    unittest.main()
