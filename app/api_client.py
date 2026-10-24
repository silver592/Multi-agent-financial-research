import requests
from typing import Optional, Any, Tuple


class APIClient:
    """Helper class for communicating with the FastAPI backend."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")

    def check_health(self) -> Tuple[bool, str]:
        """Verifies backend connectivity by checking the OpenAPI docs endpoint."""
        try:
            resp = requests.get(f"{self.base_url}/openapi.json", timeout=3)
            if resp.status_code == 200:
                title = resp.json().get("info", {}).get("title", "Financial Research Workspace API")
                return True, f"Connected: {title}"
            return False, f"Server returned HTTP {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to FastAPI server. Please ensure uvicorn is running."
        except requests.exceptions.Timeout:
            return False, "Connection timed out connecting to backend."
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    def create_session(self, name: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            resp = requests.post(f"{self.base_url}/sessions", json={"name": name}, timeout=10)
            if resp.status_code == 200:
                return resp.json(), None
            return None, resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception as e:
            return None, str(e)

    def get_session(self, session_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            resp = requests.get(f"{self.base_url}/sessions/{session_id}", timeout=10)
            if resp.status_code == 200:
                return resp.json(), None
            return None, resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception as e:
            return None, str(e)

    def list_documents(self, session_id: str) -> Tuple[Optional[list], Optional[str]]:
        try:
            resp = requests.get(f"{self.base_url}/sessions/{session_id}/documents", timeout=10)
            if resp.status_code == 200:
                return resp.json(), None
            return None, resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception as e:
            return None, str(e)

    def upload_document(
        self,
        session_id: str,
        file_bytes: bytes,
        filename: str,
        company: str,
        document_type: str,
        year: int,
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            files = {"file": (filename, file_bytes, "application/pdf")}
            data = {
                "company": company,
                "document_type": document_type,
                "year": str(year),
            }
            # Uploading and embedding a full PDF can take 15-40 seconds
            resp = requests.post(
                f"{self.base_url}/sessions/{session_id}/documents",
                files=files,
                data=data,
                timeout=120,
            )
            if resp.status_code == 200:
                return resp.json(), None
            err_detail = resp.json().get("detail") if resp.headers.get("content-type") == "application/json" else resp.text
            return None, err_detail or f"HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            return None, "Upload request timed out during document chunking/embedding."
        except Exception as e:
            return None, str(e)

    def research_session(
        self,
        session_id: str,
        question: str,
        document_id: Optional[str] = None,
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            payload = {"question": question}
            if document_id:
                payload["document_id"] = document_id
            resp = requests.post(
                f"{self.base_url}/sessions/{session_id}/research",
                json=payload,
                timeout=45,
            )
            if resp.status_code == 200:
                return resp.json(), None
            return None, resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception as e:
            return None, str(e)

    def research_document(
        self,
        document_id: str,
        question: str,
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            resp = requests.post(
                f"{self.base_url}/documents/{document_id}/research",
                json={"question": question},
                timeout=45,
            )
            if resp.status_code == 200:
                return resp.json(), None
            return None, resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception as e:
            return None, str(e)

    def analyze_red_flags(self, document_id: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            resp = requests.get(
                f"{self.base_url}/documents/{document_id}/analyze/red-flags",
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json(), None
            return None, resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception as e:
            return None, str(e)

    def compare_documents(
        self,
        document_ids: list[str],
        financial_year: str = "FY 2024-25",
        reporting_basis: str = "consolidated",
        metrics: Optional[list[str]] = None,
        reference_document_id: Optional[str] = None,
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            payload = {
                "document_ids": document_ids,
                "financial_year": financial_year,
                "reporting_basis": reporting_basis,
                "metrics": metrics or ["revenue"],
            }
            if reference_document_id:
                payload["reference_document_id"] = reference_document_id
            resp = requests.post(
                f"{self.base_url}/documents/compare",
                json=payload,
                timeout=45,
            )
            if resp.status_code == 200:
                return resp.json(), None
            return None, resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception as e:
            return None, str(e)

    def generate_session_report(
        self,
        session_id: str,
        reporting_basis: str = "consolidated",
        financial_year: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            payload = {
                "reporting_basis": reporting_basis,
            }
            if financial_year:
                payload["financial_year"] = financial_year
            if document_id:
                payload["document_id"] = document_id
            resp = requests.post(
                f"{self.base_url}/sessions/{session_id}/report",
                json=payload,
                timeout=45,
            )
            if resp.status_code == 200:
                return resp.json(), None
            return None, resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception as e:
            return None, str(e)

    def generate_document_report(
        self,
        document_id: str,
        reporting_basis: str = "consolidated",
        financial_year: Optional[str] = None,
    ) -> Tuple[Optional[dict], Optional[str]]:
        try:
            payload = {"reporting_basis": reporting_basis}
            if financial_year:
                payload["financial_year"] = financial_year
            resp = requests.post(
                f"{self.base_url}/documents/{document_id}/report",
                json=payload,
                timeout=45,
            )
            if resp.status_code == 200:
                return resp.json(), None
            return None, resp.json().get("detail", f"HTTP {resp.status_code}")
        except Exception as e:
            return None, str(e)
