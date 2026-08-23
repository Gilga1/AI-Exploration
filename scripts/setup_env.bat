@echo off
setlocal
cd /d "%~dp0.."
python scripts\setup_env.py %*
if errorlevel 1 exit /b %errorlevel%
echo.
echo Activate with: .venv\Scripts\activate.bat
endlocal
