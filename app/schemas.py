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


class PlaygroundRunBody(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    # 非空则采用「权威手动」参考要点；留空则由智谱根据问题生成
    reference_answer: str | None = Field(None, max_length=12000)
    # 非空则采用手动关键词；留空则由智谱生成（或仅在你已手写参考时单独抽词）
    keywords: list[str] | None = Field(None, max_length=40)


class PlaygroundCompareBody(BaseModel):
    question_a: str = Field(min_length=1, max_length=8000)
    question_b: str = Field(min_length=1, max_length=8000)
    reference_answer_a: str | None = Field(None, max_length=12000)
    keywords_a: list[str] | None = Field(None, max_length=40)
    reference_answer_b: str | None = Field(None, max_length=12000)
    keywords_b: list[str] | None = Field(None, max_length=40)
