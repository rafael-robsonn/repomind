@echo off
REM ═══════════════════════════════════════════════════════════════════════
REM  RepoMind - Build EXE
REM ═══════════════════════════════════════════════════════════════════════
setlocal enabledelayedexpansion

echo.
echo ===== RepoMind Build EXE =====
echo.

REM ── 1. Verifica venv backend
if not exist backend\.venv (
    echo [ERRO] backend\.venv nao existe. Rode setup.bat primeiro.
    exit /b 1
)

REM ── 2. Build frontend
echo.
echo === [1/3] Building frontend ===
cd frontend

if not exist node_modules (
    echo Instalando deps frontend...
    call npm install
    if errorlevel 1 (
        echo [ERRO] npm install falhou
        cd ..
        exit /b 1
    )
)

echo Building frontend (production)...
call npm run build
if errorlevel 1 (
    echo [ERRO] npm run build falhou
    cd ..
    exit /b 1
)
cd ..

if not exist frontend\dist\index.html (
    echo [ERRO] frontend\dist nao foi gerado
    exit /b 1
)
echo [OK] Frontend buildado em frontend\dist\

REM ── 3. Instala PyInstaller no venv
echo.
echo === [2/3] Instalando PyInstaller ===
call backend\.venv\Scripts\activate.bat

pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Instalando pyinstaller...
    pip install --quiet pyinstaller
    if errorlevel 1 (
        echo [ERRO] Falha ao instalar pyinstaller
        exit /b 1
    )
)

REM Garante deps adicionais que o launcher usa
pip install --quiet httpx >nul 2>&1

echo [OK] PyInstaller pronto

REM ── 4. Limpa builds antigos
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM ── 5. Build EXE
echo.
echo === [3/3] Buildando EXE (isso demora 5-10 minutos) ===
echo.
pyinstaller RepoMind.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERRO] PyInstaller falhou. Veja mensagens acima.
    exit /b 1
)

REM ── 6. Resultado
echo.
echo =============================================================
if exist dist\RepoMind.exe (
    echo  BUILD COMPLETO!
    echo.
    echo  EXE: dist\RepoMind.exe
    for %%I in (dist\RepoMind.exe) do echo  Tamanho: %%~zI bytes
    echo.
    echo  Pra testar: dist\RepoMind.exe
    echo.
    echo  IMPORTANTE: o EXE precisa do Ollama rodando.
    echo              Garanta: ollama pull qwen2.5-coder:14b
) else (
    echo  ERRO: RepoMind.exe nao foi gerado
    exit /b 1
)
echo =============================================================
echo.

endlocal
