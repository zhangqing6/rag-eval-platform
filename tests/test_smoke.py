"""冒烟测试：不访问外网；批量执行通过 mock `_one_request` 完成。"""

import json
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import executor as executor_mod


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def _fake_one_request(client, run, case, sem):
    async with sem:
        ans = f"echo:{case.question}"
        body = {"answer": ans}
        return {
            "testcase_id": case.id,
            "request_body_json": json.dumps({"question": case.question}),
            "raw_response_text": json.dumps(body),
            "extracted_answer": ans,
            "latency_ms": 1.0,
            "tokens_json": "{}",
            "error_message": None,
        }


def test_dataset_run_execute_score_flow(client: TestClient) -> None:
    name = f"ds_{uuid.uuid4().hex[:8]}"
    r = client.post("/datasets", json={"name": name, "description": "test"})
    assert r.status_code == 200
    ds_id = r.json()["id"]

    cases = {
        "cases": [
            {"question": "hello?", "reference_answer": "echo", "must_contain": ["echo"]},
        ]
    }
    r = client.post(f"/datasets/{ds_id}/cases", json=cases)
    assert r.status_code == 200

    r = client.post(
        "/runs",
        json={
            "dataset_id": ds_id,
            "name": "t_run",
            "target_url": "http://test.invalid/ask",
            "body_template": {"question": "{question}"},
            "response_json_path": "answer",
        },
    )
    assert r.status_code == 200
    run_id = r.json()["id"]

    from app.services.executor import execute_run_sync

    with patch.object(executor_mod, "_one_request", side_effect=_fake_one_request):
        execute_run_sync(run_id)

    r = client.get(f"/runs/{run_id}/results")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert "echo:" in rows[0]["extracted_answer"]

    r = client.post(f"/runs/{run_id}/score")
    assert r.status_code == 200

    r = client.get(f"/runs/{run_id}/metrics")
    assert r.status_code == 200
    m = r.json()
    assert m["case_count"] == 1
    assert "avg_scores" in m
