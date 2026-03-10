@echo off
chcp 65001 > nul
title 동촌에프에스 Backend Server

echo ============================================
echo   동촌에프에스 Backend API Server
echo   SQLite DB 사용
echo ============================================
echo.

cd /d "%~dp0"

:: Check if venv exists
if not exist "venv" (
    echo 가상환경을 생성합니다...
    python -m venv venv
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install dependencies if needed
if exist "requirements-sqlite.txt" (
    pip install -r requirements-sqlite.txt --quiet
) else (
    pip install fastapi uvicorn sqlalchemy pydantic-settings python-multipart --quiet
)

echo.
echo 서버를 시작합니다... (http://localhost:8000)
echo API 문서: http://localhost:8000/docs
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
