# 一键：虚拟环境、评测平台 :8000、Ollama 桥 :9999、打开简易评测首页
# 用法：在资源管理器中右键「使用 PowerShell 运行」，或：powershell -ExecutionPolicy Bypass -File .\start-dev.ps1

$Root = $PSScriptRoot
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[start-dev] Creating .venv and installing dependencies..."
    python -m venv (Join-Path $Root ".venv")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $venvPython -m pip install -q -r (Join-Path $Root "requirements.txt")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$argListEval = @(
    "/k", "cd /d `"$Root`" && `"$venvPython`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)
$argListBridge = @(
    "/k", "cd /d `"$Root`" && `"$venvPython`" -m uvicorn scripts.mock_agent:app --host 127.0.0.1 --port 9999"
)

Write-Host "[start-dev] Starting eval platform on :8000 ..."
Start-Process -FilePath "cmd.exe" -ArgumentList $argListEval -WindowStyle Normal

Write-Host "[start-dev] Starting Ollama bridge on :9999 ..."
Start-Process -FilePath "cmd.exe" -ArgumentList $argListBridge -WindowStyle Normal

Write-Host "[start-dev] Waiting for servers..."
Start-Sleep -Seconds 4

Write-Host "[start-dev] Opening http://127.0.0.1:8000/ (简易评测前端)"
Start-Process "http://127.0.0.1:8000/"

Write-Host ""
Write-Host "简易评测首页: http://127.0.0.1:8000/"
Write-Host "API 文档:     http://127.0.0.1:8000/docs"
Write-Host "经典批量台:   http://127.0.0.1:8000/classic.html"
Write-Host "Ollama 桥:    http://127.0.0.1:9999/health"
Write-Host "Close the two cmd windows to stop servers."
