@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel% equ 0 (set PYTHON=py) else (set PYTHON=python)
%PYTHON% -m pip install -r requirements.txt
if not exist "data\sistema.db" %PYTHON% init_db.py
start http://127.0.0.1:8000
%PYTHON% -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
