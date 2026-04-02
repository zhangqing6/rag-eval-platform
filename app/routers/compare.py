from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.database import get_session
from app.models import ExperimentRun
from app.services.compare_metrics import compare_runs

router = APIRouter(prefix="/compare", tags=["compare"])


@router.get("")
def compare(
    run_a_id: int = Query(..., description="First experiment run id"),
    run_b_id: int = Query(..., description="Second experiment run id"),
    session: Session = Depends(get_session),
) -> dict:
    for rid in (run_a_id, run_b_id):
        if not session.get(ExperimentRun, rid):
            raise HTTPException(status_code=404, detail=f"Run {rid} not found")
    return compare_runs(session, run_a_id, run_b_id)
