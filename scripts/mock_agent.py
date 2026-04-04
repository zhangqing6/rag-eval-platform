"""
本地 Ollama Agent：把评测平台的 HTTP 请求转发到本机 Ollama（默认 qwen2.5:7b）。

先在本机启动 Ollama 并拉好模型：ollama pull qwen2.5:7b

启动本服务：
  python -m uvicorn scripts.mock_agent:app --host 127.0.0.1 --port 9999

环境变量（可选）：
  OLLAMA_BASE   默认 http://127.0.0.1:11434
  OLLAMA_MODEL  默认 qwen2.5:7b
  OLLAMA_SYSTEM 可选系统提示词

评测平台创建 Run：
  target_url = http://127.0.0.1:9999/ask
  body_template = {"question": "{question}"}
  response_json_path = answer
"""

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException


def _load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.is_file():
        load_dotenv(env_path)


_load_dotenv_if_present()

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_SYSTEM = os.getenv("OLLAMA_SYSTEM", "").strip()

app = FastAPI(title="Ollama Bridge (Qwen)")


@app.get("/health")
async def health() -> dict:
    """探测本机 Ollama，用于确认桥接指向的是 Ollama 而非假数据。"""
    out: dict = {
        "bridge": "ollama_http_bridge",
        "ollama_base": OLLAMA_BASE,
        "configured_model": OLLAMA_MODEL,
        "ollama_reachable": False,
        "local_model_names": [],
        "configured_model_installed": False,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code == 200:
                out["ollama_reachable"] = True
                models = r.json().get("models") or []
                names = [m.get("name", "") for m in models if isinstance(m, dict)]
                out["local_model_names"] = names
                out["configured_model_installed"] = OLLAMA_MODEL in names
            else:
                out["ollama_error"] = f"HTTP {r.status_code}: {r.text[:200]}"
    except httpx.ConnectError:
        out["hint"] = "连不上 Ollama，请确认 ollama serve 已运行且 OLLAMA_BASE 正确。"
    except Exception as e:
        out["probe_error"] = str(e)[:200]
    return out


@app.post("/ask")
async def ask(payload: dict) -> dict:
    q = str(payload.get("question") or payload.get("query") or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="missing question or query")

    messages: list[dict[str, str]] = []
    if OLLAMA_SYSTEM:
        messages.append({"role": "system", "content": OLLAMA_SYSTEM})
    messages.append({"role": "user", "content": q})

    url = f"{OLLAMA_BASE}/api/chat"
    body = {"model": OLLAMA_MODEL, "messages": messages, "stream": False}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            r = await client.post(url, json=body)
    except httpx.ConnectError as e:
        raise HTTPException(
            status_code=503,
            detail=f"无法连接 Ollama（{OLLAMA_BASE}）。请先运行 ollama serve 并确认模型已安装。",
        ) from e
    except httpx.TimeoutException as e:
        raise HTTPException(status_code=504, detail="Ollama 响应超时") from e

    if r.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama 错误 {r.status_code}: {r.text[:500]}",
        )

    data = r.json()
    content = (data.get("message") or {}).get("content") or ""
    return {
        "answer": content.strip(),
        "meta": {"source": "ollama", "model": OLLAMA_MODEL},
    }
