"""
本地假 Agent：用于联调评测平台，无需真实 RAG。

启动：python -m uvicorn scripts.mock_agent:app --host 127.0.0.1 --port 9999

评测平台创建 Run 时填写：
  target_url = http://127.0.0.1:9999/ask
  body_template = {"question": "{question}"}
  response_json_path = answer
"""

from fastapi import FastAPI

app = FastAPI(title="Mock Agent")


@app.post("/ask")
def ask(payload: dict) -> dict:
    q = str(payload.get("question") or payload.get("query") or "")
    return {
        "answer": f"[mock] 收到问题：{q[:200]}",
        "meta": {"source": "mock_agent"},
    }
