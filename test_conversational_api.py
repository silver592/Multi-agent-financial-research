# test_conversational_api.py
# Milestone 3 - Phase 6: Automated test suite for Conversational Research API
# Tests both /documents/{document_id}/research and /sessions/{session_id}/research
# Covers:
# 1. Normal financial question with relevant evidence
# 2. Multi-part financial question
# 3. Question with insufficient supporting evidence
# 4. Invalid document or session identifier handling (404 and 400)
# 5. Correct citation fields, page numbers, chunk IDs, and source text preservation
# 6. Follow-up questions in the same session preserving session and document context
# 7. Document isolation preventing foreign document leakage
# 8. Empty question validation (400)

import unittest
from fastapi.testclient import TestClient

from main import app


class TestConversationalResearchAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Real indexed documents & sessions in research.db
        cls.reliance_session_id = "8b14afa0-9d0a-4487-8c2f-ff6f9588c276"
        cls.reliance_doc_id = "87bee45d-2ab7-4ee9-8724-8635305692be"

        cls.infosys_session_id = "cccb4108-0f0b-4568-960d-02396dcf2856"
        cls.infosys_doc_id = "40b20e4f-dc46-421b-808d-d219a0b96460"

        cls.tcs_session_id = "423def80-8459-47ec-bc46-5d2b8b810654"
        cls.tcs_doc_id = "2baf3782-7723-4e1e-bdcf-3a008164aa95"

    # 1. Normal financial question with relevant evidence
    def test_normal_financial_question_reliance(self):
        question = "What was the company's consolidated revenue from operations in FY 2024-25 and FY 2023-24?"
        response = self.client.post(
            f"/sessions/{self.reliance_session_id}/research",
            json={"question": question, "document_id": self.reliance_doc_id}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["question"], question)
        self.assertEqual(data["document_id"], self.reliance_doc_id)
        self.assertEqual(data["session_id"], self.reliance_session_id)
        self.assertIn("Reliance Industries", data["company"])
        self.assertIn("980,136", data["answer"])
        self.assertIn("914,472", data["answer"])

        # Check citations
        self.assertTrue(len(data["citations"]) > 0)
        cite_pages = [c["page_number"] for c in data["citations"]]
        self.assertIn(100, cite_pages)

    # 2. Multi-part financial question
    def test_multipart_financial_question_infosys(self):
        question = (
            "What was the company's revenue in the two reported financial years, "
            "what was the percentage change, and did the Red Flag Agent identify a revenue-decline warning?"
        )
        response = self.client.post(
            f"/sessions/{self.infosys_session_id}/research",
            json={"question": question}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["document_id"], self.infosys_doc_id)
        self.assertEqual(data["session_id"], self.infosys_session_id)
        self.assertIn("162,990", data["answer"])
        self.assertIn("Red Flag Agent Status:", data["answer"])
        self.assertTrue(len(data["findings"]) >= 2)

    # 3. Question with insufficient supporting evidence
    def test_insufficient_evidence_question(self):
        question = "Why is the sky blue?"
        response = self.client.post(
            f"/sessions/{self.reliance_session_id}/research",
            json={"question": question}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("insufficient evidence", data["answer"].lower())
        self.assertTrue(len(data["limitations"]) > 0)
        self.assertTrue(any("insufficient" in lim.lower() or "no relevant evidence" in lim.lower() for lim in data["limitations"]))

    # 4. Invalid document or session identifier handling
    def test_invalid_session_id_returns_404(self):
        response = self.client.post(
            "/sessions/non-existent-session-id-12345/research",
            json={"question": "What is the revenue?"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_invalid_document_id_in_session_returns_404(self):
        response = self.client.post(
            f"/sessions/{self.reliance_session_id}/research",
            json={"question": "What is the revenue?", "document_id": "non-existent-doc-id-9999"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("does not belong to session", response.json()["detail"].lower())

    def test_foreign_document_id_in_session_rejected(self):
        # Passing Infosys doc_id into Reliance session must be rejected
        response = self.client.post(
            f"/sessions/{self.reliance_session_id}/research",
            json={"question": "What is the revenue?", "document_id": self.infosys_doc_id}
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("does not belong to session", response.json()["detail"].lower())

    # 5. Correct citation fields, page numbers, chunk IDs, and source text preservation
    def test_citation_fields_and_source_text(self):
        question = "What was the standalone revenue from operations?"
        response = self.client.post(
            f"/documents/{self.reliance_doc_id}/research",
            json={"question": question}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["session_id"], self.reliance_session_id)
        self.assertTrue(len(data["citations"]) > 0)
        first_cite = data["citations"][0]

        self.assertEqual(first_cite["document_id"], self.reliance_doc_id)
        self.assertIsNotNone(first_cite["page_number"])
        self.assertIsNotNone(first_cite["chunk_id"])
        self.assertTrue(len(first_cite["source_text"]) > 0)

    # 6. Follow-up questions in the same session preserving session context
    def test_followup_questions_in_same_session(self):
        # Turn 1: Ask about revenue
        turn1 = self.client.post(
            f"/sessions/{self.reliance_session_id}/research",
            json={"question": "What was the consolidated revenue in FY 2024-25 and FY 2023-24?"}
        )
        self.assertEqual(turn1.status_code, 200)
        d1 = turn1.json()
        self.assertEqual(d1["session_id"], self.reliance_session_id)
        self.assertEqual(d1["document_id"], self.reliance_doc_id)
        self.assertIn("980,136", d1["answer"])

        # Turn 2: Follow-up question about Red Flag warnings in same session
        turn2 = self.client.post(
            f"/sessions/{self.reliance_session_id}/research",
            json={"question": "Did the Red Flag Agent identify any revenue-decline warning?"}
        )
        self.assertEqual(turn2.status_code, 200)
        d2 = turn2.json()
        self.assertEqual(d2["session_id"], self.reliance_session_id)
        self.assertEqual(d2["document_id"], self.reliance_doc_id)
        self.assertIn("Red Flag Agent Status:", d2["answer"])

        # Turn 3: Follow-up question about equity dividends in same session
        turn3 = self.client.post(
            f"/sessions/{self.reliance_session_id}/research",
            json={"question": "What was the dividend on equity shares?"}
        )
        self.assertEqual(turn3.status_code, 200)
        d3 = turn3.json()
        self.assertEqual(d3["session_id"], self.reliance_session_id)
        self.assertEqual(d3["document_id"], self.reliance_doc_id)
        self.assertTrue(len(d3["findings"]) > 0)

    # 7. Empty question returns 400
    def test_empty_question_returns_400(self):
        response = self.client.post(
            f"/sessions/{self.reliance_session_id}/research",
            json={"question": "   "}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be empty", response.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
