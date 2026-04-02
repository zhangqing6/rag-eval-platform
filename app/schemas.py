from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    name: str
    description: str = ""


class DatasetRead(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TestCaseItem(BaseModel):
    question: str
    reference_answer: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    must_contain: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class TestCaseBulkUpload(BaseModel):
    cases: list[TestCaseItem]


class RunCreate(BaseModel):
    dataset_id: int
    name: str
    target_url: str
    target_method: str = "POST"
    target_headers: dict[str, str] = Field(default_factory=dict)
    body_template: dict[str, Any] = Field(
        default_factory=lambda: {"question": "{question}"},
        description="Use {question} placeholder in string values.",
    )
    response_json_path: str = Field(
        default="",
        description="Dot path to extract answer from JSON response, e.g. 'answer' or 'data.text'. Empty = stringify whole body.",
    )


class RunRead(BaseModel):
    id: int
    dataset_id: int
    name: str
    status: str
    target_url: str
    target_method: str
    response_json_path: str
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class CompareQuery(BaseModel):
    run_a_id: int
    run_b_id: int


class CompareMetrics(BaseModel):
    run_id: int
    run_name: str
    case_count: int
    avg_scores: dict[str, float]
    error_rate: float


class CompareResult(BaseModel):
    a: CompareMetrics
    b: CompareMetrics
    delta: dict[str, float]
