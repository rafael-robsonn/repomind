@echo off
REM ═══════════════════════════════════════════════════════════════════════
REM  RepoMind - Setup automatizado Windows
REM ═══════════════════════════════════════════════════════════════════════
setlocal enabledelayedexpansion

echo.
echo ===== RepoMind Setup =====
echo.

REM ── 1. Verifica Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH
    echo Instale Python 3.11+ em https://python.org
    exit /b 1
)
echo [OK] Python encontrado
python --version

REM ── 2. Verifica Ollama
where ollama >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Ollama nao encontrado
    echo Baixe em https://ollama.com/download/windows
    exit /b 1
)
echo [OK] Ollama encontrado

REM ── 3. Backend setup
echo.
echo ===== Backend =====
cd backend

if not exist .venv (
    echo Criando venv...
    python -m venv .venv
)

echo Ativando venv...
call .venv\Scripts\activate.bat

echo Instalando dependencias (pode demorar alguns minutos)...
pip install --quiet --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar deps
    exit /b 1
)
echo [OK] Dependencias instaladas

if not exist .env (
    echo Criando .env a partir de .env.example...
    copy .env.example .env >nul
    echo [OK] .env criado
)

cd ..

REM ── 4. Modelo Ollama
echo.
echo ===== Ollama Model =====
echo Baixando qwen2.5-coder:14b (9GB, demora alguns minutos na primeira vez)...
ollama pull qwen2.5-coder:14b

REM ── 5. Validate
echo.
echo ===== Validacao =====
python scripts\validate_setup.py
if errorlevel 1 (
    echo.
    echo [ERRO] Validacao falhou. Veja mensagens acima.
    exit /b 1
)

echo.
echo ===== Setup completo! =====
echo.
echo Para rodar:
echo   1. Backend:  cd backend ^&^& .venv\Scripts\activate ^&^& uvicorn api.main:app --reload --port 8000
echo   2. Frontend: cd frontend ^&^& npm install ^&^& npm run dev
echo   3. Abre:     http://localhost:5173
echo.
endlocal
