# test_comparison_agent.py
# Comprehensive test suite for Milestone 3 - Phase 5: Comparison Agent.
# Covers all 14 core unit test requirements and FastAPI endpoint integration tests:
# 1. Two companies with comparable revenue values
# 2. Correct absolute difference calculation
# 3. Correct percentage difference calculation relative to selected reference company
# 4. Correct alignment of revenue and net profit as separate metrics
# 5. Handling of missing net profit in one company while revenue is available
# 6. Handling of mismatched financial years
# 7. Handling of standalone vs. consolidated reporting mismatch
# 8. Handling of incompatible units (e.g. crores vs. lakhs or millions)
# 9. Rejection of duplicate or invalid document IDs
# 10. Proper document isolation (candidate from one doc is never attributed to another)
# 11. Proper citation preservation (page number, chunk ID, source text)
# 12. Zero or missing percentage denominator handled safely without division by zero
# 13. Ambiguous duplicate candidates flagged or handled cleanly without silent arbitrary selection
# 14. Missing page number or chunk ID does not fabricate citation metadata
# 15. FastAPI endpoint integration tests with real indexed documents (Reliance vs. Infosys)

import unittest
from fastapi.testclient import TestClient

from app.main import app
from agents.comparison_agent import (
    compare_company_metrics,
    select_company_metric_value,
    normalize_metric_name,
    normalize_financial_year,
    normalize_unit,
)


class TestComparisonAgentUnit(unittest.TestCase):
    """Unit tests for deterministic calculations, isolation, citation, and boundary handling."""

    def setUp(self):
        # Base synthetic candidate data for unit tests
        self.doc_a = "doc_alpha_111"
        self.doc_b = "doc_beta_222"

        self.candidates_a = {
            "revenue": [
                {
                    "metric": "revenue_from_operations",
                    "statement_type": "consolidated",
                    "values_found": [100000.0, 90000.0],
                    "financial_years_found": ["2024-25", "2023-24"],
                    "unit": "crore",
                    "source": {
                        "document_id": self.doc_a,
                        "page_number": 45,
                        "chunk_id": f"{self.doc_a}_p45_c1",
                        "original_text": "Revenue from operations: 100000 90000",
                    },
                }
            ],
            "net_profit": [
                {
                    "metric": "profit_for_the_year",
                    "statement_type": "consolidated",
                    "values_found": [20000.0, 18000.0],
                    "financial_years_found": ["2024-25", "2023-24"],
                    "unit": "crore",
                    "source": {
                        "document_id": self.doc_a,
                        "page_number": 46,
                        "chunk_id": f"{self.doc_a}_p46_c2",
                        "original_text": "Profit for the year: 20000 18000",
                    },
                }
            ],
        }

        self.candidates_b = {
            "revenue": [
                {
                    "metric": "revenue_from_operations",
                    "statement_type": "consolidated",
                    "values_found": [80000.0, 75000.0],
                    "financial_years_found": ["2024-25", "2023-24"],
                    "unit": "crore",
                    "source": {
                        "document_id": self.doc_b,
                        "page_number": 60,
                        "chunk_id": f"{self.doc_b}_p60_c3",
                        "original_text": "Revenue from operations: 80000 75000",
                    },
                }
            ],
            "net_profit": [
                {
                    "metric": "profit_for_the_year",
                    "statement_type": "consolidated",
                    "values_found": [15000.0, 14000.0],
                    "financial_years_found": ["2024-25", "2023-24"],
                    "unit": "crore",
                    "source": {
                        "document_id": self.doc_b,
                        "page_number": 61,
                        "chunk_id": f"{self.doc_b}_p61_c4",
                        "original_text": "Profit for the year: 15000 14000",
                    },
                }
            ],
        }

        self.synthetic_candidates = {
            self.doc_a: self.candidates_a,
            self.doc_b: self.candidates_b,
        }

    # -------------------------------------------------------------------------
    # Requirement 1: Two companies with comparable revenue values
    # -------------------------------------------------------------------------
    def test_two_companies_comparable_revenue(self):
        """Tests that two companies with matching year and basis compare cleanly."""
        res = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue"],
            candidates_by_doc=self.synthetic_candidates,
        )
        self.assertEqual(len(res["metrics"]), 1)
        m = res["metrics"][0]
        self.assertEqual(m["metric"], "revenue")
        self.assertEqual(m["status"], "compared")
        self.assertEqual(len(m["values"]), 2)
        self.assertEqual(m["values"][0]["value"], 100000.0)
        self.assertEqual(m["values"][1]["value"], 80000.0)

    # -------------------------------------------------------------------------
    # Requirement 2: Correct absolute difference calculation
    # -------------------------------------------------------------------------
    def test_correct_absolute_difference(self):
        """Verifies absolute difference is always non-negative: |v2 - v1|."""
        # doc_a = 100000, doc_b = 80000 -> absolute diff = 20000
        res = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue"],
            candidates_by_doc=self.synthetic_candidates,
        )
        m = res["metrics"][0]
        self.assertEqual(m["absolute_difference"], 20000.0)

        # Reversed order: doc_b first, doc_a second -> absolute diff still 20000
        res_rev = compare_company_metrics(
            document_ids=[self.doc_b, self.doc_a],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue"],
            candidates_by_doc=self.synthetic_candidates,
        )
        self.assertEqual(res_rev["metrics"][0]["absolute_difference"], 20000.0)

    # -------------------------------------------------------------------------
    # Requirement 3: Correct percentage difference calculation relative to reference company
    # -------------------------------------------------------------------------
    def test_correct_percentage_difference_relative_to_reference(self):
        """
        Verifies percentage calculation:
        With doc_a as reference (100000):
          signed diff = 80000 - 100000 = -20000
          pct diff = ((80000 - 100000) / 100000) * 100 = -20.00%
        With doc_b as reference (80000):
          signed diff = 100000 - 80000 = +20000
          pct diff = ((100000 - 80000) / 80000) * 100 = +25.00%
        """
        # Ref = doc_a
        res_a = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue"],
            reference_document_id=self.doc_a,
            candidates_by_doc=self.synthetic_candidates,
        )
        m_a = res_a["metrics"][0]
        self.assertEqual(m_a["signed_difference"], -20000.0)
        self.assertEqual(m_a["percentage_difference"], -20.0)
        self.assertIn(self.doc_a, m_a["percentage_reference"])

        # Ref = doc_b
        res_b = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue"],
            reference_document_id=self.doc_b,
            candidates_by_doc=self.synthetic_candidates,
        )
        m_b = res_b["metrics"][0]
        self.assertEqual(m_b["signed_difference"], 20000.0)
        self.assertEqual(m_b["percentage_difference"], 25.0)
        self.assertIn(self.doc_b, m_b["percentage_reference"])

    # -------------------------------------------------------------------------
    # Requirement 4: Correct alignment of revenue and net profit as separate metrics
    # -------------------------------------------------------------------------
    def test_revenue_and_net_profit_separate_metrics(self):
        """Verifies both revenue and net profit are evaluated as separate metrics."""
        res = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue", "net_profit"],
            candidates_by_doc=self.synthetic_candidates,
        )
        self.assertEqual(len(res["metrics"]), 2)
        metric_names = [m["metric"] for m in res["metrics"]]
        self.assertIn("revenue", metric_names)
        self.assertIn("net_profit", metric_names)

        # Revenue
        rev = next(m for m in res["metrics"] if m["metric"] == "revenue")
        self.assertEqual(rev["absolute_difference"], 20000.0)

        # Net Profit: 20000 vs 15000 -> absolute diff = 5000
        np = next(m for m in res["metrics"] if m["metric"] == "net_profit")
        self.assertEqual(np["absolute_difference"], 5000.0)
        self.assertEqual(np["status"], "compared")

    # -------------------------------------------------------------------------
    # Requirement 5: Handling of missing net profit in one company
    # -------------------------------------------------------------------------
    def test_missing_net_profit_in_one_company(self):
        """
        When doc_a has net profit but doc_b has NO net profit candidate:
        - revenue comparison succeeds (status='compared')
        - net_profit comparison yields status='partial_data', exactly 1 value, None difference
        - limitations records that doc_b is missing net profit
        """
        cand_b_no_np = {
            "revenue": self.candidates_b["revenue"],
            "net_profit": [],  # doc_b has no net profit
        }
        test_cands = {
            self.doc_a: self.candidates_a,
            self.doc_b: cand_b_no_np,
        }
        res = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue", "net_profit"],
            candidates_by_doc=test_cands,
        )
        rev = next(m for m in res["metrics"] if m["metric"] == "revenue")
        self.assertEqual(rev["status"], "compared")

        np = next(m for m in res["metrics"] if m["metric"] == "net_profit")
        self.assertEqual(np["status"], "partial_data")
        self.assertEqual(len(np["values"]), 1)
        self.assertEqual(np["values"][0]["document_id"], self.doc_a)
        self.assertIsNone(np["absolute_difference"])
        self.assertIsNone(np["percentage_difference"])
        self.assertTrue(any(self.doc_b in lim for lim in res["limitations"]))

    # -------------------------------------------------------------------------
    # Requirement 6: Handling of mismatched financial years
    # -------------------------------------------------------------------------
    def test_mismatched_financial_years(self):
        """
        When querying 2024-25, and doc_b only has 2022-23 and 2021-22:
        - doc_b yields no candidate for 2024-25
        - metric status is 'partial_data' and limitation is noted
        """
        cand_b_old_years = {
            "revenue": [
                {
                    "metric": "revenue_from_operations",
                    "statement_type": "consolidated",
                    "values_found": [70000.0, 65000.0],
                    "financial_years_found": ["2022-23", "2021-22"],
                    "unit": "crore",
                    "source": {"document_id": self.doc_b, "page_number": 10},
                }
            ],
            "net_profit": [],
        }
        test_cands = {
            self.doc_a: self.candidates_a,
            self.doc_b: cand_b_old_years,
        }
        res = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue"],
            candidates_by_doc=test_cands,
        )
        rev = res["metrics"][0]
        self.assertEqual(rev["status"], "partial_data")
        self.assertEqual(len(rev["values"]), 1)
        self.assertIsNone(rev["absolute_difference"])
        self.assertTrue(any("2024-25" in lim for lim in res["limitations"]))

    # -------------------------------------------------------------------------
    # Requirement 7: Handling of standalone vs. consolidated reporting mismatch
    # -------------------------------------------------------------------------
    def test_standalone_vs_consolidated_mismatch(self):
        """
        When querying 'consolidated', and doc_b only has 'standalone' revenue:
        - doc_b standalone candidate is NOT matched
        - metric status is 'partial_data'
        """
        cand_b_standalone_only = {
            "revenue": [
                {
                    "metric": "revenue_from_operations",
                    "statement_type": "standalone",
                    "values_found": [60000.0, 55000.0],
                    "financial_years_found": ["2024-25", "2023-24"],
                    "unit": "crore",
                    "source": {"document_id": self.doc_b, "page_number": 20},
                }
            ],
            "net_profit": [],
        }
        test_cands = {
            self.doc_a: self.candidates_a,
            self.doc_b: cand_b_standalone_only,
        }
        res = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue"],
            candidates_by_doc=test_cands,
        )
        rev = res["metrics"][0]
        self.assertEqual(rev["status"], "partial_data")
        self.assertEqual(len(rev["values"]), 1)
        self.assertEqual(rev["values"][0]["document_id"], self.doc_a)

    # -------------------------------------------------------------------------
    # Requirement 8: Handling of incompatible units
    # -------------------------------------------------------------------------
    def test_incompatible_units_handling(self):
        """
        When doc_a is in 'crore' and doc_b is in 'million':
        - Units are marked incompatible
        - status='incompatible_units'
        - differences are not calculated directly
        - note records incompatible units
        """
        cand_b_million = {
            "revenue": [
                {
                    "metric": "revenue_from_operations",
                    "statement_type": "consolidated",
                    "values_found": [80000.0, 75000.0],
                    "financial_years_found": ["2024-25", "2023-24"],
                    "unit": "million",
                    "source": {"document_id": self.doc_b, "page_number": 30},
                }
            ],
            "net_profit": [],
        }
        test_cands = {
            self.doc_a: self.candidates_a,
            self.doc_b: cand_b_million,
        }
        res = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue"],
            candidates_by_doc=test_cands,
        )
        rev = res["metrics"][0]
        self.assertEqual(rev["status"], "incompatible_units")
        self.assertIsNone(rev["absolute_difference"])
        self.assertIsNone(rev["percentage_difference"])
        self.assertIn("incompatible units", rev["notes"].lower())

    # -------------------------------------------------------------------------
    # Requirement 9: Rejection of duplicate or invalid document IDs
    # -------------------------------------------------------------------------
    def test_duplicate_or_insufficient_document_ids_validation(self):
        """Validates that compare_company_metrics raises ValueError for invalid input sets."""
        # Fewer than 2 docs
        with self.assertRaises(ValueError):
            compare_company_metrics(
                document_ids=[self.doc_a],
                candidates_by_doc=self.synthetic_candidates,
            )

        # Duplicate doc IDs
        with self.assertRaises(ValueError):
            compare_company_metrics(
                document_ids=[self.doc_a, self.doc_a],
                candidates_by_doc=self.synthetic_candidates,
            )

        # Invalid reference_document_id
        with self.assertRaises(ValueError):
            compare_company_metrics(
                document_ids=[self.doc_a, self.doc_b],
                reference_document_id="non_existent_doc_id",
                candidates_by_doc=self.synthetic_candidates,
            )

    # -------------------------------------------------------------------------
    # Requirement 10: Proper document isolation
    # -------------------------------------------------------------------------
    def test_document_isolation(self):
        """
        Verifies that candidates tagged to a foreign document are NEVER attributed to doc_b.
        select_company_metric_value enforces document isolation via the expected_doc_id parameter.
        """
        # Cross-contaminated pool: candidates tagged to a foreign document, not doc_b
        contaminated_cands = [
            {
                "metric": "revenue_from_operations",
                "statement_type": "consolidated",
                "values_found": [999999.0],
                "financial_years_found": ["2024-25"],
                "unit": "crore",
                "source": {"document_id": "doc_foreign_999", "page_number": 99},
            }
        ]
        # Actual signature: (candidates, target_year, reporting_basis, expected_doc_id) -> (val, status, note)
        val, status, note = select_company_metric_value(
            candidates=contaminated_cands,
            target_year="2024-25",
            reporting_basis="consolidated",
            expected_doc_id=self.doc_b,
        )
        # Must be rejected because document_id 'doc_foreign_999' does not match target 'doc_beta_222'
        self.assertIsNone(val)
        self.assertEqual(status, "missing_data")
        self.assertIsNotNone(note)

    # -------------------------------------------------------------------------
    # Requirement 11: Proper citation preservation
    # -------------------------------------------------------------------------
    def test_citation_preservation(self):
        """
        Verifies that page number, chunk ID, and source text from extraction
        candidates are preserved intact without mutation or truncation.
        """
        res = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue"],
            candidates_by_doc=self.synthetic_candidates,
        )
        rev = res["metrics"][0]
        val_a = next(v for v in rev["values"] if v["document_id"] == self.doc_a)
        val_b = next(v for v in rev["values"] if v["document_id"] == self.doc_b)

        self.assertEqual(val_a["page"], 45)
        self.assertEqual(val_a["chunk_id"], f"{self.doc_a}_p45_c1")
        self.assertEqual(val_a["source_text"], "Revenue from operations: 100000 90000")

        self.assertEqual(val_b["page"], 60)
        self.assertEqual(val_b["chunk_id"], f"{self.doc_b}_p60_c3")
        self.assertEqual(val_b["source_text"], "Revenue from operations: 80000 75000")

    # -------------------------------------------------------------------------
    # Requirement 12: Zero or missing percentage denominator handled safely
    # -------------------------------------------------------------------------
    def test_zero_denominator_safe_handling(self):
        """
        When reference company has value = 0.0:
        - Division by zero is avoided
        - percentage_difference is None
        - notes clearly explain why percentage was not calculated
        """
        cand_zero_ref = {
            "revenue": [
                {
                    "metric": "revenue_from_operations",
                    "statement_type": "consolidated",
                    "values_found": [0.0, 0.0],
                    "financial_years_found": ["2024-25", "2023-24"],
                    "unit": "crore",
                    "source": {"document_id": self.doc_a, "page_number": 10},
                }
            ],
            "net_profit": [],
        }
        test_cands = {
            self.doc_a: cand_zero_ref,
            self.doc_b: self.candidates_b,
        }
        res = compare_company_metrics(
            document_ids=[self.doc_a, self.doc_b],
            financial_year="2024-25",
            reporting_basis="consolidated",
            metrics=["revenue"],
            reference_document_id=self.doc_a,
            candidates_by_doc=test_cands,
        )
        rev = res["metrics"][0]
        self.assertEqual(rev["status"], "compared")
        self.assertEqual(rev["absolute_difference"], 80000.0)
        self.assertIsNone(rev["percentage_difference"])
        self.assertIn("zero", rev["notes"].lower())

    # -------------------------------------------------------------------------
    # Requirement 13: Ambiguous duplicate candidates flagged cleanly
    # -------------------------------------------------------------------------
    def test_ambiguous_duplicate_candidates_flagged(self):
        """
        When a document has two conflicting candidates with different values for the same
        year and reporting basis, select_company_metric_value returns:
        - val = None (refuses to silently pick one)
        - status = 'ambiguous'
        - note describing the conflict
        """
        conflicting_cands = [
            {
                "metric": "revenue_from_operations",
                "statement_type": "consolidated",
                "values_found": [100000.0],
                "financial_years_found": ["2024-25"],
                "unit": "crore",
                "source": {"document_id": self.doc_a, "page_number": 45},
            },
            {
                "metric": "revenue_from_operations",
                "statement_type": "consolidated",
                "values_found": [120000.0],
                "financial_years_found": ["2024-25"],
                "unit": "crore",
                "source": {"document_id": self.doc_a, "page_number": 99},
            },
        ]
        val, status, note = select_company_metric_value(
            candidates=conflicting_cands,
            target_year="2024-25",
            reporting_basis="consolidated",
            expected_doc_id=self.doc_a,
        )
        self.assertIsNone(val)
        self.assertEqual(status, "ambiguous")
        self.assertIsNotNone(note)
        self.assertTrue("ambiguous" in note.lower() or "conflicting" in note.lower())

    # -------------------------------------------------------------------------
    # Requirement 14: Missing page number or chunk ID does not fabricate metadata
    # -------------------------------------------------------------------------
    def test_missing_metadata_does_not_fabricate(self):
        """
        When source metadata lacks page number and chunk ID:
        - Output fields remain None (not fabricated)
        - source_text is empty string or None (not invented)
        - val is a plain dict; access via val['key'], not val.key
        """
        cand_no_meta = [
            {
                "metric": "revenue_from_operations",
                "statement_type": "consolidated",
                "values_found": [50000.0],
                "financial_years_found": ["2024-25"],
                "unit": "crore",
                "source": {
                    "document_id": self.doc_a,
                    "page_number": None,
                    "chunk_id": None,
                    "original_text": None,
                },
            }
        ]
        # Actual signature: (candidates, target_year, reporting_basis, expected_doc_id) -> (val, status, note)
        val, status, note = select_company_metric_value(
            candidates=cand_no_meta,
            target_year="2024-25",
            reporting_basis="consolidated",
            expected_doc_id=self.doc_a,
        )
        self.assertIsNotNone(val)
        self.assertEqual(status, "comparable")
        self.assertIsNone(note)
        # val is a dict — access via keys, not attributes
        self.assertIsNone(val["page"])
        self.assertIsNone(val["chunk_id"])
        # source_text defaults to "" when original_text is None — not fabricated
        self.assertFalse(bool(val["source_text"]))


# -------------------------------------------------------------------------
# Requirement 15: FastAPI Integration Tests with Real Documents
# -------------------------------------------------------------------------
class TestComparisonAgentIntegration(unittest.TestCase):
    """Integration tests running against real indexed documents via FastAPI TestClient."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Real document IDs stored in SQLite & ChromaDB
        cls.reliance_doc_id = "87bee45d-2ab7-4ee9-8724-8635305692be"
        cls.infosys_doc_id = "40b20e4f-dc46-421b-808d-d219a0b96460"
        cls.tcs_doc_id = "2baf3782-7723-4e1e-bdcf-3a008164aa95"

    def test_endpoint_compare_reliance_and_infosys_revenue_and_profit(self):
        """
        Integration test:
        Compares Reliance Industries vs Infosys for FY 2024-25 (consolidated):
        - Revenue:
            Reliance: 980,136 crore (Page 100)
            Infosys: 162,990 crore (Page 276)
            Absolute Difference: 817,146 crore
            Percentage Difference relative to Reliance: -83.37%
        - Net Profit:
            Reliance: 80,787 crore (Page 100)
            Infosys: 26,750 crore (Page 276)
            Absolute Difference: 54,037 crore
            Percentage Difference relative to Reliance: -66.89%
        """
        payload = {
            "document_ids": [self.reliance_doc_id, self.infosys_doc_id],
            "financial_year": "FY 2024-25",
            "reporting_basis": "consolidated",
            "metrics": ["revenue", "net_profit"],
            "reference_document_id": self.reliance_doc_id,
        }
        response = self.client.post("/documents/compare", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("comparison_id", data)
        self.assertEqual(data["financial_year"], "2024-25")
        self.assertEqual(data["reporting_basis"], "consolidated")
        self.assertEqual(len(data["metrics"]), 2)

        # Revenue
        rev = next(m for m in data["metrics"] if m["metric"] == "revenue")
        self.assertEqual(rev["status"], "compared")
        self.assertEqual(len(rev["values"]), 2)

        val_rel_rev = next(v for v in rev["values"] if v["document_id"] == self.reliance_doc_id)
        val_inf_rev = next(v for v in rev["values"] if v["document_id"] == self.infosys_doc_id)

        self.assertEqual(val_rel_rev["value"], 980136.0)
        self.assertEqual(val_rel_rev["page"], 100)
        self.assertEqual(val_inf_rev["value"], 162990.0)
        self.assertEqual(val_inf_rev["page"], 276)

        self.assertEqual(rev["absolute_difference"], 817146.0)
        self.assertEqual(rev["signed_difference"], -817146.0)
        self.assertEqual(rev["percentage_difference"], -83.37)

        # Net Profit
        np = next(m for m in data["metrics"] if m["metric"] == "net_profit")
        self.assertEqual(np["status"], "compared")
        self.assertEqual(len(np["values"]), 2)

        val_rel_np = next(v for v in np["values"] if v["document_id"] == self.reliance_doc_id)
        val_inf_np = next(v for v in np["values"] if v["document_id"] == self.infosys_doc_id)

        self.assertEqual(val_rel_np["value"], 80787.0)
        self.assertEqual(val_rel_np["page"], 100)
        self.assertEqual(val_inf_np["value"], 26750.0)
        self.assertEqual(val_inf_np["page"], 276)

        self.assertEqual(np["absolute_difference"], 54037.0)
        self.assertEqual(np["signed_difference"], -54037.0)
        self.assertEqual(np["percentage_difference"], -66.89)

    def test_endpoint_compare_with_infosys_as_reference(self):
        """
        Integration test verifying reference company reversal:
        When Infosys is the reference company:
        - Revenue percentage difference: ((980,136 - 162,990) / 162,990) * 100 = +501.35%
        """
        payload = {
            "document_ids": [self.reliance_doc_id, self.infosys_doc_id],
            "financial_year": "FY 2024-25",
            "reporting_basis": "consolidated",
            "metrics": ["revenue"],
            "reference_document_id": self.infosys_doc_id,
        }
        response = self.client.post("/documents/compare", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        rev = data["metrics"][0]
        self.assertEqual(rev["signed_difference"], 817146.0)
        self.assertEqual(rev["percentage_difference"], 501.35)
        self.assertIn("Infosys", rev["percentage_reference"])

    def test_endpoint_compare_tcs_and_infosys(self):
        """
        Integration test:
        Compares TCS vs Infosys for FY 2024-25 (consolidated):
        TCS revenue: 255,324 cr, TCS net profit: 48,797 cr (Page 181)
        Infosys revenue: 162,990 cr, Infosys net profit: 26,750 cr (Page 276)
        """
        payload = {
            "document_ids": [self.tcs_doc_id, self.infosys_doc_id],
            "financial_year": "FY 2024-25",
            "reporting_basis": "consolidated",
            "metrics": ["revenue", "net_profit"],
            "reference_document_id": self.tcs_doc_id,
        }
        response = self.client.post("/documents/compare", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        rev = next(m for m in data["metrics"] if m["metric"] == "revenue")
        self.assertEqual(rev["status"], "compared")
        # Diff: 255324 - 162990 = 92334
        self.assertEqual(rev["absolute_difference"], 92334.0)

        np = next(m for m in data["metrics"] if m["metric"] == "net_profit")
        self.assertEqual(np["status"], "compared")
        # Diff: 48797 - 26750 = 22047
        self.assertEqual(np["absolute_difference"], 22047.0)

    def test_endpoint_validation_fewer_than_two_documents_returns_400(self):
        """Tests that passing only 1 document ID returns HTTP 400."""
        payload = {
            "document_ids": [self.reliance_doc_id],
            "financial_year": "FY 2024-25",
        }
        response = self.client.post("/documents/compare", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("at least two document ids", response.json()["detail"].lower())

    def test_endpoint_validation_duplicate_document_ids_returns_400(self):
        """Tests that passing duplicate document IDs returns HTTP 400."""
        payload = {
            "document_ids": [self.reliance_doc_id, self.reliance_doc_id],
            "financial_year": "FY 2024-25",
        }
        response = self.client.post("/documents/compare", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("duplicate document ids", response.json()["detail"].lower())

    def test_endpoint_validation_non_existent_document_returns_404(self):
        """Tests that passing a non-existent document ID returns HTTP 404."""
        payload = {
            "document_ids": [self.reliance_doc_id, "non_existent_doc_guid_99999"],
            "financial_year": "FY 2024-25",
        }
        response = self.client.post("/documents/compare", json=payload)
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_endpoint_validation_invalid_reference_id_returns_400(self):
        """Tests that reference_document_id not in document_ids returns HTTP 400."""
        payload = {
            "document_ids": [self.reliance_doc_id, self.infosys_doc_id],
            "reference_document_id": self.tcs_doc_id,  # not in document_ids
        }
        response = self.client.post("/documents/compare", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("reference document id", response.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
