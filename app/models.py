from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Dataset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TestCase(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="dataset.id", index=True)
    question: str
    reference_answer: Optional[str] = None
    tags: str = "[]"  # JSON list of strings
    must_contain: str = "[]"  # JSON list of strings for rule-based checks
    extra: str = "{}"  # JSON object


class ExperimentRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dataset_id: int = Field(foreign_key="dataset.id", index=True)
    name: str
    status: str = "pending"  # pending, running, completed, failed
    target_url: str
    target_method: str = "POST"
    target_headers_json: str = "{}"  # JSON
    body_template_json: str = '{"question": "{question}"}'
    response_json_path: str = ""  # empty = use full JSON text
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class RunResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="experimentrun.id", index=True)
    testcase_id: int = Field(foreign_key="testcase.id", index=True)
    request_body_json: str = "{}"
    raw_response_text: str = ""
    extracted_answer: str = ""
    latency_ms: Optional[float] = None
    tokens_json: str = "{}"  # e.g. {"prompt": 10, "completion": 20}
    scores_json: str = "{}"  # merged rule + judge scores
    judge_raw_json: str = ""
    error_message: Optional[str] = None
