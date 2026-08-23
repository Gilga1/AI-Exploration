@echo off
setlocal
cd /d "%~dp0.."
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe scripts\train.py %*
) else (
  python scripts\train.py %*
)
exit /b %errorlevel%
