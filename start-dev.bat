@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
cd /d "%ROOT%" || exit /b 1

if not exist ".venv\Scripts\python.exe" (
  echo [start-dev] Creating .venv and installing dependencies...
  python -m venv .venv || exit /b 1
  "%ROOT%.venv\Scripts\python.exe" -m pip install -q -r requirements.txt || exit /b 1
)

set "PY=%ROOT%.venv\Scripts\python.exe"

echo [start-dev] Starting eval platform on :8000 ...
start "rag-eval-platform :8000" /D "%ROOT%" cmd /k ""%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [start-dev] Starting Ollama bridge on :9999 ...
start "ollama-bridge :9999" /D "%ROOT%" cmd /k ""%PY%" -m uvicorn scripts.mock_agent:app --host 127.0.0.1 --port 9999"

echo [start-dev] Waiting for servers to listen...
timeout /t 4 /nobreak >nul

echo [start-dev] Opening browser: http://127.0.0.1:8000/  (简易评测前端)
start "" "http://127.0.0.1:8000/"

echo.
echo 简易评测首页: http://127.0.0.1:8000/
echo API 文档:     http://127.0.0.1:8000/docs
echo 经典批量台:   http://127.0.0.1:8000/classic.html
echo Ollama 桥:    http://127.0.0.1:9999/health
echo Close the two titled console windows to stop servers.
endlocal
