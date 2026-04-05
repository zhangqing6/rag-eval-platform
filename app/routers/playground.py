from fastapi import APIRouter

from app.schemas import PlaygroundCompareBody, PlaygroundRunBody
from app.services.playground import run_playground_compare, run_playground_pipeline

router = APIRouter(prefix="/api/playground", tags=["playground"])


@router.post("/run")
async def playground_one(body: PlaygroundRunBody):
    """智谱生成参考答+关键词 → Ollama 作答 → 规则分 + 智谱评委分。"""
    return await run_playground_pipeline(body.question.strip())


@router.post("/compare")
async def playground_two(body: PlaygroundCompareBody):
    """对两个问题分别跑完整流水线，并给出分数差（B − A）。"""
    return await run_playground_compare(body.question_a.strip(), body.question_b.strip())
