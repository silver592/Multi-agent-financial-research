#schema.py --> A schema defines what data comes into or goes out of our API.

from datetime import datetime
from pydantic import BaseModel


class SessionCreate(BaseModel):
    name: str


class SessionResponse(BaseModel):
    id: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: str
    session_id: str
    filename: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


# --------------------------------------------------
# Research Agent Schemas
# --------------------------------------------------

from typing import Optional, Any


class ResearchRequest(BaseModel):
    question: str
    document_id: Optional[str] = None


class ResearchCitation(BaseModel):
    document_id: str
    company: Optional[str] = None
    page_number: Optional[int] = None
    chunk_id: Optional[str] = None
    statement_type: Optional[str] = None
    source_text: Optional[str] = None


class ResearchFinding(BaseModel):
    part: str
    claim: str
    evidence: str
    citation: Optional[ResearchCitation] = None
    figures: Optional[dict[str, Any]] = None


class ResearchResponse(BaseModel):
    question: str
    document_id: str
    session_id: Optional[str] = None
    company: Optional[str] = None
    answer: str
    findings: list[ResearchFinding] = []
    citations: list[ResearchCitation] = []
    limitations: list[str] = []


# --------------------------------------------------
# Comparison Agent Schemas
# --------------------------------------------------

class ComparisonRequest(BaseModel):
    document_ids: list[str]
    financial_year: Optional[str] = "FY 2024-25"
    reporting_basis: Optional[str] = "consolidated"
    metrics: Optional[list[str]] = ["revenue"]
    reference_document_id: Optional[str] = None


class CompanyMetricValue(BaseModel):
    company: str
    document_id: str
    value: float
    unit: str
    financial_year: str
    reporting_basis: str
    page: Optional[int] = None
    chunk_id: Optional[str] = None
    source_text: Optional[str] = None


class MetricComparisonResult(BaseModel):
    metric: str
    financial_year: str
    reporting_basis: str
    unit: str
    values: list[CompanyMetricValue] = []
    absolute_difference: Optional[float] = None
    signed_difference: Optional[float] = None
    percentage_difference: Optional[float] = None
    percentage_reference: Optional[str] = None
    status: str
    notes: Optional[str] = None


class ComparisonResponse(BaseModel):
    comparison_id: str
    financial_year: Optional[str] = None
    reporting_basis: Optional[str] = None
    metrics: list[MetricComparisonResult] = []
    limitations: list[str] = []

# --------------------------------------------------
# Report Agent Schemas
# --------------------------------------------------

class ReportRequest(BaseModel):
    document_id: Optional[str] = None
    reporting_basis: Optional[str] = "consolidated"
    financial_year: Optional[str] = None


class ReportMetricItem(BaseModel):
    metric: str
    value: float
    financial_year: str
    unit: str
    reporting_basis: str
    page: Optional[int] = None
    chunk_id: Optional[str] = None
    source_text: Optional[str] = None


class ExecutiveSummary(BaseModel):
    company: Optional[str] = None
    reporting_period: Optional[str] = None
    reporting_basis: str
    summary_text: str
    highlights: list[str] = []
    red_flags: list[str] = []


class ReportResponse(BaseModel):
    report_id: str
    session_id: Optional[str] = None
    document_id: str
    company: Optional[str] = None
    reporting_basis: str
    financial_year: Optional[str] = None
    executive_summary: ExecutiveSummary
    key_financials: list[ReportMetricItem] = []
    citations: list[ResearchCitation] = []
    limitations: list[str] = []
