from fastapi import APIRouter

from app.schemas import PlaygroundCompareBody, PlaygroundRunBody
from app.services.playground import run_playground_compare, run_playground_pipeline

router = APIRouter(prefix="/api/playground", tags=["playground"])


@router.post("/run")
async def playground_one(body: PlaygroundRunBody):
    """参考要点与关键词可手动或智谱生成（字段留空即智谱）→ Ollama → 规则分 + 智谱评委。"""
    return await run_playground_pipeline(
        body.question.strip(),
        reference_answer=body.reference_answer,
        keywords=body.keywords,
    )


@router.post("/compare")
async def playground_two(body: PlaygroundCompareBody):
    """两题对比；每题可参考/关键词独立选手动或留空走智谱。"""
    return await run_playground_compare(
        body.question_a.strip(),
        body.question_b.strip(),
        reference_answer_a=body.reference_answer_a,
        keywords_a=body.keywords_a,
        reference_answer_b=body.reference_answer_b,
        keywords_b=body.keywords_b,
    )
