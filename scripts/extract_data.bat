@echo off
setlocal
cd /d "%~dp0.."
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe scripts\extract_data.py %*
) else (
  python scripts\extract_data.py %*
)
exit /b %errorlevel%
