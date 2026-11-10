from enum import StrEnum

from pydantic import BaseModel, Field


class ResearchMode(StrEnum):
    AUTOMATIC = "automatic"
    CUSTOM = "custom"
    REPRODUCTION = "reproduction"


class ReadinessStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNCLEAR = "unclear"
    NOT_APPLICABLE = "not_applicable"


class EvidenceType(StrEnum):
    PAPER = "paper"
    INFERENCE = "inference"


class PageText(BaseModel):
    page_number: int = Field(ge=1)
    text: str


class PaperChunk(BaseModel):
    chunk_id: str
    page_number: int = Field(ge=1)
    text: str


class Evidence(BaseModel):
    page_number: int = Field(ge=1)
    excerpt: str


class AnswerResult(BaseModel):
    answer: str
    evidence: list[Evidence]


class AnalysisItem(BaseModel):
    finding: str = Field(description="A concise finding grounded in the supplied paper text")
    pages: list[int] = Field(description="PDF page numbers supporting the finding")


class PaperAnalysis(BaseModel):
    title: str
    research_question: AnalysisItem
    approach: AnalysisItem
    key_results: AnalysisItem
    contributions: AnalysisItem
    limitations: AnalysisItem
    future_work: AnalysisItem


class ReproductionItem(BaseModel):
    category: str = Field(description="Short category such as code, data, environment, or metric")
    name: str = Field(description="The resource or requirement being assessed")
    status: ReadinessStatus
    evidence_type: EvidenceType
    details: str = Field(description="What is available, missing, or unclear")
    pages: list[int] = Field(
        description="Supporting PDF pages; empty only for clearly labeled inferences"
    )
    url: str = Field(default="", description="URL printed in the paper, otherwise empty")
    approval_required: bool = Field(
        default=False,
        description="Whether a later download or external action needs user approval",
    )


class ReproductionReadiness(BaseModel):
    title: str
    overall_status: ReadinessStatus
    summary: str
    resources: list[ReproductionItem]
    environment: list[ReproductionItem]
    experiment: list[ReproductionItem]
    blockers: list[ReproductionItem]
    approval_actions: list[str]
    pdf_checks: list[str] = Field(default_factory=list)
    caveats: list[str]


class ResearchRequest(BaseModel):
    mode: ResearchMode
    question: str = ""
