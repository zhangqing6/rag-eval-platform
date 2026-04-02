import json
from typing import Any


def inject_question(obj: Any, question: str) -> Any:
    if isinstance(obj, str):
        return obj.replace("{question}", question)
    if isinstance(obj, dict):
        return {k: inject_question(v, question) for k, v in obj.items()}
    if isinstance(obj, list):
        return [inject_question(x, question) for x in obj]
    return obj


def extract_response_field(data: Any, path: str) -> str:
    if not path or not path.strip():
        if isinstance(data, str):
            return data
        return json.dumps(data, ensure_ascii=False)

    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data

    if isinstance(cur, (dict, list)):
        return json.dumps(cur, ensure_ascii=False)
    return str(cur)
