@echo off
REM Roda o backend em modo "production" (sem auto-reload)
REM Auto-reload causa restart durante indexação quando clonamos repos.
cd backend
call .venv\Scripts\activate.bat
uvicorn api.main:app --port 8000 --host 127.0.0.1
