@echo off
cd /d "%~dp0"

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000.*LISTENING" 2^>nul') do taskkill /PID %%a /F >nul 2>&1
timeout /t 1 /nobreak >nul

where python >nul 2>&1 || (
  echo Python was not found in PATH.
  pause
  exit /b 1
)

start "" /MIN python -m uvicorn server:app --host 127.0.0.1 --port 8000 --log-level warning --workers 1
timeout /t 3 /nobreak >nul

start "" /MIN cmd /c "cd /d %~dp0terminal && npm run dev"
timeout /t 6 /nobreak >nul

start http://localhost:3000
exit
