import json
from collections import defaultdict

from sqlmodel import Session, select

from app.models import ExperimentRun, RunResult


def aggregate_run(session: Session, run_id: int) -> tuple[dict[str, float], int, int, str]:
    run = session.get(ExperimentRun, run_id)
    name = run.name if run else str(run_id)
    rows = session.exec(select(RunResult).where(RunResult.run_id == run_id)).all()
    if not rows:
        return {}, 0, 0, name

    sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    errors = 0

    for rr in rows:
        if rr.error_message:
            errors += 1
        try:
            scores = json.loads(rr.scores_json or "{}")
        except json.JSONDecodeError:
            scores = {}
        for k, v in scores.items():
            if isinstance(v, (int, float)):
                sums[k] += float(v)
                counts[k] += 1

    avg = {k: sums[k] / counts[k] for k in sums if counts[k]}
    n = len(rows)
    return avg, n, errors, name


def compare_runs(session: Session, run_a_id: int, run_b_id: int) -> dict:
    avg_a, n_a, err_a, name_a = aggregate_run(session, run_a_id)
    avg_b, n_b, err_b, name_b = aggregate_run(session, run_b_id)

    keys = set(avg_a) | set(avg_b)
    delta = {k: round(avg_b.get(k, 0) - avg_a.get(k, 0), 4) for k in keys}

    return {
        "a": {
            "run_id": run_a_id,
            "run_name": name_a,
            "case_count": n_a,
            "avg_scores": avg_a,
            "error_rate": err_a / n_a if n_a else 0.0,
        },
        "b": {
            "run_id": run_b_id,
            "run_name": name_b,
            "case_count": n_b,
            "avg_scores": avg_b,
            "error_rate": err_b / n_b if n_b else 0.0,
        },
        "delta": delta,
    }
