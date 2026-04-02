import json
import re
from typing import Any

import httpx
from sqlmodel import Session, select

from app.config import get_settings
from app.models import RunResult, TestCase


def _rule_scores(case: TestCase, answer: str) -> dict[str, float]:
    out: dict[str, float] = {}
    try:
        must = json.loads(case.must_contain)
    except json.JSONDecodeError:
        must = []
    if must:
        hits = sum(1 for m in must if m and m in answer)
        out["rule_must_contain"] = hits / max(len(must), 1)
    else:
        out["rule_must_contain"] = 1.0

    ref = (case.reference_answer or "").strip()
    if ref:
        ref_tokens = set(re.findall(r"\w+", ref.lower()))
        ans_tokens = set(re.findall(r"\w+", answer.lower()))
        if ref_tokens:
            overlap = len(ref_tokens & ans_tokens) / len(ref_tokens)
            out["rule_ref_overlap"] = overlap
        else:
            out["rule_ref_overlap"] = 1.0
    else:
        out["rule_ref_overlap"] = 1.0

    return out


JUDGE_SYSTEM = """You are an evaluator for RAG / assistant answers. Score the assistant answer given the user question.
Return ONLY a compact JSON object with keys:
- factual (1-5): factual correctness vs question and reference if provided
- grounded (1-5): whether the answer avoids obvious hallucination when no evidence (use 5 if appropriate refusal)
- refusal_ok (1-5): if the question cannot be answered from typical RAG, is refusal/clarification appropriate
Scores are integers 1-5. No markdown, no explanation outside JSON."""


async def _llm_judge(
    question: str,
    reference: str | None,
    answer: str,
) -> tuple[dict[str, Any], str]:
    settings = get_settings()
    if not settings.judge_api_key.strip():
        return {}, ""

    user = json.dumps(
        {
            "question": question,
            "reference_answer": reference or "",
            "assistant_answer": answer,
        },
        ensure_ascii=False,
    )

    payload = {
        "model": settings.judge_model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{settings.judge_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.judge_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120.0,
        )
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {}, text
        try:
            parsed = json.loads(m.group())
            return parsed, text
        except json.JSONDecodeError:
            return {}, text


def _merge_scores(rule: dict[str, float], judge: dict[str, Any]) -> dict[str, float]:
    merged: dict[str, float] = dict(rule)
    for k, v in judge.items():
        if isinstance(v, (int, float)):
            merged[f"judge_{k}"] = float(v)
    return merged


async def score_run_async(session: Session, run_id: int) -> None:
    rows = session.exec(select(RunResult).where(RunResult.run_id == run_id)).all()
    settings = get_settings()
    use_judge = bool(settings.judge_api_key.strip())

    for rr in rows:
        case = session.get(TestCase, rr.testcase_id)
        if not case:
            continue
        answer = rr.extracted_answer or ""
        rule = _rule_scores(case, answer)
        judge_parsed: dict[str, Any] = {}
        judge_raw = ""
        if use_judge and not rr.error_message:
            judge_parsed, judge_raw = await _llm_judge(
                case.question,
                case.reference_answer,
                answer,
            )
        merged = _merge_scores(rule, judge_parsed)
        rr.scores_json = json.dumps(merged, ensure_ascii=False)
        rr.judge_raw_json = judge_raw[:20000]
        session.add(rr)
    session.commit()


def score_run_sync(run_id: int) -> None:
    import asyncio

    from app.database import engine

    with Session(engine) as session:
        asyncio.run(score_run_async(session, run_id))
