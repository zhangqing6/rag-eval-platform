# RAG / Agent 评测与回归平台

面向 **任意 HTTP 接口**（ LangGraph Agent、RAG 服务等）的批量跑批、规则与 LLM-as-judge 打分、两次实验指标对比，并支持 **CSV 导出**。

演示视频：
【RAG / Agent 评测与回归平台】 https://www.bilibili.com/video/BV1YMDFByE3b/?share_source=copy_web&vd_source=44cb484ede030bd06d3f1307adebee80
## 功能

- **数据集**：评测用例（`question`、可选 `reference_answer`、`must_contain`、`tags`）
- **实验 Run**：配置目标 URL、请求体模板（`{question}` 占位）、从 JSON 响应中提取答案的路径
- **执行**：异步并发调用 Agent，记录耗时与原始响应
- **打分**：规则分（关键词、与参考答案词重叠）+ 可选 LLM 评委（需配置 OpenAI 兼容 API）
- **对比**：`/compare?run_a_id=&run_b_id=` 查看平均分与误差率差异
- **简易评测台**（首页 `/`）：**参考要点、关键词**可 **手写（权威）** 或 **留空由智谱生成**（亦支持仅手写其一、另一项由智谱补全）→ Ollama → 逐词命中 → 规则分+评委+用量统计；两题对比可对 A/B 分别选手写标准

## 本地运行

```bash
cd rag-eval-platform
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # 按需填写 JUDGE_API_KEY
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **简易评测首页**：<http://127.0.0.1:8000/>（智谱 + Ollama 一键对比）
- 经典批量控制台：<http://127.0.0.1:8000/classic.html> 或 <http://127.0.0.1:8000/ui/>
- API 文档：<http://127.0.0.1:8000/docs>

### Windows 一键开发启动（虚拟环境 + 双服务 + 打开 Swagger）

在 `rag-eval-platform` 目录下：

- **双击** `start-dev.bat`，或命令行执行 `start-dev.bat`  
- 若无 `.venv` 会自动创建并 `pip install -r requirements.txt`  
- 会打开两个控制台窗口：**评测平台 :8000**、**Ollama 桥 :9999**  
- 约 4 秒后自动打开浏览器：<http://127.0.0.1:8000/>（简易评测前端）  

PowerShell（若 `.bat` 被策略拦截）：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\start-dev.ps1
```

使用前请本机已运行 **Ollama**（桥接服务会连 `11434`）。关闭两个 titled 窗口即停止对应服务。

## Docker 一键启动

```bash
docker compose up --build
```

评测平台监听 `8000`。若 Agent 在本机其他端口，Compose 中已配置 `host.docker.internal`，目标 URL 可写例如 `http://host.docker.internal:9000/ask`。

## 典型流程

1. `POST /datasets` 创建数据集  
2. `POST /datasets/{id}/cases` 上传用例（或参考 `examples/sample_cases.json`）  
3. `POST /runs` 创建 Run，`target_url` 指向你的问答接口，`body_template` 如 `{"question": "{question}"}`，`response_json_path` 填返回 JSON 里答案字段路径（如 `answer`）  
4. `POST /runs/{id}/execute` 执行批量请求  
5. `POST /runs/{id}/score` 打分（无 `JUDGE_API_KEY` 时仅规则分）  
6. `GET /compare?run_a_id=1&run_b_id=2` 对比两次实验  
7. `GET /runs/{id}/export.csv` 导出结果  

## 环境变量

见 `.env.example`。`JUDGE_BASE_URL` 可使用国内兼容网关或本地 **Ollama**（`http://127.0.0.1:11434/v1`）。

## 如何测试

### 1. 自动化（pytest）

```bash
cd rag-eval-platform
pip install -r requirements-dev.txt
pytest tests/ -v
```

- `test_health`：检查 `/health`
- `test_dataset_run_execute_score_flow`：创建数据集 → 导入用例 → 创建 Run → **mock HTTP** 执行 → 规则打分 → 拉指标（**不调用真实 Agent、不消耗 Judge API**）

### 2. 手动联调（推荐走通全流程）

**终端 A** 启动评测平台：

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**终端 B** 启动 Ollama 桥接服务（默认转发到本机 **Ollama `qwen2.5:7b`**；需先 `ollama serve` 且已 `ollama pull qwen2.5:7b`）：

```bash
python -m uvicorn scripts.mock_agent:app --host 127.0.0.1 --port 9999
```

可选环境变量：`OLLAMA_BASE`（默认 `http://127.0.0.1:11434`）、`OLLAMA_MODEL`（默认 `qwen2.5:7b`）、`OLLAMA_SYSTEM`（系统提示词）。

**如何确认真是 Ollama 在跑**：桥接服务启动后访问 <http://127.0.0.1:9999/health>，应看到 `ollama_reachable: true` 与本机 `local_model_names`；`POST /ask` 的返回里 `meta.source` 为 `ollama`、`meta.model` 为当前模型名。另可在推理时另开终端执行 `ollama ps`，会看到模型被加载。

浏览器打开 <http://127.0.0.1:8000/docs> 或首页控制台，按「典型流程」操作；创建 Run 时：

- `target_url`：`http://127.0.0.1:9999/ask`
- `body_template`：`{"question": "{question}"}`
- `response_json_path`：`answer`

执行 `POST /runs/{id}/execute` 后，用 `GET /runs/{id}` 看 `status` 是否为 `completed`，再查看 `GET /runs/{id}/results`。

**LLM 评委**：在 `.env` 中配置 `JUDGE_API_KEY` 后，再调用 `POST /runs/{id}/score`；不配则仅有规则分。

### 3. PowerShell 快速调用示例

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 定时回归

`.github/workflows/nightly.yml` 为占位 workflow，请将 `curl` 或跑批脚本换成你的线上地址与鉴权。
