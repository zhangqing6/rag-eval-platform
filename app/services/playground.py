import asyncio
import json
import re
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import get_settings
from app.services.scorer import _llm_judge, _merge_scores, compute_rule_scores

REF_SYSTEM = """你是专业助教。根据用户问题，仅输出一个 JSON 对象，不要 markdown，不要其它文字。格式严格为：
{"reference_answer":"用1-4句中文给出可作为参考的要点答案","keywords":["关键词或短语1","关键词2",...]}
keywords 请列出 3-10 个**最短必要**的中文短语：本地模型答案里若覆盖这些词，通常表示答到要点（便于逐词检查命中率）。避免冗长句子。"""


def _parse_json_object(text: str) -> dict[str, Any]:
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {}
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return {}


def compute_keyword_hits(keywords: list[str], answer: str) -> list[dict[str, Any]]:
    """与规则分一致：子串命中；用于展示「哪些词拉低命中率」。"""
    a = answer or ""
    out: list[dict[str, Any]] = []
    for term in keywords:
        t = str(term).strip()
        if not t:
            continue
        out.append({"term": t, "hit": t in a})
    return out


def _normalize_usage_tokens(u: dict[str, Any]) -> dict[str, Any]:
    """统一智谱(OpenAI 兼容)的 usage 字段名便于前端展示。"""
    if not u:
        return {}
    return {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "total_tokens": u.get("total_tokens"),
    }


async def _openai_compatible_chat(messages: list[dict[str, str]], temperature: float = 0) -> tuple[str, dict[str, Any]]:
    s = get_settings()
    if not s.judge_api_key.strip():
        raise HTTPException(status_code=400, detail="未配置 JUDGE_API_KEY（智谱等 OpenAI 兼容 Chat Completions）")
    payload = {
        "model": s.judge_model,
        "messages": messages,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
        r = await client.post(
            f"{s.judge_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {s.judge_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"智谱/模型接口错误 {r.status_code}: {r.text[:400]}",
        )
    data = r.json()
    content = str(data["choices"][0]["message"]["content"] or "")
    usage_raw = data.get("usage")
    usage = usage_raw if isinstance(usage_raw, dict) else {}
    return content, _normalize_usage_tokens(usage)


async def fetch_reference_and_keywords(question: str) -> tuple[str, list[str], dict[str, Any]]:
    messages = [
        {"role": "system", "content": REF_SYSTEM},
        {"role": "user", "content": f"问题：{question}"},
    ]
    text, usage = await _openai_compatible_chat(messages)
    data = _parse_json_object(text)
    ref = str(data.get("reference_answer") or "").strip()
    kws = data.get("keywords") or []
    if isinstance(kws, str):
        kws = [kws]
    if not isinstance(kws, list):
        kws = []
    kws = [str(x).strip() for x in kws if str(x).strip()]
    return ref, kws, usage


async def ollama_answer(question: str) -> tuple[str, dict[str, Any]]:
    s = get_settings()
    url = f"{s.ollama_base.rstrip('/')}/api/chat"
    body: dict[str, Any] = {
        "model": s.ollama_model,
        "messages": [{"role": "user", "content": question}],
        "stream": False,
    }
    if s.ollama_num_predict is not None:
        body["options"] = {"num_predict": int(s.ollama_num_predict)}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            r = await client.post(url, json=body)
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=503,
            detail=f"无法连接 Ollama（{s.ollama_base}）。请确认 ollama serve 已运行且已安装模型 {s.ollama_model}。",
        ) from e
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504, detail="Ollama 响应超时") from e

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Ollama 错误 {r.status_code}: {r.text[:400]}")

    data = r.json()
    text = str((data.get("message") or {}).get("content") or "").strip()
    usage = {
        "prompt_eval_count": data.get("prompt_eval_count"),
        "eval_count": data.get("eval_count"),
        "note": "Ollama 返回的评估计数，约等于 prompt/输出 token 规模（依 Ollama 版本略有差异）",
    }
    return text, usage


async def run_playground_pipeline(question: str) -> dict[str, Any]:
    ref, kws, zhipu_ref_usage = await fetch_reference_and_keywords(question)
    local, ollama_usage = await ollama_answer(question)
    keyword_hits = compute_keyword_hits(kws, local)
    hit_n = sum(1 for x in keyword_hits if x.get("hit"))
    total_kw = len(keyword_hits)
    rule = compute_rule_scores(ref, kws, local)
    judge_parsed, judge_raw, judge_usage = await _llm_judge(question, ref or None, local)
    merged = _merge_scores(rule, judge_parsed)

    z_total = (zhipu_ref_usage.get("total_tokens") or 0) + (judge_usage.get("total_tokens") or 0)
    o_prompt = ollama_usage.get("prompt_eval_count") or 0
    o_out = ollama_usage.get("eval_count") or 0

    return {
        "question": question,
        "reference_answer": ref,
        "keywords": kws,
        "keyword_hits": keyword_hits,
        "keyword_hit_summary": {
            "hit": hit_n,
            "total": total_kw,
            "rate": round(hit_n / total_kw, 4) if total_kw else 1.0,
            "missed_terms": [x["term"] for x in keyword_hits if not x.get("hit")],
        },
        "local_model": get_settings().ollama_model,
        "local_answer": local,
        "scores": merged,
        "judge_raw_preview": (judge_raw or "")[:800],
        "token_usage": {
            "zhipu": {
                "reference_generation": zhipu_ref_usage,
                "judge": _normalize_usage_tokens(judge_usage),
                "total_tokens_sum": z_total if z_total else None,
            },
            "ollama_local": ollama_usage,
            "ollama_local_sum_eval": (o_prompt + o_out) if (o_prompt or o_out) else None,
        },
    }


async def run_playground_compare(question_a: str, question_b: str) -> dict[str, Any]:
    a, b = await asyncio.gather(
        run_playground_pipeline(question_a),
        run_playground_pipeline(question_b),
    )
    keys = set(a["scores"]) | set(b["scores"])
    delta = {
        k: round(float(b["scores"].get(k, 0)) - float(a["scores"].get(k, 0)), 4) for k in keys
    }
    ta = a.get("token_usage") or {}
    tb = b.get("token_usage") or {}
    oa = ta.get("ollama_local_sum_eval")
    ob = tb.get("ollama_local_sum_eval")
    token_delta_note = None
    if oa is not None and ob is not None:
        diff = ob - oa
        token_delta_note = (
            f"【本机 Ollama 用量】问题 B 相对 A：评估计数相差 {diff:+d}。"
            f"（正数表示 B 侧更高；与分数高低无必然关系，仅作并列对比。）"
        )
    return {
        "question_a": question_a,
        "question_b": question_b,
        "a": a,
        "b": b,
        "delta": delta,
        "note": "delta = 问题B 的各指标分数 − 问题A（同一次智谱标准下分别评测）",
        "token_delta_note": token_delta_note,
    }
