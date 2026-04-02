import asyncio
import json
import time
from typing import Any

import httpx
from sqlmodel import Session, select

from app.config import get_settings
from app.models import ExperimentRun, RunResult, TestCase
from app.services.http_utils import extract_response_field, inject_question


async def _one_request(
    client: httpx.AsyncClient,
    run: ExperimentRun,
    case: TestCase,
    sem: asyncio.Semaphore,
) -> dict[str, Any]:
    settings = get_settings()
    body_tmpl = json.loads(run.body_template_json)
    headers = json.loads(run.target_headers_json)
    payload = inject_question(body_tmpl, case.question)

    async with sem:
        t0 = time.perf_counter()
        err: str | None = None
        raw_text = ""
        extracted = ""
        method = run.target_method.upper()
        try:
            req_kw: dict[str, Any] = {"headers": headers, "timeout": settings.http_timeout_seconds}
            if method in ("POST", "PUT", "PATCH"):
                req_kw["json"] = payload
            elif method == "GET":
                req_kw["params"] = payload if isinstance(payload, dict) else None
            else:
                req_kw["json"] = payload
            resp = await client.request(method, run.target_url, **req_kw)
            raw_text = resp.text
            try:
                data = resp.json()
            except json.JSONDecodeError:
                data = raw_text
            extracted = extract_response_field(data, run.response_json_path)
        except Exception as e:
            err = str(e)
            raw_text = err
        latency_ms = (time.perf_counter() - t0) * 1000

    return {
        "testcase_id": case.id,
        "request_body_json": json.dumps(payload, ensure_ascii=False),
        "raw_response_text": raw_text[:50000],
        "extracted_answer": extracted[:50000],
        "latency_ms": latency_ms,
        "tokens_json": "{}",
        "error_message": err,
    }


async def execute_run_async(session: Session, run_id: int) -> None:  # noqa: PLR0915
    settings = get_settings()
    run = session.get(ExperimentRun, run_id)
    if not run:
        return

    run.status = "running"
    run.error_message = None
    session.add(run)
    session.commit()

    existing = session.exec(select(RunResult).where(RunResult.run_id == run_id)).all()
    for r in existing:
        session.delete(r)
    session.commit()

    cases = session.exec(
        select(TestCase).where(TestCase.dataset_id == run.dataset_id).order_by(TestCase.id)
    ).all()

    sem = asyncio.Semaphore(settings.max_concurrent_requests)

    async with httpx.AsyncClient() as client:
        tasks = [_one_request(client, run, c, sem) for c in cases]
        results = await asyncio.gather(*tasks)

    for row, case in zip(results, cases, strict=True):
        rr = RunResult(
            run_id=run_id,
            testcase_id=case.id,
            request_body_json=row["request_body_json"],
            raw_response_text=row["raw_response_text"],
            extracted_answer=row["extracted_answer"],
            latency_ms=row["latency_ms"],
            tokens_json=row["tokens_json"],
            scores_json="{}",
            judge_raw_json="",
            error_message=row["error_message"],
        )
        session.add(rr)

    from datetime import datetime

    run.status = "completed"
    run.completed_at = datetime.utcnow()
    session.add(run)
    session.commit()


def execute_run_sync(run_id: int) -> None:
    from datetime import datetime

    from app.database import engine

    try:
        with Session(engine) as session:
            asyncio.run(execute_run_async(session, run_id))
    except Exception as e:
        with Session(engine) as session:
            run = session.get(ExperimentRun, run_id)
            if run:
                run.status = "failed"
                run.error_message = str(e)
                run.completed_at = datetime.utcnow()
                session.add(run)
                session.commit()
        raise
