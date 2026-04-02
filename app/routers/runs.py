import csv
import io
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Dataset, ExperimentRun, RunResult, TestCase
from app.schemas import RunCreate, RunRead
from app.services.compare_metrics import aggregate_run
from app.services.executor import execute_run_sync
from app.services.scorer import score_run_sync

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunRead)
def create_run(body: RunCreate, session: Session = Depends(get_session)) -> ExperimentRun:
    ds = session.get(Dataset, body.dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    run = ExperimentRun(
        dataset_id=body.dataset_id,
        name=body.name,
        target_url=body.target_url,
        target_method=body.target_method,
        target_headers_json=json.dumps(body.target_headers, ensure_ascii=False),
        body_template_json=json.dumps(body.body_template, ensure_ascii=False),
        response_json_path=body.response_json_path,
        status="pending",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


@router.get("", response_model=list[RunRead])
def list_runs(session: Session = Depends(get_session)) -> list[ExperimentRun]:
    return list(session.exec(select(ExperimentRun).order_by(ExperimentRun.id.desc())).all())


@router.get("/{run_id}", response_model=RunRead)
def get_run(run_id: int, session: Session = Depends(get_session)) -> ExperimentRun:
    run = session.get(ExperimentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/execute", response_model=dict)
def start_execute(
    run_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    run = session.get(ExperimentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    background_tasks.add_task(execute_run_sync, run_id)
    return {"status": "queued", "run_id": run_id}


@router.post("/{run_id}/score", response_model=dict)
def start_score(
    run_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    run = session.get(ExperimentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    background_tasks.add_task(score_run_sync, run_id)
    return {"status": "queued", "run_id": run_id}


@router.get("/{run_id}/results", response_model=list[dict])
def get_results(run_id: int, session: Session = Depends(get_session)) -> list[dict]:
    run = session.get(ExperimentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = session.exec(select(RunResult).where(RunResult.run_id == run_id).order_by(RunResult.id)).all()
    out: list[dict] = []
    for rr in rows:
        case = session.get(TestCase, rr.testcase_id)
        q = case.question if case else ""
        try:
            scores = json.loads(rr.scores_json or "{}")
        except json.JSONDecodeError:
            scores = {}
        out.append(
            {
                "id": rr.id,
                "question": q,
                "extracted_answer": rr.extracted_answer[:2000],
                "latency_ms": rr.latency_ms,
                "scores": scores,
                "error_message": rr.error_message,
            }
        )
    return out


@router.get("/{run_id}/export.csv")
def export_csv(run_id: int, session: Session = Depends(get_session)) -> StreamingResponse:
    run = session.get(ExperimentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = session.exec(select(RunResult).where(RunResult.run_id == run_id).order_by(RunResult.id)).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["testcase_id", "question", "extracted_answer", "latency_ms", "scores_json", "error_message"])
    for rr in rows:
        case = session.get(TestCase, rr.testcase_id)
        q = case.question if case else ""
        w.writerow([rr.testcase_id, q, rr.extracted_answer, rr.latency_ms, rr.scores_json, rr.error_message])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="run_{run_id}_results.csv"'},
    )


@router.get("/{run_id}/metrics", response_model=dict)
def run_metrics(run_id: int, session: Session = Depends(get_session)) -> dict:
    run = session.get(ExperimentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    avg, n, err, name = aggregate_run(session, run_id)
    return {
        "run_id": run_id,
        "run_name": name,
        "case_count": n,
        "avg_scores": avg,
        "error_rate": err / n if n else 0.0,
    }
