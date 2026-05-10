@echo off
REM Modo dev - hot reload, mas IGNORA pastas que mudam dinamicamente
REM (cloned_repos, chroma_db, cache) para nao reiniciar durante indexacao.
cd backend
call .venv\Scripts\activate.bat
uvicorn api.main:app ^
    --reload ^
    --port 8000 ^
    --host 127.0.0.1 ^
    --reload-dir api ^
    --reload-dir agents ^
    --reload-include "*.py"
