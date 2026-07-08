@echo off
echo Stopping AI Quant Terminal...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1 && echo   Backend :8000 stopped
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000.*LISTENING" 2^>nul') do (
    taskkill /PID %%a /F >nul 2>&1 && echo   Frontend :3000 stopped
)

del "%temp%\quant_frontend.vbs" 2>nul
echo Done.
pause
