@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [FTransfer] Creating virtual environment...
    python -m venv .venv
    call ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo.
echo [FTransfer] Starting on port 8987
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    for /f "tokens=* delims= " %%b in ("%%a") do echo   From your phone:  http://%%b:8987
)
echo   On this PC:        http://localhost:8987
echo.

".venv\Scripts\python.exe" -m uvicorn app:app --host 0.0.0.0 --port 8987
